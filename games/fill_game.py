import random
from telegram import Update
from telegram.ext import ContextTypes

words = [
"araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
"ev","köpek","kedi","oyuncak","muz","elma","armut","çilek","kiraz","meyveli",
"strateji","defter","sandalye","pantolon","mont","ayakkabı","perde","battaniye",
"siyah","beyaz","kırmızı","mavi","yeşil","turuncu"
]

games = {}

def normalize(text: str) -> str:
    text = text.lower()
    replacements = {
        "i̇": "i",
        "ı": "i",
        "ç": "c",
        "ş": "s",
        "ö": "o",
        "ü": "u",
        "ğ": "g"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def mask_word(word):
    length = len(word)
    chars = list(word)
    masked = ["-"] * length

    # ilk ve son harf açık
    masked[0] = chars[0]
    masked[-1] = chars[-1]

    indices = list(range(1, length - 1))
    random.shuffle(indices)

    if length == 5:
        num_to_reveal = 1
    elif length == 6:
        num_to_reveal = random.choice([1, 2])
    elif length == 7:
        num_to_reveal = random.choice([2, 3])
    else:
        num_to_reveal = max(1, length // 3)

    for i in indices[:num_to_reveal]:
        masked[i] = chars[i]

    return "".join(masked)


def get_letter_pool(word):
    letters = list(word)
    random.shuffle(letters)
    return " ".join(letters)


async def start_fill(update: Update, context: ContextTypes.DEFAULT_TYPE, total_rounds=15):
    chat_id = update.message.chat_id

    if chat_id in games and games[chat_id]["active"]:
        await update.message.reply_text("⚠️ Oyun zaten devam ediyor!")
        return

    word = random.choice(words)
    word = word.upper().replace("I", "İ")

    games[chat_id] = {
        "word": word,
        "masked": mask_word(word),
        "letter_pool": get_letter_pool(word),
        "scores": {},
        "active": True,
        "round": 1,
        "total_rounds": total_rounds,
        "puan": 0
    }

    game = games[chat_id]

    await update.message.reply_text(
        f"🎯 Boşluk Doldurma oyunu başladı!\n"
        f"Puan: 0\n"
        f"Round: 1/{total_rounds}\n"
        f"📚 {len(word)} harf: {game['letter_pool']}\n"
        f"🎲 {game['masked']}"
    )


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
        game["puan"] += 0.6

        await update.message.reply_text(
            f"🎉 {user_name} doğru tahmin etti!\nKelime: {game['word']}"
        )

        game["round"] += 1

        if game["round"] > game["total_rounds"]:
            await finish_game(update, context)
            return

        new_word = random.choice(words)
        new_word = new_word.upper().replace("I", "İ")

        game["word"] = new_word
        game["masked"] = mask_word(new_word)
        game["letter_pool"] = get_letter_pool(new_word)

        await update.message.reply_text(
            f"Round: {game['round']}/{game['total_rounds']}\n"
            f"📚 {len(new_word)} harf: {game['letter_pool']}\n"
            f"🎲 {game['masked']}\n"
            f"Puan: {game['puan']:.1f}"
        )


async def finish_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if chat_id not in games:
        return

    game = games[chat_id]
    game["active"] = False

    if not game["scores"]:
        await update.message.reply_text("Oyun bitti, kimse puan alamadı.")
        del games[chat_id]
        return

    leaderboard = sorted(
        game["scores"].values(),
        key=lambda x: x["score"],
        reverse=True
    )

    msg = "🏆 Lider Tablosu:\n\n"
    for i, player in enumerate(leaderboard, start=1):
        msg += f"{i}. {player['name']} - {player['score']} puan\n"

    await update.message.reply_text(msg)
    del games[chat_id]
