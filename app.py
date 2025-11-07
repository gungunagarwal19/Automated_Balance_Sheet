import streamlit as st
from db import init_db, get_db
from passlib.hash import pbkdf2_sha256 as pwd_hash

# Ensure DB and tables exist
init_db()

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'role' not in st.session_state:
    st.session_state.role = None
if 'username' not in st.session_state:
    st.session_state.username = None

st.title("Account — Login or Create Account")

tab1, tab2 = st.tabs(["Login", "Create Account"])

with tab1:
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        if not username or not password:
            st.error("Enter username and password")
        else:
            with get_db() as db:
                row = db.execute("SELECT username, password_hash, role FROM users WHERE username=?",
                                 (username,)).fetchone()
            if row and pwd_hash.verify(password, row["password_hash"]):
                st.session_state.logged_in = True
                st.session_state.username = row["username"]
                st.session_state.role = row["role"]
                st.success(f"✅ Logged in as {st.session_state.role.upper()}")

                # Redirect based on role (match existing switch_page usage)
                if st.session_state.role == "maker":
                    st.switch_page("pages/maker_dashboard.py")
                elif st.session_state.role == "reviewer":
                    st.switch_page("pages/reviewer.py")
                elif st.session_state.role == "fc":
                    st.switch_page("pages/fc_dashboard.py")
                elif st.session_state.role == "cfo":
                    st.switch_page("pages/cfo_dashboard.py")
                else:
                    st.info("Logged in — no specific dashboard configured for this role.")
            else:
                st.error("❌ Invalid username or/or password")

with tab2:
    st.markdown("Create a new account. Choose role carefully — admin privileges should be assigned by an administrator.")
    new_username = st.text_input("Username", key="new_username")
    name = st.text_input("Full name", key="new_name")
    email = st.text_input("Email", key="new_email")
    password1 = st.text_input("Password", type="password", key="new_pass1")
    password2 = st.text_input("Confirm password", type="password", key="new_pass2")
    role = st.selectbox("Role", options=["maker","reviewer","fc","cfo"], index=0, key="new_role")

    if st.button("Create Account"):
        # basic validation
        if not new_username or not password1 or not password2 or not email:
            st.error("Please fill all required fields")
        elif password1 != password2:
            st.error("Passwords do not match")
        else:
            with get_db() as db:
                # check uniqueness
                exists = db.execute("SELECT id FROM users WHERE username=? OR email=?",
                                    (new_username, email)).fetchone()
                if exists:
                    st.error("Username or email already taken")
                else:
                    ph = pwd_hash.hash(password1)
                    db.execute("INSERT INTO users(username, password_hash, role, name, email) VALUES(?,?,?,?,?)",
                               (new_username, ph, role, name, email))
                    st.success("Account created ✅ — you can now login")
