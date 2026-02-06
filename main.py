from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from games.fill_game import fill_game, guess_fill

TOKEN = "YOUR_BOT_TOKEN_HERE"  # Buraya bot tokenini koy

app = ApplicationBuilder().token(TOKEN).build()

# /start komutu
def start(update, context):
    update.message.reply_text("🎯 Boşluk Doldurma oyununa hoş geldiniz!")
    fill_game.start_round()

# /bitir komutu
def end(update, context):
    fill_game.end_game()
    update.message.reply_text("Oyun bitirildi. Lider tablosu konsola yazdırıldı!")

# Kullanıcı tahminleri
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), guess_fill))

# Komutlar
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bitir", end))

# Bot çalıştır
if __name__ == "__main__":
    print("Bot başlatıldı...")
    app.run_polling()
