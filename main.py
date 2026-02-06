import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from games import number_game, word_game, plate_game, xox_game, truth_game

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
    await update.message.reply_text(
        "🎮 Oyun Menüsü", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# /bitir komutu
async def finish(update, context):
    user_id = update.message.from_user.id
    removed = 0
    for game in [
        number_game.user_games,
        word_game.user_games,
        plate_game.user_games,
    ]:
        if user_id in game:
            del game[user_id]
            removed += 1
    await update.message.reply_text(f"✅ Oyun(lar) sona erdirildi. {removed} oyun kapatıldı.")

app = ApplicationBuilder().token(TOKEN).build()

# Komutlar
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bitir", finish))

# CallbackQueryHandler pattern filtreli
app.add_handler(CallbackQueryHandler(number_game.number_button, pattern="^sayi$"))
app.add_handler(CallbackQueryHandler(word_game.word_button, pattern="^kelime$"))
app.add_handler(CallbackQueryHandler(plate_game.plate_button, pattern="^plaka$"))
app.add_handler(CallbackQueryHandler(xox_game.xox_button, pattern="^xox$"))
app.add_handler(CallbackQueryHandler(truth_game.truth_button, pattern="^dogruluk$"))

# Mesajlar
app.add_handler(number_game.number_guess)
app.add_handler(word_game.word_guess)
app.add_handler(plate_game.plate_guess)

# Çalıştır
app.run_polling()
