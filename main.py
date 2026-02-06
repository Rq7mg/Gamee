from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from games.fill_game import fill_game, guess_fill
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = "YOUR_BOT_TOKEN_HERE"  # Buraya bot tokenini koy

app = ApplicationBuilder().token(TOKEN).build()

# Başlat komutu
def start(update, context):
    keyboard = [
        [InlineKeyboardButton("10 Round", callback_data='10'),
         InlineKeyboardButton("15 Round", callback_data='15')],
        [InlineKeyboardButton("20 Round", callback_data='20')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("🎯 Boşluk Doldurma oyununa hoş geldiniz! Round sayısını seçin:", reply_markup=reply_markup)

# Round seçimi callback
def button(update, context):
    query = update.callback_query
    rounds = int(query.data)
    fill_game.rounds = rounds
    query.answer()
    query.edit_message_text(text=f"Oyun başladı! Toplam {rounds} round oynanacak.")
    fill_game.start_round()

# Kullanıcı tahminleri
def handle_guess(update, context):
    guess_fill(update, context)

# /bitir komutu
def end(update, context):
    fill_game.end_game()
    update.message.reply_text("Oyun bitirildi. Lider tablosu konsola yazdırıldı!")

# Handler ekleme
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bitir", end))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_guess))
app.add_handler(MessageHandler(filters.StatusUpdate, lambda u, c: None))  # Gereksiz güncellemeleri yoksay

# Callback handler
app.add_handler(MessageHandler(filters.CallbackQuery, button))

# Bot çalıştır
if __name__ == "__main__":
    print("Bot başlatıldı...")
    app.run_polling()
