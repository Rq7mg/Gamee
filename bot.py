import os
import time
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

# --- LOGGING (Hataları görmek için önemli) ---
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
    logger.info("MongoDB bağlantısı başarılı.")
except Exception as e:
    logger.error(f"MongoDB Bağlantı Hatası: {e}")

# --- GLOBAL DEĞİŞKENLER ---
sudo_users = set([OWNER_ID])
games = {}       # Aktif oyun verileri
pending_dm = {}  # Özel kelime yazacak kullanıcıların takibi

# --- YARDIMCI FONKSİYONLAR ---

def tr_upper(text):
    """Türkçe karakter uyumlu büyük harf çevirici."""
    if not text: return ""
    replacements = {"i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", "ş": "Ş", "ö": "Ö", "ç": "Ç"}
    text = text.lower()
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.upper()

def escape_md(text):
    """MarkdownV2 için kaçış karakterleri."""
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
        if doc:
            return doc[0]["word"], doc[0]["hint"]
        return "kelime yok", "veritabanı boş"
    except Exception as e:
        logger.error(f"Kelime seçme hatası: {e}")
        return "hata", "hata"

# --- OYUN ARAYÜZÜ ---

def send_game_ui(context, chat_id, text_prefix=""):
    """Oyun durumuna göre butonları ve mesajı gönderir."""
    if chat_id not in games: return
    game_data = games[chat_id]
    
    # 1. DURUM: Anlatıcı Yok (Sıra salındı veya oyun yeni başladı)
    if game_data.get("waiting_for_volunteer"):
        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]
        msg = f"{text_prefix}\n⚠️ *Anlatıcı sırasını saldı\\!*\nKim anlatmak ister?"
        try:
            context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
        except:
            # Markdown hatası olursa düz metin at
            context.bot.send_message(chat_id, msg.replace("*","").replace("\\",""), reply_markup=InlineKeyboardMarkup(kb))
        return

    # 2. DURUM: Aktif Oyun (Anlatıcı Var)
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

    # Dinamik moddaysa "Sıramı Sal" butonu ekle
    if game_data["sub_mode"] == "dynamic":
        kb.append([InlineKeyboardButton("❌ Sıramı Sal", callback_data="btn_pass")])

    msg = f"{text_prefix}\n🗣 Anlatıcı: *{escape_md(name)}*"
    
    try:
        context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
    except:
        context.bot.send_message(chat_id, msg.replace("*", "").replace("\\", ""), reply_markup=InlineKeyboardMarkup(kb))

# --- BOT HANDLERS (İŞLEYİCİLER) ---

