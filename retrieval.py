import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_data.db")

def get_relevant_chunks(query, top_k=5, db_path=DB_PATH):
    conn = sqlite3.connect(db_path, timeout=10)

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT chunk FROM documents")
        rows = cursor.fetchall()
    except Exception:
        rows = []
    conn.close()
    
    if not rows:
        return []

    query_words = [w.lower() for w in query.split() if len(w) > 1]
    
    scored_chunks = []
    for row in rows:
        chunk_text = row[0]
        chunk_lower = chunk_text.lower()
        score = sum(1 for word in query_words if word in chunk_lower)
        scored_chunks.append((score, chunk_text))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)

    matching_chunks = [chunk for score, chunk in scored_chunks if score > 0]

    if matching_chunks:
        if len(matching_chunks) < top_k:
            remaining_chunks = [chunk for score, chunk in scored_chunks if score == 0]
            chunks = matching_chunks + remaining_chunks[: (top_k - len(matching_chunks))]
        else:
            chunks = matching_chunks[:top_k]
    else:
        chunks = [chunk for score, chunk in scored_chunks[:top_k]]

    return chunks[:top_k]

def get_all_chunks(db_path=DB_PATH):
    conn = sqlite3.connect(db_path, timeout=10)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT chunk FROM documents")
        rows = cursor.fetchall()
    except Exception:
        rows = []
    conn.close()
    return [row[0] for row in rows]