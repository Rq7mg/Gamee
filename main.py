from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = "6458048644:AAFdWpIucKMVVduansy2IWaFg_in5LRfW2w"

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
]

    await update.message.reply_text(
        "🎮 Oyun Menüsü",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"Seçtin: {query.data}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))

app.run_polling()