def start(update, context):
    user_id = update.effective_user.id
    # Deep Linking kontrolü (Özel kelime yazma linki)
    if context.args and context.args[0].startswith("writeword_"):
        try:
            target_chat_id = int(context.args[0].split("_")[1])
            pending_dm[user_id] = target_chat_id
            update.message.reply_text("✍️ Anlatacağınız kelimeyi şimdi bu sohbete yazın.")
        except:
            update.message.reply_text("❌ Hatalı link.")
        return

    text = (
        "👋 Merhaba! Ben Gelişmiş Tabu Botu.\n\n"
        "🎮 /game - Oyunu başlat\n"
        "🛑 /stop - Oyunu bitir\n"
        "🏆 /eniyiler - Skor tablosu\n"
        "➕ *Beni Gruba Ekle butonuna basarak botu grubuna alabilirsin.*"
    )
    kb = [[InlineKeyboardButton("➕ Beni Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games:
        update.message.reply_text("⚠️ Oyun zaten devam ediyor!")
        return
    
    kb = [[InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),
           InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")]]
    update.message.reply_text("🎮 Oyun Modunu Seçin:", reply_markup=InlineKeyboardMarkup(kb))

def mode_select(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    data = query.data
    
    # Çift tıklama veya gecikme kontrolü
    if chat_id in games and not data.startswith("mode_text_"):
        query.answer("⚠️ Oyun zaten başlatıldı!", show_alert=True)
        try: query.message.delete()
        except: pass
        return
    
    query.answer()
    
    # Yazılı mod alt menüsü
    if data == "mode_text_pre":
        kb = [[InlineKeyboardButton("👤 Sabit Anlatıcı", callback_data="mode_text_fixed"),
               InlineKeyboardButton("🔄 Değişken Anlatıcı", callback_data="mode_text_dynamic")]]
        query.edit_message_text("⌨️ Yazılı Mod: Anlatıcı Tipi Seçin", reply_markup=InlineKeyboardMarkup(kb))
        return
        
    # Oyun başlatma
    word, hint = pick_word()
    
    mode = "voice" if data == "mode_voice" else "text"
    sub_mode = "dynamic" if data == "mode_text_dynamic" else "fixed"
    
    games[chat_id] = {
        "active": True,
        "mode": mode,
        "sub_mode": sub_mode,
        "narrator_id": query.from_user.id,
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
    
    if chat_id not in games:
        query.answer("Oyun bulunamadı.", show_alert=True)
        try: query.message.delete()
        except: pass
        return

    game_data = games[chat_id]
    game_data["last_activity"] = time.time()

    # --- BUTTON: GÖNÜLLÜ OL ---
    if query.data == "btn_volunteer":
        if not game_data.get("waiting_for_volunteer"): 
            query.answer("Zaten bir anlatıcı var!", show_alert=True)
            return
        
        game_data.update({
            "narrator_id": user_id, 
            "waiting_for_volunteer": False, 
            "hint_used": False
        })
        game_data["current_word"], game_data["current_hint"] = pick_word()
        
        query.answer("✅ Yeni anlatıcı sensin!", show_alert=True)
        try: query.message.delete() 
        except: pass
        
        send_game_ui(context, chat_id, f"🔄 Yeni anlatıcı: *{escape_md(query.from_user.first_name)}*")
        return

    # --- ANLATICI KONTROLÜ ---
    # Gönüllü butonu dışındaki butonlara sadece anlatıcı basabilir
    if user_id != game_data["narrator_id"]:
        query.answer("❌ Sadece anlatıcı basabilir!", show_alert=True)
        return

    # --- BUTTON: KELİMEYİ GÖR ---
    if query.data == "btn_look":
        query.answer(f"🎯 KELİME: {tr_upper(game_data['current_word'])}\n📌 İPUCU: {game_data['current_hint']}", show_alert=True)
    
    # --- BUTTON: İPUCU VER ---
    elif query.data == "btn_hint":
        if game_data.get("hint_used"):
            query.answer("⚠️ İpucu zaten kullanıldı!", show_alert=True)
            return
        
        word = game_data['current_word']
        # İlk harfi göster, kalanı çizgi
        display_hint = tr_upper(word[0]) + " " + "_ " * (len(word) - 1)
        game_data["hint_used"] = True
        
        query.answer("💡 İpucu paylaşıldı!", show_alert=True)
        # Hata riskini önlemek için Markdown KULLANMADAN gönderiyoruz
        context.bot.send_message(chat_id=chat_id, text=f"💡 İpucu Geldi: {display_hint}\n(Bu kelime artık 0.5 puan!)")
        
    # --- BUTTON: DEĞİŞTİR (PAS) ---
    elif query.data == "btn_next":
        game_data["current_word"], game_data["current_hint"] = pick_word()
        game_data["hint_used"] = False
        query.answer(f"✅ Değişti!\n🎯 YENİ: {tr_upper(game_data['current_word'])}", show_alert=True)
        
    # --- BUTTON: SIRAMI SAL ---
    elif query.data == "btn_pass":
        game_data.update({
            "waiting_for_volunteer": True, 
            "narrator_id": None, 
            "hint_used": False
        })
        query.answer("Sıranı saldın!", show_alert=True)
        
        # Eski kontrol panelini sil
        try: query.message.delete()
        except: pass
        
        # Yeni arayüzü çağır (Waiting=True olduğu için Gönüllü butonu atacak)
        send_game_ui(context, chat_id, )

def guess_handler(update, context):
    user = update.message.from_user
    chat_id = update.message.chat.id
    text = update.message.text.strip()

    # --- DM (ÖZEL MESAJ) İLE KELİME BELİRLEME ---
    if update.message.chat.type == "private":
        if user.id in pending_dm:
            target_chat_id = pending_dm[user.id]
            # Güvenlik Kontrolü: Kullanıcı gerçekten o grubun anlatıcısı mı?
            if target_chat_id in games:
                current_game = games[target_chat_id]
                if current_game.get("narrator_id") == user.id:
                    current_game.update({
                        "current_word": text.lower(), 
                        "current_hint": "Özel Belirlendi", 
                        "hint_used": False
                    })
                    context.bot.send_message(user.id, f"✅ Kelime başarıyla ayarlandı: {text}")
                else:
                    context.bot.send_message(user.id, "❌ Şu an bu grupta anlatıcı siz değilsiniz.")
            
            pending_dm.pop(user.id, None)
        return

    # --- GRUP İÇİ TAHMİN MANTIĞI ---
    if chat_id not in games: return
    game_data = games[chat_id]
    
    # Gönüllü bekleniyorsa veya anlatan kişi yazdıysa işlem yapma
    if game_data.get("waiting_for_volunteer") or user.id == game_data["narrator_id"]: 
        return

    # Doğru Tahmin Kontrolü
    if text.lower() == game_data["current_word"].lower():
        # Puanlama
        point = 0.5 if game_data.get("hint_used") else 1.0
        
        # Skoru kaydet
        full_key = f"{user.first_name}::{user.id}"
        game_data["scores"][full_key] = game_data["scores"].get(full_key, 0) + point
        
        # Veritabanı güncelle
        try:
            scores_col.update_one(
                {"user_id": user.id}, 
                {"$inc": {"score": point}, "$set": {"name": user.first_name}}, 
                upsert=True
            )
        except Exception as e:
            logger.error(f"Skor DB hatası: {e}")

        # Kazanma Mesajı
        msg = f"🎉 *{escape_md(user.first_name)}* bildi\\! (+{point} Puan)\nKelime: *{tr_upper(game_data['current_word'])}*"
        
        # Dinamik mod ise anlatıcıyı değiştir
        if game_data["sub_mode"] == "dynamic": 
            game_data["narrator_id"] = user.id
            msg += "\n🔄 *Anlatıcı Değişti!*"
        
        # Yeni kelime seç
        new_w, new_h = pick_word()
        game_data.update({
            "current_word": new_w, 
            "current_hint": new_h, 
            "hint_used": False, 
            "last_activity": time.time()
        })
        
        send_game_ui(context, chat_id, msg)

def stop(update, context):
    """Oyunu durdurur."""
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    
    if chat_id not in games:
        update.message.reply_text("❌ Aktif bir oyun yok.")
        return

    # Yetki Kontrolü
    is_auth = False
    if user_id == OWNER_ID: is_auth = True
    else:
        try:
            member = context.bot.get_chat_member(chat_id, user_id)
            if member.status in ['creator', 'administrator']: is_auth = True
        except: pass
    
    if not is_auth:
        update.message.reply_text("❌ Sadece yöneticiler oyunu durdurabilir.")
        return

    end_game_logic(context, chat_id)

def end_game_logic(context, chat_id):
    """Oyun bitirme ve puan tablosu gösterme."""
    if chat_id not in games: return
    game_data = games[chat_id]
    
    text = "🏁 *OYUN BİTTİ - PUAN DURUMU*\n\n"
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_scores:
        text += "Kimse puan alamadı."
    else:
        for idx, (key, score) in enumerate(sorted_scores, 1):
            name = key.split("::")[0]
            text += f"{idx}\\. {escape_md(name)}: {score} puan\n"
            
    try: context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)
    except: context.bot.send_message(chat_id, text.replace("*","").replace("\\",""))
    
    del games[chat_id]

def eniyiler(update, context):
    """Global skor tablosu."""
    try:
        top = list(scores_col.find().sort("score", -1).limit(15))
        if not top:
            update.message.reply_text("📭 Henüz veri yok.")
            return

        msg = "🏆 *TÜM ZAMANLARIN EN İYİLERİ*\n\n"
        for i, u in enumerate(top, 1):
            msg += f"{i}\\. {escape_md(u.get('name','Bilinmiyor'))}: {u.get('score',0)} p\n"
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        update.message.reply_text(f"Hata oluştu: {e}")

# --- ADMIN KOMUTLARI ---

def add_sudo(update, context):
    if update.message.from_user.id == OWNER_ID:
        try: 
            sudo_users.add(int(context.args[0]))
            update.message.reply_text("✅ Sudo eklendi.")
        except: 
            update.message.reply_text("❌ ID giriniz.")

def add_word(update, context):
    if update.message.from_user.id in sudo_users:
        try:
            t = " ".join(context.args)
            if "-" in t:
                w, h = map(str.strip, t.split("-", 1))
            else:
                w, h = t.strip(), ""
            
            words_col.update_one(
                {"word": w.lower()}, 
                {"$set": {"hint": h}}, 
                upsert=True
            )
            update.message.reply_text(f"✅ Eklendi: {w}")
        except:
            update.message.reply_text("❌ Format: /addword kelime - ipucu")

def auto_stop_check(context):
    """Hareketsiz oyunları temizler (5 dakika)."""
    now = time.time()
    # Listeyi kopyalayarak dönüyoruz çünkü döngü içinde silme yapacağız
    for cid in list(games.keys()):
        if now - games[cid]["last_activity"] > 300:
            try:
                context.bot.send_message(cid, "💤 Oyun hareketsizlik nedeniyle sonlandırıldı.")
                end_game_logic(context, cid)
            except:
                # Bot gruptan atıldıysa sessizce sil
                del games[cid]

# --- MAIN ---

def main():
    if not TOKEN:
        print("HATA: BOT_TOKEN bulunamadı!")
        return

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Komutlar
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("addsudo", add_sudo))
    dp.add_handler(CommandHandler("addword", add_word))

    # Butonlar ve Mesajlar
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))
    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))

    # Otomatik Durdurma Görevi (Her 60 saniyede bir kontrol eder)
    updater.job_queue.run_repeating(auto_stop_check, interval=60)

    print("Bot çalışıyor...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main() 
