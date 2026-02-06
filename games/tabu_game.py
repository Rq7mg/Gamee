import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes

words = [
    "elma", "araba", "bilgisayar", "telefon", "kitap",
    "kalem", "masa", "çanta", "okul", "şehir", "güneş"
]

games = {}  # {chat_id: {"word": w, "anlatıcı_id": uid, "attempts":0, "active":True}}

def get_new_word():
    return random.choice(words)

def normalize(text: str) -> str:
    mapping = str.maketrans("İIı", "iii")
    return text.translate(mapping).lower()

async def tabu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    username = update.effective_user.first_name

    if chat_id in games and games[chat_id]["active"]:
        await query.edit_message_text("⚠️ Oyun zaten devam ediyor!")
        return

    word = get_new_word()
    games[chat_id] = {
        "word": word,
        "anlatıcı_id": user_id,
        "attempts": 0,
        "active": True
    }

    keyboard = [
        [InlineKeyboardButton("Kelimeyi Geç", callback_data="skip_word"),
         InlineKeyboardButton("Kelime Yaz", callback_data="set_word")]
    ]

    await query.edit_message_text(
        f"🎯 Tabu / Kelime Anlatma başladı!\n"
        f"Anlatıcı: {username}\n"
        f"Kelime: ||{word}|| 👀\n"
        f"Tahminler chat’te yazılsın.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="MarkdownV2"
    )

async def tabu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]

    if user_id != game["anlatıcı_id"]:
        await query.answer("⚠️ Sadece anlatıcı bunu kullanabilir!", show_alert=True)
        return

    if query.data == "skip_word":
        new_word = get_new_word()
        game["word"] = new_word
        game["attempts"] = 0
        await query.edit_message_text(
            f"🔄 Kelime değiştirildi! Anlatıcı: {update.effective_user.first_name}\n"
            f"Kelime: ||{new_word}|| 👀\nTahminler chat’te yazılsın.",
            reply_markup=query.message.reply_markup,
            parse_mode="MarkdownV2"
        )

    elif query.data == "set_word":
        await query.edit_message_text(
            "✏️ Yeni kelimeyi yazın, bot bunu kaydedecek."
        )
        context.user_data["awaiting_word"] = True

async def tabu_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]

    if context.user_data.get("awaiting_word") and user_id == game["anlatıcı_id"]:
        game["word"] = text
        game["attempts"] = 0
        context.user_data["awaiting_word"] = False
        await update.message.reply_text(
            f"✅ Yeni kelime set edildi! Anlatıcı: {update.effective_user.first_name}\n"
            f"Kelime: ||{text}|| 👀\nTahminler chat’te yazılsın.",
            parse_mode="MarkdownV2"
        )
        return

    if user_id == game["anlatıcı_id"]:
        return

    game["attempts"] += 1

    if normalize(text) == normalize(game["word"]):
        await update.message.reply_text(
            f"🎉 Tebrikler {update.message.from_user.first_name}! "
            f"Doğru kelime: ||{game['word']}|| "
            f"({game['attempts']} tahmin).",
            parse_mode="MarkdownV2"
        )
        game["active"] = False
