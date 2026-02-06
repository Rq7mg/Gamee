import random
from telegram import Update
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ContextTypes

plates = {"01":"Adana","06":"Ankara","34":"İstanbul","35":"İzmir","07":"Antalya"}
user_games = {}

async def plate_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data != "plaka":
        return
    user_id = query.from_user.id
    plate, city = random.choice(list(plates.items()))
    user_games[user_id] = {"plate": plate, "city": city, "attempts": 0}
    await query.edit_message_text(f"🚗 Plaka Tahmin! Plaka: {plate}. Şehir adı tahmin et.")

async def plate_guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_games:
        return
    text = update.message.text.lower()
    data = user_games[user_id]
    data["attempts"] += 1
    if text == data["city"].lower() or text == data["plate"]:
        await update.message.reply_text(f"🎉 Doğru! {data['plate']} - {data['city']} ({data['attempts']} tahmin)")
        del user_games[user_id]
    else:
        await update.message.reply_text("❌ Yanlış, tekrar dene!")

plate_guess = MessageHandler(filters.TEXT, plate_guess_handler)
