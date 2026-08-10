import sqlite3
import os

# 1. Veritabanı Bağlantısını Oluşturma
DB_NAME = "veritabani.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Metin parçalarını saklayacağımız tabloyu oluşturuyoruz
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dokumanlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metin TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("SQLite veritabanı ve tablo hazırlandı.")

# 2. Dokümanı Okuma ve Parçalara Bölme (Chunking)
def process_and_save_data(file_path):
    if not os.path.exists(file_path):
        print(f"Hata: {file_path} dosyası bulunamadı!")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Metni noktalara göre cümlelere/parçalara bölüyoruz
    chunks = [c.strip() for c in text.split(".") if len(c.strip()) > 10]

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Önceki verileri temizleyelim (tekrar çalıştırmalarda mükerrer kayıt olmasın)
    cursor.execute("DELETE FROM dokumanlar")

    for chunk in chunks:
        cursor.execute("INSERT INTO dokumanlar (metin) VALUES (?)", (chunk,))

    conn.commit()
    conn.close()
    print(f"Toplam {len(chunks)} metin parçası veritabanına başarıyla kaydedildi.")

if __name__ == "__main__":
    init_db()
    process_and_save_data("data/bilgiler.txt")
    