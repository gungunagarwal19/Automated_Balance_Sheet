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
            prev_amount REAL DEFAULT 0.0,
            curr_amount REAL,
            variance_pct REAL,
            currency TEXT,
            cost_center TEXT,
            profit_center TEXT,
            text TEXT,
            reference TEXT,
            source TEXT,         -- 'SAP' or 'NON_SAP'
            batch_id TEXT,        -- daily run identifier
            status TEXT DEFAULT 'awaiting_maker' 
              CHECK (status IN ('awaiting_maker','submitted_to_reviewer','awaiting_reviewer','submitted_to_fc','awaiting_fc','submitted_to_cfo','awaiting_cfo','approved','disapproved')),
            current_stage TEXT DEFAULT 'maker' CHECK(current_stage IN ('maker','reviewer','fc','cfo','approved')),
            maker_id INTEGER REFERENCES users(id),
            reviewer_id INTEGER REFERENCES users(id),
            fc_id INTEGER REFERENCES users(id),
            cfo_id INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS attachments(
            id INTEGER PRIMARY KEY,
            trial_line_id INTEGER REFERENCES trial_lines(id) ON DELETE CASCADE,
            uploaded_by INTEGER REFERENCES users(id),
            path TEXT,
            uploaded_at TEXT DEFAULT (datetime('now'))
        );

        -- Multiple comments per trial line - chained comments from maker -> reviewer -> fc -> cfo
        CREATE TABLE IF NOT EXISTS gl_comments(
            id INTEGER PRIMARY KEY,
            trial_line_id INTEGER REFERENCES trial_lines(id) ON DELETE CASCADE,
            comment TEXT,
            commented_by INTEGER REFERENCES users(id),
            role TEXT CHECK(role IN ('maker','reviewer','fc','cfo','admin')),
            commented_at TEXT DEFAULT (datetime('now'))
        );
        
        -- Track disapprovals with reason and who disapproved
        CREATE TABLE IF NOT EXISTS disapprovals(
            id INTEGER PRIMARY KEY,
            trial_line_id INTEGER REFERENCES trial_lines(id) ON DELETE CASCADE,
            disapproved_by INTEGER REFERENCES users(id),
            disapproved_from_role TEXT CHECK(disapproved_from_role IN ('reviewer','fc','cfo')),
            reason TEXT,
            disapproved_at TEXT DEFAULT (datetime('now'))
        );

        -- Rejections: record when a maker or reviewer rejects a trial line
        CREATE TABLE IF NOT EXISTS rejections(
            id INTEGER PRIMARY KEY,
            trial_line_id INTEGER REFERENCES trial_lines(id) ON DELETE CASCADE,
            batch_id TEXT,
            reason TEXT,
            rejected_by INTEGER REFERENCES users(id),
            rejected_at TEXT DEFAULT (datetime('now'))
        );
        """)
