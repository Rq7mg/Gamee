import os
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
global_scores_col = db["global_scores"]

games = {}

# Her chat için oyun objesi
def get_game(chat_id):
    if chat_id not in games:
        games[chat_id] = {
            "active": False,
            "mode": None,
            "current_word": None,
            "current_hint": None,
            "narrator_id": None,
            "last_activity": time.time(),
            "scores": {},
            "score_ids": {}
        }
    return games[chat_id]

def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d["hint"]
    return None, None

# GAME BAŞLAT
def game(update, context):
    chat_id = update.effective_chat.id
    game_data = get_game(chat_id)

    if game_data["active"]:
        update.message.reply_text("⚠️ Bu grupta zaten aktif bir oyun var!")
        return

    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data=f"voice_{chat_id}")],
        [InlineKeyboardButton("⌨️ Yazılı (Bakımda)", callback_data=f"text_{chat_id}")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

def mode_select(update, context):
    query = update.callback_query
    query.answer()

    data = query.data.split("_")
    mode = data[0]
    chat_id = int(data[1])

    if mode == "text":
        query.answer("⌨️ Yazılı mod bakımda!", show_alert=True)
        return

    game_data = get_game(chat_id)

    if game_data["active"]:
        query.answer("Bu grupta zaten aktif oyun var!", show_alert=True)
        return

    game_data["active"] = True
    game_data["mode"] = mode
    game_data["narrator_id"] = query.from_user.id
    game_data["current_word"], game_data["current_hint"] = pick_word()
    game_data["scores"] = {}
    game_data["score_ids"] = {}
    game_data["last_activity"] = time.time()

    send_game_message(context, chat_id)

def send_game_message(context, chat_id):
    game_data = get_game(chat_id)
    BOT_ID = context.bot.id

    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data=f"look_{chat_id}")],
        [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data=f"next_{chat_id}"),
         InlineKeyboardButton("✍️ Kelime Yaz", url=f"tg://user?id={BOT_ID}")]
    ]

    narrator_name = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user.first_name

    context.bot.send_message(
        chat_id,
        f"Anlatıcı: {narrator_name}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def button(update, context):
    query = update.callback_query
    query.answer()

    action, chat_id = query.data.split("_")
    chat_id = int(chat_id)

    game_data = get_game(chat_id)

    if query.from_user.id != game_data["narrator_id"]:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    game_data["last_activity"] = time.time()

    if action == "look":
        query.answer(
            f"🎯 Kelime:\n{game_data['current_word']}\n\n✨\n\n📌 Tanım:\n{game_data['current_hint']}",
            show_alert=True
        )

    elif action == "next":
        game_data["current_word"], game_data["current_hint"] = pick_word()
        query.answer(
            f"🎯 Yeni Kelime:\n{game_data['current_word']}\n\n✨\n\n📌 Tanım:\n{game_data['current_hint']}",
            show_alert=True
        )

def guess(update, context):
    chat_id = update.effective_chat.id
    game_data = get_game(chat_id)

    if not game_data["active"]:
        return

    text = update.message.text.strip()
    game_data["last_activity"] = time.time()

    # DM kelime yazma
    if update.message.chat.type == "private":
        for gid, gdata in games.items():
            if gdata["active"] and gdata["narrator_id"] == update.message.from_user.id:
                gdata["current_word"] = text
                gdata["current_hint"] = "Kullanıcı tarafından girildi"
                context.bot.send_message(
                    update.message.from_user.id,
                    f"🎯 Yeni Kelime:\n{text}\n\n✨\n\n📌 Tanım:\nKullanıcı tarafından girildi"
                )
                return

    if text.lower() == game_data["current_word"].lower():
        user = update.message.from_user

        game_data["scores"][user.first_name] = game_data["scores"].get(user.first_name, 0) + 1
        game_data["score_ids"][user.first_name] = user.id

        update.message.reply_text(f"🎉 {user.first_name} doğru bildi!")

        game_data["current_word"], game_data["current_hint"] = pick_word()

        context.bot.send_message(
            game_data["narrator_id"],
            f"🎯 Yeni Kelime:\n{game_data['current_word']}\n\n✨\n\n📌 Tanım:\n{game_data['current_hint']}"
        )

def stop(update, context):
    chat_id = update.effective_chat.id
    game_data = get_game(chat_id)

    admins = context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]

    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return

    end_game(context, chat_id)

def end_game(context, chat_id):
    game_data = get_game(chat_id)
    game_data["active"] = False

    # 🔥 GLOBAL SCORE KAYDI
    for name, score in game_data["scores"].items():
        user_id = game_data["score_ids"].get(name)
        global_scores_col.update_one(
            {"user_id": user_id},
            {"$inc": {"score": score}, "$set": {"name": name}},
            upsert=True
        )

    ranking = "🏆 Lider Tablosu\n\n"
    narrator_name = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user.first_name
    ranking += f"Anlatıcı: {narrator_name}\n"
    ranking += "Kazananlar;\n"

    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)

    for idx, (name, score) in enumerate(sorted_scores, 1):
        ranking += f"{idx}. {name}: {score} puan\n"

    context.bot.send_message(chat_id, ranking)

def eniyiler(update, context):
    top_players = global_scores_col.find().sort("score", -1).limit(20)

    text = "🌍 Global En İyiler\n\n"
    for idx, player in enumerate(top_players, 1):
        text += f"{idx}. {player['name']} — {player['score']} puan\n"

    update.message.reply_text(text)

def timer_check(context):
    now = time.time()
    for chat_id, game_data in list(games.items()):
        if game_data["active"] and now - game_data["last_activity"] > 300:
            context.bot.send_message(chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
            end_game(context, chat_id)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))

    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice_|text_"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look_|next_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=15)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
