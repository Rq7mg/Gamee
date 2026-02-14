import os

import time

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, Update

from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

import pymongo



# --- LOGGING ---

logging.basicConfig(

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 

    level=logging.INFO

)

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

    logger.info("✅ MongoDB bağlantısı başarılı.")

except Exception as e:

    logger.error(f"❌ MongoDB Bağlantı Hatası: {e}")

    words_col = scores_col = chats_col = None



# --- GLOBAL DEĞİŞKENLER ---

sudo_users = set([OWNER_ID])

games = {}       

pending_dm = {}  



# --- YARDIMCI FONKSİYONLAR ---



def tr_upper(text):

    """Türkçe karakterlere uyumlu büyük harf dönüşümü"""

    if not text: 

        return ""

    

    text = str(text).strip()

    

    # Özel Türkçe karakter dönüşümleri (küçükten büyüğe)

    char_map = {

        'i': 'İ', 'ı': 'I',

        'ğ': 'Ğ', 'ü': 'Ü',

        'ş': 'Ş', 'ö': 'Ö',

        'ç': 'Ç'

    }

    

    # Her karakteri kontrol et ve dönüştür

    result = []

    for char in text:

        if char in char_map:

            result.append(char_map[char])

        else:

            result.append(char.upper())

    

    return ''.join(result)



def escape_md(text):

    if text is None: 

        return ""

    text = str(text)

    escape_chars = r'_*[]()~`>#+-=|{}.!'

    for c in escape_chars:

        text = text.replace(c, f"\\{c}")

    return text



def pick_word():

    if words_col is None: 

        return "Hata", "DB Yok"

    try:

        # Rastgele kelime seç

        count = words_col.count_documents({})

        if count == 0:

            return "kelime yok", "veritabanı boş"

            

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

        chats_col.update_one(

            {"chat_id": chat_id}, 

            {"$set": {"active": True, "last_active": time.time()}}, 

            upsert=True

        )



# --- OYUN ARAYÜZÜ ---



def send_game_ui(context: CallbackContext, chat_id, text_prefix=""):

    """Oyun arayüzünü gönder"""

    if chat_id not in games: 

        return

    

    game_data = games[chat_id]

    update_chats(chat_id)

    game_data["last_activity"] = time.time()

    

    # Gönüllü bekleniyor mu?

    if game_data.get("waiting_for_volunteer"):

        kb = [[InlineKeyboardButton("✋ Ben Anlatırım", callback_data="btn_volunteer")]]

        msg = f"{text_prefix}\n⚠️ *Anlatıcı sırasını saldı\\!*\nKim anlatmak ister?"

        try:

            context.bot.send_message(

                chat_id, msg, 

                reply_markup=InlineKeyboardMarkup(kb), 

                parse_mode=ParseMode.MARKDOWN_V2

            )

        except:

            context.bot.send_message(

                chat_id, msg.replace("*","").replace("\\",""), 

                reply_markup=InlineKeyboardMarkup(kb)

            )

        return



    # Anlatıcı bilgisi

    try:

        user_info = context.bot.get_chat_member(chat_id, game_data["narrator_id"]).user

        name = user_info.first_name

    except:

        name = "Bilinmiyor"



    bot_username = context.bot.username

    deep_link = f"https://t.me/{bot_username}?start=writeword_{chat_id}"



    # Butonlar

    kb = [

        [

            InlineKeyboardButton("👀 Kelimeyi Gör", callback_data="btn_look"),

            InlineKeyboardButton("💡 İpucu Ver", callback_data="btn_hint")

        ],

        [

            InlineKeyboardButton("➡️ Değiştir", callback_data="btn_next"),

            InlineKeyboardButton("✍️ Özel Kelime Yaz", url=deep_link)

        ]

    ]

    

    if game_data["sub_mode"] == "dynamic":

        kb.append([InlineKeyboardButton("❌ Sıramı Sal", callback_data="btn_pass")])



    # Mesajı gönder

    msg = f"{text_prefix}\n🗣 Anlatıcı: *{escape_md(name)}*"

    

    try:

        context.bot.send_message(

            chat_id, msg, 

            reply_markup=InlineKeyboardMarkup(kb), 

            parse_mode=ParseMode.MARKDOWN_V2

        )

    except Exception as e:

        logger.error(f"UI gönderme hatası: {e}")

        context.bot.send_message(

            chat_id, msg.replace("*", "").replace("\\", ""), 

            reply_markup=InlineKeyboardMarkup(kb)

        )



