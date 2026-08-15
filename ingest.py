import io
import re
import sqlite3

def extract_text_from_pdf(bytes_data):
    # 1. Öncelik: pdfplumber (En temiz metin okuyan kütüphane)
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(bytes_data)) as pdf:
            text = ""
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            if text.strip():
                return text
    except Exception:
        pass

    # 2. Öncelik: pypdf
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(bytes_data))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        if text.strip():
            return text
    except Exception:
        pass

    return bytes_data.decode("utf-8", errors="ignore")

def fix_spaced_text(text):
    if not text:
        return ""

    # 'B e r f i n  A s l a n' veya harf harf ayrışmış metinleri birleştirme
    # Tekil harflerin (boşlukla ayrılmış tek karakterler) yoğunluğunu kontrol et
    words = text.split()
    if not words:
        return ""

    single_letters = sum(1 for w in words if len(w) == 1 and w.isalnum())
    if len(words) > 0 and (single_letters / len(words) > 0.25):
        # Çift boşluk veya daha fazlasını kelime ayırıcı simgeye dönüştür
        text_mod = re.sub(r' {2,}', ' [WORD_BOUND] ', text)
        if '[WORD_BOUND]' in text_mod:
            parts = text_mod.split('[WORD_BOUND]')
            cleaned_parts = [re.sub(r'\s+', '', p) for p in parts]
            text = " ".join(cleaned_parts)
        else:
            # Tekil boşluklarla harfleri birleştir
            raw_merged = re.sub(r'\s+', '', text)
            # Büyük harf/noktalama sınırlarında varsayılan ayırma yap
            text = re.sub(r'(?<=[a-zçğıöşü0-9,.!?:;])(?=[A-ZÇĞİÖŞÜ])', ' ', raw_merged)
            text = re.sub(r'(?<=[A-ZÇĞİÖŞÜ])(?=[A-ZÇĞİÖŞÜ][a-zçğıöşü])', ' ', text)

    return re.sub(r'\s+', ' ', text).strip()

def setup_database(db_path="rag_data.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 'documents' tablosunda 'filename' sütununun olup olmadığını güvenli şekilde kontrol et
    cursor.execute("PRAGMA table_info(documents)")
    columns_info = cursor.fetchall()
    column_names = [col[1] for col in columns_info]
    
    # Eğer tablo var ama 'filename' sütunu yoksa güvenli şekilde düşür (DROP TABLE IF EXISTS)
    if columns_info and "filename" not in column_names:
        cursor.execute("DROP TABLE IF EXISTS documents")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            chunk TEXT
        )
    """)
    conn.commit()
    conn.close()

def chunk_text_smart(text, target_size=400, overlap=50):
    if not text:
        return []
    
    # Cümle veya paragraf sonlarına göre böl
    sentences = re.split(r'(?<=[.!?\n])\s+', text)
    chunks = []
    current_chunk = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Çok uzun tek bir cümle varsa kelime kelime böl
        if len(sentence) > target_size:
            words = sentence.split()
            w_chunk = []
            w_len = 0
            for w in words:
                if w_len + len(w) + 1 > target_size and w_chunk:
                    chunk_str = " ".join(w_chunk)
                    chunks.append(chunk_str)
                    # Overlap için son kelimeleri koru
                    overlap_words = []
                    o_len = 0
                    for ow in reversed(w_chunk):
                        if o_len + len(ow) + 1 <= overlap:
                            overlap_words.insert(0, ow)
                            o_len += len(ow) + 1
                        else:
                            break
                    w_chunk = overlap_words + [w]
                    w_len = sum(len(x) + 1 for x in w_chunk)
                else:
                    w_chunk.append(w)
                    w_len += len(w) + 1
            if w_chunk:
                chunks.append(" ".join(w_chunk))
            continue

        if current_length + len(sentence) + 1 > target_size and current_chunk:
            chunk_str = " ".join(current_chunk)
            chunks.append(chunk_str)

            # Overlap için son cümleleri koru
            overlap_sentences = []
            o_len = 0
            for s in reversed(current_chunk):
                if o_len + len(s) + 1 <= overlap:
                    overlap_sentences.insert(0, s)
                    o_len += len(s) + 1
                else:
                    break
            current_chunk = overlap_sentences + [sentence]
            current_length = sum(len(x) + 1 for x in current_chunk)
        else:
            current_chunk.append(sentence)
            current_length += len(sentence) + 1

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return [c for c in chunks if c.strip()]

def save_uploaded_file(bytes_data, filename, db_path="rag_data.db"):
    # Tablo kontrolünü yap ve hazırla
    setup_database(db_path)

    if filename.lower().endswith(".pdf"):
        raw_text = extract_text_from_pdf(bytes_data)
    else:
        raw_text = bytes_data.decode("utf-8", errors="ignore")

    clean_text = fix_spaced_text(raw_text)

    if not clean_text:
        return 0

    chunks = chunk_text_smart(clean_text, target_size=400, overlap=50)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for chunk in chunks:
        if chunk.strip():
            cursor.execute("INSERT INTO documents (filename, chunk) VALUES (?, ?)", (filename, chunk))

    conn.commit()
    conn.close()

    return len(chunks)