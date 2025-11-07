# services.py
from typing import List, Dict
from db import get_db
from email_utiles import send_email
from datetime import datetime

# ==================== NEW WORKFLOW FUNCTIONS ====================

def add_comment(trial_line_id: int, comment: str, user_id: int, role: str):
    """Add a comment to the comment chain. Comments are appended, not replaced."""
    with get_db() as db:
        db.execute("""
            INSERT INTO gl_comments(trial_line_id, comment, commented_by, role)
            VALUES (?,?,?,?)
        """, (trial_line_id, comment, user_id, role))

def get_all_comments(trial_line_id: int) -> List[Dict]:
    """Get all comments for a trial line in chronological order."""
    with get_db() as db:
        rows = db.execute("""
            SELECT c.comment, c.role, c.commented_at, u.name as user_name
            FROM gl_comments c
            JOIN users u ON c.commented_by = u.id
            WHERE c.trial_line_id = ?
            ORDER BY c.commented_at ASC
        """, (trial_line_id,)).fetchall()
    return [dict(row) for row in rows]

def disapprove_to_previous_stage(trial_line_id: int, reason: str, user_id: int, from_role: str):
    """
    Disapprove a trial line and send it back to the previous stage.
    from_role: 'reviewer', 'fc', or 'cfo' (who is disapproving)
    """
    stage_mapping = {
        'reviewer': ('maker', 'awaiting_maker'),
        'fc': ('reviewer', 'awaiting_reviewer'),
        'cfo': ('fc', 'awaiting_fc')
    }
    
    if from_role not in stage_mapping:
        raise ValueError(f"Invalid from_role: {from_role}")
    
    previous_stage, new_status = stage_mapping[from_role]
    
    with get_db() as db:
        # Record the disapproval
        db.execute("""
            INSERT INTO disapprovals(trial_line_id, disapproved_by, disapproved_from_role, reason)
            VALUES (?,?,?,?)
        """, (trial_line_id, user_id, from_role, reason))
        
        # Update status and stage
        db.execute("""
            UPDATE trial_lines 
            SET status = ?, current_stage = ?
            WHERE id = ?
        """, (new_status, previous_stage, trial_line_id))
        
        # Add disapproval comment to the chain
        db.execute("""
            INSERT INTO gl_comments(trial_line_id, comment, commented_by, role)
            VALUES (?,?,?,?)
        """, (trial_line_id, f"[DISAPPROVED] {reason}", user_id, from_role))

def approve_to_next_stage(trial_line_id: int, user_id: int, from_role: str, next_user_id: int = None):
    """
    Approve a trial line and move it to the next stage.
    from_role: 'maker', 'reviewer', 'fc', or 'cfo' (who is approving)
    next_user_id: user ID for the next stage (reviewer_id, fc_id, or cfo_id)
    """
    stage_mapping = {
        'maker': ('reviewer', 'submitted_to_reviewer', 'reviewer_id'),
        'reviewer': ('fc', 'submitted_to_fc', 'fc_id'),
        'fc': ('cfo', 'submitted_to_cfo', 'cfo_id'),
        'cfo': ('approved', 'approved', None)
    }
    
    if from_role not in stage_mapping:
        raise ValueError(f"Invalid from_role: {from_role}")
    
    next_stage, new_status, next_user_field = stage_mapping[from_role]
    
    with get_db() as db:
        # Update status and stage
        if next_user_field and next_user_id:
            db.execute(f"""
                UPDATE trial_lines 
                SET status = ?, current_stage = ?, {next_user_field} = ?
                WHERE id = ?
            """, (new_status, next_stage, next_user_id, trial_line_id))
        else:
            db.execute("""
                UPDATE trial_lines 
                SET status = ?, current_stage = ?
                WHERE id = ?
            """, (new_status, next_stage, trial_line_id))