# --- KOMUTLAR ---



def start(update: Update, context: CallbackContext):

    """Start komutu"""

    user_id = update.effective_user.id

    chat_id = update.effective_chat.id

    

    logger.info(f"Start komutu - User: {user_id}, Chat: {chat_id}")

    update_chats(chat_id)

    

    # Özel kelime yazma işlemi

    if context.args and context.args[0].startswith("writeword_"):

        try:

            target_chat_id = int(context.args[0].split("_")[1])

            pending_dm[user_id] = target_chat_id

            update.message.reply_text("✍️ Anlatacağınız kelimeyi şimdi buraya yazın.")

            logger.info(f"Özel kelime bekleniyor - User: {user_id}, Target Chat: {target_chat_id}")

        except Exception as e:

            logger.error(f"Özel kelime hatası: {e}")

        return

    

    text = "👋 Tabu Botu!\n\n🎮 /game - Oyun başlat\n🏆 /eniyiler - Skor tablosu\n❌ /stop - Oyunu bitir"

    update.message.reply_text(text)



def game(update: Update, context: CallbackContext):

    """Oyun başlatma komutu"""

    chat_id = update.effective_chat.id

    user_id = update.effective_user.id

    

    logger.info(f"Game komutu - User: {user_id}, Chat: {chat_id}")

    

    if chat_id in games:

        update.message.reply_text("⚠️ Bu grupta oyun zaten devam ediyor!")

        return

    

    kb = [

        [

            InlineKeyboardButton("🎤 Sesli Mod", callback_data="mode_voice"),

            InlineKeyboardButton("⌨️ Yazılı Mod", callback_data="mode_text_pre")

        ]

    ]

    update.message.reply_text("🎮 Oyun modunu seçin:", reply_markup=InlineKeyboardMarkup(kb))



def eniyiler(update: Update, context: CallbackContext):

    """Skor tablosu"""

    if scores_col is None:

        update.message.reply_text("❌ Veritabanı bağlantısı yok.")

        return

        

    try:

        top = list(scores_col.find().sort("score", -1).limit(15))

        if not top:

            update.message.reply_text("📭 Henüz skor kaydı yok.")

            return

            

        msg = "🏆 *TÜM ZAMANLARIN EN İYİLERİ*\n\n"

        for i, u in enumerate(top, 1):

            name = escape_md(u.get('name', 'Bilinmiyor'))

            score = escape_md(str(u.get('score', 0)))

            msg += f"{i}\\. {name}: {score} puan\n"

            

        update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:

        logger.error(f"En iyiler hatası: {e}")

        update.message.reply_text("❌ Skorlar yüklenemedi.")



def stop(update: Update, context: CallbackContext):

    """Oyunu durdur"""

    chat_id = update.effective_chat.id

    logger.info(f"Stop komutu - Chat: {chat_id}")

    

    if chat_id in games:

        end_game_logic(context, chat_id)

        update.message.reply_text("✅ Oyun durduruldu.")

    else:

        update.message.reply_text("❌ Bu grupta aktif oyun yok.")



# --- ADMIN KOMUTLARI ---



