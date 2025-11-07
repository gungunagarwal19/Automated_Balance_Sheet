import streamlit as st
from db import get_db
from lib_ui import require_role

require_role("cfo")
st.title("🏛️ CFO Oversight")

status_choice = st.multiselect("Statuses", ["awaiting_support","submitted","reviewed","fc_approved"],
                               default=["submitted","reviewed","fc_approved"])

query = f"""
SELECT company_code, gl_account, gl_description, status, COUNT(*) cnt, 
       SUM(CASE WHEN currency='INR' THEN amount ELSE 0 END) sum_inr
FROM trial_lines
WHERE status IN ({','.join('?'*len(status_choice))})
GROUP BY company_code, gl_account, gl_description, status
ORDER BY company_code, gl_account
"""
with get_db() as db:
    rows = db.execute(query, status_choice).fetchall()

st.dataframe([{k: r[k] for k in r.keys()} for r in rows], use_container_width=True)
