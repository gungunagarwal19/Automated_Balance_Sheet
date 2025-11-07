# db.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("app.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            role TEXT CHECK(role IN ('maker','reviewer','fc','cfo','admin')),
            name TEXT,
            department TEXT,
            email TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS companies(
            id INTEGER PRIMARY KEY,
            code TEXT UNIQUE,
            name TEXT,
            sap_server_id INTEGER
        );

        CREATE TABLE IF NOT EXISTS sap_servers(
            id INTEGER PRIMARY KEY,
            name TEXT,
            host TEXT, client TEXT, user TEXT, password TEXT
        );

        CREATE TABLE IF NOT EXISTS gl_accounts(
            id INTEGER PRIMARY KEY,
            company_code TEXT,
            gl_account TEXT,
            gl_description TEXT
        );

        -- Responsibility matrix: who owns each GL
        CREATE TABLE IF NOT EXISTS responsibilities(
            id INTEGER PRIMARY KEY,
            company_code TEXT,
            gl_account TEXT,
            user_id INTEGER REFERENCES users(id)
        );

        -- FS grouping to role mapping (fallback when GL-level responsibility not present)
        CREATE TABLE IF NOT EXISTS fs_responsibilities(
            id INTEGER PRIMARY KEY,
            fs_group TEXT,
            role TEXT CHECK(role IN ('maker','reviewer','fc','cfo','admin')),
            user_id INTEGER REFERENCES users(id),
            UNIQUE(fs_group, role)
        );

        -- Trial lines (ingested or manual)
        CREATE TABLE IF NOT EXISTS trial_lines(
            id INTEGER PRIMARY KEY,
            company_code TEXT,
            gl_account TEXT,
            gl_description TEXT,
            doc_no TEXT,
            posting_date TEXT,
            amount REAL,
            currency TEXT,
            cost_center TEXT,
            profit_center TEXT,
            text TEXT,
            reference TEXT,
            source TEXT,         -- 'SAP' or 'NON_SAP'
            batch_id TEXT,        -- daily run identifier
            status TEXT DEFAULT 'awaiting_support' 
              CHECK (status IN ('awaiting_support','submitted','reviewed','fc_approved')),
            maker_id INTEGER REFERENCES users(id),
            reviewer_id INTEGER REFERENCES users(id),
            fc_id INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS attachments(
            id INTEGER PRIMARY KEY,
            trial_line_id INTEGER REFERENCES trial_lines(id) ON DELETE CASCADE,
            uploaded_by INTEGER REFERENCES users(id),
            path TEXT,
            uploaded_at TEXT DEFAULT (datetime('now'))
        );
        """)
