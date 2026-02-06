import os
import random
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# TOKEN
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("❌ ERROR: TOKEN not found in Config Vars. Add it in Heroku settings.")
    exit(1)

# Kullanıcı oyun durumları
user_number_game = {}
user_word_game = {}
user_xox_game = {}
user_truth_game = {}

# Basit kelime listesi
words = ["elma", "araba", "bilgisayar", "telefon", "kitap"]

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
    await update.message.reply_text("🎮 Oyun Menüsü", reply_markup=InlineKeyboardMarkup(keyboard))

# Buton handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Sayı Tahmin oyunu
    if query.data == "sayi":
        user_number_game[user_id] = random.randint(1, 100)
        await query.edit_message_text("🎲 1-100 arası bir sayı tuttum! Tahminini yaz ve bakalım doğru mu!")
    
    # Kelime Anlatma oyunu
    elif query.data == "kelime":
        user_word_game[user_id] = random.choice(words)
        await query.edit_message_text("🎯 Kelime Anlatma! Tahmin et: Hangi kelimeyi seçtim?")
    
    # XOX Basit placeholder
    elif query.data == "xox":
        user_xox_game[user_id] = [[" "]*3 for _ in range(3)]
        await query.edit_message_text("⭕ XOX oyunu başladı! (Placeholder, tüm hamleler kaydedilmiyor)")
    
    # Doğruluk / Cesaret
    elif query.data == "dogruluk":
        choices = ["Doğruluk: En son kime yalan söyledin?", "Cesaret: 10 şınav çek!"]
        await query.edit_message_text(random.choice(choices))
    
    # Diğer oyunlar placeholder
    else:
        await query.edit_message_text(f"{query.data} oyunu yakında!")

# Mesaj handler
async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.lower()

    # Sayı Tahmin
    if user_id in user_number_game:
        if not text.isdigit():
            await update.message.reply_text("Lütfen bir sayı gir!")
            return
        guess = int(text)
        target = user_number_game[user_id]
        if guess < target:
            await update.message.reply_text("⬆ Daha yüksek!")
        elif guess > target:
            await update.message.reply_text("⬇ Daha düşük!")
        else:
            await update.message.reply_text(f"🎉 Tebrikler! Doğru sayı {target} idi.")
            del user_number_game[user_id]
        return

    # Kelime Anlatma
    if user_id in user_word_game:
        target = user_word_game[user_id]
        if text == target:
            await update.message.reply_text(f"🎉 Tebrikler! Doğru kelime {target} idi.")
            del user_word_game[user_id]
        else:
            await update.message.reply_text("❌ Yanlış tahmin, tekrar dene!")
        return

# Botu oluştur
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT, guess_handler))

# Çalıştır
app.run_polling()
