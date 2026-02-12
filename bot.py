import os
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import pymongo

# Ortam Değişkenleri
TOKEN = os.environ.get("BOT_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
MONGO_URI = os.environ.get("MONGO_URI")

# Veritabanı Bağlantısı
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client["tabu_bot"]
words_col = db["words"]
scores_col = db["scores"]

# Global Değişkenler
sudo_users = set([OWNER_ID])
games = {}
pending_dm = {}

# --- Yardımcı Fonksiyonlar ---

def pick_word():
    # Rastgele bir kelime seçer
    pipeline = [{"$sample": {"size": 1}}]
    doc = list(words_col.aggregate(pipeline))
    if doc:
        return doc[0]["word"], doc[0]["hint"]
    return "kelime yok", "veritabanı boş"

def escape_md(text):
    # Markdown V2 için özel karakterleri kaçırır
    if not text: return ""
    text = str(text)
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    for c in escape_chars:
        text = text.replace(c, f"\\{c}")
    return text

# --- Admin & Kelime Yönetimi Komutları ---

def start(update, context):
    user_id = update.effective_user.id
    if context.args and context.args[0].startswith("writeword_"):
        chat_id = int(context.args[0].split("_")[1])
        pending_dm[user_id] = chat_id
        update.message.reply_text("✍️ Yeni anlatacağınız kelimeyi şimdi yazın.")
        return

    text = (
        "👋 Merhaba! Ben Telegram Tabu Botu.\n\n"
        "🎮 /game - Oyunu başlat\n"
        "🛑 /stop - Oyunu bitir (Admin)\n"
        "🏆 /eniyiler - Global skorlar\n"
        "📚 /wordcount - Kelime sayısı"
    )
    kb = [[InlineKeyboardButton("➕ Beni Gruba Ekle", url=f"https://t.me/{context.bot.username}?startgroup=true")]]
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

def add_sudo(update, context):
    if update.message.from_user.id != OWNER_ID: return
    try:
        uid = int(context.args[0])
        sudo_users.add(uid)
        update.message.reply_text(f"✅ {uid} sudo yapıldı.")
    except: update.message.reply_text("Hata: /addsudo <id>")

def del_sudo(update, context):
    if update.message.from_user.id != OWNER_ID: return
    try:
        uid = int(context.args[0])
        sudo_users.discard(uid)
        update.message.reply_text(f"✅ {uid} silindi.")
    except: update.message.reply_text("Hata: /delsudo <id>")

def add_word(update, context):
    if update.message.from_user.id not in sudo_users:
        update.message.reply_text("❌ Yetkisiz işlem.")
        return
    text = " ".join(context.args)
    if "-" in text:
        word, hint = map(str.strip, text.split("-", 1))
    else:
        word, hint = text.strip(), ""
    
    if words_col.find_one({"word": word.lower()}):
        update.message.reply_text("⚠️ Bu kelime zaten var.")
        return
        
    words_col.insert_one({"word": word.lower(), "hint": hint})
    update.message.reply_text(f"✅ Eklendi: {word}")

def del_word(update, context):
    if update.message.from_user.id not in sudo_users: return
    try:
        w = context.args[0].lower()
        words_col.delete_one({"word": w})
        update.message.reply_text(f"🗑 Silindi: {w}")
    except: pass

def wordcount(update, context):
    c = words_col.count_documents({})
    update.message.reply_text(f"📚 Kelime Sayısı: {c}")

def eniyiler(update, context):
    top = scores_col.find().sort("score", -1).limit(10)
    msg = "🏆 *Global En İyiler*\n\n"
    for i, u in enumerate(top, 1):
        msg += f"{i}. {escape_md(u.get('name', 'Adsız'))}: {u['score']}\n"
    update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

# --- OYUN MOTORU ---

def game(update, context):
    chat_id = update.effective_chat.id
    if chat_id in games:
        update.message.reply_text("⚠️ Oyun zaten devam ediyor! Durdurmak için /stop yazın.")
        return
    
    kb = [
        [InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),
         InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")]
    ]
    update.message.reply_text("🎮 Oyun Modunu Seçin:", reply_markup=InlineKeyboardMarkup(kb))

def mode_select(update, context):
    query = update.callback_query
    query.answer()
    chat_id = query.message.chat.id
    data = query.data

    if data == "mode_text_pre":
        kb = [
            [InlineKeyboardButton("👤 Sabit Anlatıcı", callback_data="mode_text_fixed"),
             InlineKeyboardButton("🔄 Değişken Anlatıcı", callback_data="mode_text_dynamic")]
        ]
        query.edit_message_text("⌨️ Yazılı Mod: Anlatıcı Tipi Seçin", reply_markup=InlineKeyboardMarkup(kb))
        return

    # Oyun Başlatma Hazırlığı
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
        "last_activity": time.time()
    }
    
    send_game_ui(context, chat_id, f"✅ Oyun Başladı! ({'Sesli' if mode=='voice' else 'Yazılı'})\n")

