import os
import time
import logging
import re
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
    users_col = db["users"]  
    logger.info("MongoDB bağlantısı başarılı.")
except Exception as e:
    logger.error(f"MongoDB Bağlantı Hatası: {e}")

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
    if not text: return ""
    text = str(text)
    for c in r'_*[]()~`>#+-=|{}.!':
        text = text.replace(c, f"\\{c}")
    return text

def pick_word():
    try:
        pipeline = [{"$sample": {"size": 1}}]
        doc = list(words_col.aggregate(pipeline))
        if doc: return doc[0]["word"], doc[0]["hint"]
        return "kitap", "okunan nesne"
    except:
        return "hata", "hata"

def register_stats(update):
    try:
        chat = update.effective_chat
        user = update.effective_user
        if chat and chat.type in ["group", "supergroup"]:
            chats_col.update_one({"chat_id": chat.id}, {"$set": {"title": chat.title}}, upsert=True)
        if user:
            users_col.update_one({"user_id": user.id}, {"$set": {"name": user.first_name}}, upsert=True)
    except: pass

# --- OYUN BİTİŞ MANTIĞI (Sonuçları Gösteren Kısım) ---

def end_game_logic(context, chat_id):
    """Oyun bittiğinde o ana kadarki puanları tablo olarak atar."""
    if chat_id not in games: return
    game_data = games[chat_id]
    
    text = "🏁 *OYUN BİTTİ - OTURUM SKORLARI*\n\n"
    # Skorları büyüklüğe göre sırala
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_scores:
        text += "Bu turda kimse puan alamadı\\."
    else:
        for idx, (key, score) in enumerate(sorted_scores, 1):
            name = key.split("::")[0]
            text += f"{idx}\\. *{escape_md(name)}*: `{score}` puan\n"
    
    try:
        context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)
    except:
        context.bot.send_message(chat_id, text.replace("*","").replace("`",""))
    
    del games[chat_id]

# --- OYUN ARAYÜZÜ ---

def send_game_ui(context, chat_id, text_prefix=""):
    if chat_id not in games: return
    game_data = games[chat_id]
    
    if game_data.get("waiting_for_volunteer"):
        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]
        msg = f"{text_prefix}\n⚠️ *Anlatıcı sırasını saldı\\!*\nKim anlatmak ister?"
        context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
        return

    try:
        user_info = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user
        name = user_info.first_name
    except: name = "Bilinmiyor"

    kb = [[InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="btn_look"),
           InlineKeyboardButton("💡 İpucu Ver", callback_data="btn_hint")],
          [InlineKeyboardButton("➡️ Değiştir", callback_data="btn_next"),
           InlineKeyboardButton("✍️ Özel Kelime Yaz", url=f"https://t.me/{context.bot.username}?start=writeword_{chat_id}")]]
    
    if game_data["sub_mode"] == "dynamic":
        kb.append([InlineKeyboardButton("❌ Sıramı Sal", callback_data="btn_pass")])

    msg = f"{text_prefix}\n🗣 Anlatıcı: *{escape_md(name)}*"
    context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)

# --- KOMUTLAR ---

def stop(update, context):
    """Oyunu durdurur ve o turun sonuçlarını gösterir."""
    chat_id = update.effective_chat.id
    if chat_id not in games:
        update.message.reply_text("❌ Zaten aktif bir oyun yok.")
        return
    
    # Oyun bitirme fonksiyonunu çağır (Bu fonksiyon sonuçları gösterir)
    end_game_logic(context, chat_id)

def eniyiler(update, context):
    """MongoDB'den genel skorları çeker."""
    register_stats(update)
    try:
        # Puanları 'score' alanına göre büyükten küçüğe diz
        top = list(scores_col.find().sort("score", -1).limit(10))
        if not top:
            return update.message.reply_text("📭 Henüz veritabanında skor kaydı yok.")
        
        msg = "🏆 *GENEL EN İYİLER (TOP 10)*\n\n"
        for i, u in enumerate(top, 1):
            name = u.get('name', 'Bilinmiyor')
            score = u.get('score', 0)
            msg += f"{i}\\. *{escape_md(name)}*: `{score}` Puan\n"
        
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        logger.error(f"Eniyiler Hatası: {e}")
        update.message.reply_text("❌ Skor tablosuna şu an ulaşılamıyor.")

