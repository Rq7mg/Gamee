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
    words_col = scores_col = chats_col = None

# --- GLOBAL DEĞİŞKENLER ---
sudo_users = set([OWNER_ID])
games = {}       
pending_dm = {}  

# --- YARDIMCI FONKSİYONLAR ---

def tr_upper(text):
    if not text: return ""
    replacements = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
    text = text.lower()
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.upper()

def escape_md(text):
    if text is None: return ""
    text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for c in escape_chars:
        text = text.replace(c, f"\\{c}")
    return text

def pick_word():
    if words_col is None: return "Hata", "DB Yok"
    try:
        pipeline = [{"$sample": {"size": 1}}]
        doc = list(words_col.aggregate(pipeline))
        if doc:
            return doc[0]["word"], doc[0]["hint"]
        return "kelime yok", "veritabanı boş"
    except Exception as e:
        logger.error(f"Kelime seçme hatası: {e}")
        return "hata", "hata"

def update_chats(chat_id):
    if chats_col is not None:
        chats_col.update_one({"chat_id": chat_id}, {"$set": {"active": True}}, upsert=True)

# --- OYUN ARAYÜZÜ ---
def send_game_ui(context, chat_id, text_prefix=""):
    if chat_id not in games: return
    game_data = games[chat_id]
    update_chats(chat_id)
    game_data["last_activity"] = time.time() # Her arayüz gönderiminde süreyi yenile
    
    if game_data.get("waiting_for_volunteer"):
        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]
        msg = f"{text_prefix}\n⚠️ *Anlatıcı sırasını saldı\\!*\nKim anlatmak ister?"
        try:
            context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
        except:
            context.bot.send_message(chat_id, msg.replace("*","").replace("\\",""), reply_markup=InlineKeyboardMarkup(kb))
        return

    try:
        user_info = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user
        name = user_info.first_name
    except:
        name = "Bilinmiyor"

    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start=writeword_{chat_id}"

    kb = [
        [InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="btn_look"),
         InlineKeyboardButton("💡 İpucu Ver", callback_data="btn_hint")],
        [InlineKeyboardButton("➡️ Değiştir", callback_data="btn_next"),
         InlineKeyboardButton("✍️ Özel Kelime Yaz", url=deep_link)]
    ]
    if game_data["sub_mode"] == "dynamic":
        kb.append([InlineKeyboardButton("❌ Sıramı Sal", callback_data="btn_pass")])

    msg = f"{text_prefix}\n🗣 Anlatıcı: *{escape_md(name)}*"
    try:
        context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
    except:
        context.bot.send_message(chat_id, msg.replace("*", "").replace("\\", ""), reply_markup=InlineKeyboardMarkup(kb))

# --- OYUN BİTİŞ MANTIĞI ---
def end_game_logic(context, chat_id):
    if chat_id not in games: return
    game_data = games[chat_id]
    
    text = "🏁 *OYUN BİTTİ - PUAN DURUMU*\n\n"
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_scores:
        text += "Kimse puan alamadı."
    else:
        for idx, (key, score) in enumerate(sorted_scores, 1):
            name = key.split("::")[0]
            text += f"{idx}\\. {escape_md(name)}: {escape_md(score)} puan\n"
            
    try: context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)
    except: context.bot.send_message(chat_id, text.replace("*","").replace("\\",""))
    
    if chat_id in games:
        del games[chat_id]

# --- KOMUTLAR ---

def start(update, context):
    user_id = update.effective_user.id
    update_chats(update.effective_chat.id)
    if context.args and context.args[0].startswith("writeword_"):
        target_chat_id = int(context.args[0].split("_")[1])
        pending_dm[user_id] = target_chat_id
        update.message.reply_text("✍️ Anlatacağınız kelimeyi şimdi buraya yazın.")
        return
    text = "👋 Tabu Botu!\n/game - Başlat\n/eniyiler - Skorlar"
    update.message.reply_text(text)

def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games:
        update.message.reply_text("⚠️ Oyun zaten devam ediyor!")
        return
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
    update.message.reply_text(f"📊 Grup Sayısı: {total}\n🎮 Aktif Oyun: {len(games)}")

def word_count(update, context):
    if update.effective_user.id not in sudo_users: return
    update.message.reply_text(f"📚 Toplam Kelime: {words_col.count_documents({})}")

# --- TAHMİN MANTIĞI ---

def guess_handler(update, context):
    user = update.message.from_user
    chat_id = update.message.chat.id
    text = update.message.text.strip().lower()

    if update.message.chat.type == "private" and user.id in pending_dm:
        target_chat_id = pending_dm[user.id]
        if target_chat_id in games and games[target_chat_id].get("narrator_id") == user.id:
            games[target_chat_id].update({"current_word": text, "current_hint": "Özel", "hint_used": False, "last_activity": time.time()})
            update.message.reply_text(f"✅ Ayarlandı: {text.upper()}")
        pending_dm.pop(user.id, None)
        return

    if chat_id not in games: return
    game_data = games[chat_id]
    game_data["last_activity"] = time.time() # Her tahminde süreyi sıfırla

    if game_data.get("waiting_for_volunteer") or user.id == game_data["narrator_id"]: return

    if text == game_data["current_word"].strip().lower():
        point = 0.5 if game_data.get("hint_used") else 1.0
        full_key = f"{user.first_name}::{user.id}"
        game_data["scores"][full_key] = game_data["scores"].get(full_key, 0) + point
        if scores_col:
            scores_col.update_one({"user_id": user.id}, {"$inc": {"score": point}, "$set": {"name": user.first_name}}, upsert=True)
        msg = f"🎉 *{escape_md(user.first_name)}* bildi\\!"
        if game_data["sub_mode"] == "dynamic": game_data["narrator_id"] = user.id
        w, h = pick_word()
        game_data.update({"current_word": w, "current_hint": h, "hint_used": False})
        send_game_ui(context, chat_id, msg)

# --- OTOMATİK DURDURMA GÖREVİ ---
def auto_stop_check(context):
    now = time.time()
    for cid in list(games.keys()):
        # 300 saniye = 5 dakika
        if now - games[cid].get("last_activity", 0) > 300:
            try:
                context.bot.send_message(cid, "💤 Oyun 5 dakika hareketsiz kaldığı için sonlandırıldı.")
                end_game_logic(context, cid)
            except:
                if cid in games: del games[cid]

# --- MAIN ---
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Komutlar
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", lambda u, c: end_game_logic(c, u.effective_chat.id)))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("duyuru", duyuru))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("wordcount", word_count))

    # Callback ve Mesajlar
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))
    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))

    # JOB QUEUE (OTOMATİK KONTROL) - Burası önemli!
    updater.job_queue.run_repeating(auto_stop_check, interval=60)

    updater.start_polling()
    updater.idle()

# Eksik fonksiyonları (mode_select, game_buttons, eniyiler) önceki koddan koru...
# (Kodun geri kalanı aynıdır)

if __name__ == "__main__":
    main()
