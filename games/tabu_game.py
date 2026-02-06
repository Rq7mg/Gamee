import random
from telegram import Update
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Kelime listesi
words = [
    "elma", "araba", "bilgisayar", "telefon", "kitap",
    "kalem", "masa", "çanta", "okul", "şehir", "güneş"
]

# {chat_id: {"word": kelime, "anlatıcı_id": user_id, "attempts": 0, "active": True}}
games = {}

async def tabu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    username = update.effective_user.first_name  # Chat’te gösterilecek isim

    if chat_id in games and games[chat_id]["active"]:
        await query.edit_message_text("⚠️ Oyun zaten devam ediyor!")
        return

    word = random.choice(words)
    games[chat_id] = {
        "word": word,
        "anlatıcı_id": user_id,
        "attempts": 0,
        "active": True
    }

    # Anlatıcıya özel mesaj (kelimeyi göster)
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎯 Sen anlatıcısın! Kelimen: **{word}**. Chat içinde kelimeyi açıklamaya başla."
        )
    except:
        await query.edit_message_text("❌ Anlatıcıya mesaj gönderilemedi. DM açık mı?")
        games[chat_id]["active"] = False
        return

    # Chat mesajı (anlatıcı adı gösteriliyor)
    await query.edit_message_text(
        f"🎯 Tabu / Kelime Anlatma başladı!\n"
        f"Anlatıcı: {username}\n"
        f"Tahminler chat'te yazılsın."
    )

async def tabu_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    text = update.message.text.strip().lower()

    # Oyun yoksa veya bitmişse
    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]

    # Anlatıcı tahmin edemez
    if user_id == game["anlatıcı_id"]:
        return

    game["attempts"] += 1
    word = game["word"].lower()

    # Doğru tahmin
    if text == word:
        await update.message.reply_text(
            f"🎉 Tebrikler {update.message.from_user.first_name}! "
            f"Doğru kelime: **{game['word']}** ({game['attempts']} tahmin denendi)."
        )
        game["active"] = False
        return

    # Yanlış tahminlerde artık tepki yok
