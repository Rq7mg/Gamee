import json
import random
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import *

TOKEN = "BOT_TOKEN_BURAYA"

game_active = False
mode = None
current_word = None
current_hint = None
narrator_id = None
group_chat_id = None
last_activity = time.time()

with open("words.json", encoding="utf-8") as f:
    WORDS = json.load(f)


def load_scores():
    with open("scores.json", encoding="utf-8") as f:
        return json.load(f)


def save_scores(scores):
    with open("scores.json", "w", encoding="utf-8") as f:
        json.dump(scores, f)


def pick_word():
    w = random.choice(WORDS)
    return w["word"], w["hint"]


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


def mode_select(update, context):
    global game_active, narrator_id, current_word, current_hint, mode, last_activity

    query = update.callback_query
    query.answer()

    game_active = True
    narrator_id = query.from_user.id
    mode = query.data
    current_word, current_hint = pick_word()
    last_activity = time.time()

    keyboard = [[InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")]]

    query.message.reply_text(
        f"Oyun başladı!\nMod: {mode}\nAnlatıcı: {query.from_user.first_name}",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    context.bot.send_message(
        narrator_id,
        f"Kelimen:\n{current_word}\nİpucu: {current_hint}"
    )


def button(update, context):
    query = update.callback_query

    if query.from_user.id != narrator_id:
        query.answer("Sadece anlatıcı görebilir.", show_alert=True)
        return

    query.answer(
        text=f"Kelime: {current_word}\nİpucu: {current_hint}",
        show_alert=True
    )


def guess(update, context):
    global narrator_id, current_word, current_hint, last_activity

    if not game_active:
        return

    last_activity = time.time()

    if update.message.text.lower() == current_word.lower():
        user = update.message.from_user
        scores = load_scores()

        scores[user.first_name] = scores.get(user.first_name, 0) + 1
        save_scores(scores)

        update.message.reply_text(
            f"🎉 {user.first_name} bildi! +1 puan"
        )

        if mode == "text":
            narrator_id = user.id

        current_word, current_hint = pick_word()

        context.bot.send_message(
            narrator_id,
            f"Yeni kelime:\n{current_word}\nİpucu: {current_hint}"
        )


def stop(update, context):
    admins = context.bot.get_chat_administrators(update.effective_chat.id)
    admin_ids = [a.user.id for a in admins]

    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece adminler durdurabilir.")
        return

    end_game(context)


def end_game(context):
    global game_active
    game_active = False

    scores = load_scores()
    ranking = "🏆 Lider Tablosu\n\n"

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    for name, score in sorted_scores:
        ranking += f"{name}: {score}\n"

    context.bot.send_message(group_chat_id, ranking)


def timer_check(context):
    global game_active

    if game_active and time.time() - last_activity > 300:
        context.bot.send_message(
            group_chat_id,
            "⏱ 5 dk işlem yok. Oyun bitti."
        )
        end_game(context)


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, 10)

    updater.start_polling()
    updater.idle()


main()
