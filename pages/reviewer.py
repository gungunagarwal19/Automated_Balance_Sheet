import streamlit as st
from db import get_db
from lib_ui import require_role, current_user_id
from services import on_reviewer_reviewed, request_changes, get_gl_comment, set_gl_comment
from email_utiles import send_email

require_role("reviewer")
st.title("🔍 Reviewer Dashboard")
with get_db() as db:
    items = db.execute("""
        SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description, tl.status, tl.amount, tl.posting_date, tl.batch_id, tl.maker_id
        FROM trial_lines tl
        WHERE tl.reviewer_id=? AND tl.status='submitted'
        ORDER BY tl.created_at DESC
    """, (current_user_id(),)).fetchall()

# bulk FC assignment
st.write("### Bulk actions")
bulk_fc = st.number_input("Assign Business FC (user id) for bulk approve", min_value=0, step=1, value=0, help="Enter user id and click Bulk Approve to send selected items to FC")
bulk_approve = st.button("Bulk Approve Selected → Send to FC")

selected_ids = []
for it in items:
    with st.expander(f"{it['company_code']} • GL {it['gl_account']} — {it['gl_description']}"):
        st.write(f"Amount: {it.get('amount')}  |  Posting date: {it.get('posting_date')}  |  Batch: {it.get('batch_id')}")
        # selection checkbox for bulk actions
        sel = st.checkbox("Select for bulk actions", key=f"select_{it['id']}")
        if sel:
            selected_ids.append(it['id'])

        st.write("Attachments:")
        atts = get_db().__enter__().execute(
            "SELECT path FROM attachments WHERE trial_line_id=?", (it["id"],)
        ).fetchall()
        for a in atts:
            st.write(f"- {a['path']}")

        # show existing comment (editable by reviewer as well)
        existing = get_gl_comment(it['id'])
        existing_text = existing['comment'] if existing and existing.get('comment') else ""
        comment_box = st.text_area("Comment (visible to all)", value=existing_text, key=f"cm_r_{it['id']}")
        if st.button("Save Comment", key=f"savec_r_{it['id']}"):
            set_gl_comment(it['id'], comment_box, current_user_id())
            st.success("Saved comment")

        # per-GL reject
        if st.button("Reject GL — Notify Source", key=f"reject_gl_r_{it['id']}"):
            st.session_state[f"reject_gl_r_open_{it['id']}"] = True
        if st.session_state.get(f"reject_gl_r_open_{it['id']}", False):
            rej_reason = st.text_area("Reason for rejecting this GL (will be emailed to source)", key=f"rej_reason_r_{it['id']}")
            if st.button("Send Rejection Email for GL", key=f"send_rej_gl_r_{it['id']}"):
                recipients = set()
                # try to get source email from trial_lines.source
                try:
                    with get_db() as db:
                        row = db.execute("SELECT source FROM trial_lines WHERE id=?", (it['id'],)).fetchone()
                    if row and row.get('source') and isinstance(row.get('source'), str) and '@' in row.get('source'):
                        recipients.add(row.get('source'))
                except Exception:
                    pass
                # fallback to maker email
                try:
                    with get_db() as db:
                        maker = db.execute("SELECT u.email FROM users u WHERE u.id=?", (it.get('maker_id'),)).fetchone()
                    if maker and maker.get('email'):
                        recipients.add(maker.get('email'))
                except Exception:
                    pass

                if not recipients:
                    with get_db() as db:
                        admins = db.execute("SELECT email FROM users WHERE role='admin'").fetchall()
                    for a in admins:
                        if a and a.get('email'):
                            recipients.add(a['email'])

                if not recipients:
                    st.error("No recipient email found (no source email or admin configured). Cannot send rejection email.")
                else:
                    to_list = ",".join(recipients)
                    subject = f"[Rejection] GL {it['gl_account']} / {it['company_code']} — Balance sheet not appropriate"
                    body = f"The following GL has been rejected by the reviewer.\n\nGL: {it['gl_account']}\nCompany: {it['company_code']}\nReason provided:\n{rej_reason}\n\nPlease review — the balance is not appropriate."
                    try:
                        send_email(to_list, subject, body)
                        set_gl_comment(it['id'], rej_reason, current_user_id())
                        st.success(f"Rejection email sent to: {to_list}")
                        st.session_state[f"reject_gl_r_open_{it['id']}"] = False
                    except Exception as e:
                        st.error(f"Error sending email: {str(e)}")

        fc_id = st.number_input("Assign Business FC (user id)", min_value=1, step=1,
                                key=f"fc_{it['id']}")
        comment = st.text_area("If requesting changes, enter comments here", key=f"c_{it['id']}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Approve → Send to FC", key=f"rv_{it['id']}"):
                on_reviewer_reviewed(it["id"], fc_id)
                st.success("Sent to FC ✅")
        with col2:
            if st.button("Request Changes → Back to Maker", key=f"req_{it['id']}"):
                request_changes(it["id"], comment, current_user_id())
                st.success("Requested changes and notified maker ✅")

# Bulk approve selected
if bulk_approve:
    if bulk_fc <= 0:
        st.error("Please enter a valid Business FC user id for bulk approve")
    elif not selected_ids:
        st.error("No items selected for bulk approve")
    else:
        for sid in selected_ids:
            try:
                on_reviewer_reviewed(sid, bulk_fc)
            except Exception:
                pass
        st.success(f"Sent {len(selected_ids)} selected items to FC")
