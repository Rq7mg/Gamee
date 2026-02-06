import random
from telegram import Update
from telegram.ext import ContextTypes

# 1000 Türkçe kelime listesi (örnek)
words = [
    "araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
    "ev","köpek","kedi","oyuncak","muz","elma","armut","çilek","kiraz","muzik",
    "resim","kalemlik","defter","sandalye","kapı","pencere","halı","lamba","televizyon","radyo",
    "bisiklet","uçak","tren","gemi","otomobil","motorsiklet","otobüs","minibüs","kamyon","deniz",
    "göl","nehir","şelale","dağ","ova","orman","bahçe","park","meydan",
    # ... toplam 1000 kelime olacak şekilde doldurulacak
]

games = {}  # {chat_id: {"word": w, "masked": m, "attempts":0, "active":True}}

def mask_word(word):
    """İlk harfi açık, geri kalan harfler gizli"""
    if len(word) <= 1:
        return "*"  # Tek harfli kelimeyse tamamen gizle
    return word[0] + "*" * (len(word)-1)

def normalize(text: str) -> str:
    """Büyük/küçük harf ve I/İ farkını yok say"""
    mapping = str.maketrans("İIı", "iii")
    return text.translate(mapping).lower()

async def start_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # CallbackQuery ile çağrıldığında query.message üzerinden chat_id al
    if hasattr(update, "callback_query") and update.callback_query:
        chat_id = update.callback_query.message.chat_id
        msg_func = update.callback_query.edit_message_text
    else:
        chat_id = update.message.chat_id
        msg_func = update.message.reply_text

    if chat_id in games and games[chat_id]["active"]:
        await msg_func("⚠️ Oyun zaten devam ediyor!")
        return

    word = random.choice(words)
    masked = mask_word(word)
    games[chat_id] = {"word": word, "masked": masked, "attempts": 0, "active": True}

    await msg_func(
        f"🎯 Boşluk Doldurma oyunu başladı!\n"
        f"Kelimede {len(word)} harf var.\n"
        f"{masked}"
    )

async def guess_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]
    game["attempts"] += 1

    if normalize(text) == normalize(game["word"]):
        await update.message.reply_text(
            f"🎉 {update.message.from_user.first_name} doğru tahmin etti! "
            f"Kelime: {game['word']}"
        )
        # Oyun bitmez, herkes tahmin edebilir
    else:
        await update.message.reply_text(f"❌ Yanlış! Tekrar deneyin:\n{game['masked']}")
