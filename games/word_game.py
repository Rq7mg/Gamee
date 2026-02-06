import random
from telegram import Update
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes

words = ["elma","araba","bilgisayar","telefon","kitap","kalem","masa","çanta","okul","şehir","güneş"]
user_games = {}

async def word_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data != "kelime":
        return
    user_id = query.from_user.id
    word = random.choice(words)
    user_games[user_id] = {"word": word, "attempts": 0}
    await query.edit_message_text(f"🎯 Kelime Anlatma! Kelime {len(word)} harfli. İlk harfi: {word[0]}")

async def word_guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_games:
        return
    text = update.message.text.lower()
    data = user_games[user_id]
    data["attempts"] += 1
    target = data["word"]
    if text == target.lower():
        await update.message.reply_text(f"🎉 Tebrikler! {target} {data['attempts']} tahmin ile bulundu.")
        del user_games[user_id]
    else:
        hint = ""
        if data["attempts"] % 2 == 0:
            hint = f"İpucu: Kelimenin son harfi '{target[-1]}'"
        await update.message.reply_text(f"❌ Yanlış tahmin! {hint}")

word_guess = MessageHandler(filters.TEXT, word_guess_handler)
