import os
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

# --- AYARLAR ---
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

# Veritabanı
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["tabu_bot"]
words_col = db["words"]
scores_col = db["scores"]

# Global Değişkenler
sudo_users = set([OWNER_ID])
games = {}
pending_dm = {}

# --- YARDIMCI FONKSİYONLAR ---

def tr_upper(text):
    """Türkçe karakterlere uygun büyük harf dönüşümü"""
    if not text: return ""
    replacements = {
        "i": "İ", "ı": "I", "ğ": "Ğ", "ü": "Ü", 
        "ş": "Ş", "ö": "Ö", "ç": "Ç"
    }
    text = text.lower()
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text.upper()

def escape_md(text):
    """Markdown V2 kaçış karakterleri"""
    if not text: return ""
    text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for c in escape_chars:
        text = text.replace(c, f"\\{c}")
    return text

def pick_word():
    """Rastgele kelime seçer"""
    pipeline = [{"$sample": {"size": 1}}]
    doc = list(words_col.aggregate(pipeline))
    if doc:
        return doc[0]["word"], doc[0]["hint"]
    return "kelime yok", "veritabanı boş"

# --- OYUN ARAYÜZÜ ---

def send_game_ui(context, chat_id, text_prefix=""):
    """Oyun mesajını ve butonlarını gönderir"""
    if chat_id not in games: return
    game_data = games[chat_id]
    
    # Eğer anlatıcı "Pas" dediyse ve gönüllü aranıyorsa arayüz farklı olur
    if game_data.get("waiting_for_volunteer"):
        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]
        msg = f"{text_prefix}\n⚠️ *Anlatıcı sırasını saldı\\!*\nKim anlatmak ister?"
        try:
            context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
        except:
            context.bot.send_message(chat_id, msg.replace("*","").replace("\\",""), reply_markup=InlineKeyboardMarkup(kb))
        return

    # Normal Oyun Arayüzü
    try:
        u = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user
        name = u.first_name
    except:
        name = "Bilinmiyor"

    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start=writeword_{chat_id}"

    # Butonlar
    kb = [
        [InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="btn_look")],
        [InlineKeyboardButton("➡️ Değiştir", callback_data="btn_next"),
         InlineKeyboardButton("✍️ Özel Kelime Yaz", url=deep_link)]
    ]

    # Sadece DEĞİŞKEN modda anlatıcıya PAS hakkı ver
    if game_data["sub_mode"] == "dynamic":
        kb.append([InlineKeyboardButton("❌ Sıramı Sal", callback_data="btn_pass")])

    msg = f"{text_prefix}\n🗣 Anlatıcı: *{escape_md(name)}*"
    
    try:
        context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
    except:
        context.bot.send_message(chat_id, msg.replace("*", "").replace("\\", ""), reply_markup=InlineKeyboardMarkup(kb))

# --- BOT HANDLERS ---

