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
    """Türkçe karakterlere uyumlu büyük harf dönüşümü (i -> İ, ı -> I)"""
    if not text: return ""
    text = str(text).strip()
    replacements = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
    lower_text = text.lower()
    for char, replacement in replacements.items():
        lower_text = lower_text.replace(char, replacement)
    return lower_text.upper()

def escape_md(text):
    if text is None: return ""
    text = str(text)
    # MarkdownV2 için kaçış yapılacak karakterler
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
    game_data["last_activity"] = time.time()
    
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
    update_chats(update.effective_chat.id)
    if context.args and context.args[0].startswith("writeword_"):
        try:
            target_chat_id = int(context.args[0].split("_")[1])
            pending_dm[user_id] = target_chat_id
            update.message.reply_text("✍️ Anlatacağınız kelimeyi şimdi buraya yazın.")
        except: pass
        return
    text = "👋 Tabu Botu!\n\n🎮 /game - Başlat\n🏆 /eniyiler - Skorlar"
    update.message.reply_text(text)

def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games:
        update.message.reply_text("⚠️ Oyun zaten devam ediyor!")
        return
    kb = [[InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),
           InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")]]
    update.message.reply_text("🎮 Mod Seçin:", reply_markup=InlineKeyboardMarkup(kb))

def eniyiler(update, context):
    try:
        top = list(scores_col.find().sort("score", -1).limit(15))
        if not top:
            return update.message.reply_text("📭 Henüz veri yok.")
        msg = "🏆 *TÜM ZAMANLARIN EN İYİLERİ*\n\n"
        for i, u in enumerate(top, 1):
            msg += f"{i}\\. {escape_md(u.get('name','Bilinmiyor'))}: {escape_md(u.get('score',0))} p\n"
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except: update.message.reply_text("Skorlar yüklenemedi.")

# --- ADMIN KOMUTLARI ---

def duyuru(update, context):
    if update.effective_user.id != OWNER_ID: return
    msg = update.message.reply_to_message
    if not msg: return update.message.reply_text("❌ Bir mesajı yanıtlayın.")
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
    update.message.reply_text(f"📊 Grup: {total}\n🎮 Aktif: {len(games)}")

def word_count(update, context):
    if update.effective_user.id not in sudo_users: return
    update.message.reply_text(f"📚 Toplam Kelime: {words_col.count_documents({})}")

def addword(update, context):
    if update.effective_user.id not in sudo_users: return
    try:
        content = " ".join(context.args)
        word, hint = (map(str.strip, content.split("-", 1))) if "-" in content else (content.strip(), "İpucu yok")
        words_col.update_one({"word": word.lower()}, {"$set": {"hint": hint}}, upsert=True)
        update.message.reply_text(f"✅ Eklendi: {tr_upper(word)}")
    except: update.message.reply_text("Format: /addword kelime - ipucu")

def addsudo(update, context):
    if update.effective_user.id != OWNER_ID: return
    try:
        new_id = int(context.args[0])
        sudo_users.add(new_id)
        update.message.reply_text(f"✅ {new_id} eklendi.")
    except: update.message.reply_text("Kullanım: /addsudo ID")

# --- OYUN MANTIĞI ---

def end_game_logic(context, chat_id):
    if chat_id not in games: return
    game_data = games[chat_id]
    text = "🏁 *OYUN BİTTİ - PUAN DURUMU*\n\n"
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
    if not sorted_scores: text += "Kimse puan alamadı."
    else:
        for idx, (key, score) in enumerate(sorted_scores, 1):
            name = key.split("::")[0]
            text += f"{idx}\\. {escape_md(name)}: {escape_md(score)} p\n"
    try: context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)
    except: context.bot.send_message(chat_id, "Oyun bitti, puanlar gönderilemedi.")
    if chat_id in games: del games[chat_id]

