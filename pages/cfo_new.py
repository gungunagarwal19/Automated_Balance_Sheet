import streamlit as st
from db import get_db
from lib_ui import require_role, current_user_id
from services import add_comment, get_all_comments, approve_to_next_stage, disapprove_to_previous_stage

require_role("cfo")
st.title("👔 CFO Dashboard")

st.write("### Items for Final CFO Approval (Variance >= 30%)")

# Get items submitted to CFO with variance >= 30%
with get_db() as db:
    items = db.execute("""
        SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description,
               tl.prev_amount, tl.curr_amount, tl.variance_pct, tl.status,
               tl.current_stage, tl.batch_id, tl.maker_id, tl.reviewer_id, tl.fc_id,
               u_maker.name as maker_name, 
               u_reviewer.name as reviewer_name,
               u_fc.name as fc_name
        FROM trial_lines tl
        JOIN users u_maker ON tl.maker_id = u_maker.id
        LEFT JOIN users u_reviewer ON tl.reviewer_id = u_reviewer.id
        LEFT JOIN users u_fc ON tl.fc_id = u_fc.id
        WHERE tl.cfo_id = ? 
          AND tl.status IN ('submitted_to_cfo', 'awaiting_cfo')
          AND tl.variance_pct >= 30.0
        ORDER BY tl.variance_pct DESC, tl.created_at DESC
    """, (current_user_id(),)).fetchall()

if not items:
    st.info("No items pending for CFO approval (with variance >= 30%).")
else:
    st.write(f"Found {len(items)} items with high variance (>= 30%) awaiting final approval:")
    
    for item in items:
        with st.expander(f"GL {item['gl_account']} - {item['gl_description']} (Variance: {item['variance_pct']:.2f}%)"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Company:** {item['company_code']}")
                st.write(f"**Maker:** {item['maker_name']}")
                st.write(f"**Reviewer:** {item['reviewer_name']}")
                st.write(f"**FC:** {item['fc_name']}")
                st.write(f"**Batch:** {item['batch_id']}")
            
            with col2:
                st.write(f"**Previous Amount:** {item['prev_amount']:,.2f}")
                st.write(f"**Current Amount:** {item['curr_amount']:,.2f}")
                st.write(f"**Variance:** {item['variance_pct']:.2f}%")
            
            # Show complete comment history (Maker -> Reviewer -> FC -> CFO)
            st.write("---")
            st.write("**Complete Comment History (All Stages):**")
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
            
            # Allow CFO to add their final comment
            st.write("---")
            st.write("**Add Your CFO Comment:**")
            cfo_comment = st.text_area(
                "Your comment (will be added to the chain):",
                key=f"cfo_comment_{item['id']}",
                placeholder="Add your final CFO review notes or approval comments..."
            )
            
            # Actions
            st.write("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Final Approval:**")
                
                if st.button("✅ Give Final Approval", key=f"approve_{item['id']}"):
                    if not cfo_comment.strip():
                        st.error("Please add a comment before approving")
                    else:
                        try:
                            # Add CFO's comment
                            add_comment(item['id'], cfo_comment, current_user_id(), 'cfo')
                            
                            # Final approval (no next user needed)
                            approve_to_next_stage(item['id'], current_user_id(), 'cfo', None)
                            
                            st.success("✅ Final approval granted!")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with col2:
                st.write("**Disapprove & Send Back to FC:**")
                disapproval_reason = st.text_area(
                    "Reason for disapproval:",
                    key=f"disapprove_reason_{item['id']}",
                    placeholder="Explain why this needs to go back to FC..."
                )
                
                if st.button("❌ Disapprove to FC", key=f"disapprove_{item['id']}"):
                    if not disapproval_reason.strip():
                        st.error("Please provide a reason for disapproval")
                    else:
                        try:
                            # Disapprove back to FC
                            disapprove_to_previous_stage(item['id'], disapproval_reason, 
                                                        current_user_id(), 'cfo')
                            
                            st.warning("Disapproved and sent back to FC")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

st.write("---")
st.write("### My CFO Statistics")

with get_db() as db:
    stats = db.execute("""
        SELECT 
            COUNT(*) as total_assigned,
            SUM(CASE WHEN status = 'submitted_to_cfo' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as final_approved
        FROM trial_lines
        WHERE cfo_id = ?
    """, (current_user_id(),)).fetchone()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Assigned", stats['total_assigned'] if stats else 0)
with col2:
    st.metric("Pending Approval", stats['pending'] if stats else 0)
with col3:
    st.metric("Final Approved", stats['final_approved'] if stats else 0)

# Show approved items history
st.write("---")
st.write("### Recently Approved Items")

with get_db() as db:
    approved = db.execute("""
        SELECT tl.id, tl.company_code, tl.gl_account, tl.gl_description,
               tl.variance_pct, tl.created_at
        FROM trial_lines tl
        WHERE tl.cfo_id = ? AND tl.status = 'approved'
        ORDER BY tl.created_at DESC
        LIMIT 10
    """, (current_user_id(),)).fetchall()

if approved:
    for item in approved:
        st.write(f"✅ GL {item['gl_account']} - {item['gl_description']} (Variance: {item['variance_pct']:.2f}%) - Approved on {item['created_at']}")
else:
    st.info("No approved items yet")
