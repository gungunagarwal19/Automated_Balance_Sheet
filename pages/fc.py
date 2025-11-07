import streamlit as st
from db import get_db
from lib_ui import require_role, current_user_id
from services import on_fc_approved

require_role("fc")
st.title("💼 Business FC Dashboard")

with get_db() as db:
    items = db.execute("""
        SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description, tl.status
        FROM trial_lines tl
        WHERE tl.fc_id=? AND tl.status='reviewed'
        ORDER BY tl.created_at DESC
    """, (current_user_id(),)).fetchall()

for it in items:
    with st.expander(f"{it['company_code']} • GL {it['gl_account']} — {it['gl_description']}"):
        if st.button("Approve and Notify Maker", key=f"ap_{it['id']}"):
            on_fc_approved(it["id"])
            st.success("Approved and maker notified ✅")
