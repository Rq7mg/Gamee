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
scores_col = db["scores"]

# Global veriler
sudo_users = set([OWNER_ID])
groups_data = {}
games = {}

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
    if chat_id in games and games[chat_id]["active"]:
        update.message.reply_text("❌ Bu grupta oyun zaten devam ediyor!")
        return
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

    current_word, current_hint = pick_word()
    games[chat_id] = {
        "active": True,
        "mode": query.data,
        "narrator_id": query.from_user.id,
        "current_word": current_word,
        "current_hint": current_hint,
        "last_activity": time.time(),
        "scores": {},
        "awaiting_new_word": False
    }
    send_game_message(context, chat_id)

# Oyun mesajı
def send_game_message(context, chat_id):
    game = games[chat_id]
    narrator_id = game["narrator_id"]
    BOT_ID = context.bot.id
    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next"),
         InlineKeyboardButton("✍️ Kelime Yaz", callback_data="write_word")]
    ]
    context.bot.send_message(chat_id,
                             f"Anlatıcı: {context.bot.get_chat_member(chat_id, narrator_id).user.first_name}",
                             reply_markup=InlineKeyboardMarkup(keyboard))

# Buton işlemleri
def button(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    game = games.get(chat_id)
    if not game:
        return

    user = query.from_user
    if user.id != game["narrator_id"]:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    game["last_activity"] = time.time()
    if query.data == "look":
        query.answer(f"🎯 Kelime: {game['current_word']}\n📌 Tanım: {game['current_hint']}", show_alert=True)
    elif query.data == "next":
        game["current_word"], game["current_hint"] = pick_word()
        query.answer(f"🎯 Yeni kelime:\n{game['current_word']}\n📌 Tanım: {game['current_hint']}", show_alert=True)
    elif query.data == "write_word":
        game["awaiting_new_word"] = True
        query.answer("✍️ Lütfen özelden yeni kelimenizi yazın.", show_alert=True)

# Tahmin kontrolü
def guess(update, context):
    chat_id = update.message.chat.id
    game = games.get(chat_id)
    if not game or not game["active"]:
        return

    text = update.message.text.strip()
    game["last_activity"] = time.time()

    # DM üzerinden kelime yazma
    if update.message.chat.type == "private" and update.message.from_user.id in [g["narrator_id"] for g in games.values()]:
        for g_chat_id, g in games.items():
            if g["narrator_id"] == update.message.from_user.id and g.get("awaiting_new_word", False):
                g["current_word"] = text
                g["current_hint"] = "Kullanıcı tarafından girildi"
                g["awaiting_new_word"] = False
                context.bot.send_message(update.message.from_user.id, f"✅ Yeni kelime alındı. Anlatacağınız kelime: {text}")
                send_game_message(context, g_chat_id)
                return

    # Grup tahmini (kısmi eşleşme)
    if game["current_word"].lower() in text.lower():
        user = update.message.from_user
        user_key = f"{user.first_name}[{user.id}]"
        game["scores"][user_key] = game["scores"].get(user_key, 0) + 1

        # Tek mesajla bilinen kelime ve yeni kelime
        context.bot.send_message(chat_id,
            f"🎉 {user.first_name} doğru bildi!\n\nAnlatıcı: {context.bot.get_chat_member(chat_id, game['narrator_id']).user.first_name}"
        )

        # Yeni kelime anlatıcıya pop-up
        game["current_word"], game["current_hint"] = pick_word()
        context.bot.send_message(game["narrator_id"], f"🎯 Yeni kelime:\n{game['current_word']}\n📌 Tanım: {game['current_hint']}")

# /stop
def stop(update, context):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game:
        update.message.reply_text("❌ Bu grupta oyun yok.")
        return

    admins = context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]
    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return

    end_game(context, chat_id)

# Oyun bitirme ve skor kaydı
def end_game(context, chat_id):
    game = games.get(chat_id)
    if not game:
        return

    ranking = "🏆 Lider Tablosu\n\n"
    narrator_name = context.bot.get_chat_member(chat_id, game["narrator_id"]).user.first_name
    ranking += f"Anlatıcı: {narrator_name}\nKazananlar:\n"

    sorted_scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
    for idx, (name, score) in enumerate(sorted_scores, 1):
        medal = ["🥇","🥈","🥉"] + ["🏅"]*7
        ranking += f"{medal[idx-1]} {idx}. {name}: {score} puan\n"

        # MongoDB skor kaydı
        user_name, user_id = name.split("[")
        user_id = int(user_id.rstrip("]"))
        scores_col.update_one(
            {"user_id": user_id},
            {"$inc": {"score": score}, "$set": {"name": user_name}},
            upsert=True
        )

    context.bot.send_message(chat_id, ranking)
    game["active"] = False

# /eniyiler
def eniyiler(update, context):
    top = scores_col.find().sort("score", -1).limit(10)
    msg = "🏆 Global En İyiler\n\n"
    for idx, u in enumerate(top, 1):
        medal = ["🥇","🥈","🥉"] + ["🏅"]*7
        msg += f"{medal[idx-1]} {idx}. {u['name']} [{u['user_id']}]: {u['score']} puan\n"
    update.message.reply_text(msg)

# Inactivity kontrol
def timer_check(context):
    for chat_id, game in list(games.items()):
        if game["active"] and time.time() - game["last_activity"] > 300:
            context.bot.send_message(chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
            end_game(context, chat_id)

# Main
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("addsudo", add_sudo))
    dp.add_handler(CommandHandler("delsudo", del_sudo))
    dp.add_handler(CommandHandler("addword", add_word))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text_maintenance"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|write_word"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
