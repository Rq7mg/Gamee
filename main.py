from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Bot token
TOKEN = "TOKEN_BURAYA"

# Başlangıç menüsü
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Kelime Anlatma", callback_data="kelime")],
        [InlineKeyboardButton("📝 Boşluk Doldurma", callback_data="bosluk")],
        [
            InlineKeyboardButton("🔤 Kelime Sarmalı", callback_data="sarmal"),
            InlineKeyboardButton("➗ Hızlı Matematik", callback_data="math"),
        ],
        [
            InlineKeyboardButton("🎲 Sayı Tahmin", callback_data="sayi"),
            InlineKeyboardButton("🔎 Fark Bulmaca", callback_data="fark"),
        ],
        [
            InlineKeyboardButton("🧠 Bilgi Oyunu", callback_data="bilgi"),
            InlineKeyboardButton("🏳️ Bayrak Oyunu", callback_data="bayrak"),
        ],
        [
            InlineKeyboardButton("🔗 Kelime Zinciri", callback_data="zincir"),
            InlineKeyboardButton("🏛 Başkent Tahmin", callback_data="baskent"),
        ],
        [
            InlineKeyboardButton("🚗 Plaka Oyunu", callback_data="plaka"),
            InlineKeyboardButton("⭕ XOX", callback_data="xox"),
        ],
        [
            InlineKeyboardButton("🎲 Doğruluk / Cesaret", callback_data="dogruluk"),
            InlineKeyboardButton("⚡ Hafıza Şimşeği", callback_data="hafiza"),
        ],
        [
            InlineKeyboardButton("🌡 Sıcak Soğuk", callback_data="sicak"),
            InlineKeyboardButton("📚 Eser-Yazar", callback_data="eser"),
        ],
    ]

    await update.message.reply_text(
        "🎮 Oyun Menüsü",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# Butonlara tıklayınca çalışacak handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Placeholder mesajlar
    responses = {
        "kelime": "🎯 Kelime Anlatma oyunu yakında!",
        "bosluk": "📝 Boşluk Doldurma yakında!",
        "sarmal": "🔤 Kelime Sarmalı oyunu yakında!",
        "math": "➗ Hızlı Matematik oyunu yakında!",
        "sayi": "🎲 1-100 arası Sayı Tahmin oyunu!",
        "fark": "🔎 Fark Bulmaca oyunu yakında!",
        "bilgi": "🧠 Bilgi Oyunu yakında!",
        "bayrak": "🏳️ Bayrak Tahmin oyunu yakında!",
        "zincir": "🔗 Kelime Zinciri oyunu yakında!",
        "baskent": "🏛 Başkent Tahmin oyunu yakında!",
        "plaka": "🚗 Plaka Oyunu yakında!",
        "xox": "⭕ XOX oyunu yakında!",
        "dogruluk": "🎲 Doğruluk / Cesaret oyunu yakında!",
        "hafiza": "⚡ Hafıza Şimşeği oyunu yakında!",
        "sicak": "🌡 Sıcak Soğuk oyunu yakında!",
        "eser": "📚 Eser-Yazar oyunu yakında!",
    }

    msg = responses.get(query.data, "❌ Bu oyun bulunamadı.")
    await query.edit_message_text(msg)

# Uygulama oluştur
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

# Botu çalıştır
app.run_polling()
