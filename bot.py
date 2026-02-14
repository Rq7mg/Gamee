import os
import time
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- AYARLAR ---
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

# --- VERİTABANI BAĞLANTISI ---
try:
    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client["tabu_bot"]
    words_col = db["words"]
    scores_col = db["scores"]
    chats_col = db["chats"] 
    logger.info("MongoDB bağlantısı başarılı.")
except Exception as e:
    logger.error(f"MongoDB Bağlantı Hatası: {e}")

# --- GLOBAL DEĞİŞKENLER ---
sudo_users = set([OWNER_ID])
games = {}       
pending_dm = {}  

# --- TÜRKÇE VE METİN DÜZENLEME ---
def stabilize_text(text):
    if not text: return ""
    text = str(text).strip()
    replacements = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
    t_lower = text.lower()
    for char, rep in replacements.items():
        t_lower = t_lower.replace(char, rep)
    return t_lower.upper()

def escape_md(text):
    text = str(text)
    for c in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(c, f"\\{c}")
    return text

def pick_word():
    try:
        doc = list(words_col.aggregate([{"$sample": {"size": 1}}]))
        if doc: return doc[0]["word"], doc[0]["hint"]
    except: pass
    return "kitap", "okunan nesne"

def update_chats(chat_id):
    if chats_col is not None:
        chats_col.update_one({"chat_id": chat_id}, {"$set": {"active": True}}, upsert=True)

# --- OYUN ARAYÜZÜ ---
def send_game_ui(context, chat_id, text_prefix=""):
    if chat_id not in games: return
    game_data = games[chat_id]
    update_chats(chat_id)
    game_data["last_activity"] = time.time()
    
    if game_data.get("waiting_for_volunteer"):
        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]
        msg = f"{text_prefix}\n⚠️ *Anlatıcı sırasını saldı\\!*\nKim anlatmak ister?"
        context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
        return

    try: 
        user = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user
        name = user.first_name
    except: name = "Bilinmiyor"

    kb = [
        [InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="btn_look"),
         InlineKeyboardButton("💡 İpucu Ver", callback_data="btn_hint")],
        [InlineKeyboardButton("➡️ Değiştir", callback_data="btn_next"),
         InlineKeyboardButton("✍️ Özel Kelime Yaz", url=f"https://t.me/{context.bot.username}?start=write_{chat_id}")]
    ]
    if game_data["sub_mode"] == "dynamic":
        kb.append([InlineKeyboardButton("❌ Sıramı Sal", callback_data="btn_pass")])

    msg = f"{text_prefix}\n🗣 Anlatıcı: *{escape_md(name)}*"
    context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)

# --- KOMUTLAR ---
def start(update, context):
    user_id = update.effective_user.id
    if context.args and context.args[0].startswith("write_"):
        target_id = int(context.args[0].replace("write_", ""))
        if target_id in games and games[target_id].get("narrator_id") == user_id:
            pending_dm[user_id] = target_id
            update.message.reply_text("✍️ Anlatacağınız kelimeyi yazın:")
        else:
            update.message.reply_text("❌ Şu an anlatıcı değilsiniz.")
        return
    update.message.reply_text("👋 Tabu Botu Aktif!\n/game - Oyunu Başlat\n/eniyiler - Skor Tablosu")

