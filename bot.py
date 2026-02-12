import os
import random
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["tabu_bot"]
words_col = db["words"]
scores_col = db["scores"]

sudo_users = set([OWNER_ID])
groups_data = {}
games = {}
pending_dm = {}

def pick_word():
    doc = words_col.aggregate([{"$sample": {"size": 1}}])
    for d in doc:
        return d["word"], d["hint"]
    return None, None

def track_group(update):
    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or update.effective_chat.username or "Özel Chat"
    groups_data[chat_id] = {
        "title": chat_title,
        "users": update.effective_chat.get_member_count() if hasattr(update.effective_chat, "get_member_count") else 0
    }

def escape_md(text):
    # MarkdownV2 karakterlerini escape et
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for c in escape_chars:
        text = text.replace(c, f"\\{c}")
    return text

def start(update, context):
    track_group(update)
    if context.args:
        arg = context.args[0]
        if arg.startswith("writeword_"):
            chat_id = int(arg.split("_")[1])
            pending_dm[update.effective_user.id] = chat_id
            update.message.reply_text("✍️ Yeni anlatacağınız kelimeyi yazın.")
            return

    text = (
        "Merhaba! Ben Telegram Tabu Oyun Botu 😄\n"
        "Komutlar:\n"
        "/game → Oyunu başlatır\n"
        "/stop → Oyunu durdurur (admin)\n"
        "/eniyiler → Global en iyileri gösterir\n"
        "/wordcount → Toplam kelime sayısını gösterir"
    )

    keyboard = [
        [InlineKeyboardButton("Beni Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        [InlineKeyboardButton("👑 Sahip", url=f"tg://user?id={OWNER_ID}")]
    ]

    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def add_sudo(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    try:
        user_id = int(context.args[0])
        sudo_users.add(user_id)
        update.message.reply_text(f"✅ {user_id} sudo olarak eklendi.")
    except:
        update.message.reply_text("❌ Kullanım: /addsudo <id>")

def del_sudo(update, context):
    if update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Sadece owner kullanabilir.")
        return
    try:
        user_id = int(context.args[0])
        if user_id in sudo_users:
            sudo_users.remove(user_id)
            update.message.reply_text(f"✅ {user_id} sudo listeden kaldırıldı.")
        else:
            update.message.reply_text("❌ Bu kullanıcı sudo değil.")
    except:
        update.message.reply_text("❌ Kullanım: /delsudo <id>")

def add_word(update, context):
    if update.message.from_user.id not in sudo_users:
        update.message.reply_text("❌ Sadece sudo kullanıcı kelime ekleyebilir.")
        return
    text = " ".join(context.args)
    if "-" in text:
        word, hint = map(str.strip, text.split("-", 1))
    else:
        word, hint = text.strip(), ""
    word_lower = word.lower()
    if words_col.find_one({"word": word_lower}):
        update.message.reply_text("❌ Bu kelime zaten var.")
        return
    words_col.insert_one({"word": word_lower, "hint": hint})
    update.message.reply_text(f"✅ Kelime eklendi: {word} - {hint}")

def del_word(update, context):
    if update.message.from_user.id not in sudo_users:
        update.message.reply_text("❌ Sadece sudo kullanıcı kelime silebilir.")
        return
    word_lower = context.args[0].lower()
    result = words_col.delete_one({"word": word_lower})
    if result.deleted_count:
        update.message.reply_text(f"✅ Kelime silindi: {word_lower}")
    else:
        update.message.reply_text("❌ Kelime bulunamadı.")

def wordcount(update, context):
    count = words_col.count_documents({})
    update.message.reply_text(f"📚 Toplam kelime sayısı: {count}")

def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games and games[chat_id]["active"]:
        update.message.reply_text("❌ Bu grupta oyun zaten devam ediyor!")
        return
    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="voice")],
        [InlineKeyboardButton("⌨️ Yazılı", callback_data="text_mode")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

def mode_select(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat.id

    if chat_id in games and games[chat_id]["active"]:
        query.answer("❌ Bu grupta zaten aktif bir oyun var!", show_alert=True)
        return

    if query.data == "voice":
        current_word, current_hint = pick_word()
        games[chat_id] = {
            "active": True,
            "mode": "voice",
            "narrator_id": query.from_user.id,
            "current_word": current_word,
            "current_hint": current_hint,
            "last_activity": time.time(),
            "scores": {},
            "last_messages": [],
            "correct_count": 0
        }
        send_game_message(context, chat_id)
    elif query.data == "text_mode":
        keyboard = [
            [InlineKeyboardButton("Sabit Anlatıcı (Grup)", callback_data="text_fixed")],
            [InlineKeyboardButton("Değişken Anlatıcı (İlk Bilen)", callback_data="text_variable")]
        ]
        query.message.edit_text("Yazılı mod seçildi, seçenek belirleyin:", reply_markup=InlineKeyboardMarkup(keyboard))

def text_mode_select(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat.id
    current_word, current_hint = pick_word()

    narrator_id = query.from_user.id if query.data=="text_fixed" else None

    games[chat_id] = {
        "active": True,
        "mode": "text",
        "narrator_id": narrator_id,
        "current_word": current_word,
        "current_hint": current_hint,
        "last_activity": time.time(),
        "scores": {},
        "last_messages": [],
        "correct_count": 0,
        "variable_narrator": query.data=="text_variable"
    }

    send_game_message(context, chat_id)

def send_game_message(context, chat_id, prefix_msg=""):
    game = games[chat_id]
    narrator_id = game.get("narrator_id")
    bot_username = context.bot.username
    dm_link = f"https://t.me/{bot_username}?start=writeword_{chat_id}"

    keyboard = [
        [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next"),
         InlineKeyboardButton("✍️ Kelime Yaz", url=dm_link)]
    ]

    if narrator_id:  # sadece anlatıcı görebilir kelimeyi
        keyboard.insert(0, [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")])
    elif game.get("variable_narrator") and narrator_id is None:
        keyboard.append([InlineKeyboardButton("Anlatıcı olmak istiyorum", callback_data="be_narrator")])

    if game["correct_count"] >= 2:
        for msg_id in game["last_messages"][:2]:
            try:
                context.bot.delete_message(chat_id, msg_id)
            except:
                pass

    narrator_name = context.bot.get_chat_member(chat_id, narrator_id).user.first_name if narrator_id else "Henüz yok"
    msg_text = f"{escape_md(prefix_msg)}\nAnlatıcı: {escape_md(narrator_name)}" if prefix_msg else f"Anlatıcı: {escape_md(narrator_name)}"

    message = context.bot.send_message(
        chat_id, msg_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN_V2
    )

    game["last_messages"].append(message.message_id)
    game["last_messages"] = game["last_messages"][-5:]

def button(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    game = games.get(chat_id)
    if not game:
        return
    user_id = query.from_user.id

    if query.data == "look":
        if user_id != game.get("narrator_id"):
            query.answer("Sadece anlatıcı görebilir.", show_alert=True)
            return
        query.answer(f"🎯 Kelime: {escape_md(game['current_word'])}\n📌 Tanım: {escape_md(game['current_hint'])}", show_alert=True)

    elif query.data == "next":
        game["current_word"], game["current_hint"] = pick_word()
        query.answer(f"🎯 Yeni kelime: {escape_md(game['current_word'])}\n📌 Tanım: {escape_md(game['current_hint'])}", show_alert=True)
    elif query.data == "be_narrator":
        if game.get("variable_narrator") and game.get("narrator_id") is None:
            game["narrator_id"] = user_id
            send_game_message(context, chat_id, prefix_msg=f"🎤 {escape_md(query.from_user.first_name)} artık anlatıcı!")
            query.answer("✅ Artık anlatıcısınız", show_alert=True)

def guess(update, context):
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    text = update.message.text.strip()

    if update.message.chat.type == "private":
        if user_id in pending_dm:
            target_chat = pending_dm[user_id]
            game = games.get(target_chat)
            if game:
                game["current_word"] = text
                game["current_hint"] = "Kullanıcı tarafından girildi"
                context.bot.send_message(user_id, f"🎯 Yeni anlatacağınız kelime: {text}")
            pending_dm.pop(user_id, None)
        return

    game = games.get(chat_id)
    if not game or not game["active"]:
        return

    if game["current_word"].lower() in text.lower() and user_id != game.get("narrator_id"):
        user = update.message.from_user
        user_key = f"{user.first_name}[{user.id}]"
        game["scores"][user_key] = game["scores"].get(user_key, 0) + 1
        game["correct_count"] += 1

        scores_col.update_one(
            {"user_id": user.id},
            {"$inc": {"score": 1}, "$set": {"name": user.first_name}},
            upsert=True
        )

        prefix_msg = f"🎉 {escape_md(user.first_name)} '*{escape_md(game['current_word'])}*' kelimesini doğru bildi!"
        game["current_word"], game["current_hint"] = pick_word()
        send_game_message(context, chat_id, prefix_msg=prefix_msg)

        if game.get("narrator_id"):
            context.bot.send_message(
                game["narrator_id"],
                f"🎯 Yeni kelime:\n{escape_md(game['current_word'])}\n📌 Tanım: {escape_md(game['current_hint'])}",
                parse_mode=ParseMode.MARKDOWN_V2
            )

def stop(update, context):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game:
        update.message.reply_text("❌ Bu grupta oyun yok.")
        return

    admins = context.bot.get_chat_administrators(chat_id)
    admin_ids = [a.user.id for a in admins]

    if update.message.from_user.id not in admin_ids:
        update.message.reply_text("Sadece admin durdurabilir.")
        return

    end_game(context, chat_id)

def end_game(context, chat_id):
    game = games.get(chat_id)
    if not game:
        return

    ranking = "🏆 Lider Tablosu\n\n"
    narrator_name = context.bot.get_chat_member(chat_id, game.get("narrator_id")).user.first_name if game.get("narrator_id") else "Henüz yok"
    ranking += f"Anlatıcı: {escape_md(narrator_name)}\nKazananlar:\n"

    sorted_scores = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
    for idx, (name, score) in enumerate(sorted_scores, 1):
        medal = ["🥇","🥈","🥉"] + ["🏅"]*7
        ranking += f"{medal[idx-1]} {idx}. {escape_md(name)}: {score} puan\n"

    context.bot.send_message(chat_id, ranking, parse_mode=ParseMode.MARKDOWN_V2)
    game["active"] = False
    games.pop(chat_id, None)

def eniyiler(update, context):
    top = scores_col.find().sort("score", -1).limit(10)
    msg = "🏆 Global En İyiler\n\n"
    for idx, u in enumerate(top, 1):
        medal = ["🥇","🥈","🥉"] + ["🏅"]*7
        msg += f"{medal[idx-1]} {idx}. {escape_md(u['name'])} [{u['user_id']}]: {u['score']} puan\n"
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

def timer_check(context):
    for chat_id, game in list(games.items()):
        if game["active"] and time.time() - game["last_activity"] > 300:
            context.bot.send_message(chat_id, "⏱ 5 dk işlem yok. Oyun bitti.")
            end_game(context, chat_id)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("addsudo", add_sudo))
    dp.add_handler(CommandHandler("delsudo", del_sudo))
    dp.add_handler(CommandHandler("addword", add_word))
    dp.add_handler(CommandHandler("delword", del_word))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("wordcount", wordcount))

    dp.add_handler(CallbackQueryHandler(mode_select, pattern="voice|text_mode"))
    dp.add_handler(CallbackQueryHandler(text_mode_select, pattern="text_fixed|text_variable"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next|be_narrator"))

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))

    updater.job_queue.run_repeating(timer_check, interval=10)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
