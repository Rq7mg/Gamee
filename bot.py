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
    if not text: return ""
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

# --- Tüm Admin ve Sudo Handlerları ---
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
    if not context.args: return
    word_lower = context.args[0].lower()
    result = words_col.delete_one({"word": word_lower})
    if result.deleted_count:
        update.message.reply_text(f"✅ Kelime silindi: {word_lower}")
    else:
        update.message.reply_text("❌ Kelime bulunamadı.")

def wordcount(update, context):
    count = words_col.count_documents({})
    update.message.reply_text(f"📚 Toplam kelime sayısı: {count}")

# --- Oyun Mantığı ve Modlar ---
def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games and games[chat_id]["active"]:
        update.message.reply_text("❌ Bu grupta oyun zaten devam ediyor!")
        return
    keyboard = [
        [InlineKeyboardButton("🎤 Sesli", callback_data="mode_v"),
         InlineKeyboardButton("⌨️ Yazılı", callback_data="mode_t_choice")]
    ]
    update.message.reply_text("Oyun modu seç:", reply_markup=InlineKeyboardMarkup(keyboard))

def mode_select(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat.id

    if query.data == "mode_t_choice":
        keyboard = [
            [InlineKeyboardButton("👤 Sabit Anlatıcı", callback_data="sub_fixed"),
             InlineKeyboardButton("🔄 Değişken Anlatıcı", callback_data="sub_dynamic")]
        ]
        query.edit_message_text("Yazılı Mod Türü:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    mode = "voice" if query.data == "mode_v" else "text"
    sub_mode = "dynamic" if query.data == "sub_dynamic" else "fixed"
    
    current_word, current_hint = pick_word()
    games[chat_id] = {
        "active": True, "mode": mode, "sub_mode": sub_mode, "narrator_id": query.from_user.id,
        "current_word": current_word, "current_hint": current_hint, "last_activity": time.time(),
        "scores": {}, "last_messages": [], "correct_count": 0
    }
    send_game_message(context, chat_id)

def send_game_message(context, chat_id, prefix_msg=""):
    game = games[chat_id]
    narrator_id = game["narrator_id"]
    dm_link = f"https://t.me/{context.bot.username}?start=writeword_{chat_id}"
    
    keyboard = [
        [InlineKeyboardButton("👀 Kelimeye Bak", callback_data="look")],
        [InlineKeyboardButton("➡️ Kelimeyi Değiştir", callback_data="next"),
         InlineKeyboardButton("✍️ Kelime Yaz", url=dm_link)]
    ]
    
    try:
        n_name = context.bot.get_chat_member(chat_id, narrator_id).user.first_name
    except:
        n_name = "Anlatıcı"

    msg = f"{prefix_msg}\n\nAnlatıcı: *{escape_md(n_name)}*" if prefix_msg else f"Anlatıcı: *{escape_md(n_name)}*"
    sent_msg = context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    game["last_messages"].append(sent_msg.message_id)

def button(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    game = games.get(chat_id)
    if not game or query.from_user.id != game["narrator_id"]:
        query.answer("Sadece anlatıcı!", show_alert=True)
        return
    
    game["last_activity"] = time.time()
    if query.data == "look":
        query.answer(f"🎯 Kelime: {game['current_word']}\n📌 İpucu: {game['current_hint']}", show_alert=True)
    elif query.data == "next":
        game["current_word"], game["current_hint"] = pick_word()
        query.answer("🔄 Kelime değiştirildi!", show_alert=True)

def guess(update, context):
    chat_id = update.message.chat.id
    user = update.message.from_user
    text = update.message.text.strip().lower()

    if update.message.chat.type == "private":
        if user.id in pending_dm:
            target = pending_dm[user.id]
            if target in games:
                games[target]["current_word"] = text
                context.bot.send_message(user.id, f"✅ Kelime '{text}' olarak ayarlandı.")
            pending_dm.pop(user.id, None)
        return

    game = games.get(chat_id)
    if not game or not game["active"]: return

    if text == game["current_word"].lower() and user.id != game["narrator_id"]:
        user_key = f"{user.first_name}[{user.id}]"
        game["scores"][user_key] = game["scores"].get(user_key, 0) + 1
        scores_col.update_one({"user_id": user.id}, {"$inc": {"score": 1}, "$set": {"name": user.first_name}}, upsert=True)

        # Kelime KALIN harflerle yazılıyor
        p_msg = f"🎉 *{escape_md(user.first_name)}* kelimeyi bildi: *{escape_md(game['current_word'].upper())}*"
        
        if game.get("sub_mode") == "dynamic":
            game["narrator_id"] = user.id
            p_msg += "\n🔄 Yeni anlatıcı seçildi!"

        game["current_word"], game["current_hint"] = pick_word()
        game["last_activity"] = time.time()
        send_game_message(context, chat_id, prefix_msg=p_msg)

def stop(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in games:
        update.message.reply_text("❌ Oyun zaten yok.")
        return
    
    status = context.bot.get_chat_member(chat_id, update.message.from_user.id).status
    if status not in ["creator", "administrator"] and update.message.from_user.id != OWNER_ID:
        update.message.reply_text("❌ Yetkiniz yok.")
        return
    end_game(context, chat_id)

def end_game(context, chat_id):
    game = games.get(chat_id)
    if not game: return
    rank = "🏆 *Oyun Bitti - Lider Tablosu*\n\n"
    sorted_s = sorted(game["scores"].items(), key=lambda x: x[1], reverse=True)
    if not sorted_s: rank += "Puan yok."
    for idx, (n, s) in enumerate(sorted_s, 1):
        rank += f"{idx}. {escape_md(n)}: {s} puan\n"
    context.bot.send_message(chat_id, rank, parse_mode=ParseMode.MARKDOWN_V2)
    games.pop(chat_id, None)

def eniyiler(update, context):
    top = scores_col.find().sort("score", -1).limit(10)
    msg = "🏆 Global En İyiler\n\n"
    for idx, u in enumerate(top, 1):
        msg += f"{idx}. {u['name']}: {u['score']} puan\n"
    update.message.reply_text(msg)

def timer_check(context):
    for chat_id, game in list(games.items()):
        if time.time() - game["last_activity"] > 300:
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
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="mode_v|mode_t_choice|sub_fixed|sub_dynamic"))
    dp.add_handler(CallbackQueryHandler(button, pattern="look|next"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess))
    updater.job_queue.run_repeating(timer_check, interval=60)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()

