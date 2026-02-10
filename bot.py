import os
import random
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["tabu_bot"]
words_col = db["words"]

game_active = False
mode = None
current_word = None
current_hint = None
narrator_id = None
group_chat_id = None
last_activity = time.time()
scores = {}
sudo_users = set([OWNER_ID])
groups_data = {}
last_winner = None

def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d["hint"]
    return None, None

def track_group(update):
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or update.effective_chat.username or "Özel Chat"
    groups_data[chat_id] = {
        "title": chat_title,
        "users": update.effective_chat.get_member_count() if hasattr(update.effective_chat, "get_member_count") else 0
    }

def start(update, context):
    track_group(update)
    text = (
        "Merhaba! Ben Telegram Tabu Oyun Botu 😄\n\n"
        "/game → Oyunu başlatır\n"
        "/stop → Oyunu durdurur (admin)\n"
    )
    keyboard = [[
        InlineKeyboardButton("👑 Sahip", url=f"tg://user?id={OWNER_ID}"),
        InlineKeyboardButton("➕ Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true"),
        InlineKeyboardButton("💬 Destek Kanalı", url="https://t.me/kiyiciupdate")
    ]]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def stats(update, context):
    if update.message.from_user.id != OWNER_ID:
        return
    total_groups = len(groups_data)
    total_users = sum(v["users"] for v in groups_data.values())
    update.message.reply_text(f"📊 Gruplar: {total_groups}\n👥 Kullanıcılar: {total_users}")

def ping(update, context):
    if update.message.from_user.id != OWNER_ID:
        return
    ping_time = round(time.time() - update.message.date.timestamp(), 2)
    update.message.reply_text(f"🏓 Ping: {ping_time} sn")

def game(update, context):
    global group_chat_id, scores
    group_chat_id = update.effective_chat.id
    scores = {}
    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı (Bakımda)", callback_data="text_maintenance")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

def mode_select(update, context):
    global game_active, narrator_id, current_word, current_hint, last_activity
    query = update.callback_query
    query.answer()

    if query.data == "text_maintenance":
        query.answer("⌨️ Yazılı mod bakımda!", show_alert=True)
        return

    game_active = True
    narrator_id = query.from_user.id
    current_word, current_hint = pick_word()
    last_activity = time.time()
    send_game_message(context)

def send_game_message(context, info_text=None):
    BOT_ID = context.bot.id
    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [
            InlineKeyboardButton("➡️ Kelimeyi Geç", callback_data="next"),
            InlineKeyboardButton("✍️ Kelime Yaz", url=f"tg://user?id={BOT_ID}")
        ]
    ]

    narrator_name = context.bot.get_chat_member(group_chat_id, narrator_id).user.first_name
    text = "Oyun başladı!\n"
    text += f"Anlatıcı: {narrator_name}"

    if info_text:
        text = info_text + "\n\n" + text

    context.bot.send_message(group_chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard))

def button(update, context):
    global current_word, current_hint, last_activity
    query = update.callback_query
    if query.from_user.id != narrator_id:
        query.answer("Sadece anlatıcı.", show_alert=True)
        return

    last_activity = time.time()

    if query.data == "look":
        query.answer(f"Kelime: {current_word}\nİpucu: {current_hint}", show_alert=True)

    elif query.data == "next":
        current_word, current_hint = pick_word()
        query.answer("Yeni kelime verildi!", show_alert=True)

def guess(update, context):
    global current_word, current_hint, last_activity, last_winner

    if not game_active:
        return

    text = update.message.text.strip()
    last_activity = time.time()

    if update.message.chat.type == "private" and update.message.from_user.id == narrator_id:
        current_word = text
        current_hint = "Anlatıcı girdi"
        return

    if text.lower() == current_word.lower():
        user = update.message.from_user
        scores[user.first_name] = scores.get(user.first_name, 0) + 1
        last_winner = user.first_name
        current_word, current_hint = pick_word()
        send_game_message(context, f"🎉 {user.first_name} doğru bildi!")

def stop(update, context):
    admins = [a.user.id for a in context.bot.get_chat_administrators(update.effective_chat.id)]
    if update.message.from_user.id not in admins:
        return
    end_game(context)

def end_game(context):
    global game_active
    game_active = False

    narrator_name = context.bot.get_chat_member(group_chat_id, narrator_id).user.first_name
    ranking = f"🏆 Lider Tablosu\n\n🎙 Anlatıcı: {narrator_name} – ağzına sağlık 👏\n\n"

    for name, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        ranking += f"{name}: {score} puan\n"

    context.bot.send_message(group_chat_id, ranking)

def timer_check(context):
    if game_active and time.time() - last_activity > 300:
        context.bot.send_message(group_chat_id, "⏱ Oyun sonlandı.")
        end_game(context)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("ping", ping))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text_maintenance"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
