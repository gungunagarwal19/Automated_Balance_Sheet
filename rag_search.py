import os
os.environ["USE_TORCH"] = "1"  # Force CPU/PyTorch, fix Keras/TensorFlow issues

import numpy as np
import pickle
import faiss
from sentence_transformers import SentenceTransformer

# Load results from disk (created previously by rag_extract_embed.py)
ids, texts, embeddings = pickle.load(open("rag_data.pkl", "rb"))

# Build FAISS index
def build_faiss_index(embeddings):
    embeddings_np = np.array(embeddings).astype('float32')
    index = faiss.IndexFlatL2(embeddings_np.shape[1])
    index.add(embeddings_np)
    return index

# Semantic search with optional GL-account filtering
def semantic_search(query, model, index, texts, ids, gl_account=None, top_k=10):
    query_emb = model.encode([query])
    D, I = index.search(np.array(query_emb).astype('float32'), top_k)
    results = [(ids[i], texts[i]) for i in I[0]]
    if gl_account:
        # Only include results where exact GL account is mentioned
        results = [r for r in results if f"GL Account {gl_account}" in r[1]]
    return results[:5]  # Return top 5 after filtering

if __name__ == "__main__":
    model = SentenceTransformer('all-MiniLM-L6-v2')
    index = build_faiss_index(embeddings)
    print("FAISS index built. Ready for chat!\n")

    while True:
        query = input("Ask a question about GL reviews: ")
        acct = input("GL account for filtering (optional): ").strip() or None
        results = semantic_search(query, model, index, texts, ids, gl_account=acct)
        print("\nTop matches:")
        for rid, txt in results:
            print(f"[{rid}] {txt}\n")
        print("---")
