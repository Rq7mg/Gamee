import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from games import number_game, plate_game, xox_game, truth_game, fill_game

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ TOKEN missing in Config Vars!")
    exit(1)

async def start(update, context):
    keyboard = [
        [InlineKeyboardButton("🎯 Boşluk Doldurma", callback_data="fill")],
        [InlineKeyboardButton("🎲 Sayı Tahmin", callback_data="sayi")],
        [InlineKeyboardButton("🚗 Plaka Oyunu", callback_data="plaka")],
        [InlineKeyboardButton("⭕ XOX", callback_data="xox")],
        [InlineKeyboardButton("🎲 Doğruluk / Cesaret", callback_data="dogruluk")],
    ]
    await update.message.reply_text("🎮 Oyun Menüsü", reply_markup=InlineKeyboardMarkup(keyboard))

async def finish(update, context):
    chat_id = update.message.chat_id
    await fill_game.finish_game(update, context)
    for game in [number_game.user_games, plate_game.user_games]:
        if chat_id in game:
            del game[chat_id]

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

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

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bitir", finish))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), fill_game.guess_fill))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), number_game.number_guess))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), plate_game.plate_guess))
app.run_polling()
