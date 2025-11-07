import streamlit as st
import pandas as pd
from db import get_db
from lib_ui import require_role, store_attachment, current_user_id
from services import on_user_uploaded_support, set_gl_comment, get_gl_comment
from email_utiles import send_email

require_role("maker")
st.title("📌 Maker Dashboard")

# helper to find a likely email column name in uploaded dataframe
def find_email_col(cols):
    for c in cols:
        if any(k in c.lower() for k in ("email", "e-mail", "contact", "from", "sender")):
            return c
    return None

tab1, tab2 = st.tabs(["My pending GLs", "Upload NON-SAP trial"])

with tab1:
    with get_db() as db:
        items = db.execute("""
            SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description, tl.status, tl.batch_id, tl.reviewer_id
            FROM trial_lines tl
            WHERE tl.maker_id=?
            ORDER BY tl.created_at DESC
        """, (current_user_id(),)).fetchall()

    for it in items:
        approved = True if it['status'] in ('reviewed','fc_approved') else False
        header = f"{it['company_code']} • GL {it['gl_account']} — {it['gl_description']}"
        if approved:
            header = header + "  ✅ Approved by Checker"
        else:
            header = header + f"  (status: {it['status']})"
        with st.expander(header):
            f = st.file_uploader("Upload supporting / backup working file", key=f"up_{it['id']}")
            reviewer_id = st.number_input("Assign Reviewer (user id)", min_value=1, step=1,
                                          key=f"rev_{it['id']}")
            st.write(f"Batch: {it.get('batch_id')}  •  Reviewer: {it.get('reviewer_id')} ")
            # Comment section (editable by anyone and visible to all)
            existing = get_gl_comment(it['id'])
            existing_text = existing['comment'] if existing and existing.get('comment') else ""
            comment_text = st.text_area("Comment (visible to all)", value=existing_text, key=f"cm_{it['id']}")
            if st.button("Save Comment", key=f"savec_{it['id']}"):
                set_gl_comment(it['id'], comment_text, current_user_id())
                st.success("Saved comment")
            if f and st.button("Submit Support", key=f"btn_{it['id']}"):
                store_attachment(it["id"], f)
                on_user_uploaded_support(it["id"], reviewer_id)
                st.success("Uploaded and sent to Reviewer ✅")

            # Per-GL reject button: allow maker to reject a single GL and notify source/admins
            if st.button("Reject GL — Notify Source", key=f"reject_gl_{it['id']}"):
                st.session_state[f"reject_gl_open_{it['id']}"] = True

            if st.session_state.get(f"reject_gl_open_{it['id']}", False):
                rej_reason = st.text_area("Reason for rejecting this GL (will be emailed to source)", key=f"rej_reason_{it['id']}")
                if st.button("Send Rejection Email for GL", key=f"send_rej_gl_{it['id']}"):
                    # find source email from trial_lines.source or fallback to admins
                    recipients = set()
                    # try to locate a source email stored on the trial line
                    try:
                        with get_db() as db:
                            row = db.execute("SELECT source, batch_id, company_code, gl_account FROM trial_lines WHERE id=?", (it['id'],)).fetchone()
                        if row and row.get('source') and isinstance(row.get('source'), str) and '@' in row.get('source'):
                            recipients.add(row.get('source'))
                    except Exception:
                        pass

                    # fallback to admins if no recipients found
                    if not recipients:
                        with get_db() as db:
                            admins = db.execute("SELECT email FROM users WHERE role='admin'").fetchall()
                        for a in admins:
                            if a and a.get('email'):
                                recipients.add(a['email'])

                    if not recipients:
                        st.error("No recipient email found (no source email or admin configured). Cannot send rejection email.")
                    else:
                        # persist rejection and update status
                        from services import record_rejection
                        try:
                            record_rejection(it['id'], rej_reason, current_user_id())
                        except Exception:
                            pass
                        to_list = ",".join(recipients)
                        subject = f"[Rejection] GL {it['gl_account']} / {it['company_code']} — Balance sheet not appropriate"
                        body = f"The following GL has been rejected by the maker.\n\nGL: {it['gl_account']}\nCompany: {it['company_code']}\nReason provided:\n{rej_reason}\n\nPlease review — the balance is not appropriate."
                        try:
                            send_email(to_list, subject, body)
                            st.success(f"Rejection email sent to: {to_list}")
                            st.session_state[f"reject_gl_open_{it['id']}"] = False
                        except Exception as e:
                            st.error(f"Error sending email: {str(e)}")