def insert_trial_batch_new(rows: List[Dict], batch_id: str, source: str, maker_id: int):
    """
    Insert trial balance lines with prev_amount, curr_amount, and variance calculation.
    """
    with get_db() as db:
        for r in rows:
            company = r.get("company_code")
            gl = r.get("gl_account")
            prev_amt = float(r.get("prev_amount", 0.0))
            curr_amt = float(r.get("curr_amount", 0.0))
            
            # Calculate variance percentage
            if abs(prev_amt) < 1e-9:
                if abs(curr_amt) < 1e-9:
                    variance_pct = 0.0
                else:
                    variance_pct = 100.0  # or float('inf') - using 100% for practical purposes
            else:
                variance_pct = abs((curr_amt - prev_amt) / prev_amt) * 100.0

            # Find assigned users from responsibilities
            reviewer_row = db.execute("""
                SELECT u.id FROM responsibilities resp 
                JOIN users u ON resp.user_id=u.id 
                WHERE resp.company_code=? AND resp.gl_account=? AND u.role='reviewer' 
                LIMIT 1
            """, (company, gl)).fetchone()
            
            fc_row = db.execute("""
                SELECT u.id FROM responsibilities resp 
                JOIN users u ON resp.user_id=u.id 
                WHERE resp.company_code=? AND resp.gl_account=? AND u.role='fc' 
                LIMIT 1
            """, (company, gl)).fetchone()
            
            cfo_row = db.execute("""
                SELECT u.id FROM responsibilities resp 
                JOIN users u ON resp.user_id=u.id 
                WHERE resp.company_code=? AND resp.gl_account=? AND u.role='cfo' 
                LIMIT 1
            """, (company, gl)).fetchone()

            reviewer_id = reviewer_row['id'] if reviewer_row else None
            fc_id = fc_row['id'] if fc_row else None
            cfo_id = cfo_row['id'] if cfo_row else None

            # Insert trial line
            db.execute("""
                INSERT INTO trial_lines(
                    company_code, gl_account, gl_description, doc_no, posting_date,
                    prev_amount, curr_amount, variance_pct, currency, 
                    cost_center, profit_center, text, reference,
                    source, batch_id, status, current_stage, 
                    maker_id, reviewer_id, fc_id, cfo_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                company, gl, r.get("gl_description",""), r.get("doc_no",""), r.get("posting_date",""),
                prev_amt, curr_amt, variance_pct, r.get("currency","INR"),
                r.get("cost_center",""), r.get("profit_center",""),
                r.get("text",""), r.get("reference",""), 
                source, batch_id, 'awaiting_maker', 'maker',
                maker_id, reviewer_id, fc_id, cfo_id
            ))

# ==================== LEGACY FUNCTIONS (kept for backward compatibility) ====================

def notify_attachment_mismatch(trial_line_id: int, found_sum: float):
    with get_db() as db:
        tl = db.execute("SELECT tl.id, u.email as maker_email, r.user_id as resp_user, tl.gl_account, tl.company_code, tl.amount, u.name as maker_name FROM trial_lines tl JOIN users u ON tl.maker_id=u.id LEFT JOIN responsibilities r ON r.company_code=tl.company_code AND r.gl_account=tl.gl_account WHERE tl.id=?", (trial_line_id,)).fetchone()
        # try to find reviewer
        reviewer = db.execute("SELECT u.email FROM users u JOIN trial_lines tl ON tl.reviewer_id=u.id WHERE tl.id=?", (trial_line_id,)).fetchone()
    if tl:
        body = f"Supporting file amounts ({found_sum}) do not match trial amount ({tl['amount']}) for GL {tl['gl_account']} / {tl['company_code']}. Please review."
        # notify maker
        send_email(to=tl['maker_email'], subject=f"[Mismatch] Support file mismatch for GL {tl['gl_account']}", html=body)
        # notify reviewer if present
        if reviewer:
            send_email(to=reviewer['email'], subject=f"[Alert] Support file mismatch for GL {tl['gl_account']}", html=body)

def request_changes(trial_line_id: int, comment: str, reviewer_id: int):
    # set status back to awaiting_support and notify maker
    with get_db() as db:
        db.execute("UPDATE trial_lines SET status='awaiting_support' WHERE id=?", (trial_line_id,))
        row = db.execute("SELECT u.email, tl.gl_account, tl.company_code FROM trial_lines tl JOIN users u ON tl.maker_id=u.id WHERE tl.id=?", (trial_line_id,)).fetchone()
    if row:
        send_email(
            to=row['email'],
            subject=f"[Action Required] Changes requested for GL {row['gl_account']} / {row['company_code']}",
            html=f"Reviewer has requested changes: <br><b>{comment}</b>"
        )

def notify_balance_change(company_code: str, gl_account: str, old_sum: float, new_sum: float):
    # notify all responsible users (maker) about change
    with get_db() as db:
        rows = db.execute("SELECT u.email FROM responsibilities r JOIN users u ON r.user_id=u.id WHERE r.company_code=? AND r.gl_account=?", (company_code, gl_account)).fetchall()
    body = f"Balance changed for GL {gl_account} / {company_code}: previous {old_sum}, new {new_sum}. Please review supporting documents."
    for r in rows:
        send_email(to=r['email'], subject=f"[Change] GL {gl_account} balance changed", html=body)

def upsert_users_responsibility_matrix(matrix_rows: List[Dict]):
    """matrix_rows: [{company_code, gl_account, user_id}]"""
    with get_db() as db:
        for r in matrix_rows:
            db.execute("""
                INSERT INTO responsibilities(company_code, gl_account, user_id)
                VALUES (?,?,?)
                ON CONFLICT DO NOTHING
            """, (r["company_code"], r["gl_account"], r["user_id"]))

def insert_trial_batch(rows: List[Dict], batch_id: str, source: str):
    with get_db() as db:
        for r in rows:
            company = r.get("company_code")
            gl = r.get("gl_account")

            # check existing sum for this GL
            old = db.execute("SELECT COALESCE(SUM(amount),0.0) as s FROM trial_lines WHERE company_code=? AND gl_account=?",
                             (company, gl)).fetchone()
            old_sum = float(old["s"]) if old else 0.0

            # find assigned users from responsibilities by role
            maker_row = db.execute("SELECT u.id FROM responsibilities resp JOIN users u ON resp.user_id=u.id WHERE resp.company_code=? AND resp.gl_account=? AND u.role='maker' LIMIT 1",
                                    (company, gl)).fetchone()
            reviewer_row = db.execute("SELECT u.id FROM responsibilities resp JOIN users u ON resp.user_id=u.id WHERE resp.company_code=? AND resp.gl_account=? AND u.role='reviewer' LIMIT 1",
                                      (company, gl)).fetchone()
            fc_row = db.execute("SELECT u.id FROM responsibilities resp JOIN users u ON resp.user_id=u.id WHERE resp.company_code=? AND resp.gl_account=? AND u.role='fc' LIMIT 1",
                                (company, gl)).fetchone()

            maker_id = maker_row['id'] if maker_row else None
            reviewer_id = reviewer_row['id'] if reviewer_row else None
            fc_id = fc_row['id'] if fc_row else None

            # fallback to FS-level responsibilities if fs_group provided and role not found
            fs_group = r.get('fs_group') or r.get('fs_grouping') or r.get('FS Grouping')
            if fs_group:
                if not reviewer_id:
                    fr = db.execute("SELECT user_id FROM fs_responsibilities WHERE fs_group=? AND role='reviewer' LIMIT 1", (fs_group,)).fetchone()
                    if fr:
                        reviewer_id = fr['user_id']
                if not fc_id:
                    ff = db.execute("SELECT user_id FROM fs_responsibilities WHERE fs_group=? AND role='fc' LIMIT 1", (fs_group,)).fetchone()
                    if ff:
                        fc_id = ff['user_id']

            # perform insertion with resolved user ids
            db.execute("""
                INSERT INTO trial_lines(
                    company_code, gl_account, gl_description, doc_no, posting_date,
                    amount, currency, cost_center, profit_center, text, reference,
                    source, batch_id, status, maker_id, reviewer_id, fc_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                company, gl, r.get("gl_description",""), r.get("doc_no",""), r.get("posting_date",""),
                r.get("amount",0.0), r.get("currency",""), r.get("cost_center",""), r.get("profit_center",""),
                r.get("text",""), r.get("reference",""), source, batch_id, 'awaiting_support', maker_id, reviewer_id, fc_id
            ))

            # check new sum and notify if changed
            new = db.execute("SELECT COALESCE(SUM(amount),0.0) as s FROM trial_lines WHERE company_code=? AND gl_account=?",
                             (company, gl)).fetchone()
            new_sum = float(new["s"]) if new else 0.0
            if abs(new_sum - old_sum) > 1e-6:
                try:
                    notify_balance_change(company, gl, old_sum, new_sum)
                except Exception:
                    # don't fail batch insertion on notification errors
                    pass

