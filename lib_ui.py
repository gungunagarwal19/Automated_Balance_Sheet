# lib_ui.py
import streamlit as st
from pathlib import Path
from db import get_db

UPLOAD_ROOT = Path("uploads")
UPLOAD_ROOT.mkdir(exist_ok=True)

def require_role(role: str):
    if "role" not in st.session_state or st.session_state.role != role:
        st.error("⛔ Unauthorized")
        st.stop()

def current_user_id():
    with get_db() as db:
        row = db.execute("SELECT id FROM users WHERE username=?",
                         (st.session_state.username,)).fetchone()
    return row["id"] if row else None

def store_attachment(trial_line_id: int, file):
    company_dir = UPLOAD_ROOT / str(trial_line_id)
    company_dir.mkdir(parents=True, exist_ok=True)
    path = company_dir / file.name
    with open(path, "wb") as f:
        f.write(file.getbuffer())
    with get_db() as db:
        db.execute("INSERT INTO attachments(trial_line_id, uploaded_by, path) VALUES(?,?,?)",
                   (trial_line_id, current_user_id(), str(path)))
