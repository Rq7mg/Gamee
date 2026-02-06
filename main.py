import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# Oyun modülleri
from games import number_game, plate_game, xox_game, truth_game, fill_game

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN missing in Config Vars!")
    exit(1)

# Başlangıç menüsü
async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("🎯 Boşluk Doldurma", callback_data="fill")],
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
    for game in [number_game.user_games, plate_game.user_games, fill_game.games]:
        if game.get(update.message.chat_id):
            del game[update.message.chat_id]
            removed += 1
    await update.message.reply_text(f"✅ Oyun(lar) sona erdirildi. {removed} oyun kapatıldı.")

# Bot uygulaması
app = ApplicationBuilder().token(TOKEN).build()

# Komutlar
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bitir", finish))

# CallbackQueryHandler
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id

    if query.data == "fill":
        await fill_game.start_fill(update, context)
    elif query.data == "sayi":
        await number_game.number_button(update, context)
    elif query.data == "plaka":
        await plate_game.plate_button(update, context)
    elif query.data == "xox":
        await xox_game.xox_button(update, context)
    elif query.data == "dogruluk":
        await truth_game.truth_button(update, context)

app.add_handler(CallbackQueryHandler(button_handler))

# Mesaj handlerları
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), fill_game.guess_fill))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), number_game.number_guess))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), plate_game.plate_guess))

# Çalıştır
app.run_polling()