def send_game_ui(context, chat_id, text_prefix=""):
    if chat_id not in games: return
    game_data = games[chat_id]
    
    # Anlatıcı ismini bul
    try:
        u = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user
        name = u.first_name
    except:
        name = "Bilinmiyor"

    bot_username = context.bot.username
    deep_link = f"https://t.me/{bot_username}?start=writeword_{chat_id}"

    kb = [
        [InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="btn_look")],
        [InlineKeyboardButton("➡️ Değiştir", callback_data="btn_next"),
         InlineKeyboardButton("✍️ Özel Kelime Yaz", url=deep_link)]
    ]

    msg = f"{text_prefix}\n🗣 Anlatıcı: *{escape_md(name)}*"
    
    try:
        context.bot.send_message(chat_id, msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        print(f"Mesaj atma hatası: {e}")
        # Hata olursa düz metin at
        context.bot.send_message(chat_id, msg.replace("*", "").replace("\\", ""), reply_markup=InlineKeyboardMarkup(kb))

def game_buttons(update, context):
    query = update.callback_query
    chat_id = query.message.chat.id
    
    if chat_id not in games:
        query.answer("Oyun yok.", show_alert=True)
        return

    game_data = games[chat_id]
    
    if query.from_user.id != game_data["narrator_id"]:
        query.answer("❌ Sadece anlatıcı basabilir!", show_alert=True)
        return

    game_data["last_activity"] = time.time()

    if query.data == "btn_look":
        query.answer(
            f"🎯 KELİME: {game_data['current_word'].upper()}\n📌 İPUCU: {game_data['current_hint']}",
            show_alert=True
        )
    
    elif query.data == "btn_next":
        # İSTEĞİNİZ: Değiştir butonuna basınca yeni kelimeyi popup olarak göster
        new_w, new_h = pick_word()
        game_data["current_word"] = new_w
        game_data["current_hint"] = new_h
        
        query.answer(
            f"✅ Değişti!\n🎯 YENİ KELİME: {new_w.upper()}\n📌 İPUCU: {new_h}",
            show_alert=True
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
                games[target_chat]["current_hint"] = "Kullanıcı tarafından belirlendi"
                context.bot.send_message(user.id, f"✅ Kelime ayarlandı: {text}")
            pending_dm.pop(user.id, None)
        return

    # Grup İçi Tahmin
    if chat_id not in games: return
    game_data = games[chat_id]
    
    # Anlatıcı tahmin edemez
    if user.id == game_data["narrator_id"]: return

    # DOĞRU TAHMİN
    if text.lower() == game_data["current_word"].lower():
        # Skor güncelle
        user_key = f"{user.first_name}" 
        # (Benzersizlik için ID'yi arka planda tutabiliriz ama basitlik için isme ekliyoruz)
        full_key = f"{user.first_name}::{user.id}"
        
        game_data["scores"][full_key] = game_data["scores"].get(full_key, 0) + 1
        scores_col.update_one({"user_id": user.id}, {"$inc": {"score": 1}, "$set": {"name": user.first_name}}, upsert=True)

        winner_name = escape_md(user.first_name)
        won_word = escape_md(game_data["current_word"].upper())

        msg_prefix = f"🎉 *{winner_name}* bildi\\! Kelime: *{won_word}*"

        # Mod kontrolü (Değişken mi?)
        if game_data["sub_mode"] == "dynamic":
            game_data["narrator_id"] = user.id
            msg_prefix += "\n🔄 *Anlatıcı Değişti!*"

        # Yeni kelime seç
        game_data["current_word"], game_data["current_hint"] = pick_word()
        game_data["last_activity"] = time.time()
        
        send_game_ui(context, chat_id, msg_prefix)

def stop(update, context):
    chat_id = update.effective_chat.id
    user_id = update.message.from_user.id
    
    if chat_id not in games:
        update.message.reply_text("❌ Zaten aktif bir oyun yok.")
        return

    # Admin Kontrolü (Hatasız Sürüm)
    is_authorized = False
    if user_id == OWNER_ID:
        is_authorized = True
    else:
        try:
            member = context.bot.get_chat_member(chat_id, user_id)
            if member.status in ['creator', 'administrator']:
                is_authorized = True
        except:
            pass
    
    if not is_authorized:
        update.message.reply_text("❌ Oyunu sadece Yöneticiler bitirebilir.")
        return

    end_game_logic(context, chat_id)

def end_game_logic(context, chat_id):
    if chat_id not in games: return
    game_data = games[chat_id]
    
    # Skor Tablosu Hazırla
    text = "🏁 *OYUN BİTTİ - PUAN DURUMU*\n\n"
    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)
    
    if not sorted_scores:
        text += "Kimse puan alamadı 😔"
    else:
        for idx, (key, score) in enumerate(sorted_scores, 1):
            name = key.split("::")[0] # ID'yi ayıkla
            medals = ["🥇", "🥈", "🥉"]
            medal = medals[idx-1] if idx <= 3 else "🎗"
            text += f"{medal} {idx}\\. {escape_md(name)}: {score} puan\n"

    # Mesajı Gönder (Hata yakalamalı)
    try:
        context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)
    except Exception as e:
        # Markdown hatası olursa formatı temizle gönder
        clean_text = text.replace("*", "").replace("\\", "").replace("_", "")
        context.bot.send_message(chat_id, clean_text)
    
    # Oyunu sil
    del games[chat_id]

def auto_stop_check(context):
    now = time.time()
    for cid in list(games.keys()):
        if now - games[cid]["last_activity"] > 300: # 5 Dakika
            try:
                context.bot.send_message(cid, "⏱ Süre doldu! Oyun otomatik sonlandırılıyor.")
                end_game_logic(context, cid)
            except:
                del games[cid]

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Komutlar
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("game", game))
    dp.add_handler(CommandHandler("stop", stop))
    dp.add_handler(CommandHandler("eniyiler", eniyiler))
    dp.add_handler(CommandHandler("wordcount", wordcount))
    
    # Admin Komutları
    dp.add_handler(CommandHandler("addsudo", add_sudo))
    dp.add_handler(CommandHandler("delsudo", del_sudo))
    dp.add_handler(CommandHandler("addword", add_word))
    dp.add_handler(CommandHandler("delword", del_word))

    # Callback (Butonlar)
    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))
    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))

    # Mesajlar (Tahmin)
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, guess_handler))

    # Zamanlayıcı
    updater.job_queue.run_repeating(auto_stop_check, interval=60)

    print("Bot çalışıyor...")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
