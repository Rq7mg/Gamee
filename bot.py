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
leaderboard_col = db["leaderboard"]

# Oyun değişkenleri (chat bazlı)
chats = {}  # Her chat_id için ayrı instance

sudo_users = set([OWNER_ID])
groups_data = {}

# --- Yardımcı Fonksiyonlar ---

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

def get_chat_data(chat_id):
    if chat_id not in chats:
        chats[chat_id] = {
            "game_active": False,
            "mode": None,
            "current_word": None,
            "current_hint": None,
            "narrator_id": None,
            "last_activity": time.time(),
            "scores": {}
        }
    return chats[chat_id]

# --- Komutlar ---

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

def stats(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    track_group(update)
    total_groups = len(groups_data)
    total_users = sum([v["users"] for v in groups_data.values()])
    update.message.reply_text(f"📊 Toplam Gruplar: {total_groups}\n📌 Toplam Kullanıcılar: {total_users}")

def ping(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    ping_time = round(time.time() - update.message.date.timestamp(), 2)
    update.message.reply_text(f"🏓 Ping: {ping_time} sn")

def word_count(update, context):
    count = words_col.count_documents({})
    update.message.reply_text(f"📊 Toplam kelime: {count}")

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

# --- Oyun Fonksiyonları ---

def game(update, context):
    chat_id = update.effective_chat.id
    chat_data = get_chat_data(chat_id)

    if chat_data["game_active"]:
        update.message.reply_text("❌ Bu sohbette oyun zaten devam ediyor.")
        return

    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı (Bakımda)", callback_data="text_maintenance")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

def mode_select(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat.id
    chat_data = get_chat_data(chat_id)

    if query.data == "text_maintenance":
        query.answer("⌨️ Yazılı mod şu an bakımda!", show_alert=True)
        return

    chat_data["game_active"] = True
    chat_data["narrator_id"] = query.from_user.id
    chat_data["mode"] = query.data
    chat_data["current_word"], chat_data["current_hint"] = pick_word()
    chat_data["last_activity"] = time.time()
    chat_data["scores"] = {}

    send_game_message(context, chat_id)

def send_game_message(context, chat_id):
    chat_data = get_chat_data(chat_id)
    BOT_ID = context.bot.id
    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next"),
         InlineKeyboardButton("✍️ Kelime Yaz", url=f"tg://user?id={BOT_ID}")]
    ]
    context.bot.send_message(chat_id,
                             f"Anlatıcı: {context.bot.get_chat_member(chat_id, chat_data['narrator_id']).user.first_name}",
                             reply_markup=InlineKeyboardMarkup(keyboard))

def button(update, context):
    query = update.callback_query
    user = query.from_user
    chat_id = query.message.chat.id
    chat_data = get_chat_data(chat_id)

    if user.id != chat_data["narrator_id"]:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    chat_data["last_activity"] = time.time()

    if query.data == "look":
        query.answer(f"🎯 Kelime: {chat_data['current_word']}\n📌 Tanım: {chat_data['current_hint']}", show_alert=True)
    elif query.data == "next":
        chat_data["current_word"], chat_data["current_hint"] = pick_word()
        query.answer(f"🎯 Yeni kelime:\n{chat_data['current_word']}\n📌 Tanım: {chat_data['current_hint']}", show_alert=True)

def guess(update, context):
    text = update.message.text.strip().lower()
    chat_id = update.message.chat.id
    chat_data = get_chat_data(chat_id)

    if not chat_data["game_active"]:
        return

    chat_data["last_activity"] = time.time()
    user = update.message.from_user
    user_key = f"{user.first_name}[{user.id}]"

    # Özelden yeni kelime
    if update.message.chat.type == "private" and user.id == chat_data["narrator_id"]:
        chat_data["current_word"] = text
        chat_data["current_hint"] = "Kullanıcı tarafından girildi"
        context.bot.send_message(user.id,
                                 f"🎯 Yeni kelime:\n{chat_data['current_word']}\n📌 Tanım: {chat_data['current_hint']}")
        return

    # Grup tahmini → kelime parçalarını da kabul et
    if chat_data["current_word"].lower() in text:
        chat_data["scores"][user_key] = chat_data["scores"].get(user_key, 0) + 1
        update.message.reply_text(f"🎉 {user.first_name} doğru bildi!")
        chat_data["current_word"], chat_data["current_hint"] = pick_word()
        context.bot.send_message(chat_data["narrator_id"],
                                 f"🎯 Yeni kelime:\n{chat_data['current_word']}\n📌 Tanım: {chat_data['current_hint']}")

def stop(update, context):
    chat_id = update.effective_chat.id
    chat_data = get_chat_data(chat_id)

    admins = context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]
    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return
    end_game(context, chat_id)

def end_game(context, chat_id):
    chat_data = get_chat_data(chat_id)
    chat_data["game_active"] = False

    ranking = "🏆 Lider Tablosu\n\n"
    if chat_data["narrator_id"]:
        narrator_name = context.bot.get_chat_member(chat_id, chat_data["narrator_id"]).user.first_name
        ranking += f"Anlatıcı: {narrator_name}\n"
    ranking += "Kazananlar:\n"

    sorted_scores = sorted(chat_data["scores"].items(), key=lambda x: x[1], reverse=True)

    for idx, (user_key, score) in enumerate(sorted_scores, 1):
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = "🏅"
        ranking += f"{medal} {idx}. {user_key}: {score} puan\n"

        # MongoDB kaydı (isim + id)
        name, user_id_str = user_key.rsplit("[", 1)
        user_id_int = int(user_id_str[:-1])
        existing = leaderboard_col.find_one({"id": user_id_int})
        if existing:
            leaderboard_col.update_one({"id": user_id_int}, {"$inc": {"score": score}})
        else:
            leaderboard_col.insert_one({"name": name, "id": user_id_int, "score": score})

    context.bot.send_message(chat_id, ranking)

def timer_check(context):
    for chat_id, chat_data in chats.items():
        if chat_data["game_active"] and time.time() - chat_data["last_activity"] > 300:
            context.bot.send_message(chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
            end_game(context, chat_id)

# --- /eniyiler ---
def eniyiler(update, context):
    top_players = leaderboard_col.find().sort("score", -1).limit(10)
    msg = "🏆 Global En İyiler\n\n"
    has_player = False
    for idx, player in enumerate(top_players, 1):
        has_player = True
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = "🏅"
        msg += f"{medal} {idx}. {player['name']} [{player['id']}]: {player['score']} puan\n"
    if not has_player:
        msg = "📊 Henüz puanlı oyuncu yok."
    update.message.reply_text(msg)

# --- Main ---

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
