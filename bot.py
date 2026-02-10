import json
import random
import time
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

TOKEN = os.environ.get("BOT_TOKEN")  # Heroku env değişkeni

# Oyun değişkenleri
game_active = False
mode = None
current_word = None
current_hint = None
narrator_id = None
group_chat_id = None
last_activity = time.time()

# Kelime veritabanı
with open("words.json", encoding="utf-8") as f:
    WORDS = json.load(f)

SCORES_FILE = "scores.json"

def load_scores():
    try:
        with open(SCORES_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_scores(scores):
    with open(SCORES_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f)

def pick_word():
    w = random.choice(WORDS)
    return w["word"], w["hint"]

# /start komutu
def start(update, context):
    text = (
        "Merhaba! Ben Telegram Kelime Oyunu Botuyum 😄\n\n"
        "Komutlar:\n"
        "/start → Bu mesajı gösterir\n"
        "/game → Oyunu başlatır\n"
        "/stop → Oyunu durdurur (sadece admin)\n\n"
        "Oyun özellikleri:\n"
        "- Sesli ve yazılı mod\n"
        "- 👀 Kelimeye Bak → popup (grupta, sadece anlatıcı görür)\n"
        "- ➡️ Kelimeyi Geç → popup (grupta, sadece anlatıcı görür)\n"
        "- ✍️ Kelime Yaz → özel mesaj ile anlatıcı yeni kelime belirler\n"
        "- Doğru tahmin +1 puan, lider tablosu\n"
        "- 5 dk işlem yoksa oyun otomatik biter"
    )
    update.message.reply_text(text)

# /game komutu
def game(update, context):
    global group_chat_id
    group_chat_id = update.effective_chat.id

    keyboard = [
        [InlineKeyboardButton("🎤 Sesli Mod", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="text")]
    ]

    update.message.reply_text(
        "Oyun modu seç:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Mod seçimi
def mode_select(update, context):
    global game_active, narrator_id, current_word, current_hint, mode, last_activity

    query = update.callback_query
    query.answer()

    game_active = True
    narrator_id = query.from_user.id
    mode = query.data
    current_word, current_hint = pick_word()
    last_activity = time.time()

    keyboard = [
        [
            InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look"),
            InlineKeyboardButton("➡️ Kelimeyi Geç", callback_data="next"),
            InlineKeyboardButton("✍️ Kelime Yaz", callback_data="write")
        ]
    ]

    query.message.reply_text(
        f"Oyun başladı!\nMod: {mode}\nAnlatıcı: {query.from_user.first_name}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Buton mantığı
def button(update, context):
    global current_word, current_hint, narrator_id, last_activity
    query = update.callback_query
    user = query.from_user

    if user.id != narrator_id:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    last_activity = time.time()

    if query.data == "look":
        query.answer(f"Kelime: {current_word}\nİpucu: {current_hint}", show_alert=True)
    elif query.data == "next":
        current_word, current_hint = pick_word()
        query.answer(f"Yeni kelime:\n{current_word}\nİpucu: {current_hint}", show_alert=True)
    elif query.data == "write":
        try:
            context.bot.send_message(narrator_id, "✍️ Yeni kelimeyi yazın. Bu kelime artık oyun kelimesi olacak.")
            query.answer("Özel mesaja gönderildi, kelimeyi yazın!", show_alert=True)
        except:
            query.answer("Özel mesaja gönderilemedi. Bot ile DM açın.", show_alert=True)

# Tahmin kontrolü
def guess(update, context):
    global narrator_id, current_word, current_hint, last_activity
    if not game_active:
        return

    text = update.message.text.strip()
    last_activity = time.time()

    # DM'den yeni kelime
    if update.message.chat.type == "private" and update.message.from_user.id == narrator_id:
        current_word = text
        current_hint = "Kullanıcı tarafından girildi"
        context.bot.send_message(narrator_id, f"Yeni kelime ayarlandı: {current_word}")
        return

    # Grup tahmini
    if text.lower() == current_word.lower():
        user = update.message.from_user
        scores = load_scores()
        scores[user.first_name] = scores.get(user.first_name, 0) + 1
        save_scores(scores)

        update.message.reply_text(f"🎉 {user.first_name} doğru bildi! +1 puan")

        if mode == "text":
            narrator_id = user.id
            context.bot.send_message(narrator_id, f"Siz artık anlatıcısınız! Kelimeyi anlatın.")
            current_word, current_hint = pick_word()
            context.bot.send_message(narrator_id, f"Yeni kelime:\n{current_word}\nİpucu: {current_hint}")
        else:
            current_word, current_hint = pick_word()
            context.bot.send_message(narrator_id, f"Yeni kelime:\n{current_word}\nİpucu: {current_hint}")

# /stop komutu
def stop(update, context):
    global game_active
    admins = context.bot.get_chat_administrators(update.effective_chat.id)
    admin_ids = [a.user.id for a in admins]

    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece adminler durdurabilir.")
        return

    end_game(context)

# Oyun bitirme ve lider tablosu
def end_game(context):
    global game_active
    game_active = False
    scores = load_scores()
    ranking = "🏆 Lider Tablosu\n\n"
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    for name, score in sorted_scores:
        ranking += f"{name}: {score} puan\n"
    context.bot.send_message(group_chat_id, ranking)

# 5 dk inactivity kontrol
def timer_check(context):
    global game_active
    if game_active and time.time() - last_activity > 300:
        context.bot.send_message(group_chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
        end_game(context)

# Main
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|write"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, 10)

    updater.start_polling()
    updater.idle()

main()