def notify_maker_upload_support(trial_line_id: int):
    with get_db() as db:
        tl = db.execute("SELECT tl.id, u.email, tl.gl_account, tl.company_code \
                         FROM trial_lines tl JOIN users u ON tl.maker_id=u.id \
                         WHERE tl.id=?", (trial_line_id,)).fetchone()
    if tl:
        send_email(
            to=tl["email"],
            subject=f"[Action] Upload support for GL {tl['gl_account']} / {tl['company_code']}",
            html=f"""Please upload supporting document for GL <b>{tl['gl_account']}</b>
                     (Company {tl['company_code']})."""
        )

def on_user_uploaded_support(trial_line_id: int, reviewer_id: int):
    # status -> submitted; notify reviewer
    with get_db() as db:
        db.execute("UPDATE trial_lines SET status='submitted', reviewer_id=? WHERE id=?",
                   (reviewer_id, trial_line_id))
        row = db.execute("SELECT u.email, tl.gl_account, tl.company_code \
                          FROM trial_lines tl JOIN users u ON tl.reviewer_id=u.id \
                          WHERE tl.id=?", (trial_line_id,)).fetchone()
    if row:
        send_email(
            to=row["email"],
            subject=f"[Review] Support uploaded for GL {row['gl_account']} / {row['company_code']}",
            html="A user has uploaded the working/supporting file. Please review."
        )