def duyuru(update: Update, context: CallbackContext):

    """Duyuru gönder (sadece owner)"""

    if update.effective_user.id != OWNER_ID: 

        return

    

    msg = update.message.reply_to_message

    if not msg: 

        update.message.reply_text("❌ Duyuru yapmak için bir mesajı yanıtlayın.")

        return

    

    if chats_col is None:

        update.message.reply_text("❌ Veritabanı bağlantısı yok.")

        return

        

    chats = list(chats_col.find({"active": True}))

    success = 0

    

    update.message.reply_text(f"📤 Duyuru {len(chats)} gruba gönderiliyor...")

    

    for chat in chats:

        try:

            context.bot.copy_message(

                chat_id=chat['chat_id'], 

                from_chat_id=update.effective_chat.id, 

                message_id=msg.message_id

            )

            success += 1

            time.sleep(0.05)  # Rate limit koruması

        except Exception as e:

            logger.error(f"Duyuru gönderme hatası {chat['chat_id']}: {e}")

    

    update.message.reply_text(f"✅ Duyuru {success} gruba iletildi.")



def stats(update: Update, context: CallbackContext):

    """Bot istatistikleri"""

    if update.effective_user.id not in sudo_users: 

        return

    

    if chats_col is None:

        update.message.reply_text("❌ Veritabanı bağlantısı yok.")

        return

    

    total_chats = chats_col.count_documents({})

    active_chats = chats_col.count_documents({"active": True})

    

    msg = f"📊 **BOT İSTATİSTİKLERİ**\n\n"

    msg += f"📌 Toplam Grup: {total_chats}\n"

    msg += f"✅ Aktif Grup: {active_chats}\n"

    msg += f"🎮 Aktif Oyun: {len(games)}\n"

    

    if words_col:

        total_words = words_col.count_documents({})

        msg += f"📚 Toplam Kelime: {total_words}\n"

    

    update.message.reply_text(msg)



def word_count(update: Update, context: CallbackContext):

    """Kelime sayısı"""

    if update.effective_user.id not in sudo_users: 

        return

    

    if words_col is None:

        update.message.reply_text("❌ Veritabanı bağlantısı yok.")

        return

    

    count = words_col.count_documents({})

    update.message.reply_text(f"📚 Veritabanında {count} kelime var.")



def addword(update: Update, context: CallbackContext):

    """Kelime ekle"""

    if update.effective_user.id not in sudo_users: 

        return

    

    if words_col is None:

        update.message.reply_text("❌ Veritabanı bağlantısı yok.")

        return

        

    try:

        if not context.args:

            update.message.reply_text("❌ Format: /addword kelime - ipucu")

            return

            

        content = " ".join(context.args)

        

        if "-" in content:

            word, hint = map(str.strip, content.split("-", 1))

        else:

            word, hint = content.strip(), "İpucu yok"

        

        # Kelimeyi küçük harfle kaydet

        words_col.update_one(

            {"word": word.lower()}, 

            {"$set": {"hint": hint, "added_by": update.effective_user.id}}, 

            upsert=True

        )

        

        update.message.reply_text(f"✅ Kelime eklendi: {tr_upper(word)}")

        logger.info(f"Yeni kelime eklendi: {word} - {hint}")

        

    except Exception as e:

        logger.error(f"Kelime ekleme hatası: {e}")

        update.message.reply_text("❌ Format: /addword kelime - ipucu")



def addsudo(update: Update, context: CallbackContext):

    """Sudo kullanıcı ekle"""

    if update.effective_user.id != OWNER_ID: 

        return

    

    try:

        if not context.args:

            update.message.reply_text("❌ Kullanım: /addsudo ID")

            return

            

        new_id = int(context.args[0])

        sudo_users.add(new_id)

        update.message.reply_text(f"✅ Sudo kullanıcı eklendi: {new_id}")

    except Exception as e:

        logger.error(f"Sudo ekleme hatası: {e}")

        update.message.reply_text("❌ Geçersiz ID")



# --- OYUN MANTIĞI ---



