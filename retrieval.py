import sqlite3

def get_relevant_chunks(query, top_k=3, db_path="rag_data.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT chunk FROM documents")
        rows = cursor.fetchall()
    except Exception:
        rows = []
    conn.close()
    
    if not rows:
        return []

    chunks = [row[0] for row in rows if any(word.lower() in row[0].lower() for word in query.split())]
    if not chunks:
        chunks = [row[0] for row in rows[:top_k]]
    return chunks[:top_k]

def get_all_chunks(db_path="rag_data.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT chunk FROM documents")
        rows = cursor.fetchall()
    except Exception:
        rows = []
    conn.close()
    return [row[0] for row in rows]