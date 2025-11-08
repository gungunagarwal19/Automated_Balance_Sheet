import os
os.environ["USE_TORCH"] = "1"


import streamlit as st
import os
import numpy as np
import pickle
import faiss
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
from pathlib import Path

# Optional: Set your Gemini API key here, or set as env variable outside script
os.environ["GOOGLE_API_KEY"] = "AIzaSyBKRnSUmuJnP2Zn2GxB-qiPhZW4TDkUgzM"  # Replace with your key

st.set_page_config(page_title="GL Account Chatbot", page_icon="🤖", layout="wide")

# Title
st.title("🤖 GL Account Review Chatbot")
st.markdown("Ask questions about GL account reviews, variances, and trends using AI-powered insights.")

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'model' not in st.session_state:
    st.session_state.model = None
if 'index' not in st.session_state:
    st.session_state.index = None
if 'texts' not in st.session_state:
    st.session_state.texts = None
if 'ids' not in st.session_state:
    st.session_state.ids = None
if 'initialized' not in st.session_state:
    st.session_state.initialized = False

# Functions from rag_chatbot.py
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

# Initialize the chatbot
@st.cache_resource
def initialize_chatbot():
    """Initialize the model and load data - cached to avoid reloading"""
    try:
        # Check if rag_data.pkl exists
        rag_data_path = Path("rag_data.pkl")
        if not rag_data_path.exists():
            return None, None, None, None, "RAG data file not found. Please run rag_extract_embed.py first."
        
        # Load embeddings and reviews
        ids, texts, embeddings = pickle.load(open("rag_data.pkl", "rb"))
        
        # Load semantic search model
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Build FAISS index
        index = build_faiss_index(embeddings)
        
        return model, index, texts, ids, None
    except Exception as e:
        return None, None, None, None, f"Error initializing chatbot: {str(e)}"

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Initialize button
    if st.button("🔄 Initialize/Reload Chatbot", type="primary"):
        st.session_state.initialized = False
        st.cache_resource.clear()
        st.rerun()
    
    st.markdown("---")
    
    # Search settings
    st.subheader("Search Parameters")
    top_k = st.slider("Number of results to retrieve", min_value=5, max_value=50, value=30, step=5)
    
    st.markdown("---")
    
    # GL Account filter
    st.subheader("Filters")
    gl_filter = st.text_input("Filter by GL Account (optional)", placeholder="e.g., 1000001")
    
    st.markdown("---")
    
    # Info
    st.info("""
    **How to use:**
    1. Click 'Initialize/Reload Chatbot' if not loaded
    2. Type your question in the chat
    3. Get AI-powered insights about GL accounts
    
    **Example questions:**
    - What are the high variance accounts?
    - Explain GL account 1000001
    - Show accounts with revenue trends
    - Which accounts need attention?
    """)
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()

# Initialize if not done
if not st.session_state.initialized:
    with st.spinner("Loading AI models and data... This may take a minute..."):
        model, index, texts, ids, error = initialize_chatbot()
        
        if error:
            st.error(error)
            st.info("💡 **Tip:** Make sure you have run `rag_extract_embed.py` to generate the RAG data file first.")
            st.stop()
        else:
            st.session_state.model = model
            st.session_state.index = index
            st.session_state.texts = texts
            st.session_state.ids = ids
            st.session_state.initialized = True
            st.success("✅ Chatbot initialized successfully!")

# Main chat interface
st.markdown("---")

# Display chat history
chat_container = st.container()

with chat_container:
    if not st.session_state.chat_history:
        st.info("👋 Welcome! Ask me anything about GL account reviews, variances, and trends.")
    else:
        for i, message in enumerate(st.session_state.chat_history):
            if message['role'] == 'user':
                with st.chat_message("user"):
                    st.markdown(message['content'])
            else:
                with st.chat_message("assistant"):
                    st.markdown(message['content'])
                    
                    # Show retrieved documents if available
                    if 'documents' in message and message['documents']:
                        with st.expander(f"📄 View {len(message['documents'])} retrieved documents"):
                            for j, (doc_id, doc_text) in enumerate(message['documents'][:5], 1):
                                st.markdown(f"**Document {j}** (ID: {doc_id})")
                                st.text(doc_text[:300] + "..." if len(doc_text) > 300 else doc_text)
                                st.markdown("---")

# Chat input
user_query = st.chat_input("Ask a question about GL reviews...")

if user_query:
    # Add user message to history
    st.session_state.chat_history.append({
        'role': 'user',
        'content': user_query
    })
    
    # Process query
    with st.spinner("🔍 Searching and analyzing..."):
        try:
            # Extract GL account if mentioned
            gl_account = gl_filter if gl_filter else None
            if not gl_account:
                # Try to auto-detect from query
                for part in user_query.split():
                    if part.isdigit() and len(part) >= 7:
                        gl_account = part
                        break
            
            # Perform semantic search
            results = semantic_search(
                user_query, 
                st.session_state.model, 
                st.session_state.index, 
                st.session_state.texts, 
                st.session_state.ids, 
                gl_account=gl_account,
                top_k=top_k
            )
            
            if results:
                # Get AI-powered answer
                answer = rag_answer_gemini(user_query, results)
                
                # Add assistant response to history
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': answer,
                    'documents': results
                })
            else:
                # No results found
                st.session_state.chat_history.append({
                    'role': 'assistant',
                    'content': "❌ No relevant review records found. Try a broader query or check if the GL account exists."
                })
            
        except Exception as e:
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': f"❌ Error processing query: {str(e)}"
            })
    
    # Rerun to display new messages
    st.rerun()

# Statistics section
if st.session_state.initialized:
    st.markdown("---")
    st.subheader("📊 Database Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Documents", len(st.session_state.texts) if st.session_state.texts else 0)
    
    with col2:
        st.metric("Embedding Dimension", 
                 st.session_state.index.d if st.session_state.index else 0)
    
    with col3:
        st.metric("Chat Messages", len(st.session_state.chat_history))

# Export chat history
if st.session_state.chat_history:
    st.markdown("---")
    if st.button("💾 Export Chat History"):
        chat_export = "\n\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in st.session_state.chat_history
        ])
        st.download_button(
            label="Download Chat History",
            data=chat_export,
            file_name="chat_history.txt",
            mime="text/plain"
        )