def stats(update, context):
    if update.effective_user.id not in sudo_users: return
    g_count = chats_col.count_documents({})
    u_count = users_col.count_documents({})
    update.message.reply_text(f"📊 *Bot Durumu*\n\n🏘 Grup: {g_count}\n👤 Kullanıcı: {u_count}\n🎮 Aktif Oyun: {len(games)}", parse_mode=ParseMode.MARKDOWN)

def duyuru(update, context):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.reply_to_message
    if not msg: return update.message.reply_text("Mesajı yanıtlayın!")
    all_chats = list(chats_col.find({}))
    count = 0
    for c in all_chats:
        try:
            context.bot.copy_message(chat_id=c['chat_id'], from_chat_id=update.effective_chat.id, message_id=msg.message_id)
            count += 1
            time.sleep(0.05)
        except: pass
    update.message.reply_text(f"✅ {count} gruba iletildi.")

# --- HANDLERS (Orijinal Yapı) ---

def mode_select(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    if chat_id in games and not query.data.startswith("mode_text_"):
        query.answer("Oyun zaten sürüyor.")
        return
    
    query.answer()
    if query.data == "mode_text_pre":
        kb = [[InlineKeyboardButton("👤 Sabit", callback_data="mode_text_fixed"),
               InlineKeyboardButton("🔄 Değişken", callback_data="mode_text_dynamic")]]
        query.edit_message_text("⌨️ Anlatıcı Tipi Seçin:", reply_markup=InlineKeyboardMarkup(kb))
        return

    word, hint = pick_word()
    games[chat_id] = {
        "narrator_id": query.from_user.id,
        "sub_mode": "dynamic" if query.data == "mode_text_dynamic" else "fixed",
        "current_word": word,
        "current_hint": hint,
        "scores": {},
        "last_activity": time.time(),
        "waiting_for_volunteer": False,
        "hint_used": False
    }
    query.message.delete()
    send_game_ui(context, chat_id, "✅ Oyun Başladı!")

def guess_handler(update, context):
    if not update.message or not update.message.text: return
    user = update.message.from_user
    chat_id = update.message.chat.id
    clean_input = tr_upper(update.message.text.strip())

    if chat_id not in games: return
    game_data = games[chat_id]
    if game_data.get("waiting_for_volunteer") or user.id == game_data["narrator_id"]: return

    # ANALİZ: Kitaplık -> Kitap
    target_word = tr_upper(game_data["current_word"])
    if target_word in clean_input:
        point = 0.5 if game_data.get("hint_used") else 1.0
        key = f"{user.first_name}::{user.id}"
        game_data["scores"][key] = game_data["scores"].get(key, 0) + point
        
        # MongoDB Güncelleme
        scores_col.update_one({"user_id": user.id}, {"$inc": {"score": point}, "$set": {"name": user.first_name}}, upsert=True)
        
        msg = f"🎉 *{escape_md(user.first_name)}* bildi\\! (+{point} Puan)\nKelime: *{target_word}*"
        if game_data["sub_mode"] == "dynamic": game_data["narrator_id"] = user.id
        
        game_data.update({"current_word": pick_word()[0], "current_hint": pick_word()[1], "hint_used": False, "last_activity": time.time()})
        send_game_ui(context, chat_id, msg)

# (Diğer start, game_buttons vb. fonksiyonlar orijinal haliyle kalmalı)
def start(update, context):
    register_stats(update)
    update.message.reply_text("👋 Tabu Botu Aktif!\n/game - Başlat\n/eniyiler - Genel Skor")

def game(update, context):
    if update.effective_chat.id in games:
        update.message.reply_text("⚠️ Oyun zaten sürüyor.")
        return
    kb = [[InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),
           InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")]]
    update.message.reply_text("🎮 Mod Seçin:", reply_markup=InlineKeyboardMarkup(kb))

def game_buttons(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    if chat_id not in games: return
    game_data = games[chat_id]
    game_data["last_activity"] = time.time()

    if query.data == "btn_volunteer":
        game_data.update({"narrator_id": query.from_user.id, "waiting_for_volunteer": False})
        query.message.delete()
        send_game_ui(context, chat_id, f"🔄 Anlatıcı: {query.from_user.first_name}")
    elif query.data == "btn_look" and query.from_user.id == game_data["narrator_id"]:
        query.answer(f"🎯 KELİME: {tr_upper(game_data['current_word'])}", show_alert=True)
    # ... (Diğer buton mantıkları aynı kalacak)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("duyuru", duyuru))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))
    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
