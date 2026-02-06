import os
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

# Bot token Heroku Config Vars'dan
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ ERROR: TOKEN not found in Config Vars. Add it in Heroku settings.")
    exit(1)

# Kullanıcı ID -> tutulan sayı
user_games = {}

# Başlangıç menüsü
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
        [
            InlineKeyboardButton("🎲 Doğruluk / Cesaret", callback_data="dogruluk"),
            InlineKeyboardButton("⚡ Hafıza Şimşeği", callback_data="hafiza"),
        ],
        [
            InlineKeyboardButton("🌡 Sıcak Soğuk", callback_data="sicak"),
            InlineKeyboardButton("📚 Eser-Yazar", callback_data="eser"),
        ],
    ]

    await update.message.reply_text(
        "🎮 Oyun Menüsü",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# Butonlara tıklayınca çalışacak handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if query.data == "sayi":
        # Rastgele sayı tut
        user_games[user_id] = random.randint(1, 100)
        await query.edit_message_text(
            "🎲 1-100 arası bir sayı tuttum! Tahminini yaz ve bakalım doğru mu?"
        )
    else:
        await query.edit_message_text(f"Bu oyun henüz hazır değil: {query.data}")

# Kullanıcının tahminlerini alacak handler
async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Kullanıcı Sayı Tahmin oyununda mı?
    if user_id not in user_games:
        return

    text = update.message.text

    # Sadece sayıysa işle
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
        await update.message.reply_text(f"🎉 Tebrikler! Doğru sayı {target} idi.")
        del user_games[user_id]  # Oyun bitti

# Botu oluştur
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, guess_handler))

# Botu çalıştır
app.run_polling()
