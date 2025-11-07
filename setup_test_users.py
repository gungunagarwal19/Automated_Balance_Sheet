"""
Setup script to initialize database and create test users for each role
"""
from db import init_db, get_db
from passlib.hash import pbkdf2_sha256 as pwd_hash

def setup_test_users():
    """Create test users for each role"""
    init_db()
    
    test_users = [
        ("maker1", "password123", "maker", "John Maker", "maker@test.com"),
        ("reviewer1", "password123", "reviewer", "Jane Reviewer", "reviewer@test.com"),
        ("fc1", "password123", "fc", "Bob FC", "fc@test.com"),
        ("cfo1", "password123", "cfo", "Alice CFO", "cfo@test.com"),
        ("admin1", "password123", "admin", "Admin User", "admin@test.com"),
    ]
    
    with get_db() as db:
        for username, password, role, name, email in test_users:
            # Check if user exists
            exists = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
            
            if not exists:
                ph = pwd_hash.hash(password)
                db.execute(
                    "INSERT INTO users(username, password_hash, role, name, email) VALUES(?,?,?,?,?)",
                    (username, ph, role, name, email)
                )
                print(f"✅ Created user: {username} ({role})")
            else:
                print(f"⏭️  User already exists: {username}")
    
    print("\n" + "="*50)
    print("Test users created successfully!")
    print("="*50)
    print("\nLogin credentials:")
    print("-" * 50)
    for username, password, role, name, email in test_users:
        print(f"Role: {role:10} | Username: {username:15} | Password: {password}")
    print("-" * 50)
    print("\nYou can now run: streamlit run app.py")

if __name__ == "__main__":
    setup_test_users()
