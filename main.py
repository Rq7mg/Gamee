import os
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from games.number_game import number_button, number_guess
from games.word_game import word_button, word_guess
from games.plate_game import plate_button, plate_guess
from games.xox_game import xox_button
from games.truth_game import truth_button

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN missing in Config Vars!")
    exit(1)

# Başlangıç menüsü
async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("🎯 Kelime Anlatma", callback_data="kelime")],
        [InlineKeyboardButton("🎲 Sayı Tahmin", callback_data="sayi")],
        [InlineKeyboardButton("🚗 Plaka Oyunu", callback_data="plaka")],
        [InlineKeyboardButton("⭕ XOX", callback_data="xox")],
        [InlineKeyboardButton("🎲 Doğruluk / Cesaret", callback_data="dogruluk")],
    ]
    await update.message.reply_text("🎮 Oyun Menüsü", reply_markup=InlineKeyboardMarkup(keyboard))

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

# Button handlerlar
app.add_handler(CallbackQueryHandler(number_button))
app.add_handler(CallbackQueryHandler(word_button))
app.add_handler(CallbackQueryHandler(plate_button))
app.add_handler(CallbackQueryHandler(xox_button))
app.add_handler(CallbackQueryHandler(truth_button))

# Message handlerlar
app.add_handler(number_guess)
app.add_handler(word_guess)
app.add_handler(plate_guess)

# Çalıştır
app.run_polling()