with tab2:
    st.write("Upload NON-SAP trial data. You can map your columns to our required fields.")
    
    f = st.file_uploader("Upload NON-SAP Trial CSV/XLSX", type=["csv","xlsx"])
    if f:
        df = pd.read_csv(f) if f.name.endswith(".csv") else pd.read_excel(f)
        if df.empty:
            st.error("File appears to be empty")
            st.stop()
            
        st.write("Preview of your data:")
        st.dataframe(df.head())
        
        # Show available columns
        st.write("### Map Your Columns")
        st.write("Select which of your columns correspond to the required fields: current amount, previous amount, company and GL.")

        def find_best_match(cols, keywords):
            for col in cols:
                if any(k.lower() in col.lower() for k in keywords):
                    return col
            return None

        company_col = st.selectbox("Company Code Column", options=[""] + list(df.columns),
                                   index=0 if not find_best_match(df.columns, ["company", "comp", "entity"]) else list(df.columns).index(find_best_match(df.columns, ["company", "comp", "entity"])) + 1)

        gl_col = st.selectbox("GL Account Column", options=[""] + list(df.columns),
                              index=0 if not find_best_match(df.columns, ["gl", "account", "acc"]) else list(df.columns).index(find_best_match(df.columns, ["gl", "account", "acc"])) + 1)

        current_col = st.selectbox("Current Amount Column", options=[""] + list(df.columns),
                                   index=0 if not find_best_match(df.columns, ["current", "this", "amount"]) else list(df.columns).index(find_best_match(df.columns, ["current", "this", "amount"])) + 1)

        previous_col = st.selectbox("Previous Amount Column", options=["[Skip]"] + list(df.columns),
                                    index=0 if not find_best_match(df.columns, ["previous", "prior", "last"]) else list(df.columns).index(find_best_match(df.columns, ["previous", "prior", "last"])) + 1)
        
        if st.button("Prepare Trial for Checker"):
            if not all([company_col, gl_col, current_col]):
                st.error("❌ Please map required fields: Company, GL, Current Amount")
                st.stop()

            # Create new dataframe with mapped columns
            mapped_df = pd.DataFrame()
            mapped_df['company_code'] = df[company_col] if company_col else None
            mapped_df['gl_account'] = df[gl_col] if gl_col else None
            mapped_df['current_amount'] = df[current_col] if current_col else 0.0
            if previous_col and previous_col != "[Skip]":
                mapped_df['previous_amount'] = df[previous_col]
            else:
                mapped_df['previous_amount'] = 0.0
            # normalize numeric columns
            mapped_df['current_amount'] = pd.to_numeric(mapped_df['current_amount'].astype(str).str.replace(',',''), errors='coerce').fillna(0.0)
            mapped_df['previous_amount'] = pd.to_numeric(mapped_df['previous_amount'].astype(str).str.replace(',',''), errors='coerce').fillna(0.0)

            # (No sign adjustments or optional fields required in this simplified flow)
            
            # Add remaining required fields for insertion
            mapped_df["source"] = "NON_SAP"
            mapped_df["batch_id"] = "manual_" + pd.Timestamp.now().strftime("%Y%m%d%H%M%S")

            # calculate trial total (do not error; just show)
            total_sum = float(mapped_df['current_amount'].sum())
            st.info(f"Trial total (sum of current amounts): {total_sum}")

            # If trial total > 0 allow maker to reject and notify source
            batch_id = mapped_df.loc[0, 'batch_id'] if 'batch_id' in mapped_df.columns else None
            if total_sum > 0:
                st.warning("Trial total is greater than zero. You may reject this batch and notify the data source if appropriate.")
                reject_key = f"reject_btn_{batch_id}"
                if st.button("Reject Trial — Notify Source", key=reject_key):
                    st.session_state[f"reject_open_{batch_id}"] = True

                if st.session_state.get(f"reject_open_{batch_id}", False):
                    reason = st.text_area("Reason for rejection (this will be sent to the source)", key=f"reject_reason_{batch_id}")
                    if st.button("Send Rejection Email", key=f"send_rej_{batch_id}"):
                        # find potential recipient emails from uploaded dataframe
                        recipients = set()
                        # try to locate an email-like column
                        def find_email_col(cols):
                            for c in cols:
                                if any(k in c.lower() for k in ("email","e-mail","contact","from","sender")):
                                    return c
                            return None

                        email_col = find_email_col(list(df.columns))
                        if email_col:
                            try:
                                for val in df[email_col].dropna().astype(str).unique().tolist():
                                    if "@" in val:
                                        recipients.add(val)
                            except Exception:
                                pass

                        # also check mapped source field
                        if 'source' in mapped_df.columns:
                            s = mapped_df.loc[0, 'source']
                            if isinstance(s, str) and '@' in s:
                                recipients.add(s)

                        # fallback: notify admins if no source email found
                        if not recipients:
                            with get_db() as db:
                                admins = db.execute("SELECT email FROM users WHERE role='admin'").fetchall()
                            for a in admins:
                                if a and a.get('email'):
                                    recipients.add(a['email'])

                        if not recipients:
                            st.error("No recipient email found (no source email or admin configured). Cannot send rejection email.")
                        else:
                            # persist rejection for batch and notify recipients
                            from services import record_batch_rejection
                            try:
                                record_batch_rejection(batch_id, reason, current_user_id())
                            except Exception:
                                pass
                            to_list = ",".join(recipients)
                            subject = f"[Rejection] Batch {batch_id or '(unknown)'} — Balance sheet not appropriate"
                            body = f"The following batch has been rejected by the maker.\n\nBatch: {batch_id}\nTrial total: {total_sum}\n\nReason provided:\n{reason}\n\nPlease review — the balance sheet is not appropriate."
                            try:
                                send_email(to_list, subject, body)
                                st.success(f"Rejection email sent to: {to_list}")
                                # close the reject box
                                st.session_state[f"reject_open_{batch_id}"] = False
                            except Exception as e:
                                st.error(f"Error sending email: {str(e)}")

            # Compute actual variation percent per row
            def compute_variation_pct(curr, prev):
                try:
                    curr = float(curr)
                    prev = float(prev)
                except Exception:
                    return 0.0
                if abs(prev) < 1e-9:
                    if abs(curr) < 1e-9:
                        return 0.0
                    return float('inf')
                return abs((curr - prev) / prev) * 100.0

            mapped_df['actual_variation_pct'] = mapped_df.apply(lambda r: compute_variation_pct(r['current_amount'], r['previous_amount']), axis=1)
        
            # Show preview of mapped data
            st.write("### Preview of Mapped Data")
            st.dataframe(mapped_df[['company_code','gl_account','current_amount','previous_amount','actual_variation_pct']].head())

            # Single allowed variation (applies to all rows) and show only rows meeting/exceeding it
            st.write("### Review variations and add comments where needed")
            allowed_batch = st.number_input("Allowed variation % for this batch", value=70.0, step=0.1, help="If actual variation for a row is >= this percent (or infinite), it will be shown here and a reason required.")
            # build mask of rows exceeding or equal to allowed_batch
            def exceeds_allowed(r):
                actual = r['actual_variation_pct']
                try:
                    # treat infinite as exceeding
                    if actual == float('inf'):
                        return True
                    return float(actual) >= float(allowed_batch)
                except Exception:
                    return False

            df_reset = mapped_df.reset_index()
            flagged = df_reset[df_reset.apply(exceeds_allowed, axis=1)]

            if flagged.empty:
                st.info("No rows meet or exceed the allowed variation — nothing to review for variation reasons.")
                # still allow sending all rows to checker without extra comments
                if st.button("Send All to Checker"):
                    try:
                        rows_to_insert = []
                        for i, r in mapped_df.iterrows():
                            rows_to_insert.append({
                                'company_code': r['company_code'],
                                'gl_account': r['gl_account'],
                                'gl_description': '',
                                'amount': float(r['current_amount']),
                                'currency': 'INR',
                                'cost_center': '',
                                'profit_center': '',
                                'text': '',
                                'reference': '',
                                'fs_group': '',
                            })
                        from services import insert_trial_batch
                        insert_trial_batch(rows_to_insert, mapped_df.loc[0, 'batch_id'], 'NON_SAP')
                        # forward to reviewer
                        with get_db() as db:
                            ids = db.execute("SELECT id, reviewer_id FROM trial_lines WHERE batch_id=? AND maker_id=?",
                                             (mapped_df.loc[0, 'batch_id'], current_user_id())).fetchall()
                        for r in ids:
                            try:
                                on_user_uploaded_support(r['id'], r.get('reviewer_id'))
                            except Exception:
                                pass
                        st.success(f"✅ Sent {len(rows_to_insert)} lines to reviewer for checking")
                    except Exception as e:
                        st.error(f"Error sending to checker: {str(e)}")
            else:
                st.write(f"{len(flagged)} rows meet or exceed the allowed variation ({allowed_batch}%). Please provide reasons for these rows before sending to checker.")
                variation_inputs = []
                missing_comments = False
                for idx, row in flagged.iterrows():
                    col_a, col_b, col_c = st.columns([2,2,4])
                    with col_a:
                        st.write(f"{row['company_code']} • {row['gl_account']}")
                    with col_b:
                        st.write(f"Actual var: {row['actual_variation_pct'] if row['actual_variation_pct']!=float('inf') else '∞'}%")
                        with col_c:
                            comment_val = st.text_area("Please enter reason for variation", key=f"var_comment_{row['index']}")
                            if not comment_val or comment_val.strip() == "":
                                missing_comments = True
                            variation_inputs.append({'idx': row['index'], 'comment': comment_val})

                            # Per-GL reject for flagged rows
                            if st.button("Reject GL — Notify Source", key=f"reject_flag_{row['index']}"):
                                st.session_state[f"reject_flag_open_{row['index']}"] = True

                            if st.session_state.get(f"reject_flag_open_{row['index']}", False):
                                flag_reason = st.text_area("Reason for rejecting this GL (will be emailed to source)", key=f"flag_rej_reason_{row['index']}")
                                if st.button("Send Rejection Email for GL", key=f"send_flag_rej_{row['index']}"):
                                    recipients = set()
                                    # try to find email in uploaded df for this row
                                    try:
                                        email_col = find_email_col(list(df.columns))
                                        if email_col:
                                            val = df.iloc[row['index']][email_col]
                                            if isinstance(val, str) and '@' in val:
                                                recipients.add(val)
                                    except Exception:
                                        pass

                                    # also check mapped source
                                    try:
                                        s = mapped_df.loc[row['index'], 'source'] if 'source' in mapped_df.columns else None
                                        if isinstance(s, str) and '@' in s:
                                            recipients.add(s)
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
                                        subject = f"[Rejection] GL {mapped_df.loc[row['index'],'gl_account']} / {mapped_df.loc[row['index'],'company_code']} — Balance sheet not appropriate"
                                        body = f"The following GL has been rejected by the maker.\n\nGL: {mapped_df.loc[row['index'],'gl_account']}\nCompany: {mapped_df.loc[row['index'],'company_code']}\nReason provided:\n{flag_reason}\n\nPlease review — the balance is not appropriate."
                                        try:
                                            send_email(to_list, subject, body)
                                            st.success(f"Rejection email sent to: {to_list}")
                                            st.session_state[f"reject_flag_open_{row['index']}"] = False
                                        except Exception as e:
                                            st.error(f"Error sending email: {str(e)}")

                if missing_comments:
                    st.warning("Some flagged rows are missing reasons. Please add comments before sending to checker.")

                if st.button("Send Flagged to Checker"):
                    if missing_comments:
                        st.error("Please provide required comments for flagged variations before sending to checker.")
                    else:
                        try:
                            # prepare rows for insertion (use current_amount as amount)
                            rows_to_insert = []
                            for i, r in mapped_df.iterrows():
                                rows_to_insert.append({
                                    'company_code': r['company_code'],
                                    'gl_account': r['gl_account'],
                                    'gl_description': '',
                                    'amount': float(r['current_amount']),
                                    'currency': 'INR',
                                    'cost_center': '',
                                    'profit_center': '',
                                    'text': '',
                                    'reference': '',
                                    'fs_group': '',
                                })

                            from services import insert_trial_batch
                            insert_trial_batch(rows_to_insert, mapped_df.loc[0, 'batch_id'], 'NON_SAP')

                            # fetch newly inserted ids for the batch and set comments if present
                            with get_db() as db:
                                new_rows = db.execute("SELECT id, company_code, gl_account FROM trial_lines WHERE batch_id=? AND maker_id=?",
                                                      (mapped_df.loc[0, 'batch_id'], current_user_id())).fetchall()
                            # map back by company+gl (best-effort) and save comments only for flagged rows
                            for vi in variation_inputs:
                                cidx = vi['idx']
                                comp = mapped_df.reset_index().loc[cidx, 'company_code']
                                gl = mapped_df.reset_index().loc[cidx, 'gl_account']
                                comment = vi.get('comment')
                                if comment and comment.strip():
                                    match = None
                                    for nr in new_rows:
                                        if nr['company_code'] == comp and nr['gl_account'] == gl:
                                            match = nr
                                            break
                                    if match:
                                        set_gl_comment(match['id'], comment, current_user_id())

                            # forward to reviewer (notify)
                            with get_db() as db:
                                ids = db.execute("SELECT id, reviewer_id FROM trial_lines WHERE batch_id=? AND maker_id=?",
                                                 (mapped_df.loc[0, 'batch_id'], current_user_id())).fetchall()
                            for r in ids:
                                try:
                                    on_user_uploaded_support(r['id'], r.get('reviewer_id'))
                                except Exception:
                                    pass
                            st.success(f"✅ Sent {len(rows_to_insert)} lines to reviewer for checking")
                        except Exception as e:
                            st.error(f"Error sending to checker: {str(e)}")

        
