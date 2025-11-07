# ingest_daily.py
from db import get_db, init_db
from sap_connectors import fetch_company_trial_from_sap, extract_trial_balances
from services import insert_trial_batch, notify_maker_upload_support
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

def load_servers_and_companies():
    with get_db() as db:
        servers = db.execute("SELECT * FROM sap_servers").fetchall()
        companies = db.execute("SELECT * FROM companies").fetchall()
    return servers, companies

def run_daily_ingestion():
    init_db()
    batch_id = datetime.now().strftime("batch_%Y%m%d")
    servers, companies = load_servers_and_companies()

    for c in companies:
        # Find that company's SAP server
        srv = next((s for s in servers if s["id"] == c["sap_server_id"]), None)
        if not srv:
            continue
        rows = fetch_company_trial_from_sap(dict(srv), c["code"])
        insert_trial_batch(rows, batch_id, source="SAP")

    # Notify all makers on new items
    from db import get_db
    with get_db() as db:
        ids = db.execute("SELECT id FROM trial_lines WHERE batch_id=?",
                         (batch_id,)).fetchall()
    for r in ids:
        notify_maker_upload_support(r["id"])

scheduler = BlockingScheduler()
@scheduler.scheduled_job('cron', hour=1)  # Run at 1 AM
def scheduled_extract():
    extract_trial_balances()

scheduler.start()

if __name__ == "__main__":
    run_daily_ingestion()
