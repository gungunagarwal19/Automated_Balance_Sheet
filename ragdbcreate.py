import pandas as pd
import psycopg2
import random
import sys

# --- Config ---
CSV_PATH = "Augmented_GL_Reconciliation_Data.csv"
DB_PARAMS = {
    "dbname": "neondb",
    "user": "neondb_owner",
    "password": "npg_TvZiyahl4H3m",
    "host": "ep-twilight-river-ahdd9h45-pooler.c-3.us-east-1.aws.neon.tech",
    "port": 5432,
    "sslmode": "require"
}
CYCLES = 10
VAR_MIN, VAR_MAX = 5, 15

# --- Connect to PostgreSQL ---
print("Attempting database connection...")
try:
    conn = psycopg2.connect(**DB_PARAMS)
    conn.set_session(autocommit=False)  # Explicit transaction mode
    cur = conn.cursor()
    print("✓ Connected successfully")
except Exception as e:
    sys.exit(f"DB connection failed: {e}")

# --- Ensure table exists ---
print("Creating/verifying table...")
try:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS gl_reviews (
        id SERIAL PRIMARY KEY,
        gl_account VARCHAR(50),
        review_cycle INT,
        prev_amount NUMERIC(18,2),
        current_amount NUMERIC(18,2),
        variance_value NUMERIC(10,2),
        record_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()
    print("✓ Table ready")
except Exception as e:
    print(f"Table creation error: {e}")
    conn.rollback()

# --- Check initial record count ---
try:
    cur.execute("SELECT COUNT(*) FROM gl_reviews;")
    initial_count = cur.fetchone()[0]
    print(f"✓ Current records in gl_reviews: {initial_count}")
except Exception as e:
    print(f"Error checking table: {e}")

# --- Load CSV ---
print(f"Loading CSV from {CSV_PATH}...")
try:
    df = pd.read_csv(CSV_PATH)
    print(f"✓ Loaded {len(df)} rows from CSV")
    print(f"Columns: {list(df.columns)}")
except Exception as e:
    sys.exit(f"CSV loading failed: {e}")

gl_col = "g_l_acct"
amt_col = "current_amount"

# Verify columns exist
if gl_col not in df.columns:
    sys.exit(f"Column '{gl_col}' not found in CSV")
if amt_col not in df.columns:
    sys.exit(f"Column '{amt_col}' not found in CSV")

def compute_variance(current, prev):
    if prev == 0:
        return 0
    return round(((current - prev) / prev) * 100, 2)

# --- Insert data ---
inserted_count = 0
try:
    for idx, row in df.iterrows():
        gl_account = str(row[gl_col])
        base_amount = float(row[amt_col])
        current_amount = base_amount
        
        for cycle in range(1, CYCLES + 1):
            sign = random.choice([-1, 1])
            pct_change = sign * random.uniform(VAR_MIN, VAR_MAX)
            next_amount = round(current_amount * (1 + pct_change / 100), 2)
            variance_value = compute_variance(next_amount, current_amount)
            record_text = (
                f"GL Account {gl_account}, Review {cycle}: "
                f"previous={current_amount}, current={next_amount}, "
                f"variance={variance_value}%"
            )
            
            cur.execute("""
                INSERT INTO gl_reviews (gl_account, review_cycle, prev_amount, 
                                      current_amount, variance_value, record_text)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (gl_account, cycle, current_amount, next_amount, 
                  variance_value, record_text))
            inserted_count += 1
            
            current_amount = next_amount
        
        # Commit every 100 GL accounts to avoid connection timeout
        if (idx + 1) % 100 == 0:
            conn.commit()
            print(f"✓ Processed {idx + 1}/{len(df)} GL accounts ({inserted_count} records)")
    
    # Final commit
    conn.commit()
    print(f"✓ All inserts completed. Total: {inserted_count} records")
    
    # Verify final count
    cur.execute("SELECT COUNT(*) FROM gl_reviews;")
    final_count = cur.fetchone()[0]
    print(f"✓ Final record count: {final_count} (added {final_count - initial_count})")

except Exception as e:
    conn.rollback()
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

finally:
    cur.close()
    conn.close()
    print("Connection closed.")
