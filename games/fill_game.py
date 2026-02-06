import random
from telegram import Update
from telegram.ext import ContextTypes

# Örnek 1000 kelime (tamamını ekleyebilirsin)
words = [
"araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
"ev","köpek","kedi","oyuncak","muz","elma","armut","çilek","kiraz","muzik","meyveli","aslan","kaplan","panter","leopar","ceylan","geyik","karaca","domuz","sığır","inek",
"boğa","at","eşek","deve","tavşan","hamster","gerbil","kaplumbağa","kertenkele","yılan",
"örümcek","karınca","arı","kelebek","böcek","balık","köpekbalığı","ton balığı","somon","levrek",
"alabalık","orkinos","ahtapot","kalamar","midye","istiridye","denizanası","denizkestanesi","denizatı","mercan",
"su","nehir","göl","akarsu","şelale","kayalık","kıyı","plaj","kum","taş",
"toprak","çamur","kil","çam","meşe","kayın","söğüt","ıhlamur","ladin","karaçam",
"orman","ağaçlık","çalı","bitki","çiçek","ot","otlak","tarla","bahçe","sera",
"tarım","çiftlik","hayvan","çalışma","patron","toplantı","sunum","rapor","proje","hedef",
"planlama","süreç","strateji","lider","yönetim","ekip","takım","performans","gelişim","motivasyon",
"analiz","veri","istatistik","grafik","sunumlar","toplantılar","görüşme","eğitim","öğrenim","deneyim","yatırımlar","para","ödeme","hesap","banka","kart","nakit","fatura","abonelik","satıcı",
"alışveriş","market","mağaza","kampanya","indirim","stok","talep","sipariş","kargo","teslimat",
"üretim","imalat","tedarik","hammadde","malzeme","depolama","lojistik","taşıma","nakliye","sevk",
"kontrol","denetim","kalite","güvenlik","risk","acil","önlem","plan","program","strateji",
"raporlama","veri","analiz","istatistik","grafik","sunum","toplantı","çalışma","işbirliği","ekip",
"liderlik","motivasyon","performans","gelişim","kariyer","yetenek","staj","sertifika","deneyim","öğrenim",
"eğitim","kurs","ödev","proje","araştırma","laboratuvar","deney","kavram","tanım","örnek",
"teorik","pratik","uygulama","problem","çözüm","strateji","yöntem","hedef","sonuç","öneri",
"amaç","girişim","şirket","işletme","finans","yatırımcı","müşteri","pazar","rekabet","ürün",
"hizmet","tanıtım","reklam","kampanya","satış","talep","stok","üretim","imalat","tedarik"
# ... 1000 kelime buraya eklenmeli
]

games = {}  # chat_id: {"word":..., "masked":..., "letter_pool":..., "scores":{}, "active":True, "round":1, "total_rounds":15, "puan":0}

def normalize(text: str) -> str:
    """
    Türkçe karakterleri normalize eder ve küçük harfe çevirir.
    i, İ, ı → i
    ç → c
    ş → s
    ö → o
    ü → u
    ğ → g
    """
    mapping = str.maketrans("İIıçşöüğ", "iii csoug")
    return text.translate(mapping).lower()

def mask_word(word):
    word = word.upper()
    length = len(word)
    
    if length <= 2:
        return word[0] + "-"*(length-1)

    chars = list(word)
    indices = list(range(1, length-1))
    random.shuffle(indices)

    if length == 5:
        num_to_reveal = 1
    elif length == 6:
        num_to_reveal = random.choice([1,2])
    elif length == 7:
        num_to_reveal = random.choice([2,3])
    else:
        num_to_reveal = max(1, length // 3)

    to_reveal = indices[:num_to_reveal]

    masked = ""
    for i, c in enumerate(chars):
        if i == 0 or i == length-1 or i in to_reveal:
            masked += c
        else:
            masked += "-"
    return masked

def get_letter_pool(word):
    letters = list(word.upper())
    random.shuffle(letters)
    return " ".join(letters)

async def start_fill(update: Update, context: ContextTypes.DEFAULT_TYPE, total_rounds=15):
    chat_id = update.message.chat_id if not hasattr(update, "callback_query") else update.callback_query.message.chat_id
    msg_func = update.message.reply_text if not hasattr(update, "callback_query") else update.callback_query.edit_message_text

    if chat_id in games and games[chat_id]["active"]:
        await msg_func("⚠️ Oyun zaten devam ediyor!")
        return

    word = random.choice(words).upper()
    masked = mask_word(word)
    letter_pool = get_letter_pool(word)

    games[chat_id] = {
        "word": word,
        "masked": masked,
        "letter_pool": letter_pool,
        "scores": {},
        "active": True,
        "round": 1,
        "total_rounds": total_rounds,
        "puan": 0
    }

    await msg_func(f"🎯 Boşluk Doldurma oyunu başladı!\nZorluk: Kolay\nPuan: 0\nRound: 1/{total_rounds}\n📚 {len(word)} harf: {letter_pool}\n🎲 {masked}")

async def guess_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]
    user_id = update.message.from_user.id
    user_name = update.message.from_user.first_name

    if normalize(text) == normalize(game["word"]):
        game["scores"].setdefault(user_id, {"name": user_name, "score": 0})
        game["scores"][user_id]["score"] += 1
        game["puan"] += 0.6  # Sabit puan

        await update.message.reply_text(f"🎉 {user_name} doğru tahmin etti!\nKelime: {game['word']}")

        # Yeni round
        game["round"] += 1
        if game["round"] > game["total_rounds"]:
            await finish_game(update, context)
            return

        new_word = random.choice(words).upper()
        game["word"] = new_word
        game["masked"] = mask_word(new_word)
        game["letter_pool"] = get_letter_pool(new_word)

        await update.message.reply_text(f"Round: {game['round']}/{game['total_rounds']}\n📚 {len(new_word)} harf: {game['letter_pool']}\n🎲 {game['masked']}\nPuan: {game['puan']:.1f}")

    else:
        await update.message.reply_text(f"❌ Yanlış! Tekrar deneyin:\n🎲 {game['masked']}")

async def finish_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in games or not games[chat_id]["active"]:
        await update.message.reply_text("⚠️ Bu chat'te aktif bir oyun yok!")
        return

    game = games[chat_id]
    game["active"] = False

    if not game["scores"]:
        await update.message.reply_text("Oyun bitti, kimse puan alamadı.")
        del games[chat_id]
        return

    leaderboard = sorted(game["scores"].values(), key=lambda x: x["score"], reverse=True)
    msg = "🏆 Lider Tablosu:\n\n"
    for i, player in enumerate(leaderboard, start=1):
        msg += f"{i}. {player['name']} - {player['score']} puan\n"

    await update.message.reply_text(msg)
    del games[chat_id]