def end_game_logic(context: CallbackContext, chat_id):

    """Oyunu bitir ve skorları göster"""

    if chat_id not in games: 

        return

    

    game_data = games[chat_id]

    

    # Skor mesajını hazırla

    text = "🏁 *OYUN BİTTİ - PUAN DURUMU*\n\n"

    sorted_scores = sorted(game_data["scores"].items(), key=lambda x: x[1], reverse=True)

    

    if not sorted_scores: 

        text += "Kimse puan alamadı."

    else:

        for idx, (key, score) in enumerate(sorted_scores, 1):

            name = key.split("::")[0]

            text += f"{idx}\\. {escape_md(name)}: {escape_md(str(score))} puan\n"

    

    # Skorları gönder

    try: 

        context.bot.send_message(chat_id, text, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:

        logger.error(f"Skor gönderme hatası: {e}")

        context.bot.send_message(chat_id, "Oyun bitti, puanlar gönderilemedi.")

    

    # Oyunu sil

    if chat_id in games: 

        del games[chat_id]

        logger.info(f"Oyun sonlandı - Chat: {chat_id}")



def mode_select(update: Update, context: CallbackContext):

    """Mod seçimi callback handler"""

    query = update.callback_query

    chat_id = query.message.chat.id

    user_id = query.from_user.id

    

    logger.info(f"Mod seçimi - User: {user_id}, Chat: {chat_id}, Data: {query.data}")

    

    if chat_id in games and not query.data.startswith("mode_text_"):

        query.answer("Zaten oyun var!", show_alert=True)

        return

    

    query.answer()

    

    if query.data == "mode_voice":

        query.edit_message_text("🎤 Sesli mod yakında aktif olacak!")

        return

    

    if query.data == "mode_text_pre":

        kb = [

            [

                InlineKeyboardButton("👤 Sabit Anlatıcı", callback_data="mode_text_fixed"),

                InlineKeyboardButton("🔄 Değişken Anlatıcı", callback_data="mode_text_dynamic")

            ]

        ]

        query.edit_message_text("⌨️ Anlatıcı tipini seçin:", reply_markup=InlineKeyboardMarkup(kb))

        return

    

    # Oyunu başlat

    w, h = pick_word()

    sub_mode = "dynamic" if query.data == "mode_text_dynamic" else "fixed"

    

    games[chat_id] = {

        "narrator_id": user_id, 

        "sub_mode": sub_mode, 

        "current_word": w, 

        "current_hint": h, 

        "scores": {}, 

        "last_activity": time.time(), 

        "waiting_for_volunteer": False, 

        "hint_used": False

    }

    

    query.message.delete()

    send_game_ui(context, chat_id, "✅ Oyun başladı!")

    logger.info(f"Oyun başladı - Chat: {chat_id}, Anlatıcı: {user_id}, Kelime: {w}")



def game_buttons(update: Update, context: CallbackContext):

    """Oyun butonları callback handler"""

    query = update.callback_query

    chat_id = query.message.chat.id

    user_id = query.from_user.id

    

    logger.info(f"Buton tıklandı - User: {user_id}, Chat: {chat_id}, Data: {query.data}")

    

    if chat_id not in games: 

        query.answer("Oyun bulunamadı!", show_alert=True)

        return

    

    game_data = games[chat_id]

    game_data["last_activity"] = time.time()

    

    # Gönüllü butonu

    if query.data == "btn_volunteer":

        if not game_data.get("waiting_for_volunteer"):

            query.answer("Şu anda gönüllü gerekmiyor!", show_alert=True)

            return

            

        game_data.update({

            "narrator_id": user_id, 

            "waiting_for_volunteer": False, 

            "hint_used": False

        })

        game_data["current_word"], game_data["current_hint"] = pick_word()

        query.message.delete()

        send_game_ui(context, chat_id, f"🔄 Yeni anlatıcı: {query.from_user.first_name}")

        query.answer()

        return

    

    # Anlatıcı butonları

    if user_id != game_data["narrator_id"]:

        query.answer("Bu butonlar sadece anlatıcı içindir!", show_alert=True)

        return

    

    if query.data == "btn_look":

        word_display = tr_upper(game_data['current_word'])

        hint_display = game_data['current_hint']

        query.answer(

            f"🎯 KELİME: {word_display}\n📌 İPUCU: {hint_display}", 

            show_alert=True

        )

        

    elif query.data == "btn_hint":

        if game_data["hint_used"]:

            query.answer("İpucu zaten kullanıldı!", show_alert=True)

        else:

            game_data["hint_used"] = True

            word = game_data['current_word']

            first_letter = tr_upper(word[0])

            display = first_letter + " " + "_ " * (len(word) - 1)

            context.bot.send_message(chat_id, f"💡 İpucu: {display}")

            query.answer()

            

    elif query.data == "btn_next":

        game_data["current_word"], game_data["current_hint"] = pick_word()

        game_data["hint_used"] = False

        query.answer(f"Yeni kelime: {tr_upper(game_data['current_word'])}", show_alert=True)

        

    elif query.data == "btn_pass":

        game_data.update({

            "waiting_for_volunteer": True, 

            "narrator_id": None

        })

        query.message.delete()

        send_game_ui(context, chat_id)

        query.answer()



def guess_handler(update: Update, context: CallbackContext):

    """Mesajları yakala ve kelime tahminlerini işle"""

    user = update.message.from_user

    chat_id = update.message.chat.id

    message_text = update.message.text

    

    logger.info(f"Mesaj alındı - User: {user.id}, Chat: {chat_id}, Mesaj: {message_text[:50]}")

    

    # Türkçe karakterleri düzgün işle

    input_text_upper = tr_upper(message_text)



    # ÖZEL MESAJ KONTROLÜ

    if update.message.chat.type == "private":

        if user.id in pending_dm:

            target_chat_id = pending_dm[user.id]

            logger.info(f"Özel kelime - User: {user.id}, Target Chat: {target_chat_id}")

            

            if target_chat_id in games and games[target_chat_id]["narrator_id"] == user.id:

                games[target_chat_id].update({

                    "current_word": message_text,  # Orijinal haliyle kaydet

                    "current_hint": "📝 Özel kelime", 

                    "hint_used": False, 

                    "last_activity": time.time()

                })

                update.message.reply_text(f"✅ Kelime ayarlandı: {tr_upper(message_text)}")

                logger.info(f"Özel kelime ayarlandı - Chat: {target_chat_id}, Kelime: {message_text}")

            else:

                update.message.reply_text("❌ Oyun bulunamadı veya anlatıcı siz değilsiniz!")

            

            pending_dm.pop(user.id, None)

        else:

            # Özel mesaj ama bekleyen kelime yok

            update.message.reply_text("Bu bot sadece gruplarda çalışır. Bir grupta oyun başlatın!")

        return



    # GRUP MESAJI - OYUN KONTROLÜ

    if chat_id not in games: 

        logger.info(f"Mesaj atıldı ama oyun yok - Chat: {chat_id}")

        return

    

    game_data = games[chat_id]

    

    # Anlatıcı kontrolü

    if user.id == game_data["narrator_id"]:

        logger.info(f"Anlatıcı mesajı - Chat: {chat_id}")

        return

    

    # Gönüllü bekleniyor mu?

    if game_data.get("waiting_for_volunteer"):

        logger.info(f"Gönüllü bekleniyor - Chat: {chat_id}")

        return



    # KELİME TAHMİN KONTROLÜ

    current_word_upper = tr_upper(game_data["current_word"])

    

    logger.info(f"Kelime karşılaştırma - Tahmin: '{input_text_upper}', Hedef: '{current_word_upper}'")

    

    if input_text_upper == current_word_upper:

        # DOĞRU TAHMİN

        point = 0.5 if game_data["hint_used"] else 1.0

        full_key = f"{user.first_name}::{user.id}"

        game_data["scores"][full_key] = game_data["scores"].get(full_key, 0) + point

        

        logger.info(f"✓ DOĞRU TAHMİN! - User: {user.first_name}, Puan: {point}, Toplam: {game_data['scores'][full_key]}")

        

        # Veritabanına kaydet

        if scores_col: 

            scores_col.update_one(

                {"user_id": user.id}, 

                {

                    "$inc": {"score": point}, 

                    "$set": {

                        "name": user.first_name,

                        "last_guess": time.time()

                    }

                }, 

                upsert=True

            )

        

        # Başarı mesajı

        msg = f"🎉 *{escape_md(user.first_name)}* bildi\\! (+{escape_md(str(point))} Puan)\nKelime: *{tr_upper(game_data['current_word'])}*"

        

        # Yeni kelime seç

        if game_data["sub_mode"] == "dynamic": 

            game_data["narrator_id"] = user.id

            

        game_data["current_word"], game_data["current_hint"] = pick_word()

        game_data["hint_used"] = False

        

        # UI'ı güncelle

        send_game_ui(context, chat_id, msg)

    else:

        logger.info(f"✗ Yanlış tahmin - Chat: {chat_id}")



def auto_stop_check(context: CallbackContext):

    """5 dakika hareketsiz oyunları otomatik bitir"""

    now = time.time()

    for cid in list(games.keys()):

        if now - games[cid].get("last_activity", 0) > 300:  # 5 Dakika

            logger.info(f"Otomatik stop - Chat: {cid} (5 dk hareketsiz)")

            try:

                context.bot.send_message(cid, "💤 Oyun 5 dakika hareketsiz kaldığı için sonlandırıldı.")

                end_game_logic(context, cid)

            except Exception as e:

                logger.error(f"Otomatik stop hatası {cid}: {e}")

                if cid in games: 

                    del games[cid]



def error_handler(update: Update, context: CallbackContext):

    """Hata yakalayıcı"""

    logger.error(f"Güncelleme {update} hata verdi: {context.error}")



# --- MAIN ---



def main():

    """Ana fonksiyon"""

    logger.info("Bot başlatılıyor...")

    

    # Updater'ı oluştur

    updater = Updater(TOKEN, use_context=True)

    dp = updater.dispatcher



    # KOMUT HANDLERLAR

    dp.add_handler(CommandHandler("start", start))

    dp.add_handler(CommandHandler("game", game))

    dp.add_handler(CommandHandler("stop", stop))

    dp.add_handler(CommandHandler("eniyiler", eniyiler))

    

    # ADMIN KOMUTLARI

    dp.add_handler(CommandHandler("duyuru", duyuru))

    dp.add_handler(CommandHandler("stats", stats))

    dp.add_handler(CommandHandler("wordcount", word_count))

    dp.add_handler(CommandHandler("addword", addword))

    dp.add_handler(CommandHandler("addsudo", addsudo))



    # CALLBACK HANDLERLAR

    dp.add_handler(CallbackQueryHandler(mode_select, pattern="^mode_"))

    dp.add_handler(CallbackQueryHandler(game_buttons, pattern="^btn_"))

    

    # MESAJ HANDLERI - TÜM METİN MESAJLARINI YAKALA

    dp.add_handler(MessageHandler(

        Filters.text & (~Filters.command),  # Komut olmayan tüm metin mesajları

        guess_handler

    ))

    

    # HATA HANDLERI

    dp.add_error_handler(error_handler)



    # ZAMANLAYICI

    updater.job_queue.run_repeating(auto_stop_check, interval=60, first=10)



    # Botu başlat

    updater.start_polling(

        drop_pending_updates=True,  # Bekleyen güncellemeleri temizle

        timeout=30

    )

    

    logger.info("✅ Bot başarıyla başlatıldı!")

    logger.info(f"Bot: @{updater.bot.username}")

    logger.info(f"Owner ID: {OWNER_ID}")

    

    updater.idle()



if __name__ == "__main__":

    main()
