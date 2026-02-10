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

# Oyun değişkenleri
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

# Kelime seç
def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d["hint"]
    return None, None

# Grup takip
def track_group(update):
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or update.effective_chat.username or "Özel Chat"
    groups_data[chat_id] = {
        "title": chat_title,
        "users": update.effective_chat.get_member_count() if hasattr(update.effective_chat, "get_member_count") else 0
    }

# /start
def start(update, context):
    track_group(update)
    text = (
        "Merhaba! Ben Telegram Tabu Oyun Botu 😄\n"
        "Komutlar:\n"
        "/game → Oyunu başlatır\n"
        "/stop → Oyunu durdurur (admin)\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("👑 Sahip", url=f"tg://user?id={OWNER_ID}"),
            InlineKeyboardButton("➕ Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true"),
            InlineKeyboardButton("💬 Destek Kanalı", url="https://t.me/kiyiciupdate")
        ]
    ]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# /stats → sadece owner
def stats(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    track_group(update)
    total_groups = len(groups_data)
    total_users = sum([v["users"] for v in groups_data.values()])
    update.message.reply_text(f"📊 Toplam Gruplar: {total_groups}\n📌 Toplam Kullanıcılar: {total_users}")

# /ping → sadece owner
def ping(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    ping_time = round(time.time() - update.message.date.timestamp(), 2)
    update.message.reply_text(f"🏓 Ping: {ping_time} sn")

# /wordcount
def word_count(update, context):
    count = words_col.count_documents({})
    update.message.reply_text(f"📊 Toplam kelime: {count}")

# /addsudo
def add_sudo(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    try:
        user_id = int(context.args[0])
        sudo_users.add(user_id)
        update.message.reply_text(f"✅ {user_id} sudo olarak eklendi.")
    except:
        update.message.reply_text("❌ Kullanım: /addsudo <id>")

# /delsudo
def del_sudo(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    try:
        user_id = int(context.args[0])
        if user_id in sudo_users:
            sudo_users.remove(user_id)
            update.message.reply_text(f"✅ {user_id} sudo listeden kaldırıldı.")
        else:
            update.message.reply_text("❌ Bu kullanıcı sudo değil.")
    except:
        update.message.reply_text("❌ Kullanım: /delsudo <id>")

# /addword
def add_word(update, context):
    if update.message.from_user.id not in sudo_users:
        update.message.reply_text("❌ Sadece sudo kullanıcı kelime ekleyebilir.")
        return
    if len(context.args) < 1:
        update.message.reply_text("❌ Kullanım: /addword kelime - tanım")
        return
    text = " ".join(context.args)
    if "-" in text:
        word, hint = map(str.strip, text.split("-", 1))
    else:
        word = text.strip()
        hint = ""
    word_lower = word.lower()
    if words_col.find_one({"word": word_lower}):
        update.message.reply_text("❌ Bu kelime zaten var.")
        return
    words_col.insert_one({"word": word_lower, "hint": hint})
    update.message.reply_text(f"✅ Kelime eklendi: {word} - {hint}")

# /game → mod seçimi
def game(update, context):
    global group_chat_id
    group_chat_id = update.effective_chat.id
    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı (Bakımda)", callback_data="text_maintenance")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

# Mod seçimi
def mode_select(update, context):
    global game_active, narrator_id, current_word, current_hint, mode, last_activity, scores
    query = update.callback_query
    query.answer()
    if query.data == "text_maintenance":
        query.answer("⌨️ Yazılı mod şu an bakımda!", show_alert=True)
        return
    game_active = True
    narrator_id = query.from_user.id
    mode = query.data
    current_word, current_hint = pick_word()
    last_activity = time.time()
    scores = {}
    send_game_message(context)

# Oyun mesajı → buton düzeni ve gizlilik
def send_game_message(context, correct_user=None):
    global group_chat_id, narrator_id, current_word, current_hint
    BOT_ID = context.bot.id
    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [InlineKeyboardButton("➡️ Kelimeyi Geç", callback_data="next"),
         InlineKeyboardButton("✍️ Kelime Yaz", url=f"tg://user?id={BOT_ID}")]
    ]
    message_text = ""
    if correct_user:
        message_text += f"🎉 {correct_user} doğru bildi!\n\n"
    # Kelime ve tanım (tanım başında emoji)
    message_text += f"🎯 Kelime: {current_word}\n📌 Tanım: {current_hint}"
    context.bot.send_message(group_chat_id, message_text, reply_markup=InlineKeyboardMarkup(keyboard))

# Buton işlemleri
def button(update, context):
    global current_word, current_hint, narrator_id, last_activity
    query = update.callback_query
    user = query.from_user
    last_activity = time.time()
    if query.data == "look":
        if user.id == narrator_id:
            query.answer(f"🎯 Kelime: {current_word}\n📌 Tanım: {current_hint}", show_alert=True)
        else:
            query.answer("Sadece anlatıcı görebilir.", show_alert=True)
    elif query.data == "next":
        current_word, current_hint = pick_word()
        if user.id == narrator_id:
            query.answer(f"🎯 Yeni Kelime:\n{current_word}\n📌 Tanım: {current_hint}", show_alert=True)
        else:
            query.answer("Sadece anlatıcı görebilir.", show_alert=True)

# Tahmin kontrolü
def guess(update, context):
    global narrator_id, current_word, current_hint, last_activity, scores
    if not game_active:
        return
    text = update.message.text.strip()
    last_activity = time.time()
    # Özelden yeni kelime
    if update.message.chat.type == "private" and update.message.from_user.id == narrator_id:
        current_word = text
        current_hint = "Kullanıcı tarafından girildi"
        context.bot.send_message(narrator_id, f"Yeni kelime ayarlandı: {current_word}")
        return
    # Grup tahmini
    if text.lower() == current_word.lower():
        user = update.message.from_user
        scores[user.first_name] = scores.get(user.first_name, 0) + 1
        current_word, current_hint = pick_word()
        send_game_message(context, correct_user=user.first_name)

# /stop
def stop(update, context):
    global game_active
    admins = context.bot.get_chat_administrators(update.effective_chat.id)
    admin_ids = [a.user.id for a in admins]
    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return
    end_game(context)

# Oyun bitirme
def end_game(context):
    global game_active
    game_active = False
    ranking = "🏆 Lider Tablosu\n\n"
    if narrator_id:
        narrator_name = context.bot.get_chat_member(group_chat_id, narrator_id).user.first_name
        ranking += f"Anlatıcı: {narrator_name}\n"
    ranking += "Kazananlar:\n"
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for i, (name, score) in enumerate(sorted_scores, 1):
        ranking += f"{i}. {name}: {score} puan\n"
    context.bot.send_message(group_chat_id, ranking)

# 5 dk inactivity kontrol
def timer_check(context):
    global game_active
    if game_active and time.time() - last_activity > 300:
        context.bot.send_message(group_chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
        end_game(context)

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
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text_maintenance"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|write"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
