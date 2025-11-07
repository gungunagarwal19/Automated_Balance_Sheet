# lib_ui.py
import streamlit as st
from pathlib import Path
from db import get_db
import pandas as pd
from services import notify_attachment_mismatch

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
    # If attachment is a CSV/XLSX, attempt to validate summed amount against trial line
    try:
        if file.name.endswith('.csv') or file.name.endswith('.xlsx') or file.name.endswith('.xls'):
            # read file into dataframe
            df = pd.read_csv(path) if file.name.endswith('.csv') else pd.read_excel(path)
            if 'amount' in df.columns:
                found_sum = df['amount'].sum()
                # fetch trial line amount
                with get_db() as db:
                    tl = db.execute('SELECT amount FROM trial_lines WHERE id=?', (trial_line_id,)).fetchone()
                if tl and abs(found_sum - tl['amount']) > 1e-6:
                    # notify about mismatch
                    notify_attachment_mismatch(trial_line_id, float(found_sum))
    except Exception:
        # don't block upload on verification errors
        pass
