import random
from telegram import Update
from telegram.ext import ContextTypes

# Örnek 1000 kelime (tamamını ekleyebilirsin)
words = [
"araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
"ev","köpek","kedi","oyuncak","muz","elma","armut","çilek","kiraz","muzik",
"resim","kalemlik","defter","sandalye","kapı","pencere","halı","lamba","televizyon","radyo",
"bisiklet","uçak","tren","gemi","otomobil","motorsiklet","otobüs","minibüs","kamyon","deniz","gece","akşam","spor","futbol","basket","voleybol","yüzme","koşu","tenis","boks",
"tatil","havuz","otel","renkler","kırmızı","mavi","yeşil","sarı","mor","beyaz",
"siyah","pembe","duygu","mutlu","üzgün","kızgın","korku","heyecan","gurur","utangaç",
"huzur","doktor","öğretmen","mühendis","hemşire","pilot","şirket","girişim","yatırım","parala",
"bütçe","kredi","maaş","çalış","işçi","patron","toplan","sunum","rapor","proje",
"hedef","planla","süreç","yöntem","analiz","istatistik","sonuç","deney","laboratuvar","teklif",
"araştır","teknoloji","yenilik","ürünler","pazar","müşteri","rekabet","logo","website","uygulama",
"mobil","oyunlar","tasarım","grafik","fotoğraf","video","kamera","mikrofon","hoparlör","donanım",
"kodlar","program","fonksiyon","döngü","sözlü","listele","modül","paket","sunucu","istemci",
"veritaban","arayüz","formlar","butonla","eğitim","sınavlar","dersler","müfredat","üniversite","laboratuvar",
"çeşitli","ödevler","konferans","sertifika","mezunlar","stajlar","kariyer","yetenek","motivasyon","liderlik",
"takımlar","çalışma","etkiyle","örnekle","pratik","teorik","deneyim","bakış","kavram","tanımı",
"analiz","yorumla","eleştir","tartışma","sonuç","öneri","amaç","hedef","planlama","süreçle",
"özellik","bölümler","özelce","akıllı","kimse","sanayi","çevre","toplum","insanlar","arkadaş",
"göl","nehir","şelale","dağ","ova","orman","bahçe","park","meydan","mutfak",
"banyo","oturma","yatak","koltuk","dolap","kitaplık","raf","ayna","kapak","çorap",
"ayakkabı","pantolon","gömlek","kazak","şapka","atkı","eldiven","kemer","mont","ceket",
"pantolon","etek","eldiven","çorap","terlik","bot","sneaker","tshirt","şort","eşofman","komşular","şirketi","işletme","yatırım","finans","yatırımlar","çalışma","işçi","patron","toplantı",
"sunum","rapor","proje","hedef","planlama","süreç","özellik","bölümler","özel","akıllı",
"kimse","sanayi","çevre","toplum","insanlar","arkadaş","komşular","şirket","işletme","yatırım",
"finans","yatırımlar","çalışma","işçi","patron","toplantı","sunum","rapor","proje","hedef",
"planlama","süreç","özellik","bölümler","özel","akıllı","kimse","sanayi","çevre","toplum",
"insanlar","arkadaş","komşular","şirket","işletme","yatırım","finans","yatırımlar","çalışma","işçi",
"patron","toplantı","sunum","rapor","proje","hedef","planlama","süreç","özellik","bölümler",
"özel","akıllı","kimse","sanayi","çevre","toplum","insanlar","arkadaş","komşular","şirket",
"işletme","yatırım","finans","yatırımlar","çalışma","işçi","patron","toplantı","sunum","rapor",
"proje","hedef","planlama","süreç","özellik","bölümler","özel","akıllı","kimse","sanayi",
"çevre","toplum","insanlar","arkadaş","komşular","şirket","işletme","yatırım","finans","yatırımlar",
"çalışma","işçi","patron","toplantı","sunum","rapor","proje","hedef","planlama","süreç","özellik","bölümler","özel","akıllı","kimse","sanayi","çevre","toplum","insanlar","arkadaş",
"komşular","şirket","işletme","yatırım","finans","yatırımlar","çalışma","işçi","patron","toplantı",
"sunum","rapor","proje","hedef","planlama","süreç","özellik","bölümler","özel","akıllı",
"kimse","sanayi","çevre","toplum","insanlar","arkadaş","komşular","şirket","işletme","yatırım",
"finans","yatırımlar","çalışma","işçi","patron","toplantı","sunum","rapor","proje","hedef",
"planlama","süreç","özellik","bölümler","özel","akıllı","kimse","sanayi","çevre","toplum",
"insanlar","arkadaş","komşular","şirket","işletme","yatırım","finans","yatırımlar","çalışma","işçi",
"patron","toplantı","sunum","rapor","proje","hedef","planlama","süreç","özellik","bölümler",
"özel","akıllı","kimse","sanayi","çevre","toplum","insanlar","arkadaş","komşular","şirket",
"işletme","yatırım","finans","yatırımlar","çalışma","işçi","patron","toplantı","sunum","rapor",
"proje","hedef","planlama","süreç","özellik","bölümler","özel","akıllı","kimse","sanayi",
"kazak","mont","palto","trençkot","gözlük","kolye","bilezik","küpe","yüzük","saç","buton","eğitim","sınavlar","dersler","müfredat","üniversite","laboratuvar","çeşitli","ödevler","konferans",
"sertifika","mezunlar","stajlar","kariyer","yetenek","motivasyon","liderlik","takımlar","çalışma","etki",
"örnek","pratik","teorik","deneyim","bakış","kavram","tanım","yorum","eleştiri","tartışma",
"sonuç","öneri","amaç","hedef","planlama","süreç","özellik","bölüm","özel","akıllı",
"kimse","sanayi","çevre","toplum","insanlar","arkadaş","komşu","işletme","yatırımlar","finans",
"çalışan","patron","toplantı","sunum","rapor","proje","hedef","planlama","süreç","özellik",
"bölümler","özel","akıllı","kimse","sanayi","çevre","toplum","insanlar","arkadaş","komşular",
"şirket","işletme","yatırım","finans","yatırımlar","çalışma","işçi","patron","toplantı","sunum",
"rapor","proje","hedef","planlama","süreç","özellik","bölümler","özel","akıllı","kimse",
"sanayi","çevre","toplum","insanlar","arkadaş","komşular","şirket","işletme","yatırım","finans",
"yatırımlar","çalışma","işçi","patron","toplantı","sunum","rapor","proje","hedef","planlama","mevsim","ilkbahar","sonbahar","kışlar","yollar","bulut","rüzgar","fırtına","yağmur","karlar",
"kumlar","kıyı","kayalık","adalar","uyku","rüya","yastık","yorgan","pijama","alarm",
"gece","akşam","spor","futbol","basket","voleybol","yüzme","koşu","tenis","boks",
"tatil","havuz","otel","renkler","kırmızı","mavi","yeşil","sarı","mor","beyaz",
"siyah","pembe","duygu","mutlu","üzgün","kızgın","korku","heyecan","gurur","utangaç",
"huzur","doktor","öğretmen","mühendis","hemşire","pilot","şirket","girişim","yatırım","parala",
"bütçe","kredi","maaş","işçi","patron","toplantı","sunum","rapor","proje","hedef",
"planlama","süreç","yöntem","analiz","istatistik","deney","laboratuvar","teklif","araştır","teknoloji",
"yenilik","ürünler","pazar","müşteri","rekabet","logo","website","uygulama","mobil","oyunlar",
"tasarım","grafik","fotoğraf","video","kamera","mikrofon","hoparlör","donanım","kodlar","program",
"fonksiyon","döngü","sözlü","listele","modül","paket","istemci","veritaban","arayüz","formlar","yatırımlar","para","ödeme","hesap","banka","kart","nakit","fatura","abonelik","satıcı",
"alışveriş","market","mağaza","kampanya","indirim","stok","talep","sipariş","kargo","teslimat",
"üretim","imalat","tedarik","hammadde","malzeme","depolama","lojistik","taşıma","nakliye","sevk",
"kontrol","denetim","kalite","güvenlik","risk","acil","önlem","plan","program","strateji",
"raporlama","veri","analiz","istatistik","grafik","sunum","toplantı","çalışma","işbirliği","ekip",
"liderlik","motivasyon","performans","gelişim","kariyer","yetenek","staj","sertifika","deneyim","öğrenim",
"eğitim","kurs","ödev","proje","araştırma","laboratuvar","deney","kavram","tanım","örnek",
"teorik","pratik","uygulama","problem","çözüm","strateji","yöntem","hedef","sonuç","öneri",
"amaç","girişim","şirket","işletme","finans","yatırımcı","müşteri","pazar","rekabet","ürün",
"hizmet","tanıtım","reklam","kampanya","satış","talep","stok","üretim","imalat","tedarik","bahçe","çimen","çiçek","ağaç","dal","yaprak","kök","meyve","tohum","çiçeklik",
"sera","bahçıvan","gübre","toprak","sulama","hortum","damla","bitki","çiçekçi","çiğdem",
"menekşe","lale","gül","kardelen","narcis","papatya","orkide","bonsai","kaktüs","sukulent",
"bodur","çalı","orman","ağaçlık","koru","park","mesire","piknik","çardak","patika",
"yol","taş","kaya","tepe","dağ","vadi","göl","nehir","dere","akarsu",
"şelale","deniz","kıyı","plaj","kum","kıyıtaşı","kayalık","adalar","lagün","mangrov",
"kuş","serçe","martı","kartal","baykuş","turna","kaz","ördek","tavuk","horoz",
"kedi","köpek","fare","tavşan","sincap","kirpi","tilki","ayı","aslan","kaplan",
"zebra","giraffe","fil","zürafa","maymun","goril","şempanze","leopar","panter","ceylan",
"geyik","karaca","domuz","sığır","inek","boğa","at","eşek","katır","deve",
"tavşan","hamster","gerbil","kaplumbağa","kertenkele","yılan","örümcek","karınca","arı","kelebek",
"böcek","balık","köpekbalığı","ton balığı","somon","levrek","alabalık","orkinos","ahtapot","kalamar",
"toka","şapka","bere","atkı","çanta","cüzdan","kemer","anahtar","telefon","kulaklık","yıldız","gezegen","uydu","güneş","ay","asteroid","meteor","kuyruklu","karadelik","nebula",
"galaksi","evren","samanyolu","gezegenimsi","asteroid","kuasar","süpernova","teleskop","mikroskop","radyo",
"elektron","proton","nötron","atom","molekül","kimya","bileşik","element","oksijen","hidrojen",
"karbon","azot","kalsiyum","demir","altın","gümüş","platin","bakır","çinko","kurşun",
"alüminyum","silisyum","fosfor","kükürt","klor","sodyum","potasyum","magnesium","lityum","berilyum",
"doğal","mineral","taş","kayalar","granit","mermer","kireçtaşı","bazalt","kumtaşı","çakıl",
"toprak","çamur","kil","kum","çam","meşe","kayın","söğüt","ıhlamur","ladin",
"çamur","bataklık","gölge","orman","ağaçlık","çalı","bitki","çiçek","ot","otlak",
"tarla","bahçe","sera","tarım","hayvan","çiftlik","inek","koyun","keçi","at",
"eşek","katır","tavuk","ördek","kaz","hindi","bıldırcın","sincap","tilki","ayı","aslan","kaplan","panter","leopar","ceylan","geyik","karaca","domuz","sığır","inek",
"boğa","at","eşek","deve","tavşan","hamster","gerbil","kaplumbağa","kertenkele","yılan",
"örümcek","karınca","arı","kelebek","böcek","balık","köpekbalığı","ton balığı","somon","levrek",
"alabalık","orkinos","ahtapot","kalamar","midye","istiridye","denizanası","denizkestanesi","denizatı","mercan",
"su","nehir","göl","akarsu","şelale","kayalık","kıyı","plaj","kum","taş",
"toprak","çamur","kil","çam","meşe","kayın","söğüt","ıhlamur","ladin","karaçam","kariyer","staj","sertifika","tecrübe","yetkinlik","işlem","uygulama","program","fonksiyon","döngü",
"algoritma","kodlama","yazılım","donanım","ağlar","internet","sunucular","istemci","veritabanı","arayüz",
"form","buton","menü","grafik","tasarım","fotoğraf","video","kamera","mikrofon","hoparlör",
"ekran","tablet","laptop","telefon","klavye","fare","oyun","mobil","uygulama","sistem",
"modem","router","veri","bulut","platform","websitesi","site","seo","içerik","dijital",
"pazarlama","reklam","kampanya","müşteri","satış","ürün","hizmet","tanıtım","kampanya","satış",
"talep","stok","üretim","imalat","tedarik","hammadde","malzeme","depolama","lojistik","taşıma",
"nakliye","sevk","kontrol","denetim","kalite","güvenlik","risk","acil","önlem","plan",
"program","strateji","raporlama","veri","analiz","istatistik","grafik","sunum","toplantı","çalışma",
"orman","ağaçlık","çalı","bitki","çiçek","ot","otlak","tarla","bahçe","sera",
"tarım","çiftlik","hayvan","çalışma","patron","toplantı","sunum","rapor","proje","hedef",
"planlama","süreç","strateji","lider","yönetim","ekip","takım","performans","gelişim","motivasyon",
"analiz","veri","istatistik","grafik","sunumlar","toplantılar","görüşme","eğitim","öğrenim","deneyim",
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
