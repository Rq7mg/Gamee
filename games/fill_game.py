import random
from telegram import Update
from telegram.ext import ContextTypes

words = [
"araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir",
"güneş","kitap","siyah","beyaz","kırmızı","mavi","yeşil","strateji",
"defter","perde","yatak","radyo","kapı","bardak","tabak","dolap"
]

games = {}

def normalize(text: str) -> str:
    text = text.lower()
    replacements = {
        "ı": "i", "i̇": "i",
        "ç": "c", "ş": "s",
        "ö": "o", "ü": "u", "ğ": "g"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text

def mask_word(word):
    length = len(word)
    chars = list(word)
    masked = ["-"] * length

    masked[0] = chars[0]
    masked[-1] = chars[-1]

    reveal_count = 1 if length <= 6 else 2
    indices = list(range(1, length - 1))
    random.shuffle(indices)

    for i in indices[:reveal_count]:
        masked[i] = chars[i]

    return "".join(masked)

def get_letter_pool(word):
    letters = list(word)
    random.shuffle(letters)
    return " ".join(letters)

async def start_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id in games:
        await update.message.reply_text("Oyun zaten aktif.")
        return

    word = random.choice(words).upper().replace("I", "İ")

    games[chat_id] = {
        "word": word,
        "round": 1,
        "total": 15,
        "puan": 0
    }

    await update.message.reply_text(
        f"🎯 Boşluk Doldurma başladı!\n"
        f"Round: 1/15\n"
        f"📚 {len(word)} harf: {get_letter_pool(word)}\n"
        f"🎲 {mask_word(word)}"
    )

async def guess_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if chat_id not in games:
        return

    game = games[chat_id]

    if normalize(text) == normalize(game["word"]):
        game["puan"] += 1
        await update.message.reply_text(f"✅ Bildin! {game['word']}")

        game["round"] += 1

        if game["round"] > game["total"]:
            await update.message.reply_text("🏁 Oyun bitti!")
            del games[chat_id]
            return

        new_word = random.choice(words).upper().replace("I", "İ")
        game["word"] = new_word

        await update.message.reply_text(
            f"Round: {game['round']}/15\n"
            f"📚 {len(new_word)} harf: {get_letter_pool(new_word)}\n"
            f"🎲 {mask_word(new_word)}"
        )