def on_reviewer_reviewed(trial_line_id: int, fc_id: int):
    # status -> reviewed; notify FC
    with get_db() as db:
        db.execute("UPDATE trial_lines SET status='reviewed', fc_id=? WHERE id=?",
                   (fc_id, trial_line_id))
        row = db.execute("SELECT u.email, tl.gl_account, tl.company_code \
                          FROM trial_lines tl JOIN users u ON tl.fc_id=u.id \
                          WHERE tl.id=?", (trial_line_id,)).fetchone()
    if row:
        send_email(
            to=row["email"],
            subject=f"[FC] Item ready for review: GL {row['gl_account']} / {row['company_code']}",
            html="Reviewer has approved the support. Please perform FC review."
        )

def on_fc_approved(trial_line_id: int):
    # status -> fc_approved; notify maker
    with get_db() as db:
        db.execute("UPDATE trial_lines SET status='fc_approved' WHERE id=?", (trial_line_id,))
        row = db.execute("SELECT u.email, tl.gl_account, tl.company_code \
                          FROM trial_lines tl JOIN users u ON tl.maker_id=u.id \
                          WHERE tl.id=?", (trial_line_id,)).fetchone()
    if row:
        send_email(
            to=row["email"],
            subject=f"[Closed] GL {row['gl_account']} / {row['company_code']} approved by FC",
            html="Your GL item has been reviewed and approved by Business FC."
        )


def record_rejection(trial_line_id: int, reason: str, user_id: int):
    """Persist a rejection for a single trial line and mark its status as 'rejected'."""
    with get_db() as db:
        # fetch batch id for context
        row = db.execute("SELECT batch_id FROM trial_lines WHERE id=?", (trial_line_id,)).fetchone()
        batch_id = row['batch_id'] if row else None
        db.execute("INSERT INTO rejections(trial_line_id, batch_id, reason, rejected_by) VALUES (?,?,?,?)",
                   (trial_line_id, batch_id, reason, user_id))
        db.execute("UPDATE trial_lines SET status='rejected' WHERE id=?", (trial_line_id,))


def record_batch_rejection(batch_id: str, reason: str, user_id: int):
    """Persist a rejection for all trial lines in a batch and mark them 'rejected'."""
    with get_db() as db:
        rows = db.execute("SELECT id FROM trial_lines WHERE batch_id=?", (batch_id,)).fetchall()
        for r in rows:
            db.execute("INSERT INTO rejections(trial_line_id, batch_id, reason, rejected_by) VALUES (?,?,?,?)",
                       (r['id'], batch_id, reason, user_id))
        db.execute("UPDATE trial_lines SET status='rejected' WHERE batch_id=?", (batch_id,))


def set_gl_comment(trial_line_id: int, comment: str, user_id: int):
    """Insert or update a single comment for a trial line. Any user can edit."""
    with get_db() as db:
        # try update
        updated = db.execute("""
            UPDATE gl_comments SET comment=?, updated_by=?, updated_at=(datetime('now'))
            WHERE trial_line_id=?
        """, (comment, user_id, trial_line_id)).rowcount
        if not updated:
            db.execute("""
                INSERT INTO gl_comments(trial_line_id, comment, updated_by)
                VALUES (?,?,?)
            """, (trial_line_id, comment, user_id))


def get_gl_comment(trial_line_id: int):
    with get_db() as db:
        row = db.execute("SELECT comment, updated_by, updated_at FROM gl_comments WHERE trial_line_id=?", (trial_line_id,)).fetchone()
        if row:
            return dict(row)
        return None
