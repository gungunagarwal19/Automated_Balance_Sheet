import streamlit as st
from db import get_db
from lib_ui import require_role, current_user_id
from services import add_comment, get_all_comments, approve_to_next_stage, disapprove_to_previous_stage
from mailjet_mailer import send_reviewer_to_fc

require_role("reviewer")
st.title("🔍 Reviewer Dashboard")

st.write("### Items for Review (Variance >= 30%)")

# Get items submitted to reviewer with variance >= 30%
with get_db() as db:
    items = db.execute("""
        SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description,
               tl.prev_amount, tl.curr_amount, tl.variance_pct, tl.status,
               tl.current_stage, tl.batch_id, tl.maker_id, tl.fc_id,
               u.name as maker_name
        FROM trial_lines tl
        JOIN users u ON tl.maker_id = u.id
        WHERE tl.reviewer_id = ? 
          AND tl.status IN ('submitted_to_reviewer', 'awaiting_reviewer')
          AND tl.variance_pct >= 30.0
        ORDER BY tl.variance_pct DESC, tl.created_at DESC
    """, (current_user_id(),)).fetchall()

if not items:
    st.info("No items pending for review (with variance >= 30%).")
else:
    st.write(f"Found {len(items)} items with high variance (>= 30%) awaiting your review:")
    
    st.info("💡 **Workflow**: Add your comments to items you want to approve, then click 'Submit Selected to FC' at the bottom")
    
    # Initialize session state for reviewer comments
    if 'reviewer_comments' not in st.session_state:
        st.session_state['reviewer_comments'] = {}
    if 'selected_for_fc' not in st.session_state:
        st.session_state['selected_for_fc'] = set()
    
    for item in items:
        with st.expander(f"GL {item['gl_account']} - {item['gl_description']} (Variance: {item['variance_pct']:.2f}%)"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Company:** {item['company_code']}")
                st.write(f"**Maker:** {item['maker_name']}")
                st.write(f"**Batch:** {item['batch_id']}")
            
            with col2:
                st.write(f"**Previous Amount:** {item['prev_amount']:,.2f}")
                st.write(f"**Current Amount:** {item['curr_amount']:,.2f}")
                st.write(f"**Variance:** {item['variance_pct']:.2f}%")
            
            # Show all comments in the chain (from maker)
            st.write("---")
            st.write("**Maker's Comments:**")
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
                    
                    # Highlight disapprovals
                    if '[DISAPPROVED]' in comm['comment']:
                        st.error(comm['comment'])
                    else:
                        st.info(comm['comment'])
            else:
                st.warning("No comments from maker")
            
            # Allow reviewer to add their comment
            st.write("---")
            st.write("**Add Your Review Comment:**")
            
            comment_key = f"{item['company_code']}_{item['gl_account']}_{item['id']}"
            
            # Sample comment button for reviewer too
            col_comment, col_sample = st.columns([4, 1])
            with col_sample:
                if st.button("📝 Sample", key=f"sample_rev_{item['id']}", help="Fill with sample comment"):
                    import random
                    sample_comments = [
                        "Reviewed and verified - variance is justified",
                        "Supporting documentation reviewed - acceptable",
                        "Cross-checked with previous trends - approved",
                        "Variance explanation is reasonable and well-documented",
                        "Approved based on business justification provided"
                    ]
                    st.session_state['reviewer_comments'][comment_key] = random.choice(sample_comments)
                    st.rerun()
            
            with col_comment:
                reviewer_comment = st.text_area(
                    "Your comment (required to approve):",
                    key=f"rev_comment_{item['id']}",
                    value=st.session_state['reviewer_comments'].get(comment_key, ""),
                    placeholder="Add your review notes, approval comments, or click 'Sample'..."
                )
                st.session_state['reviewer_comments'][comment_key] = reviewer_comment
            
            # Selection checkbox to approve this item
            col_select, col_disapprove = st.columns(2)
            
            with col_select:
                selected = st.checkbox(
                    "✅ Select to Approve & Send to FC",
                    key=f"select_{item['id']}",
                    value=item['id'] in st.session_state['selected_for_fc']
                )
                if selected:
                    st.session_state['selected_for_fc'].add(item['id'])
                else:
                    st.session_state['selected_for_fc'].discard(item['id'])
            
            with col_disapprove:
                # Disapprove option
                if st.button("❌ Disapprove to Maker", key=f"disapprove_btn_{item['id']}"):
                    st.session_state[f'disapprove_mode_{item["id"]}'] = True
            
            # Handle disapproval
            if st.session_state.get(f'disapprove_mode_{item["id"]}', False):
                st.error("⚠️ Disapproving will send this back to maker")
                disapproval_reason = st.text_area(
                    "Reason for disapproval:",
                    key=f"disapprove_reason_{item['id']}",
                    placeholder="Explain why this needs to go back to maker..."
                )
                
                col_cancel, col_confirm = st.columns(2)
                with col_cancel:
                    if st.button("Cancel", key=f"cancel_dis_{item['id']}"):
                        st.session_state[f'disapprove_mode_{item["id"]}'] = False
                        st.rerun()
                
                with col_confirm:
                    if st.button("⚠️ Confirm Disapproval", key=f"confirm_dis_{item['id']}", type="primary"):
                        if not disapproval_reason.strip():
                            st.error("Please provide a reason for disapproval")
                        else:
                            try:
                                # Disapprove back to maker
                                disapprove_to_previous_stage(item['id'], disapproval_reason, 
                                                            current_user_id(), 'reviewer')
                                
                                st.success("Disapproved and sent back to maker")
                                st.session_state[f'disapprove_mode_{item["id"]}'] = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

    # Submit selected items to FC
    st.write("---")
    st.write("### Submit Selected Items to FC")
    
    selected_count = len(st.session_state['selected_for_fc'])
    
    if selected_count == 0:
        st.info("No items selected. Check the boxes next to items you want to approve.")
    else:
        st.success(f"✅ {selected_count} item(s) selected for approval")
        
        # Check if all selected items have comments
        missing_comments = []
        for item_id in st.session_state['selected_for_fc']:
            # Find the item
            item = next((i for i in items if i['id'] == item_id), None)
            if item:
                comment_key = f"{item['company_code']}_{item['gl_account']}_{item['id']}"
                if not st.session_state['reviewer_comments'].get(comment_key, "").strip():
                    missing_comments.append(f"GL {item['gl_account']}")
        
        if missing_comments:
            st.warning(f"⚠️ Please add comments to: {', '.join(missing_comments)}")
        
        # Quick fill all selected with sample comments
        col_fill, col_submit = st.columns(2)
        
        with col_fill:
            if st.button("🚀 Fill Selected with Sample Comments", disabled=len(missing_comments) == 0):
                import random
                sample_comments = [
                    "Reviewed and verified - variance is justified",
                    "Supporting documentation reviewed - acceptable",
                    "Cross-checked with previous trends - approved",
                    "Variance explanation is reasonable and well-documented",
                    "Approved based on business justification provided"
                ]
                for item_id in st.session_state['selected_for_fc']:
                    item = next((i for i in items if i['id'] == item_id), None)
                    if item:
                        comment_key = f"{item['company_code']}_{item['gl_account']}_{item['id']}"
                        if not st.session_state['reviewer_comments'].get(comment_key, "").strip():
                            st.session_state['reviewer_comments'][comment_key] = random.choice(sample_comments)
                st.success("✅ Comments filled!")
                st.rerun()
        
        with col_submit:
            if st.button("✅ Submit Selected to FC", type="primary", disabled=len(missing_comments) > 0):
                try:
                    # Get first available FC
                    with get_db() as db:
                        fc = db.execute("SELECT id FROM users WHERE role='fc' LIMIT 1").fetchone()
                        fc_id = fc['id'] if fc else None
                    
                    if not fc_id:
                        st.error("No FC found in system")
                    else:
                        # Process each selected item
                        for item_id in st.session_state['selected_for_fc']:
                            item = next((i for i in items if i['id'] == item_id), None)
                            if item:
                                comment_key = f"{item['company_code']}_{item['gl_account']}_{item['id']}"
                                comment = st.session_state['reviewer_comments'].get(comment_key, "")
                                
                                # Add comment and approve
                                add_comment(item_id, comment, current_user_id(), 'reviewer')
                                approve_to_next_stage(item_id, current_user_id(), 'reviewer', fc_id)
                        
                        # Send email to FC
                        try:
                            gl_summary = f"{selected_count} GL accounts"
                            status_code, response = send_reviewer_to_fc(gl_summary)
                            if status_code not in [200, 201]:
                                st.warning(f"Email send issue: {response}")
                        except Exception as e:
                            st.warning(f"Email error (non-blocking): {e}")
                        
                        st.success(f"✅ Successfully submitted {selected_count} item(s) to FC! 📧 Email sent.")
                        
                        # Clear session state
                        st.session_state['reviewer_comments'] = {}
                        st.session_state['selected_for_fc'] = set()
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"Error submitting to FC: {str(e)}")

st.write("---")
st.write("### My Review Statistics")

with get_db() as db:
    stats = db.execute("""
        SELECT 
            COUNT(*) as total_assigned,
            SUM(CASE WHEN status = 'submitted_to_reviewer' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'submitted_to_fc' THEN 1 ELSE 0 END) as approved_to_fc
        FROM trial_lines
        WHERE reviewer_id = ?
    """, (current_user_id(),)).fetchone()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Assigned", stats['total_assigned'] if stats else 0)
with col2:
    st.metric("Pending Review", stats['pending'] if stats else 0)
with col3:
    st.metric("Approved to FC", stats['approved_to_fc'] if stats else 0)