def mode_select(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    if chat_id in games and not query.data.startswith("mode_text_"):
        return query.answer("Zaten oyun var.", show_alert=True)
    query.answer()
    if query.data == "mode_text_pre":
        kb = [[InlineKeyboardButton("👤 Sabit", callback_data="mode_text_fixed"),
               InlineKeyboardButton("🔄 Değişken", callback_data="mode_text_dynamic")]]
        query.edit_message_text("⌨️ Anlatıcı Tipi:", reply_markup=InlineKeyboardMarkup(kb))
        return
    w, h = pick_word()
    games[chat_id] = {"narrator_id": query.from_user.id, "sub_mode": "dynamic" if query.data=="mode_text_dynamic" else "fixed", "current_word": w, "current_hint": h, "scores": {}, "last_activity": time.time(), "waiting_for_volunteer": False, "hint_used": False}
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
        game_data.update({"narrator_id": user_id, "waiting_for_volunteer": False, "hint_used": False})
        game_data["current_word"], game_data["current_hint"] = pick_word()
        query.message.delete()
        send_game_ui(context, chat_id, f"🔄 Anlatıcı: {query.from_user.first_name}")
    elif user_id == game_data["narrator_id"]:
        if query.data == "btn_look":
            query.answer(f"🎯 KELİME: {tr_upper(game_data['current_word'])}\n📌 İPUCU: {game_data['current_hint']}", show_alert=True)
        elif query.data == "btn_hint" and not game_data["hint_used"]:
            game_data["hint_used"] = True
            display = tr_upper(game_data['current_word'][0]) + " " + "_ " * (len(game_data['current_word']) - 1)
            context.bot.send_message(chat_id, f"💡 İpucu: {display}")
        elif query.data == "btn_next":
            game_data["current_word"], game_data["current_hint"] = pick_word()
            game_data["hint_used"] = False
            query.answer(f"Kelime: {tr_upper(game_data['current_word'])}", show_alert=True)
        elif query.data == "btn_pass":
            game_data.update({"waiting_for_volunteer": True, "narrator_id": None})
            query.message.delete()
            send_game_ui(context, chat_id)

def guess_handler(update, context):
    """Gelen tüm mesajları işler (komutlar dahil). Metin mesajı değilse veya komutsa uygun şekilde elenir."""
    # Sadece metin mesajlarını işle
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    chat_id = update.message.chat.id
    input_text = tr_upper(update.message.text)

    # --- ÖZEL MESAJ: Kelime ekleme (pending_dm) ---
    if update.message.chat.type == "private" and user.id in pending_dm:
        target_chat_id = pending_dm[user.id]
        # Hedef grupta oyun var mı ve gönderen kişi anlatıcı mı kontrol et
        if target_chat_id in games and games[target_chat_id]["narrator_id"] == user.id:
            games[target_chat_id].update({
                "current_word": input_text,  # input_text zaten tr_upper ile büyük harfli
                "current_hint": "Özel",
                "hint_used": False,
                "last_activity": time.time()
            })
            update.message.reply_text(f"✅ Kelime ayarlandı: {input_text}")
        else:
            update.message.reply_text("❌ Oyun bulunamadı veya siz anlatıcı değilsiniz.")
        # İşlem bitti, pending kaydını temizle
        pending_dm.pop(user.id, None)
        return

    # --- GRUP MESAJI: Oyun tahmini ---
    if chat_id not in games:
        return  # Oyun yoksa hiçbir şey yapma

    game_data = games[chat_id]

    # Anlatıcı veya gönüllü bekleniyorsa tahminleri işleme
    if game_data.get("waiting_for_volunteer") or user.id == game_data["narrator_id"]:
        return

    # Kelime tahmini kontrolü
    if input_text == tr_upper(game_data["current_word"]):
        point = 0.5 if game_data["hint_used"] else 1.0
        full_key = f"{user.first_name}::{user.id}"
        game_data["scores"][full_key] = game_data["scores"].get(full_key, 0) + point

        if scores_col:
            scores_col.update_one(
                {"user_id": user.id},
                {"$inc": {"score": point}, "$set": {"name": user.first_name}},
                upsert=True
            )

        msg = f"🎉 *{escape_md(user.first_name)}* bildi\\! (+{escape_md(point)} Puan)\nKelime: *{tr_upper(game_data['current_word'])}*"

        # Dinamik modda anlatıcıyı değiştir
        if game_data["sub_mode"] == "dynamic":
            game_data["narrator_id"] = user.id

        # Yeni kelime seç
        game_data["current_word"], game_data["current_hint"] = pick_word()
        game_data["hint_used"] = False

        # Arayüzü güncelle
        send_game_ui(context, chat_id, msg)

def auto_stop_check(context):
    now = time.time()
    for cid in list(games.keys()):
        if now - games[cid].get("last_activity", 0) > 300:  # 5 Dakika
            try:
                context.bot.send_message(cid, "💤 Oyun 5 dakika hareketsiz kaldığı için sonlandırıldı.")
                end_game_logic(context, cid)
            except:
                if cid in games: del games[cid]

# --- MAIN ---

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", lambda u, c: end_game_logic(c, u.effective_chat.id)))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("duyuru", duyuru))
    dp.add_handler(CommandHandler("stats", stats))
    dp.add_handler(CommandHandler("wordcount", word_count))
    dp.add_handler(CommandHandler("addword", addword))
    dp.add_handler(CommandHandler("addsudo", addsudo))

    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))
    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))

    # 🔧 DÜZELTME: Filters.all kullanarak tüm mesajları al, metin kontrolünü içeride yap
    dp.add_handler(MessageHandler(Filters.all, guess_handler))

    updater.job_queue.run_repeating(auto_stop_check, interval=60)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
