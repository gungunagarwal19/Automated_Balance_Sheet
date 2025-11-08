import os
os.environ["USE_TORCH"] = "1"


import os
# Optional: Set your Gemini API key here, or set as env variable outside script
os.environ["GOOGLE_API_KEY"] = "AIzaSyBKRnSUmuJnP2Zn2GxB-qiPhZW4TDkUgzM"  # Replace with your key

import numpy as np
import pickle
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai

# ---- Load embeddings and reviews ----
ids, texts, embeddings = pickle.load(open("rag_data.pkl", "rb"))

def build_faiss_index(embeddings):
    embeddings_np = np.array(embeddings).astype('float32')
    index = faiss.IndexFlatL2(embeddings_np.shape[1])
    index.add(embeddings_np)
    return index

def semantic_search(query, model, index, texts, ids, gl_account=None, top_k=30):
    query_emb = model.encode([query])
    D, I = index.search(np.array(query_emb).astype('float32'), top_k)
    results = [(ids[i], texts[i]) for i in I[0]]
    if gl_account:
        results = [r for r in results if f"GL Account {gl_account}" in r[1]]
    return results

def compute_stats(reviews):
    variances = []
    for _, txt in reviews:
        for seg in txt.split(','):
            if "variance=" in seg:
                try:
                    val = float(seg.split('=')[1].replace('%', ''))
                    variances.append(val)
                except:
                    pass
    avg_var = np.mean(variances) if variances else 0
    max_var = max(variances) if variances else 0
    min_var = min(variances) if variances else 0
    summary = f"Average variance: {avg_var:.2f}% | Max: {max_var:.2f}% | Min: {min_var:.2f}%"
    return summary

def rag_answer_gemini(query, retrieved_chunks):
    stats = compute_stats(retrieved_chunks)
    context = "\n".join(txt for _, txt in retrieved_chunks)
    prompt = (
        f"You are a financial analyst. "
        f"Given these GL account reviews (with stats: {stats}):\n{context}\n\n"
        f"Give a high-level summary with trends, anomalies, and explanations, and answer this question:\n{query}"
    )
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text

# ---- Main chatbot loop ----
if __name__ == "__main__":
    print("Loading semantic search model (may take a minute)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    index = build_faiss_index(embeddings)
    print("FAISS index built. Ready for Q&A with Gemini!\n")

    while True:
        query = input("Ask a question about GL reviews: ")
        acct = None
        # Optional: auto-detect GL account number from question
        for part in query.split():
            if part.isdigit() and len(part) >= 7:
                acct = part
                break
        results = semantic_search(query, model, index, texts, ids, gl_account=acct)
        print(f"\nTop {len(results)} matches:")
        for rid, txt in results:
            print(f"[{rid}] {txt}\n")
        if results:
            print("\nSending context to Gemini for high-level insight...")
            answer = rag_answer_gemini(query, results)
            print(f"\n>>> BOT INSIGHT (Gemini):\n{answer}")
        else:
            print("\nNo relevant review records found. Try a broader GL or query.")
        print("---")
