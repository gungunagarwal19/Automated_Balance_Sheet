import streamlit as st
import pandas as pd
from db import get_db
from lib_ui import require_role, store_attachment, current_user_id
from services import on_user_uploaded_support

require_role("maker")
st.title("📌 Maker Dashboard")

tab1, tab2 = st.tabs(["My pending GLs", "Upload NON-SAP trial"])

with tab1:
    with get_db() as db:
        items = db.execute("""
            SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description, tl.status
            FROM trial_lines tl
            WHERE tl.maker_id=? AND tl.status='awaiting_support'
            ORDER BY tl.created_at DESC
        """, (current_user_id(),)).fetchall()

    for it in items:
        with st.expander(f"{it['company_code']} • GL {it['gl_account']} — {it['gl_description']}"):
            f = st.file_uploader("Upload supporting / backup working file", key=f"up_{it['id']}")
            reviewer_id = st.number_input("Assign Reviewer (user id)", min_value=1, step=1,
                                          key=f"rev_{it['id']}")
            if f and st.button("Submit Support", key=f"btn_{it['id']}"):
                store_attachment(it["id"], f)
                on_user_uploaded_support(it["id"], reviewer_id)
                st.success("Uploaded and sent to Reviewer ✅")

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
        st.write("Select which of your columns correspond to our required fields:")
        
        # Required field mappings
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Required Fields**")
            
            # Default to columns that match our names or contain keywords
            def find_best_match(cols, keywords):
                for col in cols:
                    if any(k.lower() in col.lower() for k in keywords):
                        return col
                return None
            
            company_col = st.selectbox(
                "Company Code Column",
                options=[""] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["company", "comp", "entity"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["company", "comp", "entity"])) + 1
            )
            
            gl_col = st.selectbox(
                "GL Account Column",
                options=[""] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["gl", "account", "acc"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["gl", "account", "acc"])) + 1
            )
            
            amount_col = st.selectbox(
                "Amount Column",
                options=[""] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["amount", "value", "balance"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["amount", "value", "balance"])) + 1
            )
            
            # For demo, default currency to INR if not found
            currency_col = st.selectbox(
                "Currency Column (or enter default)",
                options=["[Default: INR]"] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["currency", "curr", "ccy"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["currency", "curr", "ccy"])) + 1
            )
        
        with col2:
            st.markdown("**Optional Fields**")
            desc_col = st.selectbox(
                "Description Column",
                options=["[Skip]"] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["desc", "name", "text"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["desc", "name", "text"])) + 1
            )
            
            date_col = st.selectbox(
                "Posting Date Column",
                options=["[Skip]"] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["date", "post"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["date", "post"])) + 1
            )
            
            cc_col = st.selectbox(
                "Cost Center Column",
                options=["[Skip]"] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["cost", "cc"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["cost", "cc"])) + 1
            )
            
            pc_col = st.selectbox(
                "Profit Center Column",
                options=["[Skip]"] + list(df.columns),
                index=0 if not find_best_match(df.columns, ["profit", "pc"]) else 
                     list(df.columns).index(find_best_match(df.columns, ["profit", "pc"])) + 1
            )
        
        if st.button("Ingest NON-SAP Trial"):
            if not all([company_col, gl_col, amount_col]):
                st.error("❌ Please map all required fields (Company, GL, Amount)")
                st.stop()
                
            # Create new dataframe with mapped columns
            mapped_df = pd.DataFrame()
            mapped_df['company_code'] = df[company_col] if company_col else None
            mapped_df['gl_account'] = df[gl_col] if gl_col else None
            mapped_df['amount'] = df[amount_col] if amount_col else None
            mapped_df['currency'] = df[currency_col] if currency_col != "[Default: INR]" else "INR"
            
            # Optional columns
            if desc_col != "[Skip]":
                mapped_df['gl_description'] = df[desc_col]
            if date_col != "[Skip]":
                mapped_df['posting_date'] = df[date_col]
            if cc_col != "[Skip]":
                mapped_df['cost_center'] = df[cc_col]
            if pc_col != "[Skip]":
                mapped_df['profit_center'] = df[pc_col]
            
            # Add remaining required fields
            mapped_df["source"] = "NON_SAP"
            mapped_df["batch_id"] = "manual_" + pd.Timestamp.now().strftime("%Y%m%d%H%M")
        
            # Convert to records for insertion
            rows = mapped_df.to_dict(orient="records")
            
            # Show preview of mapped data
            st.write("### Preview of Mapped Data")
            st.dataframe(mapped_df.head())
            
            if st.button("Confirm and Save"):
                try:
                    from services import insert_trial_batch, notify_maker_upload_support
                    insert_trial_batch(rows, rows[0]["batch_id"], "NON_SAP")
                    
                    # notify current maker for all new lines assigned to them today
                    with get_db() as db:
                        ids = db.execute("""
                            SELECT id FROM trial_lines
                            WHERE batch_id=? AND maker_id=?
                        """, (rows[0]["batch_id"], current_user_id())).fetchall()
                    for r in ids:
                        notify_maker_upload_support(r["id"])
                    st.success(f"✅ Successfully ingested {len(rows)} lines and notified makers")
                except Exception as e:
                    st.error(f"❌ Error ingesting data: {str(e)}")
                    st.stop()

        from services import insert_trial_batch, notify_maker_upload_support
        insert_trial_batch(rows, rows[0]["batch_id"], "NON_SAP")

        # notify current maker for all new lines assigned to them today
        with get_db() as db:
            ids = db.execute("""
                SELECT id FROM trial_lines
                WHERE batch_id=? AND maker_id=?
            """, (rows[0]["batch_id"], current_user_id())).fetchall()
        for r in ids:
            notify_maker_upload_support(r["id"])
        st.success(f"Ingested {len(rows)} lines and notified makers ✅")
