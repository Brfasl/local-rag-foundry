import sqlite3
import io
from pypdf import PdfReader

def extract_text_from_pdf(file_bytes):
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text

def chunk_text(text, chunk_size=300, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def save_uploaded_file(file_bytes, file_name, db_path="rag_data.db"):
    if file_name.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
    else:
        text = file_bytes.decode("utf-8", errors="ignore")

    chunks = chunk_text(text)
    if not chunks:
        return 0

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT,
            chunk TEXT
        )
    """)

    for chunk in chunks:
        cursor.execute("INSERT INTO documents (source, chunk) VALUES (?, ?)", (file_name, chunk))

    conn.commit()
    conn.close()
    return len(chunks)