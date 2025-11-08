# rag_extract_embed.py
import os
os.environ["USE_TORCH"] = "1"
import psycopg2
from sentence_transformers import SentenceTransformer

DB_PARAMS = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_TvZiyahl4H3m",
    "host": "ep-twilight-river-ahdd9h45-pooler.c-3.us-east-1.aws.neon.tech",
    "port": 5432,
    "sslmode": "require"
}

# Step 1: Extract review records
def fetch_review_texts():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    cur.execute("SELECT id, record_text FROM gl_reviews;")
    records = cur.fetchall()
    cur.close()
    conn.close()
    ids = [r[0] for r in records]
    texts = [r[1] for r in records]
    return ids, texts

# Step 2: Embed all review texts
def embed_texts(texts):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(texts, show_progress_bar=True)
    return embeddings

if __name__ == "__main__":
    print("Fetching review texts from DB...")
    ids, texts = fetch_review_texts()
    print(f"Fetched {len(texts)} review records.")
    print("Embedding all review texts...")
    embeddings = embed_texts(texts)
    import pickle
# Save results to disk
    pickle.dump((ids, texts, embeddings), open("rag_data.pkl", "wb"))
    print("Done! You now have DB ids, texts, and embeddings ready for semantic search.")


