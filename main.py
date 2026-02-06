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
        [InlineKeyboardButton("Kelime Anlatma", callback_data="kelime")],
        [InlineKeyboardButton("Boşluk Doldurma", callback_data="bosluk")],
        [InlineKeyboardButton("Sayı Tahmin", callback_data="sayi")],
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
