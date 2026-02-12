import os
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

# --- ENV ---
TOKEN = os.environ.get("BOT_TOKEN")  # Hem sesli hem yazılı mod için aynı token
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

# --- DB ---
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["tabu_bot"]
words_col = db["words"]
scores_col = db["scores"]

# --- GLOBALS ---
games_text = {}       # Yazılı mod oyunları
pending_dm_text = {}  # DM ile kelime ekleme
sudo_users = set([OWNER_ID])

# --- FONKSİYONLAR ---
def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d["hint"]
    return None, None

# --- /game → Sesli / Yazılı Mod Seçimi ---
def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games_text and games_text[chat_id]["active"]:
        update.message.reply_text("❌ Bu grupta yazılı modda oyun zaten devam ediyor!")
        return

    keyboard = [
        [InlineKeyboardButton("🎤 Sesli Mod", callback_data="voice_mode")],
        [InlineKeyboardButton("📝 Yazılı Mod", callback_data="text_mode")]
    ]
    update.message.reply_text("Oyun modunu seçin:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Yazılı mod başlatma ---
def start_text_game(chat_id, narrator_id, mode, context):
    current_word, current_hint = pick_word()
    games_text[chat_id] = {
        "active": True,
        "mode": mode,  # fixed / rotating
        "narrator_id": narrator_id,
        "current_word": current_word,
        "current_hint": current_hint,
        "last_activity": time.time(),
        "scores": {},
        "last_messages": [],
        "correct_count": 0
    }
    send_game_message(context, chat_id)

# --- Yazılı mod mesaj ve butonları ---
def send_game_message(context, chat_id, prefix_msg=""):
    game = games_text[chat_id]
    bot_username = context.bot.username
    dm_link = f"https://t.me/{bot_username}?start=writeword_{chat_id}"

    if game["mode"] == "fixed":
        keyboard = [
            [InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="look")],
            [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next")],
            [InlineKeyboardButton("✍️ Kelime Yaz", url=dm_link)]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="look")],
            [InlineKeyboardButton(f"🎤 Anlatıcı: {context.bot.get_chat_member(chat_id, game['narrator_id']).user.first_name}", callback_data="narrator_button")],
            [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next")],
            [InlineKeyboardButton("✍️ Kelime Yaz", url=dm_link)],
            [InlineKeyboardButton("🙅 Anlatıcı Olmak İstemiyorum", callback_data="skip_narrator")]
        ]

    narrator_name = context.bot.get_chat_member(chat_id, game['narrator_id']).user.first_name
    msg = f"{prefix_msg}\nAnlatıcı: {narrator_name}" if prefix_msg else f"Anlatıcı: {narrator_name}"

    message = context.bot.send_message(
        chat_id, msg,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

    game["last_messages"].append(message.message_id)
    game["last_messages"] = game["last_messages"][-5:]

# --- CallbackQueryHandler ---
def button(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    game = games_text.get(chat_id)
    user = query.from_user

    # Sesli / Yazılı mod seçimi
    if query.data == "voice_mode":
        query.answer("🎤 Sesli mod seçildi. Sesli bot akışı devreye girer.", show_alert=True)
        return

    if query.data == "text_mode":
        keyboard = [
            [InlineKeyboardButton("🟦 Sabit Mod", callback_data="mode_fixed")],
            [InlineKeyboardButton("🔄 Değişken Mod", callback_data="mode_rotating")]
        ]
        query.message.edit_text("Yazılı mod seçin:", reply_markup=InlineKeyboardMarkup(keyboard))
        query.answer()
        return

    if query.data in ["mode_fixed", "mode_rotating"]:
        mode = "fixed" if query.data == "mode_fixed" else "rotating"
        start_text_game(chat_id, query.from_user.id, mode, context)
        query.answer(f"✅ {mode.capitalize()} mod seçildi!", show_alert=True)
        return

    if not game or not game["active"]:
        return

    # Yazılı mod oyun butonları
    game["last_activity"] = time.time()

    if game["mode"] == "fixed" and query.data in ["look", "next"] and user.id != game["narrator_id"]:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    if query.data == "look":
        query.answer(f"🎯 Kelime: {game['current_word']}\n📌 Tanım: {game['current_hint']}", show_alert=True)

    elif query.data == "next":
        game["current_word"], game["current_hint"] = pick_word()
        query.answer(f"🎯 Yeni kelime: {game['current_word']}", show_alert=True)
        send_game_message(context, chat_id)

    elif query.data == "skip_narrator" and game["mode"] == "rotating":
        query.answer("🙅 Anlatıcı olmayı reddettiniz.", show_alert=True)
        game["narrator_id"] = None
        send_game_message(context, chat_id)

# --- Tahmin ---
def guess(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if update.message.chat.type == "private":
        if user_id in pending_dm_text:
            target_chat = pending_dm_text[user_id]
            game = games_text.get(target_chat)
            if game:
                game["current_word"] = text
                game["current_hint"] = "Kullanıcı tarafından girildi"
                context.bot.send_message(user_id, f"🎯 Yeni anlatacağınız kelime: {text}")
            pending_dm_text.pop(user_id, None)
        return

    game = games_text.get(chat_id)
    if not game or not game["active"]:
        return

    if game["current_word"].lower() in text.lower() and user_id != game.get("narrator_id"):
        user = update.message.from_user
        user_key = f"{user.first_name}[{user.id}]"
        game["scores"][user_key] = game["scores"].get(user_key, 0) + 1
        game["correct_count"] += 1

        # MongoDB güncelle
        scores_col.update_one(
            {"user_id": user.id},
            {"$inc": {"score": 1}, "$set": {"name": user.first_name}},
            upsert=True
        )

        prefix_msg = f"🎉 {user.first_name} '*{game['current_word']}*' kelimesini doğru bildi!"
        if game["mode"] == "rotating":
            game["narrator_id"] = user.id
            prefix_msg += " Yeni anlatıcı sizsiniz."

        game["current_word"], game["current_hint"] = pick_word()
        send_game_message(context, chat_id, prefix_msg=prefix_msg)

# --- Stop / End ---
def stop(update, context):
    chat_id = update.effective_chat.id
    game = games_text.get(chat_id)
    if not game:
        update.message.reply_text("❌ Bu grupta oyun yok.")
        return

    admins = context.bot.get_chat_administrators(chat_id)
    if update.message.from_user.id not in [a.user.id for a in admins]:
        update.message.reply_text("Sadece admin durdurabilir.")
        return

    end_game(context, chat_id)

def end_game(context, chat_id):
    game = games_text.get(chat_id)
    if not game:
        return

    ranking = "🏆 Lider Tablosu\n\n"
    narrator_id = game.get("narrator_id")
    narrator_name = context.bot.get_chat_member(chat_id, narrator_id).user.first_name if narrator_id else "Belirsiz"
    ranking += f"Anlatıcı: {narrator_name}\nKazananlar:\n"

    sorted_scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
    for idx, (name, score) in enumerate(sorted_scores, 1):
        medal = ["🥇","🥈","🥉"] + ["🏅"]*7
        ranking += f"{medal[idx-1]} {idx}. {name}: {score} puan\n"

    context.bot.send_message(chat_id, ranking)
    games_text.pop(chat_id, None)

# --- Global skor ---
def eniyiler(update, context):
    top = scores_col.find().sort("score", -1).limit(10)
    msg = "🏆 Global En İyiler\n\n"
    for idx, u in enumerate(top, 1):
        medal = ["🥇","🥈","🥉"] + ["🏅"]*7
        msg += f"{medal[idx-1]} {idx}. {u['name']} [{u['user_id']}]: {u['score']} puan\n"
    update.message.reply_text(msg)

# --- Zamanlayıcı: 5 dk boşta kalan oyun ---
def timer_check(context):
    for chat_id, game in list(games_text.items()):
        if game["active"] and time.time() - game["last_activity"] > 300:
            context.bot.send_message(chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
            end_game(context, chat_id)

# --- MAIN ---
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("wordcount", lambda u,c: u.message.reply_text(f"📚 Toplam kelime sayısı: {words_col.count_documents({})}")))

    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|skip_narrator|mode_fixed|mode_rotating|voice_mode|text_mode"))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
