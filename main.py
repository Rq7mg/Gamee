from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# mevcut oyunlar
from games import number_game
from games import plate_game
from games import xox_game
from games import truth_game

# yeni oyun
from games import fill_game


TOKEN = "YOUR_BOT_TOKEN"


app = ApplicationBuilder().token(TOKEN).build()

# --------------------
# SAYI TAHMİN OYUNU
# --------------------
app.add_handler(CommandHandler("sayi", number_game.start_number))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), number_game.guess_number))

# --------------------
# PLAKA OYUNU
# --------------------
app.add_handler(CommandHandler("plaka", plate_game.start_plate))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), plate_game.guess_plate))

# --------------------
# XOX OYUNU
# --------------------
app.add_handler(CommandHandler("xox", xox_game.start_xox))
app.add_handler(CallbackQueryHandler(xox_game.button))

# --------------------
# DOĞRULUK CESARET
# --------------------
app.add_handler(CommandHandler("dc", truth_game.start_dc))

# --------------------
# BOŞLUK DOLDURMA
# --------------------
app.add_handler(CommandHandler("fill", fill_game.start_fill))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), fill_game.guess_fill))

# --------------------

print("Bot çalışıyor...")
app.run_polling()
