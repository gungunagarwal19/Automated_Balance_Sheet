# services.py
from typing import List, Dict
from db import get_db
from email_utiles import send_email
from datetime import datetime

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
            db.execute("""
                INSERT INTO trial_lines(
                    company_code, gl_account, gl_description, doc_no, posting_date,
                    amount, currency, cost_center, profit_center, text, reference,
                    source, batch_id, status, maker_id
                )
                SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?, 'awaiting_support', users.id
                FROM users 
                JOIN responsibilities resp 
                  ON resp.user_id = users.id
                 AND resp.company_code = ?
                 AND resp.gl_account = ?
                LIMIT 1
            """, (
                r["company_code"], r["gl_account"], r.get("gl_description",""),
                r.get("doc_no",""), r.get("posting_date",""),
                r.get("amount",0.0), r.get("currency",""),
                r.get("cost_center",""), r.get("profit_center",""),
                r.get("text",""), r.get("reference",""),
                source, batch_id,
                r["company_code"], r["gl_account"]
            ))

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
