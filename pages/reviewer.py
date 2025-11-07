import streamlit as st
from db import get_db
from lib_ui import require_role, current_user_id
from services import on_reviewer_reviewed

require_role("reviewer")
st.title("🔍 Reviewer Dashboard")

with get_db() as db:
    items = db.execute("""
        SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description, tl.status
        FROM trial_lines tl
        WHERE tl.reviewer_id=? AND tl.status='submitted'
        ORDER BY tl.created_at DESC
    """, (current_user_id(),)).fetchall()

for it in items:
    with st.expander(f"{it['company_code']} • GL {it['gl_account']} — {it['gl_description']}"):
        st.write("Attachments:")
        atts = get_db().__enter__().execute(
            "SELECT path FROM attachments WHERE trial_line_id=?", (it["id"],)
        ).fetchall()
        for a in atts:
            st.write(f"- {a['path']}")
        fc_id = st.number_input("Assign Business FC (user id)", min_value=1, step=1,
                                key=f"fc_{it['id']}")
        if st.button("Mark Reviewed → Send to FC", key=f"rv_{it['id']}"):
            on_reviewer_reviewed(it["id"], fc_id)
            st.success("Sent to FC ✅")
