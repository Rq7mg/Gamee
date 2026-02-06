import random

# Örnek kelime listesi
words = [
    "SİYAH","KIRMIZI","MAVİ","YEŞİL","SARI","MOR","BEYAZ","ÇANTA","ARABA","TELEFON",
    "BİLGİSAYAR","KALEM","MASA","OKUL","ŞEHİR","DENİZ","ORMAN","BÜYÜK","KÜÇÜK","KÖPEK"
]

class FillGame:
    def __init__(self, rounds=10):
        self.rounds = rounds
        self.current_round = 0
        self.score = {}
        self.current_word = ""
        self.masked_word = ""
        self.revealed_letters = []

    def start_round(self):
        self.current_round += 1
        self.current_word = random.choice(words)
        letters_to_reveal = self.calculate_letters_to_reveal(self.current_word)
        self.masked_word, self.revealed_letters = self.mask_word(self.current_word, letters_to_reveal)
        print(f"🎯 Boşluk Doldurma oyunu başladı!")
        print(f"Zorluk: Kolay")
        print(f"Puan: {self.score}")
        print(f"Round: {self.current_round}/{self.rounds}")
        print(f"📚 {len(self.current_word)} harf: {' '.join(self.revealed_letters)}")
        print(f"🎲 {self.masked_word}")

    def mask_word(self, word: str, letters_to_reveal: int):
        """
        Kelimeyi maskeler ve açılan harfleri + olarak gösterir
        """
        word_letters = list(word)
        masked = ["-" for _ in word_letters]
        indices = list(range(len(word_letters)))
        random.shuffle(indices)
        reveal_indices = indices[:letters_to_reveal]
        for i in reveal_indices:
            masked[i] = "+"  # açılan harflerin yerine +
        return " ".join(masked), [word_letters[i] for i in reveal_indices]

    def calculate_letters_to_reveal(self, word: str):
        l = len(word)
        if l <= 5:
            return 1
        elif l == 6:
            return random.choice([1,2])
        else:
            return random.choice([2,3])

    def guess(self, user: str, guess_word: str):
        if self.normalize(guess_word) == self.normalize(self.current_word):
            self.score[user] = self.score.get(user, 0) + 1
            print(f"{user} doğru tahmin etti! Puan: {self.score[user]}")
            if self.current_round < self.rounds:
                self.start_round()
            else:
                self.end_game()
        else:
            print(f"{user} yanlış tahmin: {guess_word}")

    def end_game(self):
        print("🏆 Oyun bitti! Lider tablosu:")
        sorted_score = sorted(self.score.items(), key=lambda x: x[1], reverse=True)
        for rank, (user, points) in enumerate(sorted_score, start=1):
            print(f"{rank}. {user}: {points} puan")

    @staticmethod
    def normalize(word: str) -> str:
        mapping = str.maketrans(
            "İIıiÇçŞşÖöÜüĞğ",
            "IIIiccssoougg"
        )
        return word.translate(mapping).lower()


# Telegram bot için hazır fonksiyon
fill_game = FillGame(rounds=10)

def guess_fill(update, context):
    user = update.effective_user.first_name
    guess_word = update.message.text
    fill_game.guess(user, guess_word)