def start(update, context):
    user_id = update.effective_user.id
    if context.args and context.args[0].startswith("writeword_"):
        chat_id = int(context.args[0].split("_")[1])
        pending_dm[user_id] = target_chat = chat_id
        update.message.reply_text("✍️ Yeni anlatacağınız kelimeyi şimdi yazın.")
        return

    text = (
        "👋 Merhaba! Ben Gelişmiş Tabu Botu.\n\n"
        "🎮 /game - Oyunu başlat\n"
        "🛑 /stop - Oyunu bitir (Admin)\n"
        "🏆 /eniyiler - Global sıralama\n"
    )
    kb = [[InlineKeyboardButton("➕ Beni Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games:
        update.message.reply_text("⚠️ Oyun zaten devam ediyor! /stop ile durdurabilirsiniz.")
        return
    
    kb = [
        [InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),
         InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")]
    ]
    update.message.reply_text("🎮 Oyun Modunu Seçin:", reply_markup=InlineKeyboardMarkup(kb))

def mode_select(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    data = query.data

    # KRİTİK DÜZELTME: Eğer oyun zaten kurulduysa (başka bir butona basıldıysa) işlemi iptal et
    if chat_id in games:
        query.answer("⚠️ Oyun zaten başlatıldı!", show_alert=True)
        try:
            query.message.delete()
        except:
            pass
        return

    query.answer()

    if data == "mode_text_pre":
        kb = [
            [InlineKeyboardButton("👤 Sabit Anlatıcı", callback_data="mode_text_fixed"),
             InlineKeyboardButton("🔄 Değişken Anlatıcı", callback_data="mode_text_dynamic")]
        ]
        query.edit_message_text("⌨️ Yazılı Mod: Anlatıcı Tipi Seçin", reply_markup=InlineKeyboardMarkup(kb))
        return

    narrator_id = query.from_user.id
    mode = "voice" if data == "mode_voice" else "text"
    sub_mode = "dynamic" if data == "mode_text_dynamic" else "fixed"

    word, hint = pick_word()
    
    games[chat_id] = {
        "active": True,
        "mode": mode,
        "sub_mode": sub_mode,
        "narrator_id": narrator_id,
        "current_word": word,
        "current_hint": hint,
        "scores": {},
        "last_activity": time.time(),
        "waiting_for_volunteer": False
    }
    
    # Mesajı düzenleyerek butonları temizle ki tekrar basılmasın
    try:
        query.message.delete()
    except:
        pass
        
    send_game_ui(context, chat_id, f"✅ Oyun Başladı! ({'Sesli' if mode=='voice' else 'Yazılı'})")

def game_buttons(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    user_id = query.from_user.id
    
    if chat_id not in games:
        query.answer("Oyun bulunamadı.", show_alert=True)
        return

    game_data = games[chat_id]
    game_data["last_activity"] = time.time()

    # --- GÖNÜLLÜ OLMA BUTONU ---
    if query.data == "btn_volunteer":
        if not game_data.get("waiting_for_volunteer"):
            query.answer("Anlatıcı zaten var!", show_alert=True)
            return
        
        # Yeni anlatıcıyı ata
        game_data["narrator_id"] = user_id
        game_data["waiting_for_volunteer"] = False
        game_data["current_word"], game_data["current_hint"] = pick_word()
        
        query.answer("✅ Yeni anlatıcı sensin!", show_alert=True)
        
        # Mesajı silip yenisini atalım ki temiz olsun veya düzenleyelim
        try:
            query.message.delete()
        except: pass
        send_game_ui(context, chat_id, f"🔄 Yeni anlatıcı: *{escape_md(query.from_user.first_name)}*")
        return

    # --- ANLATICI KONTROLLERİ ---
    if user_id != game_data["narrator_id"]:
        query.answer("❌ Sadece anlatıcı basabilir!", show_alert=True)
        return

    if query.data == "btn_look":
        # Türkçe karakter düzeltmesi ile göster
        word_display = tr_upper(game_data['current_word'])
        query.answer(
            f"🎯 KELİME: {word_display}\n📌 İPUCU: {game_data['current_hint']}",
            show_alert=True
        )
    
    elif query.data == "btn_next":
        new_w, new_h = pick_word()
        game_data["current_word"] = new_w
        game_data["current_hint"] = new_h
        
        # Türkçe karakter düzeltmesi ile göster
        word_display = tr_upper(new_w)
        query.answer(
            f"✅ Değişti!\n🎯 YENİ KELİME: {word_display}\n📌 İPUCU: {new_h}",
            show_alert=True
        )

    elif query.data == "btn_pass":
        # Pas geçme mantığı
        game_data["waiting_for_volunteer"] = True
        game_data["narrator_id"] = None # Kimse değil
        query.answer("Sıranı saldın!", show_alert=True)
        
        # Mevcut mesajı güncelle
        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]
        try:
            query.edit_message_text(
                "⚠️ *Anlatıcı sırasını saldı!* Kim anlatmak ister?",
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except:
             query.edit_message_text(
                "⚠️ Anlatıcı sırasını saldı! Kim anlatmak ister?",
                reply_markup=InlineKeyboardMarkup(kb)
            )

def guess_handler(update, context):
    user = update.message.from_user
    chat_id = update.message.chat.id
    text = update.message.text.strip()

    # Özel Mesaj (Kelime belirleme)
    if update.message.chat.type == "private":
        if user.id in pending_dm:
            target_chat = pending_dm[user.id]
            if target_chat in games:
                games[target_chat]["current_word"] = text.lower()
                games[target_chat]["current_hint"] = "Özel belirlendi"
                context.bot.send_message(user.id, f"✅ Kelime ayarlandı: {text}")
            pending_dm.pop(user.id, None)
        return

    if chat_id not in games: return
    game_data = games[chat_id]

    # Eğer gönüllü bekleniyorsa tahmin yapılamaz
    if game_data.get("waiting_for_volunteer"): return
    
    # Anlatıcı tahmin edemez
    if user.id == game_data["narrator_id"]: return

    # DOĞRU TAHMİN
    if text.lower() == game_data["current_word"].lower():
        # Skor
        full_key = f"{user.first_name}::{user.id}"
        game_data["scores"][full_key] = game_data["scores"].get(full_key, 0) + 1
        
        # Global DB güncelle
        scores_col.update_one(
            {"user_id": user.id}, 
            {"$inc": {"score": 1}, "$set": {"name": user.first_name}}, 
            upsert=True
        )

        winner_name = escape_md(user.first_name)
        won_word = tr_upper(game_data["current_word"]) # Kalın ve Türkçe karakterli
        
        msg_prefix = f"🎉 *{winner_name}* bildi\\! Kelime: *{won_word}*"

        # Mod kontrolü
        if game_data["sub_mode"] == "dynamic":
            game_data["narrator_id"] = user.id
            msg_prefix += "\n🔄 *Anlatıcı Değişti!*"
        
        game_data["current_word"], game_data["current_hint"] = pick_word()
        game_data["last_activity"] = time.time()
        
        send_game_ui(context, chat_id, msg_prefix)

def stop(update, context):
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    
    if chat_id not in games:
        update.message.reply_text("❌ Zaten aktif bir oyun yok.")
        return

    # Admin Kontrolü
    is_authorized = False
    if user_id == OWNER_ID:
        is_authorized = True
    else:
        try:
            member = context.bot.get_chat_member(chat_id, user_id)
            if member.status in ['creator', 'administrator']:
                is_authorized = True
        except: pass
    
    if not is_authorized:
        update.message.reply_text("❌ Oyunu sadece Yöneticiler bitirebilir.")
        return

    end_game_logic(context, chat_id)

def end_game_logic(context, chat_id):
    if chat_id not in games: return
    game_data = games[chat_id]
    
    text = "🏁 *OYUN BİTTİ - PUAN DURUMU*\n\n"
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_scores:
        text += "Kimse puan alamadı 😔"
    else:
        for idx, (key, score) in enumerate(sorted_scores, 1):
            name = key.split("::")[0]
            medals = ["🥇", "🥈", "🥉"]
            medal = medals[idx-1] if idx <= 3 else "🎗"
            text += f"{medal} {idx}\\. {escape_md(name)}: {score} puan\n"

    try:
        context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)
    except:
        context.bot.send_message(chat_id, text.replace("*", "").replace("\\", ""))
    
    del games[chat_id]

def eniyiler(update, context):
    # Global sıralama - Veritabanındaki herkesi kapsar
    try:
        top = list(scores_col.find().sort("score", -1).limit(15))
        
        if not top:
            update.message.reply_text("📭 Henüz kayıtlı skor yok.")
            return

        msg = "🏆 *TÜM ZAMANLARIN EN İYİLERİ*\n\n"
        for i, u in enumerate(top, 1):
            name = escape_md(u.get('name', 'Bilinmeyen'))
            score = u.get('score', 0)
            medals = ["🥇", "🥈", "🥉"]
            medal = medals[i-1] if i <= 3 else f"{i}\\."
            msg += f"{medal} {name}: {score} puan\n"
            
        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        update.message.reply_text(f"❌ Sıralama alınamadı: {e}")

# --- Admin Komutları (Aynen korundu) ---
def add_sudo(update, context):
    if update.message.from_user.id != OWNER_ID: return
    try: sudo_users.add(int(context.args[0])); update.message.reply_text("✅")
    except: pass
def del_sudo(update, context):
    if update.message.from_user.id != OWNER_ID: return
    try: sudo_users.discard(int(context.args[0])); update.message.reply_text("✅")
    except: pass
def add_word(update, context):
    if update.message.from_user.id not in sudo_users: return
    t = " ".join(context.args)
    w, h = map(str.strip, t.split("-", 1)) if "-" in t else (t.strip(), "")
    if not words_col.find_one({"word": w.lower()}):
        words_col.insert_one({"word": w.lower(), "hint": h})
        update.message.reply_text("✅")
def del_word(update, context):
    if update.message.from_user.id not in sudo_users: return
    words_col.delete_one({"word": context.args[0].lower()}); update.message.reply_text("✅")
def wordcount(update, context):
    update.message.reply_text(f"📚 {words_col.count_documents({})}")

def auto_stop_check(context):
    now = time.time()
    for cid in list(games.keys()):
        if now - games[cid]["last_activity"] > 300:
            end_game_logic(context, cid)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("wordcount", wordcount))
    dp.add_handler(CommandHandler("addsudo", add_sudo))
    dp.add_handler(CommandHandler("delsudo", del_sudo))
    dp.add_handler(CommandHandler("addword", add_word))
    dp.add_handler(CommandHandler("delword", del_word))

    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))
    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))

    updater.job_queue.run_repeating(auto_stop_check, interval=60)
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
