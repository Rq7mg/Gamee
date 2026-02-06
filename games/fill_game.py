import random
from telegram import Update
from telegram.ext import ContextTypes

# Örnek kelimeler
words = [
    "araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
    # ... toplam 1000 kelime eklenebilir
]

games = {}  # {chat_id: {"word": w, "masked": m, "letter_pool":..., "attempts":0, "active":True, "scores":{user_id: puan}}}

def normalize(text: str) -> str:
    mapping = str.maketrans("İIı", "iii")
    return text.translate(mapping).lower()

def mask_word(word):
    if len(word) <= 2:
        return word[0] + "_"*(len(word)-1)
    
    word_chars = list(word.upper())
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
    letter_pool = get_letter_pool(word)

    games[chat_id] = {
        "word": word,
        "masked": masked,
        "letter_pool": letter_pool,
        "attempts": 0,
        "active": True,
        "scores": {}
    }

    await msg_func(
        f"🎯 Boşluk Doldurma oyunu başladı!\n"
        f"Kelimede {len(word)} harf var.\n{masked}\n\nHarfler: {letter_pool}"
    )

async def guess_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]
    game["attempts"] += 1

    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name

    if normalize(text) == normalize(game["word"]):
        # Puanı ekle
        if user_id not in game["scores"]:
            game["scores"][user_id] = {"name": user_name, "score": 0}
        game["scores"][user_id]["score"] += 1

        await update.message.reply_text(
            f"🎉 {user_name} doğru tahmin etti! "
            f"Kelime: {game['word']}\nYeni kelime geliyor..."
        )

        # Yeni kelime
        new_word = random.choice(words)
        game["word"] = new_word
        game["masked"] = mask_word(new_word)
        game["letter_pool"] = get_letter_pool(new_word)
        game["attempts"] = 0

        await update.message.reply_text(
            f"Kelimede {len(new_word)} harf var.\n{game['masked']}\n\nHarfler: {game['letter_pool']}"
        )
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

    # Lider tablosu oluştur
    leaderboard = sorted(game["scores"].values(), key=lambda x: x["score"], reverse=True)
    msg = "🏆 Lider Tablosu:\n\n"
    for i, player in enumerate(leaderboard, start=1):
        msg += f"{i}. {player['name']} - {player['score']} puan\n"
    
    await update.message.reply_text(msg)

    # Oyunu temizle
    del games[chat_id]