def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games: return update.message.reply_text("⚠️ Oyun zaten sürüyor.")
    kb = [[InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),
           InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")]]
    update.message.reply_text("🎮 Mod Seçin:", reply_markup=InlineKeyboardMarkup(kb))

# --- ADMIN KOMUTLARI ---
def duyuru(update, context):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.reply_to_message
    if not msg: return update.message.reply_text("Bir mesajı yanıtlayın.")
    chats = list(chats_col.find({"active": True}))
    success = 0
    for chat in chats:
        try:
            context.bot.copy_message(chat_id=chat['chat_id'], from_chat_id=update.effective_chat.id, message_id=msg.message_id)
            success += 1
            time.sleep(0.05)
        except: pass
    update.message.reply_text(f"✅ {success} gruba iletildi.")

def stats(update, context):
    if update.effective_user.id not in sudo_users: return
    total = chats_col.count_documents({})
    update.message.reply_text(f"📊 Grup: {total}\n🎮 Aktif Oyun: {len(games)}")

def word_count(update, context):
    if update.effective_user.id not in sudo_users: return
    update.message.reply_text(f"📚 Toplam Kelime: {words_col.count_documents({})}")

# --- CALLBACK İŞLEMCİSİ ---
def handle_callbacks(update, context):
    query = update.callback_query
    data = query.data
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    if data.startswith("mode_"):
        query.answer()
        if data == "mode_text_pre":
            kb = [[InlineKeyboardButton("👤 Sabit", callback_data="mode_text_fixed"),
                   InlineKeyboardButton("🔄 Değişken", callback_data="mode_text_dynamic")]]
            query.edit_message_text("⌨️ Anlatıcı Tipi:", reply_markup=InlineKeyboardMarkup(kb))
            return
        w, h = pick_word()
        games[chat_id] = {"narrator_id": user_id, "sub_mode": "dynamic" if data=="mode_text_dynamic" else "fixed", "current_word": w, "current_hint": h, "scores": {}, "last_activity": time.time(), "waiting_for_volunteer": False, "hint_used": False}
        query.message.delete()
        send_game_ui(context, chat_id, "✅ Oyun Başladı!")

    elif data.startswith("btn_"):
        if chat_id not in games: return query.answer("Oyun aktif değil.")
        game_data = games[chat_id]
        
        if data == "btn_volunteer":
            if not game_data.get("waiting_for_volunteer"): return query.answer()
            game_data.update({"narrator_id": user_id, "waiting_for_volunteer": False, "hint_used": False, "current_word": pick_word()[0], "current_hint": pick_word()[1]})
            query.message.delete()
            send_game_ui(context, chat_id, f"🔄 Yeni Anlatıcı: {query.from_user.first_name}")
            return

        if user_id != game_data["narrator_id"]: return query.answer("⚠️ Sadece anlatıcı basabilir!", show_alert=True)

        if data == "btn_look":
            query.answer(f"🎯 KELİME: {stabilize_text(game_data['current_word'])}\n📌 İPUCU: {game_data['current_hint']}", show_alert=True)
        elif data == "btn_hint" and not game_data["hint_used"]:
            game_data["hint_used"] = True
            word = stabilize_text(game_data['current_word'])
            context.bot.send_message(chat_id, f"💡 İpucu: {word[0]} " + "_ "*(len(word)-1))
        elif data == "btn_next":
            game_data["current_word"], game_data["current_hint"] = pick_word()
            game_data["hint_used"] = False
            query.answer("Yeni Kelime Geldi", show_alert=True)
        elif data == "btn_pass":
            game_data.update({"waiting_for_volunteer": True, "narrator_id": None})
            query.message.delete()
            send_game_ui(context, chat_id)

# --- TAHMİN HANDLER ---
def guess_handler(update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    input_text = stabilize_text(update.message.text)

    if update.message.chat.type == "private" and user_id in pending_dm:
        target = pending_dm[user_id]
        if target in games and games[target]["narrator_id"] == user_id:
            games[target].update({"current_word": input_text, "current_hint": "Özel", "hint_used": False})
            update.message.reply_text(f"✅ Ayarlandı: {input_text}")
        pending_dm.pop(user_id, None)
        return

    if chat_id not in games: return
    game_data = games[chat_id]
    if game_data.get("waiting_for_volunteer") or user_id == game_data["narrator_id"]: return

    if input_text == stabilize_text(game_data["current_word"]):
        point = 0.5 if game_data["hint_used"] else 1.0
        name = update.effective_user.first_name
        key = f"{name}::{user_id}"
        game_data["scores"][key] = game_data["scores"].get(key, 0) + point
        if scores_col: scores_col.update_one({"user_id": user_id}, {"$inc": {"score": point}, "$set": {"name": name}}, upsert=True)
        
        msg = f"🎉 *{escape_md(name)}* bildi\\! (+{escape_md(point)} Puan)\nKelime: *{input_text}*"
        if game_data["sub_mode"] == "dynamic": game_data["narrator_id"] = user_id
        game_data["current_word"], game_data["current_hint"] = pick_word()
        game_data["hint_used"] = False
        send_game_ui(context, chat_id, msg)

def auto_stop(context):
    for cid in list(games.keys()):
        if time.time() - games[cid].get("last_activity", 0) > 300:
            try: context.bot.send_message(cid, "💤 5 dk hareketsizlik. Oyun bitti.")
            except: pass
            del games[cid]

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("duyuru", duyuru))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("wordcount", word_count))
    dp.add_handler(CallbackQueryHandler(handle_callbacks))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))
    updater.job_queue.run_repeating(auto_stop, interval=60)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
