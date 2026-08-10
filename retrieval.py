import sqlite3

DB_NAME = "veritabani.db"

def get_relevant_chunks(query, top_k=2):
    """
    Soru ile veritabanındaki metin parçalarını karşılaştırır 
    ve en alakalı olan top_k kadar parçayı getirir.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, metin FROM dokumanlar")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    # Basit ve etkili anlamsal/kelime eşleşme skoru
    query_words = set(query.lower().split())
    scored_chunks = []

    for row_id, metin in rows:
        metin_words = set(metin.lower().split())
        # Soru kelimeleri ile metin kelimelerinin kesişim sayısı
        score = len(query_words.intersection(metin_words))
        scored_chunks.append((score, metin))

    # Skora göre büyükten küçüğe sıralıyoruz
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    
    # En alakalı top_k parçayı döndürüyoruz
    return [chunk for score, chunk in scored_chunks[:top_k]]

if __name__ == "__main__":
    test_soru = "RAG mimarisi nedir?"
    bulunan_parcalar = get_relevant_chunks(test_soru)
    
    print(f"Soru: {test_soru}\n")
    print("Bulunan Alakalı Parçalar:")
    for idx, parca in enumerate(bulunan_parcalar, 1):
        print(f"{idx}. {parca}")