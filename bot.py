import os
import random
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

# MongoDB bağlantısı
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["tabu_bot"]
words_col = db["words"]
scores_col = db["scores"]  # global en iyiler için

# Oyun durumları chat bazlı olacak
chats_data = {}  # {chat_id: {game_active, narrator_id, current_word, current_hint, last_activity, scores}}

sudo_users = set([OWNER_ID])

# Kelime seç
def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d["hint"]
    return None, None

# /start
def start(update, context):
    text = (
        "Merhaba! Ben Telegram Tabu Oyun Botu 😄\n"
        "Komutlar:\n"
        "/game → Oyunu başlatır\n"
        "/stop → Oyunu durdurur (admin)\n"
        "/eniyiler → Global en iyileri gösterir"
    )
    keyboard = [
        [InlineKeyboardButton("Beni Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        [InlineKeyboardButton("👑 Sahip", url=f"tg://user?id={OWNER_ID}"),
         InlineKeyboardButton("💬 Destek", url="https://t.me/kiyiciupdate")]
    ]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# /game
def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in chats_data and chats_data[chat_id]["game_active"]:
        update.message.reply_text("❌ Oyun zaten devam ediyor!")
        return

    chats_data[chat_id] = {
        "game_active": False,
        "narrator_id": None,
        "current_word": None,
        "current_hint": None,
        "last_activity": time.time(),
        "scores": {}
    }

    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı (Bakımda)", callback_data="text_maintenance")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

# Mod seçimi
def mode_select(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat_id

    if query.data == "text_maintenance":
        query.answer("⌨️ Yazılı mod şu an bakımda!", show_alert=True)
        return

    chats_data[chat_id]["game_active"] = True
    chats_data[chat_id]["narrator_id"] = query.from_user.id
    chats_data[chat_id]["current_word"], chats_data[chat_id]["current_hint"] = pick_word()
    chats_data[chat_id]["last_activity"] = time.time()
    chats_data[chat_id]["scores"] = {}

    send_game_message(context, chat_id)

# Oyun mesajı
def send_game_message(context, chat_id, correct_user=None):
    data = chats_data[chat_id]
    narrator_id = data["narrator_id"]
    BOT_ID = context.bot.id

    text = ""
    if correct_user:
        text += f"🎉 {correct_user} doğru bildi!\n\n"

    narrator_name = context.bot.get_chat_member(chat_id, narrator_id).user.first_name
    text += f"Anlatıcı: {narrator_name}"

    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next"),
         InlineKeyboardButton("✍️ Kelime Yaz", callback_data="write")]
    ]
    context.bot.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard))

# Buton işlemleri
def button(update, context):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat_id
    data = chats_data[chat_id]

    if user.id != data["narrator_id"]:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    data["last_activity"] = time.time()

    if query.data == "look":
        query.answer(f"🎯 Kelime: {data['current_word']}\n📌 Tanım: {data['current_hint']}", show_alert=True)
    elif query.data == "next":
        data["current_word"], data["current_hint"] = pick_word()
        query.answer(f"🎯 Yeni kelime:\n{data['current_word']}\n📌 Tanım: {data['current_hint']}", show_alert=True)
    elif query.data == "write":
        context.bot.send_message(user.id, "📌 Yeni kelimeyi girin, bu artık anlatılacak kelime olacak:")

# Tahmin kontrolü
def guess(update, context):
    chat_id = update.message.chat.id
    if chat_id not in chats_data or not chats_data[chat_id]["game_active"]:
        return

    data = chats_data[chat_id]
    text = update.message.text.strip()
    data["last_activity"] = time.time()

    # Özel DM’den kelime girme
    if update.message.chat.type == "private" and update.message.from_user.id == data["narrator_id"]:
        data["current_word"] = text
        data["current_hint"] = "Kullanıcı tarafından girildi"
        context.bot.send_message(data["narrator_id"],
                                 f"🎯 Bu artık anlatılacak kelime:\n{data['current_word']}\n📌 Tanım: {data['current_hint']}")
        return

    # Tahmin kontrolü
    if text.lower() == data["current_word"].lower() or data["current_word"].lower() in text.lower():
        user = update.message.from_user
        data["scores"][user.first_name] = data["scores"].get(user.first_name, 0) + 1
        # Grup mesajı tek olacak
        send_game_message(context, chat_id, correct_user=user.first_name)

# /stop
def stop(update, context):
    chat_id = update.effective_chat.id
    data = chats_data.get(chat_id)
    if not data or not data["game_active"]:
        update.message.reply_text("❌ Oyun zaten başlamadı!")
        return

    admins = context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]
    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return
    end_game(context, chat_id)

# Oyun bitirme
def end_game(context, chat_id):
    data = chats_data[chat_id]
    data["game_active"] = False
    ranking = "🏆 Lider Tablosu\n\n"
    narrator_name = context.bot.get_chat_member(chat_id, data["narrator_id"]).user.first_name
    ranking += f"Anlatıcı: {narrator_name}\nKazananlar:\n"

    sorted_scores = sorted(data["scores"].items(), key=lambda x: x[1], reverse=True)
    for idx, (name, score) in enumerate(sorted_scores, 1):
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = "🏅"
        ranking += f"{medal} {idx}. {name}: {score} puan\n"

        # Global puan kaydı MongoDB
        scores_col.update_one({"name": name}, {"$inc": {"score": score}}, upsert=True)

    context.bot.send_message(chat_id, ranking)

# /eniyiler
def eniyiler(update, context):
    top = scores_col.find().sort("score", -1).limit(10)
    text = "🌟 Global En İyiler 🌟\n\n"
    for idx, user in enumerate(top, 1):
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = "🏅"
        text += f"{medal} {idx}. {user['name']} [{user['_id']}] : {user['score']} puan\n"
    update.message.reply_text(text)

# 5 dk inactivity kontrol
def timer_check(context):
    for chat_id, data in chats_data.items():
        if data["game_active"] and time.time() - data["last_activity"] > 300:
            context.bot.send_message(chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
            end_game(context, chat_id)

# Main
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("ping", ping))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("wordcount", word_count))
    dp.add_handler(CommandHandler("addsudo", add_sudo))
    dp.add_handler(CommandHandler("delsudo", del_sudo))
    dp.add_handler(CommandHandler("addword", add_word))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text_maintenance"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|write"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
