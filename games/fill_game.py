import random
from telegram import Update
from telegram.ext import ContextTypes

# 1000 kelimelik örnek liste (gerekirse daha da genişlet)
words = [
"araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
"ev","köpek","kedi","oyuncak","muz","elma","armut","çilek","kiraz","muzik",
"resim","kalemlik","defter","sandalye","kapı","pencere","halı","lamba","televizyon","radyo",
# ... 1000 kelimeyi buraya ekle
]

games = {}  # chat_id: {"word":..., "masked":..., "letter_pool":..., "scores":{}, "active":True}

def normalize(text: str) -> str:
    mapping = str.maketrans("İIı", "iii")
    return text.translate(mapping).lower()

def mask_word(word):
    """
    İlk ve son harf açık, ortadaki 1-3 harf rastgele açık.
    Geri kalan '_' ile maskelenir.
    """
    word = word.upper()
    if len(word) <= 2:
        return word[0] + "_"*(len(word)-1)

    word_chars = list(word)
    indices = list(range(1, len(word)-1))
    random.shuffle(indices)
    num_to_reveal = min(3, len(indices))
    to_reveal = indices[:num_to_reveal]

    masked = ""
    for i, c in enumerate(word_chars):
        if i == 0 or i == len(word)-1 or i in to_reveal:
            masked += c
        else:
            masked += "_"
    return masked

def get_letter_pool(word):
    letters = list(word.upper())
    random.shuffle(letters)
    return " ".join(letters)

async def start_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id if not hasattr(update, "callback_query") else update.callback_query.message.chat_id
    msg_func = update.message.reply_text if not hasattr(update, "callback_query") else update.callback_query.edit_message_text

    if chat_id in games and games[chat_id]["active"]:
        await msg_func("⚠️ Oyun zaten devam ediyor!")
        return

    word = random.choice(words).upper()
    masked = mask_word(word)
    letter_pool = get_letter_pool(word)

    games[chat_id] = {
        "word": word,
        "masked": masked,
        "letter_pool": letter_pool,
        "scores": {},
        "active": True
    }

    await msg_func(f"🎯 Boşluk Doldurma oyunu başladı!\nKelimede {len(word)} harf var.\n{masked}\n\nHarfler: {letter_pool}")

async def guess_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name

    if normalize(text) == normalize(game["word"]):
        game["scores"].setdefault(user_id, {"name": user_name, "score": 0})
        game["scores"][user_id]["score"] += 1

        await update.message.reply_text(f"🎉 {user_name} doğru tahmin etti!\nKelime: {game['word']}\nYeni kelime geliyor...")

        new_word = random.choice(words).upper()
        game["word"] = new_word
        game["masked"] = mask_word(new_word)
        game["letter_pool"] = get_letter_pool(new_word)

        await update.message.reply_text(f"Kelimede {len(new_word)} harf var.\n{game['masked']}\n\nHarfler: {game['letter_pool']}")
    else:
        await update.message.reply_text(f"❌ Yanlış! Tekrar deneyin:\n{game['masked']}")

async def finish_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in games or not games[chat_id]["active"]:
        await update.message.reply_text("⚠️ Bu chat'te aktif bir oyun yok!")
        return

    game = games[chat_id]
    game["active"] = False

    if not game["scores"]:
        await update.message.reply_text("Oyun bitti, kimse puan alamadı.")
        return

    leaderboard = sorted(game["scores"].values(), key=lambda x: x["score"], reverse=True)
    msg = "🏆 Lider Tablosu:\n\n"
    for i, player in enumerate(leaderboard, start=1):
        msg += f"{i}. {player['name']} - {player['score']} puan\n"

    await update.message.reply_text(msg)
    del games[chat_id]
