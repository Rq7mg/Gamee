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
    chats_col = db["chats"] # Grupları takip etmek için
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

# --- GRUP TAKİBİ ---
def update_chats(chat_id):
    if chats_col is not None:
        chats_col.update_one({"chat_id": chat_id}, {"$set": {"active": True}}, upsert=True)

# --- OYUN ARAYÜZÜ ---
def send_game_ui(context, chat_id, text_prefix=""):
    if chat_id not in games: return
    game_data = games[chat_id]
    update_chats(chat_id)
    
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

# --- KOMUTLAR ---

def start(update, context):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    update_chats(chat_id)

    if context.args and context.args[0].startswith("writeword_"):
        try:
            target_chat_id = int(context.args[0].split("_")[1])
            pending_dm[user_id] = target_chat_id
            update.message.reply_text("✍️ Anlatacağınız kelimeyi şimdi buraya yazın.")
        except:
            update.message.reply_text("❌ Hatalı link.")
        return

    text = "👋 Merhaba! Gelişmiş Tabu Botuna hoş geldin.\n\n🎮 /game - Oyunu başlat\n🛑 /stop - Oyunu bitir\n🏆 /eniyiler - Skor tablosu"
    kb = [[InlineKeyboardButton("➕ Beni Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

def game(update, context):
    chat_id = update.effective_chat.id
    update_chats(chat_id)
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
    if not msg:
        update.message.reply_text("❌ Duyuru yapmak için bir mesajı yanıtlayın: /duyuru")
        return

    chats = list(chats_col.find({"active": True}))
    success = 0
    fail = 0
    
    status_msg = update.message.reply_text(f"📢 Duyuru başladı... (Hedef: {len(chats)} grup)")
    
    for chat in chats:
        try:
            context.bot.copy_message(chat_id=chat['chat_id'], from_chat_id=update.effective_chat.id, message_id=msg.message_id)
            success += 1
            time.sleep(0.1) # Flood önlemi
        except:
            fail += 1
            
    status_msg.edit_text(f"✅ Duyuru Tamamlandı!\n\nBaşarılı: {success}\nBaşarısız: {fail}")

def stats(update, context):
    if update.effective_user.id not in sudo_users: return
    total_groups = chats_col.count_documents({})
    active_games = len(games)
    update.message.reply_text(f"📊 *Bot İstatistikleri*\n\n👥 Toplam Grup: {total_groups}\n🎮 Aktif Oyunlar: {active_games}", parse_mode=ParseMode.MARKDOWN)

def word_count(update, context):
    if update.effective_user.id not in sudo_users: return
    count = words_col.count_documents({})
    update.message.reply_text(f"📚 Veritabanında toplam *{count}* kelime bulunuyor.", parse_mode=ParseMode.MARKDOWN)

# --- OYUN MANTIĞI ---

def guess_handler(update, context):
    user = update.message.from_user
    chat_id = update.message.chat.id
    # Kelimeyi temizle (boşlukları sil, küçük harfe çevir)
    text = update.message.text.strip().lower()

    if update.message.chat.type == "private" and user.id in pending_dm:
        target_chat_id = pending_dm[user.id]
        if target_chat_id in games and games[target_chat_id].get("narrator_id") == user.id:
            games[target_chat_id].update({"current_word": text, "current_hint": "Özel Belirlendi", "hint_used": False})
            update.message.reply_text(f"✅ Kelime ayarlandı: {text.upper()}")
        pending_dm.pop(user.id, None)
        return

    if chat_id not in games: return
    game_data = games[chat_id]
    if game_data.get("waiting_for_volunteer") or user.id == game_data["narrator_id"]: return

    # Kelime Kontrolü (Tam eşleşme)
    if text == game_data["current_word"].strip().lower():
        point = 0.5 if game_data.get("hint_used") else 1.0
        full_key = f"{user.first_name}::{user.id}"
        game_data["scores"][full_key] = game_data["scores"].get(full_key, 0) + point
        
        if scores_col:
            scores_col.update_one({"user_id": user.id}, {"$inc": {"score": point}, "$set": {"name": user.first_name}}, upsert=True)

        msg = f"🎉 *{escape_md(user.first_name)}* bildi\\! (+{escape_md(point)} Puan)\nKelime: *{tr_upper(game_data['current_word'])}*"
        if game_data["sub_mode"] == "dynamic": 
            game_data["narrator_id"] = user.id
            msg += "\n🔄 *Anlatıcı Değişti!*"
        
        new_w, new_h = pick_word()
        game_data.update({"current_word": new_w, "current_hint": new_h, "hint_used": False, "last_activity": time.time()})
        send_game_ui(context, chat_id, msg)

# --- STANDART FONKSİYONLAR (Önceki koddan devam) ---
def mode_select(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    data = query.data
    if chat_id in games and not data.startswith("mode_text_"):
        query.answer("⚠️ Oyun zaten başlatıldı!", show_alert=True)
        return
    query.answer()
    if data == "mode_text_pre":
        kb = [[InlineKeyboardButton("👤 Sabit Anlatıcı", callback_data="mode_text_fixed"),
               InlineKeyboardButton("🔄 Değişken Anlatıcı", callback_data="mode_text_dynamic")]]
        query.edit_message_text("⌨️ Yazılı Mod: Anlatıcı Tipi Seçin", reply_markup=InlineKeyboardMarkup(kb))
        return
    word, hint = pick_word()
    games[chat_id] = {"active": True, "mode": "voice" if data=="mode_voice" else "text", "sub_mode": "dynamic" if data=="mode_text_dynamic" else "fixed", "narrator_id": query.from_user.id, "current_word": word, "current_hint": hint, "scores": {}, "last_activity": time.time(), "waiting_for_volunteer": False, "hint_used": False}
    query.message.delete()
    send_game_ui(context, chat_id, "✅ Oyun Başladı!")

def game_buttons(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    if chat_id not in games: return
    game_data = games[chat_id]
    game_data["last_activity"] = time.time()

    if query.data == "btn_volunteer":
        if not game_data.get("waiting_for_volunteer"): return
        game_data.update({"narrator_id": user_id, "waiting_for_volunteer": False, "hint_used": False})
        game_data["current_word"], game_data["current_hint"] = pick_word()
        query.message.delete()
        send_game_ui(context, chat_id, f"🔄 Yeni anlatıcı: *{escape_md(query.from_user.first_name)}*")
    elif user_id == game_data["narrator_id"]:
        if query.data == "btn_look":
            query.answer(f"🎯 KELİME: {tr_upper(game_data['current_word'])}\n📌 İPUCU: {game_data['current_hint']}", show_alert=True)
        elif query.data == "btn_hint":
            if not game_data.get("hint_used"):
                game_data["hint_used"] = True
                display = tr_upper(game_data['current_word'][0]) + " " + "_ " * (len(game_data['current_word']) - 1)
                context.bot.send_message(chat_id, f"💡 İpucu: {display}")
                query.answer("İpucu verildi")
        elif query.data == "btn_next":
            game_data["current_word"], game_data["current_hint"] = pick_word()
            game_data["hint_used"] = False
            query.answer(f"✅ Yeni Kelime: {tr_upper(game_data['current_word'])}", show_alert=True)
        elif query.data == "btn_pass":
            game_data.update({"waiting_for_volunteer": True, "narrator_id": None})
            query.message.delete()
            send_game_ui(context, chat_id)

def eniyiler(update, context):
    try:
        top = list(scores_col.find().sort("score", -1).limit(15))
        if not top:
            update.message.reply_text("📭 Henüz veri yok.")
            return
        msg = "🏆 *TÜM ZAMANLARIN EN İYİLERİ*\n\n"
        for i, u in enumerate(top, 1):
            msg += f"{i}\\. {escape_md(u.get('name','Bilinmiyor'))}: {escape_md(u.get('score',0))} p\n"
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except: update.message.reply_text("Skorlar yüklenemedi.")

def stop(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games:
        del games[chat_id]
        update.message.reply_text("🛑 Oyun sonlandırıldı.")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("duyuru", duyuru))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("wordcount", word_count))
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))
    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
