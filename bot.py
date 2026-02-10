import json
import random
import time
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID"))

SUDO_FILE = "sudo.json"
SCORES_FILE = "scores.json"

games = {}

with open("words.json", encoding="utf-8") as f:
    WORDS = json.load(f)

# ---------- SUDO ----------
def load_sudo():
    try:
        with open(SUDO_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_sudo(data):
    with open(SUDO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def is_authorized(uid):
    return uid == OWNER_ID or uid in load_sudo()

# ---------- SCORES ----------
def load_scores():
    try:
        with open(SCORES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_scores(data):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

def pick_word():
    w = random.choice(WORDS)
    return w["word"], w["hint"]

# ---------- COMMANDS ----------
def start(update, context):
    update.message.reply_text("🎮 Kelime Oyunu Botu\n/game ile başla")

def game(update, context):
    chat_id = update.effective_chat.id
    games[chat_id] = {
        "active": False,
        "mode": None,
        "narrator": None,
        "word": None,
        "hint": None,
        "last": time.time()
    }

    keyboard = [
        [InlineKeyboardButton("🎤 Sesli Mod", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="text")]
    ]
    update.message.reply_text("Mod seç:", reply_markup=InlineKeyboardMarkup(keyboard))

def mode_select(update, context):
    q = update.callback_query
    q.answer()
    chat_id = q.message.chat.id

    games[chat_id]["active"] = True
    games[chat_id]["mode"] = q.data
    games[chat_id]["narrator"] = q.from_user.id
    games[chat_id]["word"], games[chat_id]["hint"] = pick_word()
    games[chat_id]["last"] = time.time()

    send_game(context, chat_id)

def send_game(context, chat_id):
    g = games[chat_id]
    mode_text = "Sesli" if g["mode"] == "voice" else "Yazılı"
    narrator = context.bot.get_chat_member(chat_id, g["narrator"]).user.first_name

    keyboard = [[
        InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look"),
        InlineKeyboardButton("➡️ Kelimeyi Geç", callback_data="next"),
        InlineKeyboardButton("✍️ Kelime Yaz", callback_data="write")
    ]]

    context.bot.send_message(
        chat_id,
        f"Oyun başladı!\nMod: {mode_text}\nAnlatıcı: {narrator}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def button(update, context):
    q = update.callback_query
    chat_id = q.message.chat.id
    g = games.get(chat_id)

    if not g or q.from_user.id != g["narrator"]:
        q.answer("Sadece anlatıcı.", show_alert=True)
        return

    g["last"] = time.time()

    if q.data == "look":
        q.answer(f"Kelime: {g['word']}", show_alert=True)

    elif q.data == "next":
        g["word"], g["hint"] = pick_word()
        send_game(context, chat_id)
        q.answer("Yeni kelime")

    elif q.data == "write":
        context.bot.send_message(g["narrator"], "Yeni kelimeyi yaz:")
        q.answer("DM gönderildi")

def guess(update, context):
    chat_id = update.effective_chat.id
    g = games.get(chat_id)
    if not g or not g["active"]:
        return

    text = update.message.text.strip()
    g["last"] = time.time()

    if update.message.chat.type == "private" and update.message.from_user.id == g["narrator"]:
        g["word"] = text
        g["hint"] = "manuel"
        send_game(context, chat_id)
        return

    if text.lower() == g["word"].lower():
        user = update.message.from_user
        scores = load_scores()
        scores[user.first_name] = scores.get(user.first_name, 0) + 1
        save_scores(scores)

        update.message.reply_text(f"🎉 {user.first_name} doğru bildi!")

        if g["mode"] == "text":
            g["narrator"] = user.id

        g["word"], g["hint"] = pick_word()
        send_game(context, chat_id)

# ---------- ADMIN ----------
def addsudo(update, context):
    if update.message.from_user.id != OWNER_ID:
        return
    uid = int(context.args[0])
    sudo = load_sudo()
    if uid not in sudo:
        sudo.append(uid)
        save_sudo(sudo)
    update.message.reply_text("Sudo eklendi")

def sudolist(update, context):
    if update.message.from_user.id != OWNER_ID:
        return
    sudo = load_sudo()
    update.message.reply_text("\n".join(map(str, sudo)) or "Boş")

def addword(update, context):
    if not is_authorized(update.message.from_user.id):
        return
    text = update.message.text.replace("/addword", "").strip()
    word, hint = map(str.strip, text.split("-", 1))
    WORDS.append({"word": word, "hint": hint})
    with open("words.json", "w", encoding="utf-8") as f:
        json.dump(WORDS, f, ensure_ascii=False, indent=2)
    update.message.reply_text("Kelime eklendi")

def delword(update, context):
    if not is_authorized(update.message.from_user.id):
        return
    target = " ".join(context.args).lower()
    global WORDS
    WORDS = [w for w in WORDS if w["word"].lower() != target]
    with open("words.json", "w", encoding="utf-8") as f:
        json.dump(WORDS, f, ensure_ascii=False, indent=2)
    update.message.reply_text("Silindi")

def wordcount(update, context):
    if not is_authorized(update.message.from_user.id):
        return
    update.message.reply_text(f"Toplam kelime: {len(WORDS)}")

# ---------- STOP KOMUTU ----------
def stop(update, context):
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id

    # Owner her zaman durdurabilir
    if user_id != OWNER_ID:
        admins = context.bot.get_chat_administrators(chat_id)
        admin_ids = [a.user.id for a in admins]
        if user_id not in admin_ids:
            update.message.reply_text("⛔ Sadece adminler durdurabilir.")
            return

    game = games.get(chat_id)
    if not game or not game["active"]:
        update.message.reply_text("❗ Bu grupta aktif oyun yok.")
        return

    game["active"] = False
    update.message.reply_text("🛑 Oyun durduruldu.")

# ---------- TIMER ----------
def timer_check(context):
    now = time.time()
    for chat_id, g in list(games.items()):
        if g["active"] and now - g["last"] > 300:
            context.bot.send_message(chat_id, "⏱ Oyun bitti")
            g["active"] = False

# ---------- MAIN ----------
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("addsudo", addsudo))
    dp.add_handler(CommandHandler("sudolist", sudolist))
    dp.add_handler(CommandHandler("addword", addword))
    dp.add_handler(CommandHandler("delword", delword))
    dp.add_handler(CommandHandler("wordcount", wordcount))
    dp.add_handler(CommandHandler("stop", stop))

    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|write"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, 10)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
