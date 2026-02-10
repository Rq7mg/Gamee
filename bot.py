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
scores = {}  # Her oyun sıfırdan başlar
sudo_users = set([OWNER_ID])
duyuru_count = 0  # kaç kişiye ulaştı
groups_data = {}  # Her grup için kullanıcı sayısı saklanacak

# Kelime seç
def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d["hint"]
    return None, None

# /start
def start(update, context):
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or update.effective_chat.username or "Özel Chat"
    # Grup veri kaydı
    if chat_id not in groups_data:
        groups_data[chat_id] = {"title": chat_title, "users": 0}
    text = (
        f"Merhaba! Ben Telegram Tabu Oyun Botu 😄\n"
        f"Bu grup: {chat_title}\n"
        "Komutlar:\n"
        "/start → Bu mesajı gösterir\n"
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

# /starts → kaç kullanıcı ve kaç grup
def starts(update, context):
    total_groups = len(groups_data)
    total_users = sum([v["users"] for v in groups_data.values()])
    update.message.reply_text(f"📊 Toplam Gruplar: {total_groups}\nToplam Kullanıcılar: {total_users}")

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

    # Her gruba gönder
    count = 0
    for gid in groups_data:
        try:
            context.bot.send_message(gid, f"📢 Duyuru ({chat_title}):\n{msg_text}")
            count += 1
        except:
            continue
    duyuru_count += count
    update.message.reply_text(f"✅ Duyuru gönderildi. Toplam {count} gruba ulaştı.")

# /game
def game(update, context):
    global group_chat_id, scores
    group_chat_id = update.effective_chat.id
    scores = {}
    groups_data[group_chat_id]["users"] = update.effective_chat.get_members_count() if hasattr(update.effective_chat, "get_members_count") else 0
    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı (Bakımda)", callback_data="text_maintenance")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

# Mod seçimi
def mode_select(update, context):
    global game_active, narrator_id, current_word, current_hint, mode, last_activity
    query = update.callback_query
    query.answer()
    if query.data == "text_maintenance":
        query.answer("⌨️ Yazılı mod şu anda bakımdadır.", show_alert=True)
        return
    game_active = True
    narrator_id = query.from_user.id
    mode = query.data
    current_word, current_hint = pick_word()
    last_activity = time.time()
    send_game_message(context)

# Oyun mesajı
def send_game_message(context):
    global group_chat_id, narrator_id, current_word, current_hint
    keyboard = [
        [
            InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look"),
            InlineKeyboardButton("➡️ Kelimeyi Geç", callback_data="next"),
            InlineKeyboardButton("✍️ Kelime Yaz", callback_data="write")
        ]
    ]
    context.bot.send_message(
        group_chat_id,
        f"Oyun başladı!\nMod: {'Sesli' if mode=='voice' else 'Yazılı'}\nAnlatıcı: {context.bot.get_chat_member(group_chat_id, narrator_id).user.first_name}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Buton işlemleri
def button(update, context):
    global current_word, current_hint, narrator_id, last_activity
    query = update.callback_query
    user = query.from_user
    if user.id != narrator_id:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return
    last_activity = time.time()
    if query.data == "look":
        query.answer(f"Kelime: {current_word}\nİpucu: {current_hint}", show_alert=True)
    elif query.data == "next":
        current_word, current_hint = pick_word()
        query.answer("Yeni kelime atandı! Kelimeye Bak kısmında (;", show_alert=True)
    elif query.data == "write":
        context.bot.send_message(narrator_id, "✍️ Yeni kelimeyi yazın .")
        query.answer("Özel mesaj açıldı.", show_alert=True)

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
        update.message.reply_text(f"🎉 {user.first_name} doğru bildi!")
        current_word, current_hint = pick_word()
        send_game_message(context)

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
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for name, score in sorted_scores:
        ranking += f"{name}: {score} puan\n"
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
    dp.add_handler(CommandHandler("starts", starts))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("wordcount", word_count))
    dp.add_handler(CommandHandler("addsudo", add_sudo))
    dp.add_handler(CommandHandler("delsudo", del_sudo))
    dp.add_handler(CommandHandler("addword", add_word))
    dp.add_handler(CommandHandler("duyuru", duyuru))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text_maintenance"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|write"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))
    updater.job_queue.run_repeating(timer_check, interval=10)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
