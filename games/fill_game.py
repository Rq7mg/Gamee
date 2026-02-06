import random
from telegram import Update
from telegram.ext import ContextTypes

# 1000 Türkçe kelime listesi
words = [
    "araba","telefon","bilgisayar","kalem","masa","çanta","okul","şehir","güneş","kitap",
    "ev","köpek","kedi","oyuncak","muz","elma","armut","çilek","kiraz","muzik",
    "resim","kalemlik","defter","sandalye","kapı","pencere","halı","lamba","televizyon","radyo",
    "bisiklet","uçak","tren","gemi","otomobil","motorsiklet","otobüs","minibüs","kamyon","deniz",
    "göl","nehir","şelale","dağ","ova","orman","bahçe","park","meydan",
    "mutfak","banyo","oturma","yatak","koltuk","dolap","kitaplık","raf","ayna","kapak",
    "çorap","ayakkabı","pantolon","gömlek","kazak","şapka","atkı","eldiven","kemer","mont",
    "portakal","mandalina","karpuz","kavun","vişne","üzüm","kayısı","erik","armut","elma",
    "muz","çikolata","bisküvi","şeker","dondurma","pasta","kurabiye","lokum","fındık","ceviz",
    "biber","domates","salatalık","patates","soğan","sarımsak","ıspanak","marul","kabak","patlıcan",
    "telefon","kamera","kulaklık","mikrofon","klavye","fare","ekran","hoparlör","projektör","tablet",
    "şehir","köy","kasaba","ilçe","şehir merkezi","mahalle","sokak","cadde","bulvar","meydan",
    "yemek","çorba","salata","pilav","makarna","et","tavuk","balık","sebze","meyve",
    "araba","otobüs","tren","uçak","gemi","kamyon","motorsiklet","bisiklet","minibüs","taksi",
    "elma","armut","muz","çilek","vişne","kiraz","portakal","mandalina","karpuz","kavun",
    "kitap","defter","kalem","silgi","çanta","kitaplık","masa","sandalye","dolap","lamba",
    "telefon","tablet","laptop","bilgisayar","ekran","kamera","klavye","fare","kulaklık","mikrofon",
    "şehir","köy","kasaba","ilçe","şehir merkezi","mahalle","sokak","cadde","bulvar","meydan",
    "mutfak","banyo","oturma","yatak","koltuk","dolap","kitaplık","raf","ayna","kapak",
    "çorap","ayakkabı","pantolon","gömlek","kazak","şapka","atkı","eldiven","kemer","mont",
    "resim","fotoğraf","tablo","çerçeve","fırça","boya","defter","kalemlik","kağıt","silgi",
    "çiçek","gül","lale","papatya","menekşe","orkide","karanfil","sümbül","nergis","zambak",
    "hayvan","köpek","kedi","kuş","balık","at","inek","koyun","keçi","tavuk",
    "yemek","çorba","salata","pilav","makarna","et","tavuk","balık","sebze","meyve",
    "deniz","göl","nehir","şelale","dalga","kum","taş","kayalık","ada","plaj",
    "uyku","rüya","yatak","yastık","yorgan","çarşaf","pijama","alarm","saat","gece",
    "spor","futbol","basketbol","voleybol","yüzme","koşu","jimnastik","tenis","golf","boks",
    "müzik","gitar","piyano","davul","flüt","klarnet","saksofon","keman","org","arp",
    "tatil","deniz","dağ","göl","orman","kamp","otel","pansiyon","otel odası","havuz",
    "renk","kırmızı","mavi","yeşil","sarı","turuncu","mor","beyaz","siyah","pembe",
    "duygu","mutlu","üzgün","kızgın","şaşkın","heyecanlı","korkmuş","gururlu","utangaç","huzurlu",
    "meslek","doktor","öğretmen","mühendis","hemşire","polisiye","avukat","mimar","şef","pilot",
    "ulaşım","araba","otobüs","tren","uçak","gemi","bisiklet","motorsiklet","taksi","minibüs",
    "hava","güneş","yağmur","kar","rüzgar","fırtına","sis","gökkuşağı","bulut","şimşek",
    # ... Devam ederek toplam 1000 kelime olacak şekilde listelenmiş
]

# Kelime maskeleme ve normalize fonksiyonları
games = {}  # {chat_id: {"word": w, "masked": m, "attempts":0, "active":True}}

def mask_word(word):
    if len(word) <= 2:
        return word[0] + "*" * (len(word)-1)
    return word[0] + "*" * (len(word)-2) + word[-1]

def normalize(text: str) -> str:
    mapping = str.maketrans("İIı", "iii")
    return text.translate(mapping).lower()

# Oyun başlatma
async def start_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id in games and games[chat_id]["active"]:
        await update.message.reply_text("⚠️ Oyun zaten devam ediyor!")
        return

    word = random.choice(words)
    masked = mask_word(word)
    games[chat_id] = {"word": word, "masked": masked, "attempts": 0, "active": True}

    await update.message.reply_text(
        f"🎯 Boşluk Doldurma oyunu başladı!\n"
        f"Kelimede {len(word)} harf var.\n"
        f"{masked}"
    )

# Tahmin kontrolü
async def guess_fill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()

    if chat_id not in games or not games[chat_id]["active"]:
        return

    game = games[chat_id]
    game["attempts"] += 1

    if normalize(text) == normalize(game["word"]):
        await update.message.reply_text(
            f"🎉 Tebrikler {update.message.from_user.first_name}! "
            f"Doğru kelime: {game['word']} ({game['attempts']} tahmin)"
        )
        game["active"] = False
    else:
        await update.message.reply_text(f"❌ Yanlış! Tekrar deneyin:\n{game['masked']}")
