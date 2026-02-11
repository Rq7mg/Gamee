import os
import time
import pymongo
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["tabu_bot"]
words_col = db["words"]
scores_col = db["global_scores"]

sudo_users = set([OWNER_ID])
groups_data = {}

# Her chat için ayrı oyun
games = {}

# ------------------ KELİME ------------------

def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d.get("hint", "")
    return None, None

# ------------------ START ------------------

def start(update, context):
    text = (
        "Merhaba! Ben Telegram Tabu Botu 😄\n\n"
        "/game → Oyunu başlat\n"
        "/stop → Oyunu durdur\n"
    )

    keyboard = [[
        InlineKeyboardButton("👑 Sahip", url=f"tg://user?id={OWNER_ID}"),
        InlineKeyboardButton("➕ Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true"),
        InlineKeyboardButton("💬 Destek Kanalı", url="https://t.me/kiyiciupdate")
    ]]

    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ------------------ GAME ------------------

def game(update, context):
    chat_id = update.effective_chat.id

    if chat_id in games and games[chat_id]["active"]:
        update.message.reply_text("⚠️ Bu grupta zaten aktif oyun var.")
        return

    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı (Bakımda)", callback_data="text_maintenance")]
    ]

    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

# ------------------ MOD SEÇ ------------------

def mode_select(update, context):
    query = update.callback_query
    query.answer()

    if query.data == "text_maintenance":
        query.answer("⌨️ Yazılı mod bakımda!", show_alert=True)
        return

    chat_id = query.message.chat.id
    word, hint = pick_word()

    games[chat_id] = {
        "active": True,
        "narrator": query.from_user.id,
        "word": word,
        "hint": hint,
        "scores": {},
        "last_activity": time.time()
    }

    send_game_panel(context, chat_id)

# ------------------ OYUN PANEL ------------------

def send_game_panel(context, chat_id):
    game = games[chat_id]

    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [
            InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next"),
            InlineKeyboardButton("✍️ Kelime Yaz", url=f"tg://user?id={context.bot.id}")
        ]
    ]

    narrator_name = context.bot.get_chat_member(chat_id, game["narrator"]).user.first_name

    context.bot.send_message(
        chat_id,
        f"🎮 Oyun Başladı!\n\nAnlatıcı: {narrator_name}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ------------------ BUTON ------------------

def button(update, context):
    query = update.callback_query
    if not query:
        return

    chat_id = query.message.chat.id

    if chat_id not in games:
        query.answer("Aktif oyun yok.", show_alert=True)
        return

    game = games[chat_id]

    if not game["active"]:
        query.answer("Oyun aktif değil.", show_alert=True)
        return

    if query.from_user.id != game["narrator"]:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    game["last_activity"] = time.time()

    if query.data == "look":
        query.answer(
            f"🎯 Kelime: {game['word']}\n\n✨\n\n📌 Tanım: {game['hint']}",
            show_alert=True
        )

    elif query.data == "next":
        word, hint = pick_word()
        game["word"] = word
        game["hint"] = hint

        query.answer(
            f"🎯 Yeni Kelime: {word}\n\n✨\n\n📌 Tanım: {hint}",
            show_alert=True
        )

# ------------------ TAHMİN ------------------

def guess(update, context):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        return

    game = games[chat_id]

    if not game["active"]:
        return

    text = update.message.text.strip().lower()

    # Anlatıcı özelden kelime yazarsa
    if update.message.chat.type == "private" and update.message.from_user.id == game["narrator"]:
        game["word"] = text
        game["hint"] = "Kullanıcı tarafından girildi"
        context.bot.send_message(game["narrator"], f"Yeni kelime ayarlandı: {text}")
        return

    if text == game["word"].lower():
        user = update.message.from_user
        name = user.first_name

        game["scores"][name] = game["scores"].get(name, 0) + 1
        update.message.reply_text(f"🎉 {name} doğru bildi!")

        # Yeni kelime sadece anlatıcıya
        word, hint = pick_word()
        game["word"] = word
        game["hint"] = hint

        context.bot.send_message(
            game["narrator"],
            f"🎯 Yeni Kelime: {word}\n\n✨\n\n📌 Tanım: {hint}"
        )

# ------------------ STOP ------------------

def stop(update, context):
    chat_id = update.effective_chat.id

    if chat_id not in games:
        update.message.reply_text("Aktif oyun yok.")
        return

    admins = context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]

    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return

    end_game(context, chat_id)

# ------------------ OYUN BİTİŞ ------------------

def end_game(context, chat_id):
    game = games.get(chat_id)
    if not game:
        return

    game["active"] = False

    ranking = "🏆 Lider Tablosu\n\n"

    narrator_name = context.bot.get_chat_member(chat_id, game["narrator"]).user.first_name
    ranking += f"Anlatıcı: {narrator_name}\n\nKazananlar:\n"

    sorted_scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)

    for i, (name, score) in enumerate(sorted_scores, 1):
        ranking += f"{i}. {name}: {score} puan\n"

        # GLOBAL SKOR KAYDI
        scores_col.update_one(
            {"name": name},
            {"$inc": {"score": score}},
            upsert=True
        )

    context.bot.send_message(chat_id, ranking)

    del games[chat_id]

# ------------------ GLOBAL LİDER ------------------

def eniyiler(update, context):
    top = scores_col.find().sort("score", -1).limit(10)

    text = "🌍 Global En İyiler\n\n"
    for i, user in enumerate(top, 1):
        text += f"{i}. {user['name']} - {user['score']} puan\n"

    update.message.reply_text(text)

# ------------------ TIMER ------------------

def timer_check(context):
    now = time.time()

    for chat_id in list(games.keys()):
        game = games.get(chat_id)

        if game and game["active"]:
            if now - game["last_activity"] > 300:
                context.bot.send_message(chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
                end_game(context, chat_id)

# ------------------ MAIN ------------------

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))

    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text_maintenance"))
    dp.add_handler(CallbackQueryHandler(button))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
