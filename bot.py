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
    chats_col = db["chats"]  # Duyuru ve stats için
    users_col = db["users"]  # Stats için
    logger.info("MongoDB bağlantısı başarılı.")
except Exception as e:
    logger.error(f"MongoDB Bağlantı Hatası: {e}")

# --- GLOBAL DEĞİŞKENLER ---
sudo_users = set([OWNER_ID])
games = {}       
pending_dm = {}  

# --- YARDIMCI FONKSİYONLAR ---

def tr_upper(text):
    """Senin orijinal Türkçe karakter uyumlu fonksiyonun."""
    if not text: return ""
    replacements = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
    text = text.lower()
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.upper()

def escape_md(text):
    """Botun 'gitmesini' engelleyen en kritik parça: Karakter kaçırıcı."""
    if not text: return ""
    text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for c in escape_chars:
        text = text.replace(c, f"\\{c}")
    return text

def pick_word():
    """Veritabanından rastgele kelime çeker."""
    try:
        pipeline = [{"$sample": {"size": 1}}]
        doc = list(words_col.aggregate(pipeline))
        if doc: return doc[0]["word"], doc[0]["hint"]
        return "kitap", "okunan nesne"
    except: return "hata", "hata"

def db_kayit(update):
    """Duyuru ve Stats için arka planda sessizce kayıt yapar."""
    try:
        cid = update.effective_chat.id
        uid = update.effective_user.id
        if update.effective_chat.type in ["group", "supergroup"]:
            chats_col.update_one({"chat_id": cid}, {"$set": {"title": update.effective_chat.title}}, upsert=True)
        users_col.update_one({"user_id": uid}, {"$set": {"name": update.effective_user.first_name}}, upsert=True)
    except: pass

# --- OYUN ARAYÜZÜ (Senin Orijinal Yapın) ---

def send_game_ui(context, chat_id, text_prefix=""):
    if chat_id not in games: return
    game_data = games[chat_id]
    
    if game_data.get("waiting_for_volunteer"):
        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]
        msg = f"{text_prefix}\n⚠️ *Anlatıcı sırasını saldı\\!*\nKim anlatmak ister?"
        try: context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
        except: context.bot.send_message(chat_id, msg.replace("*","").replace("\\",""), reply_markup=InlineKeyboardMarkup(kb))
        return

    try:
        user_info = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user
        name = user_info.first_name
    except: name = "Bilinmiyor"

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

# --- KOMUTLAR ---

def start(update, context):
    db_kayit(update)
    user_id = update.effective_user.id
    if context.args and context.args[0].startswith("writeword_"):
        try:
            target_chat_id = int(context.args[0].split("_")[1])
            pending_dm[user_id] = target_chat_id
            update.message.reply_text("✍️ Kelimeyi buraya yazın.")
        except: pass
        return
    update.message.reply_text("🎮 /game yazarak oyunu başlatabilirsin!")

