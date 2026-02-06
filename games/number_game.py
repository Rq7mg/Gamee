import random
from telegram import Update
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes

user_games = {}

async def number_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data != "sayi":
        return
    user_id = query.from_user.id
    user_games[user_id] = random.randint(1, 100)
    await query.edit_message_text("🎲 1-100 arası bir sayı tuttum! Tahminini yaz.")

async def number_guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_games:
        return
    text = update.message.text
    if not text.isdigit():
        await update.message.reply_text("Lütfen bir sayı gir!")
        return
    guess = int(text)
    target = user_games[user_id]
    if guess < target:
        await update.message.reply_text("⬆ Daha yüksek!")
    elif guess > target:
        await update.message.reply_text("⬇ Daha düşük!")
    else:
        await update.message.reply_text(f"🎉 Doğru sayı {target} idi!")
        del user_games[user_id]

number_guess = MessageHandler(filters.TEXT, number_guess_handler)
