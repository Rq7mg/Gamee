import random
from telegram import Update
from telegram.ext import ContextTypes

# Örnek 1000 kelime (tamamını ekleyebilirsin)
words = [
"araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
"ev","köpek","kedi","oyuncak","muz","elma","armut","çilek","kiraz","muzik",
"resim","kalemlik","defter","sandalye","kapı","pencere","halı","lamba","televizyon","radyo",
"bisiklet","uçak","tren","gemi","otomobil","motorsiklet","otobüs","minibüs","kamyon","deniz",
"göl","nehir","şelale","dağ","ova","orman","bahçe","park","meydan","mutfak",
"banyo","oturma","yatak","koltuk","dolap","kitaplık","raf","ayna","kapak","çorap",
"ayakkabı","pantolon","gömlek","kazak","şapka","atkı","eldiven","kemer","mont","ceket",
"pantolon","etek","eldiven","çorap","terlik","bot","sneaker","tshirt","şort","eşofman",
"kazak","mont","palto","trençkot","gözlük","kolye","bilezik","küpe","yüzük","saç",
"toka","şapka","bere","atkı","çanta","cüzdan","kemer","anahtar","telefon","kulaklık",
"kamera","şarj","kablosuz","hoparlör","mikrofon","klavye","fare","ekran","monitor","laptop",
"tablet","kamera","projeksiyon","usb","fotoğraf","video","oyun","yazılım","donanım","sunucu",
"veri","internet","modem","router","uygulama","sistem","ağ","bilgi","teknoloji","robot",
"uzay","yıldız","gezegen","ay","güneş","evren","meteor","asteroit","astronomi","fizik",
"kimya","biyoloji","matematik","tarih","coğrafya","edebiyat","şiir","roman","hikaye","öykü",
"müzik","şarkı","melodi","ritim","nota","enstrüman","piyano","gitar","davul","flüt",
"klarnet","saksafon","orkestra","konser","festival","tiyatro","film","sinema","dizi","oyuncu",
"yönetmen","senaryo","kamera","set","kostüm","makyaj","perde","sahne","ışık","ses",
"zaman","saat","dakika","saniye","takvim","tarih","gece","gündüz","hafta","ay",
"yıl","mevsim","ilkbahar","yaz","sonbahar","kış","hava","yağmur","kar","rüzgar",
"fırtına","sis","gökkuşağı","bulut","şimşek","gök","deniz","kumsal","plaj","dalga",
"kum","taş","kayalık","dağ","tepe","vadi","orman","ağaç","çiçek","tohum",
"meyve","sebze","elma","armut","üzüm","karpuz","şeftali","kiraz","çilek","muz",
"patates","soğan","sarımsak","biber","domates","salatalık","havuç","marul","ıspanak","kabak",
"patlıcan","brokoli","karnabahar","lahana","mantar","bezelye","bakla","fasulye","nohut","mercimek",
"pirinç","bulgur","makarna","ekmek","tatlı","dondurma","çikolata","bisküvi","kurabiye","pasta",
"kek","şeker","bal","reçel","peynir","yoğurt","süt","yumurta","et","tavuk",
"balık","karides","kalamar","midye","pirzola","köfte","sosis","hamburger","pizza","sandviç",
"salata","çorba","pilav","kebap","döner","lahmacun","mantı","pilaki","börek","poğaça",
"kurabiye","lokum","helva","meyveli","çilekli","muzlu","çikolatalı","vanilyalı","fındıklı","bademli",
"cevizli","kuru","yağlı","acı","tatlı","ekşi","tuzlu","bitter","sütlü","karamel",
"kahve","çay","meyve suyu","limonata","su","gazoz","şerbet","kokteyl","smoothie","şarap",
"bira","alkol","meşrubat","içecek","atıştırmalık","cüretkar","heyecan","macera","hikâye","destan",
"şiirsel","melodi","senfoni","orkestra","ritmik","dans","performans","sahne","kostüm","dekor",
"oyunculuk","sanat","kamera","çekim","montaj","senaryo","senarist","yönetmen","eleştirmen","festivali",
"sergi","müze","tarih","arkeoloji","çağ","antik","modern","klasik","geleneksel","çağdaş",
"felsefe","psikoloji","sosyoloji","ekonomi","politik","hukuk","yasama","yürütme","yargı","toplum",
"insan","birey","grup","aile","arkadaş","komşu","şirket","işletme","şirketçi","girişim",
"yatırım","bankacılık","para","bütçe","faiz","kredi","maaş","çalışma","iş","işçi",
"patron","yönetici","toplantı","sunum","rapor","proje","hedef","strateji","analiz","veri",
"istatistik","sonuç","tahmin","deney","laboratuvar","cihaz","tez","makale","yayın","araştırma",
"inovasyon","teknik","mühendislik","tasarım","yenilik","ürün","pazar","müşteri","rekabet","marka",
"logo","web","site","uygulama","mobil","oyun","tasarımcı","grafik","fotoğraf","video",
"kamera","mikrofon","hoparlör","aygıt","cihaz","donanım","yazılım","kod","program","değişken",
"fonksiyon","döngü","sözlük","liste","kütüphane","modül","paket","sunucu","istemci","veritabanı",
"sql","noSQL","dosya","klasör","sürücü","yerel","uzaktan","dosya sistemi","arayüz","buton",
"form","alan","geri besleme","öğrenme","eğitim","öğrenci","öğretmen","sınav","ders","müfredat",
"üniversite","fakülte","bölüm","laboratuvar","ödev","sunum","seminer","konferans","sertifika","mezun",
"işe alım","staj","kariyer","yetenek","motivasyon","liderlik","takım","çalışma","etki","örnek",
"pratik","teori","deneyim","bakış","bakış açısı","kavram","tanım","analiz","yorum","eleştiri",
"tartışma","sonuç","öneri","amaç","hedef","strateji","plan","uygulama","süreç","yöntem"
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