def game(update, context):
    db_kayit(update)
    chat_id = update.effective_chat.id
    if chat_id in games:
        update.message.reply_text("⚠️ Oyun zaten sürüyor.")
        return
    kb = [[InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),
           InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")]]
    update.message.reply_text("🎮 Mod Seçin:", reply_markup=InlineKeyboardMarkup(kb))

# --- YENİ EKLENEN ÖZELLİKLER ---

def eniyiler(update, context):
    """Genel En İyiler (Global)"""
    try:
        top = list(scores_col.find().sort("score", -1).limit(10))
        if not top: return update.message.reply_text("Liste boş.")
        msg = "🏆 *TÜM ZAMANLARIN EN İYİLERİ*\n\n"
        for i, u in enumerate(top, 1):
            msg += f"{i}\\. {escape_md(u.get('name'))}: {u.get('score')} p\n"
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except: update.message.reply_text("Skorlar yüklenemedi.")

def stats(update, context):
    """Bot İstatistikleri"""
    if update.effective_user.id not in sudo_users: return
    g_count = chats_col.count_documents({})
    u_count = users_col.count_documents({})
    update.message.reply_text(f"📊 *İstatistikler*\n\n🏘 Grup: {g_count}\n👤 Kullanıcı: {u_count}\n🎮 Oyun: {len(games)}", parse_mode=ParseMode.MARKDOWN)

def duyuru(update, context):
    """Duyuru Mesajı"""
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.reply_to_message
    if not msg: return update.message.reply_text("Mesajı yanıtlayın!")
    chats = list(chats_col.find({}))
    for c in chats:
        try: context.bot.copy_message(chat_id=c['chat_id'], from_chat_id=update.effective_chat.id, message_id=msg.message_id)
        except: pass
    update.message.reply_text("✅ Gönderildi.")

# --- CALLBACKS (Senin Orijinal Akışın) ---

def mode_select(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    if chat_id in games and not query.data.startswith("mode_text_"):
        query.answer("Oyun zaten başladı.")
        return
    
    query.answer()
    if query.data == "mode_text_pre":
        kb = [[InlineKeyboardButton("👤 Sabit", callback_data="mode_text_fixed"),
               InlineKeyboardButton("🔄 Değişken", callback_data="mode_text_dynamic")]]
        query.edit_message_text("⌨️ Anlatıcı Tipi:", reply_markup=InlineKeyboardMarkup(kb))
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
    try: query.message.delete()
    except: pass
    send_game_ui(context, chat_id, "✅ Oyun Başladı!")

def game_buttons(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    if chat_id not in games: return
    
    game_data = games[chat_id]
    game_data["last_activity"] = time.time()

    if query.data == "btn_volunteer":
        game_data.update({"narrator_id": user_id, "waiting_for_volunteer": False, "hint_used": False})
        game_data["current_word"], game_data["current_hint"] = pick_word()
        try: query.message.delete()
        except: pass
        send_game_ui(context, chat_id, f"🔄 Yeni anlatıcı: *{escape_md(query.from_user.first_name)}*")
        return

    if user_id != game_data["narrator_id"]:
        query.answer("❌ Sadece anlatıcı basabilir!", show_alert=True)
        return

    if query.data == "btn_look":
        query.answer(f"🎯 KELİME: {tr_upper(game_data['current_word'])}\n📌 İPUCU: {game_data['current_hint']}", show_alert=True)
    elif query.data == "btn_hint":
        if game_data.get("hint_used"): return query.answer("Kullanıldı!")
        word = game_data['current_word']
        game_data["hint_used"] = True
        context.bot.send_message(chat_id, f"💡 İpucu: {tr_upper(word[0])} " + "_ " * (len(word) - 1))
    elif query.data == "btn_next":
        game_data["current_word"], game_data["current_hint"] = pick_word()
        game_data["hint_used"] = False
        query.answer("Kelime Değişti", show_alert=True)
    elif query.data == "btn_pass":
        game_data.update({"waiting_for_volunteer": True, "narrator_id": None})
        try: query.message.delete()
        except: pass
        send_game_ui(context, chat_id)

def guess_handler(update, context):
    if not update.message or not update.message.text: return
    user = update.message.from_user
    chat_id = update.message.chat.id
    raw_text = update.message.text
    
    # KİTAP -> KİTAPLIK tespiti için analiz
    clean_input = tr_upper(raw_text)

    if update.message.chat.type == "private" and user.id in pending_dm:
        target = pending_dm[user.id]
        if target in games:
            games[target].update({"current_word": raw_text, "current_hint": "Özel", "hint_used": False})
            update.message.reply_text(f"✅ Ayarlandı: {raw_text}")
        pending_dm.pop(user.id, None)
        return

    if chat_id not in games: return
    game_data = games[chat_id]
    if game_data.get("waiting_for_volunteer") or user.id == game_data["narrator_id"]: return

    # --- KİTAPLIK -> KİTAP ANALİZİ ---
    target_word = tr_upper(game_data["current_word"])
    if target_word in clean_input:
        point = 0.5 if game_data.get("hint_used") else 1.0
        key = f"{user.first_name}::{user.id}"
        game_data["scores"][key] = game_data["scores"].get(key, 0) + point
        scores_col.update_one({"user_id": user.id}, {"$inc": {"score": point}, "$set": {"name": user.first_name}}, upsert=True)
        
        msg = f"🎉 *{escape_md(user.first_name)}* bildi\\! (+{point})\nKelime: *{target_word}*"
        if game_data["sub_mode"] == "dynamic": game_data["narrator_id"] = user.id
        
        game_data.update({"current_word": pick_word()[0], "current_hint": pick_word()[1], "hint_used": False, "last_activity": time.time()})
        send_game_ui(context, chat_id, msg)

def stop(update, context):
    chat_id = update.effective_chat.id
    if chat_id not in games: return
    
    # SONUÇLARI GÖSTER (Senin ilk kodunda eksik olan kısım)
    game_data = games[chat_id]
    text = "🏁 *OYUN BİTTİ - PUANLAR*\n\n"
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
    if not sorted_scores: text += "Puan alan olmadı."
    else:
        for idx, (k, s) in enumerate(sorted_scores, 1):
            text += f"{idx}\\. {escape_md(k.split('::')[0])}: {s} p\n"
    
    try: update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN_V2)
    except: update.message.reply_text(text.replace("*","").replace("\\",""))
    del games[chat_id]

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
