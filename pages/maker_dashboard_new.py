import streamlit as st
import pandas as pd
from db import get_db
from lib_ui import require_role, current_user_id
from services import add_comment, get_all_comments, insert_trial_batch_new, approve_to_next_stage
from mailjet_mailer import send_csv_uploaded_to_maker, send_maker_submitted_to_reviewer

require_role("maker")
st.title("📌 Maker Dashboard")

tab1, tab2 = st.tabs(["Upload Trial Balance CSV", "My Pending Items"])

with tab1:
    st.write("### Upload Trial Balance CSV")
    st.info("Upload a CSV file with columns: `prev_amount` and `curr_amount`. System will calculate variance and flag items > 30%")
    
    uploaded_file = st.file_uploader("Choose CSV file", type=['csv', 'xlsx'])
    
    if uploaded_file:
        # Read the file
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.write("### Preview of uploaded data:")
        st.dataframe(df.head(10))
        
        # Column mapping
        st.write("### Map your columns")
        cols = list(df.columns)
        
        # Auto-detect or let user select
        def find_col(keywords):
            for col in cols:
                if any(k.lower() in col.lower() for k in keywords):
                    return col
            return cols[0] if cols else None
        
        col_company = st.selectbox("Company Code", options=cols, 
                                   index=cols.index(find_col(['company', 'comp', 'entity'])) if find_col(['company', 'comp', 'entity']) else 0)
        
        col_gl = st.selectbox("GL Account", options=cols,
                             index=cols.index(find_col(['gl', 'account', 'ledger'])) if find_col(['gl', 'account', 'ledger']) else 0)
        
        col_prev = st.selectbox("Previous Amount", options=cols,
                               index=cols.index(find_col(['prev', 'previous', 'prior', 'last'])) if find_col(['prev', 'previous', 'prior', 'last']) else 0)
        
        col_curr = st.selectbox("Current Amount", options=cols,
                               index=cols.index(find_col(['curr', 'current', 'present', 'this'])) if find_col(['curr', 'current', 'present', 'this']) else 0)
        
        col_desc = st.selectbox("GL Description (Optional)", options=['[Skip]'] + cols, index=0)
        
        # Variance threshold
        variance_threshold = st.number_input("Variance Threshold (%)", value=30.0, min_value=0.0, max_value=100.0, step=5.0,
                                            help="Items with variance >= this % will require comments")
        
        if st.button("Process & Calculate Variance"):
            # Create mapped dataframe
            df_mapped = pd.DataFrame()
            df_mapped['company_code'] = df[col_company].astype(str)
            df_mapped['gl_account'] = df[col_gl].astype(str)
            df_mapped['gl_description'] = df[col_desc] if col_desc != '[Skip]' else ''
            
            # Convert amounts to numeric
            df_mapped['prev_amount'] = pd.to_numeric(df[col_prev].astype(str).str.replace(',', ''), errors='coerce').fillna(0.0)
            df_mapped['curr_amount'] = pd.to_numeric(df[col_curr].astype(str).str.replace(',', ''), errors='coerce').fillna(0.0)
            
            # Calculate variance percentage
            def calc_variance(row):
                prev = row['prev_amount']
                curr = row['curr_amount']
                if abs(prev) < 1e-9:
                    if abs(curr) < 1e-9:
                        return 0.0
                    else:
                        return 100.0  # Treat as 100% variance
                return abs((curr - prev) / prev) * 100.0
            
            df_mapped['variance_pct'] = df_mapped.apply(calc_variance, axis=1)
            df_mapped['requires_comment'] = df_mapped['variance_pct'] >= variance_threshold
            
            # Calculate trial balance
            trial_balance = df_mapped['curr_amount'].sum()
            st.metric("Trial Balance (Sum of Current Amounts)", f"{trial_balance:,.2f}")
            
            if abs(trial_balance) > 0.01:
                st.warning(f"⚠️ Trial balance is not zero! Current sum: {trial_balance:,.2f}")
            else:
                st.success("✅ Trial balance is balanced (sum = 0)")
            
            # Send email to maker notifying CSV uploaded
            try:
                gl_summary = f"{len(df_mapped)} GL accounts"
                status_code, response = send_csv_uploaded_to_maker(gl_summary)
                if status_code in [200, 201]:
                    st.success("📧 Email sent to maker")
                else:
                    st.warning(f"Email send issue: {response}")
            except Exception as e:
                st.warning(f"Email error (non-blocking): {e}")
            
            # Show items requiring comments
            items_needing_comment = df_mapped[df_mapped['requires_comment']]
            
            st.write(f"### Items requiring comment ({len(items_needing_comment)} items with variance >= {variance_threshold}%)")
            
            if len(items_needing_comment) > 0:
                st.dataframe(items_needing_comment[['company_code', 'gl_account', 'gl_description', 
                                                    'prev_amount', 'curr_amount', 'variance_pct']])
                
                # Store in session state for commenting
                st.session_state['df_mapped'] = df_mapped
                st.session_state['items_needing_comment'] = items_needing_comment
                st.session_state['variance_threshold'] = variance_threshold
                
                st.info("👇 Please add comments for high-variance items below")
            else:
                st.success("No items require comments. You can proceed to submit.")
                st.session_state['df_mapped'] = df_mapped
                st.session_state['items_needing_comment'] = items_needing_comment
                st.session_state['variance_threshold'] = variance_threshold
    
    # Comment input section
    if 'items_needing_comment' in st.session_state and st.session_state['items_needing_comment'] is not None:
        items_needing_comment = st.session_state['items_needing_comment']
        df_mapped = st.session_state['df_mapped']
        
        if len(items_needing_comment) > 0:
            st.write("### Add Comments for High Variance Items")
            
            # Initialize comments storage in session state
            if 'maker_comments' not in st.session_state:
                st.session_state['maker_comments'] = {}
            
            # Sample comments for quick testing
            sample_comments = [
                "Increased due to new customer acquisitions and expanded market reach",
                "Higher operating expenses due to inflation and new hiring",
                "Additional depreciation from new equipment purchases",
                "Seasonal revenue increase aligned with Q4 projections",
                "Cost reduction initiative implemented successfully",
                "One-time adjustment for prior period correction",
                "Foreign exchange fluctuation impact",
                "Restructuring costs included in this period"
            ]
            
            for idx, row in items_needing_comment.iterrows():
                with st.expander(f"GL {row['gl_account']} - {row['gl_description']} (Variance: {row['variance_pct']:.2f}%)"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write(f"**Company:** {row['company_code']}")
                        st.write(f"**Previous Amount:** {row['prev_amount']:,.2f}")
                        st.write(f"**Current Amount:** {row['curr_amount']:,.2f}")
                        st.write(f"**Variance:** {row['variance_pct']:.2f}%")
                    
                    with col2:
                        # Quick fill with sample comment
                        if st.button("📝 Sample", key=f"sample_{idx}", help="Fill with sample comment"):
                            import random
                            st.session_state['maker_comments'][f"{row['company_code']}_{row['gl_account']}"] = random.choice(sample_comments)
                            st.rerun()
                    
                    comment_key = f"{row['company_code']}_{row['gl_account']}"
                    comment = st.text_area(
                        "Justify this variance:", 
                        key=f"comment_{idx}",
                        value=st.session_state['maker_comments'].get(comment_key, ""),
                        placeholder="Explain the reason for this variance... (or click 'Sample' for quick test)"
                    )
                    st.session_state['maker_comments'][comment_key] = comment
                    
                    # Option to disapprove individual ledger
                    st.write("---")
                    if st.button(f"❌ Disapprove GL {row['gl_account']}", key=f"disapprove_gl_{idx}"):
                        st.session_state[f'disapprove_gl_{idx}'] = True
                    
                    if st.session_state.get(f'disapprove_gl_{idx}', False):
                        disapprove_reason = st.text_area(
                            "Why disapprove this GL?",
                            key=f"disapprove_reason_{idx}",
                            placeholder="This ledger is incorrect/inappropriate because..."
                        )
                        if st.button("Confirm Disapproval", key=f"confirm_disapprove_{idx}"):
                            if disapprove_reason.strip():
                                # Mark this GL for disapproval
                                if 'disapproved_gls' not in st.session_state:
                                    st.session_state['disapproved_gls'] = {}
                                st.session_state['disapproved_gls'][comment_key] = disapprove_reason
                                st.success(f"✅ GL {row['gl_account']} marked for disapproval")
                                st.session_state[f'disapprove_gl_{idx}'] = False
                                st.rerun()
                            else:
                                st.error("Please provide a reason for disapproval")
        
        # Submit to reviewer
        st.write("---")
        st.write("### Submit to Reviewer")
        
        # Quick actions
        col_action1, col_action2 = st.columns(2)
        
        with col_action1:
            if len(items_needing_comment) > 0:
                if st.button("🚀 Fill All with Sample Comments", help="Quickly fill all high-variance items with sample comments"):
                    import random
                    sample_comments = [
                        "Increased due to new customer acquisitions and expanded market reach",
                        "Higher operating expenses due to inflation and new hiring",
                        "Additional depreciation from new equipment purchases",
                        "Seasonal revenue increase aligned with Q4 projections",
                        "Cost reduction initiative implemented successfully",
                        "One-time adjustment for prior period correction",
                        "Foreign exchange fluctuation impact",
                        "Restructuring costs included in this period"
                    ]
                    for idx, row in items_needing_comment.iterrows():
                        comment_key = f"{row['company_code']}_{row['gl_account']}"
                        if not st.session_state['maker_comments'].get(comment_key, "").strip():
                            st.session_state['maker_comments'][comment_key] = random.choice(sample_comments)
                    st.success("✅ All comments filled with samples!")
                    st.rerun()
        
        with col_action2:
            # Option to disapprove entire trial balance
            if st.button("❌ Disapprove Entire Trial Balance", help="Reject all items in this upload"):
                st.session_state['disapprove_trial_balance'] = True
        
        # Handle trial balance disapproval
        if st.session_state.get('disapprove_trial_balance', False):
            st.error("⚠️ You are about to disapprove the ENTIRE trial balance")
            trial_disapprove_reason = st.text_area(
                "Reason for disapproving entire trial balance:",
                key="trial_disapprove_reason",
                placeholder="e.g., Trial balance not zero, data quality issues, wrong period uploaded..."
            )
            
            col_cancel, col_confirm = st.columns(2)
            with col_cancel:
                if st.button("Cancel"):
                    st.session_state['disapprove_trial_balance'] = False
                    st.rerun()
            
            with col_confirm:
                if st.button("⚠️ CONFIRM: Disapprove Entire Trial", type="primary"):
                    if not trial_disapprove_reason.strip():
                        st.error("Please provide a reason for disapproval")
                    else:
                        st.warning(f"✅ Trial balance disapproved: {trial_disapprove_reason}")
                        st.info("This trial balance will not be submitted. You can upload a corrected version.")
                        # Clear session state
                        if 'df_mapped' in st.session_state:
                            del st.session_state['df_mapped']
                        if 'items_needing_comment' in st.session_state:
                            del st.session_state['items_needing_comment']
                        if 'maker_comments' in st.session_state:
                            del st.session_state['maker_comments']
                        st.session_state['disapprove_trial_balance'] = False
                        st.rerun()
            st.stop()  # Stop further processing if disapproving
        
        # Check for individually disapproved GLs
        disapproved_gls_list = list(st.session_state.get('disapproved_gls', {}).keys()) if 'disapproved_gls' in st.session_state else []
        if disapproved_gls_list:
            st.warning(f"⚠️ {len(disapproved_gls_list)} GL(s) marked for disapproval and will be excluded from submission")
        
        # Check if all required comments are provided
        all_comments_provided = True
        if len(items_needing_comment) > 0:
            for idx, row in items_needing_comment.iterrows():
                comment_key = f"{row['company_code']}_{row['gl_account']}"
                # Skip if this GL is disapproved
                if comment_key in disapproved_gls_list:
                    continue
                if not st.session_state['maker_comments'].get(comment_key, "").strip():
                    all_comments_provided = False
                    break
        
        if not all_comments_provided:
            st.warning("⚠️ Please provide comments for all high-variance items before submitting")
        
        if st.button("Submit to Reviewer", disabled=not all_comments_provided, type="primary"):
            try:
                # Generate batch ID
                batch_id = f"batch_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Get list of disapproved GLs
                disapproved_gls_list = list(st.session_state.get('disapproved_gls', {}).keys()) if 'disapproved_gls' in st.session_state else []
                
                # Prepare rows for insertion (exclude disapproved GLs)
                rows_to_insert = []
                skipped_count = 0
                
                for idx, row in df_mapped.iterrows():
                    gl_key = f"{row['company_code']}_{row['gl_account']}"
                    
                    # Skip disapproved GLs
                    if gl_key in disapproved_gls_list:
                        skipped_count += 1
                        st.info(f"⏭️ Skipped disapproved GL: {row['gl_account']} - {st.session_state['disapproved_gls'][gl_key]}")
                        continue
                    
                    rows_to_insert.append({
                        'company_code': row['company_code'],
                        'gl_account': row['gl_account'],
                        'gl_description': row['gl_description'],
                        'prev_amount': float(row['prev_amount']),
                        'curr_amount': float(row['curr_amount']),
                        'currency': 'INR',
                        'doc_no': '',
                        'posting_date': pd.Timestamp.now().strftime('%Y-%m-%d'),
                        'cost_center': '',
                        'profit_center': '',
                        'text': '',
                        'reference': ''
                    })
                
                if not rows_to_insert:
                    st.error("No items to submit - all GLs were disapproved")
                    st.stop()
                
                # Insert batch
                insert_trial_batch_new(rows_to_insert, batch_id, 'NON_SAP', current_user_id())
                
                # Add comments for high variance items (excluding disapproved)
                with get_db() as db:
                    inserted_lines = db.execute("""
                        SELECT id, company_code, gl_account 
                        FROM trial_lines 
                        WHERE batch_id = ? AND maker_id = ?
                    """, (batch_id, current_user_id())).fetchall()
                
                for line in inserted_lines:
                    comment_key = f"{line['company_code']}_{line['gl_account']}"
                    comment = st.session_state['maker_comments'].get(comment_key, "")
                    
                    if comment.strip():
                        add_comment(line['id'], comment, current_user_id(), 'maker')
                
                # Approve all items to reviewer (auto-assign to any reviewer)
                with get_db() as db:
                    # Get first available reviewer
                    reviewer = db.execute("SELECT id FROM users WHERE role='reviewer' LIMIT 1").fetchone()
                    reviewer_id = reviewer['id'] if reviewer else None
                
                if not reviewer_id:
                    st.error("No reviewer found in system. Please create a reviewer user.")
                    st.stop()
                
                for line in inserted_lines:
                    approve_to_next_stage(line['id'], current_user_id(), 'maker', reviewer_id)
                
                # Send email to reviewer
                try:
                    gl_summary = f"{len(rows_to_insert)} GL accounts"
                    status_code, response = send_maker_submitted_to_reviewer(gl_summary)
                    if status_code not in [200, 201]:
                        st.warning(f"Email send issue: {response}")
                except Exception as e:
                    st.warning(f"Email error (non-blocking): {e}")
                
                success_msg = f"✅ Successfully submitted {len(rows_to_insert)} items to reviewer! 📧 Email sent."
                if skipped_count > 0:
                    success_msg += f" ({skipped_count} GLs were disapproved and excluded)"
                
                st.success(success_msg)
                
                # Clear session state
                del st.session_state['df_mapped']
                del st.session_state['items_needing_comment']
                del st.session_state['maker_comments']
                if 'disapproved_gls' in st.session_state:
                    del st.session_state['disapproved_gls']
                
                st.rerun()
                
            except Exception as e:
                st.error(f"Error submitting to reviewer: {str(e)}")

with tab2:
    st.write("### Items Returned for Revision")
    
    # Show items that were disapproved and sent back to maker
    with get_db() as db:
        disapproved_items = db.execute("""
            SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description,
                   tl.prev_amount, tl.curr_amount, tl.variance_pct, tl.status,
                   tl.current_stage, tl.batch_id
            FROM trial_lines tl
            WHERE tl.maker_id = ? AND tl.status = 'awaiting_maker'
            ORDER BY tl.created_at DESC
        """, (current_user_id(),)).fetchall()
    
    if not disapproved_items:
        st.info("No items pending. All items have been submitted to reviewer.")
    else:
        st.write(f"Found {len(disapproved_items)} items requiring your action:")
        
        # Option to disapprove specific item permanently
        st.info("💡 Tip: You can also choose to disapprove any item permanently if you believe it shouldn't be in the trial balance.")
        
        for item in disapproved_items:
            with st.expander(f"GL {item['gl_account']} - {item['gl_description']} (Variance: {item['variance_pct']:.2f}%)"):
                st.write(f"**Company:** {item['company_code']}")
                st.write(f"**Previous Amount:** {item['prev_amount']:,.2f}")
                st.write(f"**Current Amount:** {item['curr_amount']:,.2f}")
                st.write(f"**Variance:** {item['variance_pct']:.2f}%")
                st.write(f"**Status:** {item['status']}")
                st.write(f"**Batch:** {item['batch_id']}")
                
                # Show all comments in the chain
                st.write("---")
                st.write("**Comment History:**")
                comments = get_all_comments(item['id'])
                
                if comments:
                    for comm in comments:
                        role_emoji = {
                            'maker': '👷',
                            'reviewer': '🔍',
                            'fc': '💼',
                            'cfo': '👔'
                        }.get(comm['role'], '💬')
                        
                        st.markdown(f"{role_emoji} **{comm['role'].upper()}** ({comm['user_name']}) - {comm['commented_at']}")
                        st.info(comm['comment'])
                else:
                    st.write("No comments yet")
                
                # Allow maker to add response/revision comment
                st.write("---")
                revision_comment = st.text_area(
                    "Add your revision comment:",
                    key=f"revision_{item['id']}",
                    placeholder="Explain what you've revised or provide additional justification..."
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ Re-submit to Reviewer", key=f"resubmit_{item['id']}", type="primary"):
                        if not revision_comment.strip():
                            st.error("Please add a revision comment before re-submitting")
                        else:
                            try:
                                # Add revision comment
                                add_comment(item['id'], revision_comment, current_user_id(), 'maker')
                                
                                # Get first available reviewer
                                with get_db() as db:
                                    reviewer = db.execute("SELECT id FROM users WHERE role='reviewer' LIMIT 1").fetchone()
                                    reviewer_id = reviewer['id'] if reviewer else None
                                
                                if not reviewer_id:
                                    st.error("No reviewer found in system")
                                else:
                                    # Approve to reviewer
                                    approve_to_next_stage(item['id'], current_user_id(), 'maker', reviewer_id)
                                    st.success("✅ Re-submitted to reviewer!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error re-submitting: {str(e)}")
                
                with col2:
                    if st.button("❌ Disapprove GL", key=f"disapprove_pending_{item['id']}"):
                        st.session_state[f'disapprove_pending_{item["id"]}'] = True
                
                # Handle disapproval of pending item
                if st.session_state.get(f'disapprove_pending_{item["id"]}', False):
                    st.error("⚠️ Disapproving this GL will remove it from the workflow")
                    disapprove_pending_reason = st.text_area(
                        "Reason for permanent disapproval:",
                        key=f"disapprove_pending_reason_{item['id']}",
                        placeholder="This GL is incorrect and should be removed because..."
                    )
                    
                    col_cancel, col_confirm = st.columns(2)
                    with col_cancel:
                        if st.button("Cancel", key=f"cancel_disapprove_{item['id']}"):
                            st.session_state[f'disapprove_pending_{item["id"]}'] = False
                            st.rerun()
                    
                    with col_confirm:
                        if st.button("⚠️ Confirm Disapproval", key=f"confirm_disapprove_pending_{item['id']}", type="primary"):
                            if not disapprove_pending_reason.strip():
                                st.error("Please provide a reason")
                            else:
                                try:
                                    # Add disapproval comment
                                    add_comment(item['id'], f"[MAKER DISAPPROVED] {disapprove_pending_reason}", 
                                              current_user_id(), 'maker')
                                    
                                    # Update status to disapproved
                                    with get_db() as db:
                                        db.execute("UPDATE trial_lines SET status='disapproved' WHERE id=?", (item['id'],))
                                    
                                    st.success("✅ GL disapproved and removed from workflow")
                                    st.session_state[f'disapprove_pending_{item["id"]}'] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
