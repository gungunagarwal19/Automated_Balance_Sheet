import streamlit as st
from db import get_db
from lib_ui import require_role, current_user_id
from services import add_comment, get_all_comments, approve_to_next_stage, disapprove_to_previous_stage
from mailjet_mailer import send_fc_to_cfo

require_role("fc")
st.title("💼 Financial Controller Dashboard")

st.write("### Items for FC Review (Variance >= 30%)")

# Get items submitted to FC with variance >= 30%
with get_db() as db:
    items = db.execute("""
        SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description,
               tl.prev_amount, tl.curr_amount, tl.variance_pct, tl.status,
               tl.current_stage, tl.batch_id, tl.maker_id, tl.reviewer_id, tl.cfo_id,
               u_maker.name as maker_name, u_reviewer.name as reviewer_name
        FROM trial_lines tl
        JOIN users u_maker ON tl.maker_id = u_maker.id
        LEFT JOIN users u_reviewer ON tl.reviewer_id = u_reviewer.id
        WHERE tl.fc_id = ? 
          AND tl.status IN ('submitted_to_fc', 'awaiting_fc')
          AND tl.variance_pct >= 30.0
        ORDER BY tl.variance_pct DESC, tl.created_at DESC
    """, (current_user_id(),)).fetchall()

if not items:
    st.info("No items pending for FC review (with variance >= 30%).")
else:
    st.write(f"Found {len(items)} items with high variance (>= 30%) awaiting your review:")
    
    for item in items:
        with st.expander(f"GL {item['gl_account']} - {item['gl_description']} (Variance: {item['variance_pct']:.2f}%)"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Company:** {item['company_code']}")
                st.write(f"**Maker:** {item['maker_name']}")
                st.write(f"**Reviewer:** {item['reviewer_name']}")
                st.write(f"**Batch:** {item['batch_id']}")
            
            with col2:
                st.write(f"**Previous Amount:** {item['prev_amount']:,.2f}")
                st.write(f"**Current Amount:** {item['curr_amount']:,.2f}")
                st.write(f"**Variance:** {item['variance_pct']:.2f}%")
            
            # Show all comments in the chain (Maker -> Reviewer -> FC)
            st.write("---")
            st.write("**Complete Comment History:**")
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
                st.warning("No comments in the chain")
            
            # Allow FC to add their comment
            st.write("---")
            st.write("**Add Your FC Comment:**")
            fc_comment = st.text_area(
                "Your comment (will be added to the chain):",
                key=f"fc_comment_{item['id']}",
                placeholder="Add your FC review notes, concerns, or approval comments..."
            )
            
            # Actions
            st.write("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Approve to CFO:**")
                
                if st.button("✅ Approve & Send to CFO", key=f"approve_{item['id']}", type="primary"):
                    if not fc_comment.strip():
                        st.error("Please add a comment before approving")
                    else:
                        try:
                            # Add FC's comment
                            add_comment(item['id'], fc_comment, current_user_id(), 'fc')
                            
                            # Get first available CFO
                            with get_db() as db:
                                cfo = db.execute("SELECT id FROM users WHERE role='cfo' LIMIT 1").fetchone()
                                cfo_id = cfo['id'] if cfo else None
                            
                            if not cfo_id:
                                st.error("No CFO found in system")
                            else:
                                # Approve to CFO
                                approve_to_next_stage(item['id'], current_user_id(), 'fc', cfo_id)
                                
                                # Send email to CFO
                                try:
                                    status_code, response = send_fc_to_cfo(item['gl_account'])
                                    if status_code not in [200, 201]:
                                        st.warning(f"Email send issue: {response}")
                                except Exception as e:
                                    st.warning(f"Email error (non-blocking): {e}")
                                
                                st.success("✅ Approved and sent to CFO! 📧 Email sent.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with col2:
                st.write("**Disapprove & Send Back to Reviewer:**")
                disapproval_reason = st.text_area(
                    "Reason for disapproval:",
                    key=f"disapprove_reason_{item['id']}",
                    placeholder="Explain why this needs to go back to reviewer..."
                )
                
                if st.button("❌ Disapprove to Reviewer", key=f"disapprove_{item['id']}"):
                    if not disapproval_reason.strip():
                        st.error("Please provide a reason for disapproval")
                    else:
                        try:
                            # Disapprove back to reviewer
                            disapprove_to_previous_stage(item['id'], disapproval_reason, 
                                                        current_user_id(), 'fc')
                            
                            st.warning("Disapproved and sent back to reviewer")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

st.write("---")
st.write("### My FC Statistics")

with get_db() as db:
    stats = db.execute("""
        SELECT 
            COUNT(*) as total_assigned,
            SUM(CASE WHEN status = 'submitted_to_fc' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'submitted_to_cfo' THEN 1 ELSE 0 END) as approved_to_cfo
        FROM trial_lines
        WHERE fc_id = ?
    """, (current_user_id(),)).fetchone()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Assigned", stats['total_assigned'] if stats else 0)
with col2:
    st.metric("Pending Review", stats['pending'] if stats else 0)
with col3:
    st.metric("Approved to CFO", stats['approved_to_cfo'] if stats else 0)
