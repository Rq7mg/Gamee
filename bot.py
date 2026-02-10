import os
import random
import time
import psutil
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
scores = {}  # Her oyun sıfırdan başlar
sudo_users = set([OWNER_ID])
duyuru_count = 0  # kaç gruba ulaştı
groups_data = {}  # Her grup için veri saklama

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
    if chat_id not in groups_data:
        groups_data[chat_id] = {"title": chat_title, "users": update.effective_chat.get_members_count() if hasattr(update.effective_chat, "get_members_count") else 0}

# /start → karşılama ve butonlar
def start(update, context):
    track_group(update)
    text = (
        "Merhaba! Telegram Tabu Oyun Botu 😄\n"
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
    ram = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent(interval=0.5)
    update.message.reply_text(f"🏓 Ping: {round(time.time() - update.message.date.timestamp(), 2)} sn\n💾 RAM: {ram}%\n🖥 CPU: {cpu}%")

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
        update.message.reply_text("❌ Kullanım: /addword kelime - ipucu")
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

# /duyuru
def duyuru(update, context):
    global duyuru_count
    user = update.message.from_user
    if user.id not in sudo_users:
        update.message.reply_text("❌ Sadece sudo kullanıcılar kullanabilir.")
        return

    msg_text = ""
    chat_title = ""

    if update.message.reply_to_message:
        reply_msg = update.message.reply_to_message
        if reply_msg.text:
            msg_text = reply_msg.text
        elif reply_msg.caption:
            msg_text = reply_msg.caption
        else:
            msg_text = "<Medya mesajı>"
        chat_title = reply_msg.chat.title or reply_msg.chat.username or "Bilinmeyen Kanal"
    else:
        text = " ".join(context.args)
        if not text:
            update.message.reply_text("❌ Kullanım: /duyuru metin")
            return
        msg_text = text
        chat_title = "Duyuru"

    count = 0
    for gid in groups_data:
        try:
            context.bot.send_message(gid, f"📢 Duyuru ({chat_title}):\n{msg_text}")
            count += 1
        except:
            continue
    duyuru_count += count
    update.message.reply_text(f"✅ Duyuru gönderildi. Toplam {count} gruba ulaştı.")

# Game, mode, button, guess, stop, end_game ve timer_check fonksiyonları önceki koddan aynı şekilde kalır

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
    dp.add_handler(CommandHandler("duyuru", duyuru))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text|text_maintenance"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|write"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
