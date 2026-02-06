import random
import unicodedata
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Kelime listesi
words = [
    "elma", "araba", "bilgisayar", "telefon", "kitap",
    "kalem", "masa", "çanta", "okul", "şehir", "güneş"
]

games = {}  # {chat_id: {"word": kelime, "anlatıcı_id": user_id, "attempts": 0, "active": True}}

def normalize(text: str) -> str:
    # Türkçe karakterleri normalize eder ve küçük harfe çevirir
    mapping = str.maketrans("İIı", "iii")
    return text.translate(mapping).lower()

def get_new_word():
    return random.choice(words)

# Tabu oyunu başlat
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
        f"🎯 Tabu / Kelime Anlatma başladı!\nAnlatıcı: {username}\nTahminler chat'te yazılsın.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Butonlar
async def tabu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id

    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]
    if user_id != game["anlatıcı_id"]:
        await query.answer("⚠️ Sadece anlatıcı bunu kullanabilir.", show_alert=True)
        return

    if query.data == "skip_word":
        new_word = get_new_word()
        game["word"] = new_word
        game["attempts"] = 0
        await query.edit_message_text(
            f"🔄 Kelime değiştirildi! Anlatıcı: {update.effective_user.first_name}\nTahminler chat'te yazılsın.",
            reply_markup=query.message.reply_markup
        )

    elif query.data == "set_word":
        await query.edit_message_text(
            f"✏️ Lütfen yeni kelimeyi yazın, bot bu kelimeyi kaydedecek."
        )
        context.user_data["awaiting_word"] = True

# Tahminler ve kelime set etme
async def tabu_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]

    # Anlatıcı kelime yazacaksa
    if context.user_data.get("awaiting_word") and user_id == game["anlatıcı_id"]:
        game["word"] = text
        game["attempts"] = 0
        context.user_data["awaiting_word"] = False
        await update.message.reply_text(
            f"✅ Yeni kelime set edildi! Anlatıcı: {update.effective_user.first_name}\nTahminler chat'te yazılsın."
        )
        return

    # Anlatıcı tahmin edemez
    if user_id == game["anlatıcı_id"]:
        return

    game["attempts"] += 1

    # Doğru tahmin (normalize edilmiş)
    if normalize(text) == normalize(game["word"]):
        await update.message.reply_text(
            f"🎉 Tebrikler {update.message.from_user.first_name}! "
            f"Doğru kelime: **{game['word']}** ({game['attempts']} tahmin denendi)."
        )
        game["active"] = False
