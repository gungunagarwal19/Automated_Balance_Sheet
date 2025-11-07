# services.py
from typing import List, Dict
from db import get_db
from email_utiles import send_email
from datetime import datetime

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
