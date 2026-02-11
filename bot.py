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
scores_col = db["scores"]  # Global skorlar

# Oyun durumları grup bazlı
games = {}  # {chat_id: {game_active, narrator_id, current_word, current_hint, last_activity, scores}}

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
        "/eniyiler → Global en iyileri gösterir"
    )
    keyboard = [
        [InlineKeyboardButton("Beni Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        [InlineKeyboardButton("👑 Sahip", url=f"tg://user?id={OWNER_ID}"),
         InlineKeyboardButton("💬 Destek", url="https://t.me/kiyiciupdate")]
    ]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# /stats
def stats(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    track_group(update)
    total_groups = len(groups_data)
    total_users = sum([v["users"] for v in groups_data.values()])
    update.message.reply_text(f"📊 Toplam Gruplar: {total_groups}\n📌 Toplam Kullanıcılar: {total_users}")

# /ping
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

# /game
def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games and games[chat_id]["game_active"]:
        update.message.reply_text("❌ Oyun zaten devam ediyor!")
        return
    games[chat_id] = {
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
    chat_id = query.message.chat.id
    if query.data == "text_maintenance":
        query.answer("⌨️ Yazılı mod şu an bakımda!", show_alert=True)
        return
    games[chat_id]["game_active"] = True
    games[chat_id]["narrator_id"] = query.from_user.id
    games[chat_id]["current_word"], games[chat_id]["current_hint"] = pick_word()
    games[chat_id]["last_activity"] = time.time()
    games[chat_id]["scores"] = {}
    send_game_message(context, chat_id)

# Oyun mesajı
def send_game_message(context, chat_id, correct_user=None):
    game_data = games[chat_id]
    narrator_id = game_data["narrator_id"]
    BOT_ID = context.bot.id
    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next"),
         InlineKeyboardButton("✍️ Kelime Yaz", url=f"tg://user?id={BOT_ID}")]
    ]
    message_text = ""
    if correct_user:
        message_text += f"🎉 {correct_user} doğru bildi!\n\n"
    message_text += f"Anlatıcı: {context.bot.get_chat_member(chat_id, narrator_id).user.first_name}"
    context.bot.send_message(chat_id, message_text, reply_markup=InlineKeyboardMarkup(keyboard))

# Buton işlemleri
def button(update, context):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    game_data = games.get(chat_id)
    if not game_data:
        return
    narrator_id = game_data["narrator_id"]
    if user.id != narrator_id:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return
    game_data["last_activity"] = time.time()
    if query.data == "look":
        query.answer(f"🎯 Kelime: {game_data['current_word']}\n📌 Tanım: {game_data['current_hint']}", show_alert=True)
    elif query.data == "next":
        game_data["current_word"], game_data["current_hint"] = pick_word()
        query.answer(f"🎯 Yeni kelime:\n{game_data['current_word']}\n📌 Tanım: {game_data['current_hint']}", show_alert=True)

# Tahmin kontrolü
def guess(update, context):
    text = update.message.text.strip().lower()
    chat_id = update.effective_chat.id
    game_data = games.get(chat_id)
    if not game_data or not game_data["game_active"]:
        return
    game_data["last_activity"] = time.time()
    user = update.message.from_user

    # Özelden yeni kelime
    if update.message.chat.type == "private" and user.id == game_data["narrator_id"]:
        game_data["current_word"] = text
        game_data["current_hint"] = "Kullanıcı tarafından girildi"
        context.bot.send_message(user.id, f"🎯 Yeni kelime:\n{game_data['current_word']}\n📌 Tanım: {game_data['current_hint']}")
        return

    # Tahmin kontrolü: substring kontrolü
    if game_data["current_word"].lower() in text:
        game_data["scores"][user.first_name] = game_data["scores"].get(user.first_name, 0) + 1
        # Grup mesajı: sadece kimin doğru bildiği
        update.message.reply_text(f"🎉 {user.first_name} doğru bildi!")
        # Global Mongo kaydı
        scores_col.update_one(
            {"user_id": user.id},
            {"$inc": {"score": 1}, "$set": {"name": user.first_name}},
            upsert=True
        )
        # Yeni kelime sadece anlatıcıya
        game_data["current_word"], game_data["current_hint"] = pick_word()
        context.bot.send_message(game_data["narrator_id"],
                                 f"🎯 Yeni kelime:\n{game_data['current_word']}\n📌 Tanım: {game_data['current_hint']}")
        # Yeni oyun mesajı grup için
        send_game_message(context, chat_id, correct_user=user.first_name)

# /stop
def stop(update, context):
    chat_id = update.effective_chat.id
    game_data = games.get(chat_id)
    if not game_data or not game_data["game_active"]:
        update.message.reply_text("❌ Oyun aktif değil.")
        return
    admins = context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]
    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return
    end_game(context, chat_id)

# Oyun bitirme
def end_game(context, chat_id):
    game_data = games.get(chat_id)
    if not game_data:
        return
    game_data["game_active"] = False
    ranking = "🏆 Lider Tablosu\n\n"
    if game_data["narrator_id"]:
        narrator_name = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user.first_name
        ranking += f"Anlatıcı: {narrator_name}\n"
    ranking += "Kazananlar:\n"
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
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
    context.bot.send_message(chat_id, ranking)

# /eniyiler
def eniyiler(update, context):
    top_users = scores_col.find().sort("score", -1).limit(10)
    text = "🌟 Global En İyiler 🌟\n\n"
    for idx, u in enumerate(top_users, 1):
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = "🏅"
        text += f"{medal} {idx}. {u.get('name')} [{u.get('user_id')}]: {u.get('score')} puan\n"
    update.message.reply_text(text)

# 5 dk inactivity kontrol
def timer_check(context):
    now = time.time()
    for chat_id, game_data in games.items():
        if game_data["game_active"] and now - game_data["last_activity"] > 300:
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
