# core/auth.py
import streamlit as st
import hashlib
import secrets
import string
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Password utilities ───────────────────────────────────────────────────────
def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, password):
    return stored_hash == hash_password(password)

# ── Account creation / save ──────────────────────────────────────────────────
def create_user_account(user_data, password=None):
    try:
        user_id = hashlib.sha256(f"{user_data['email']}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        
        if not password:
            password = generate_password()
        
        user_record = {
            "user_id": user_id,
            "email": user_data["email"].lower().strip(),
            "password_hash": hash_password(password),
            "account_type": user_data.get("account_for", "self"),
            "created_at": datetime.now().isoformat(),
            "last_login": datetime.now().isoformat(),
            "profile": {
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "email": user_data["email"],
                "gender": user_data.get("gender", ""),
                "birthdate": user_data.get("birthdate", ""),
                "timeline_start": user_data.get("birthdate", "")
            },
            # ... rest of the default record (settings, stats) ...
        }
        
        save_account_data(user_record)  # ← assume this function still in main for now
        return {"success": True, "user_id": user_id, "password": password, "user_record": user_record}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── Login / Signup forms ─────────────────────────────────────────────────────
def show_login_form():
    with st.form("login_form"):
        st.subheader("Welcome Back")
        email = st.text_input("Email Address", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            remember = st.checkbox("Remember me", value=True)
        with col2:
            st.markdown('<div class="forgot-password"><a href="#">Forgot password?</a></div>', unsafe_allow_html=True)
        
        if st.form_submit_button("Login to My Account", type="primary", use_container_width=True):
            if not email or not password:
                st.error("Email and password required")
            else:
                with st.spinner("Signing in..."):
                    result = authenticate_user(email, password)  # ← assume function in main for now
                    if result["success"]:
                        st.session_state.user_id = result["user_id"]
                        st.session_state.user_account = result["user_record"]
                        st.session_state.logged_in = True
                        st.session_state.data_loaded = False
                        if remember:
                            st.query_params['user'] = result["user_id"]
                        st.success("Logged in!")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Login failed"))

def show_signup_form():
    with st.form("signup_form"):
        st.subheader("Create New Account")
        col1, col2 = st.columns(2)
        with col1: first = st.text_input("First Name*", key="signup_first")
        with col2: last  = st.text_input("Last Name*",  key="signup_last")
        
        email = st.text_input("Email Address*", key="signup_email")
        
        col1, col2 = st.columns(2)
        with col1: pw   = st.text_input("Password*", type="password", key="signup_pw")
        with col2: pw2  = st.text_input("Confirm Password*", type="password", key="signup_pw2")
        
        terms = st.checkbox("I agree to Terms & Privacy*", key="signup_terms")
        
        if st.form_submit_button("Create My Account", type="primary", use_container_width=True):
            errors = []
            if not first: errors.append("First name required")
            if not last:  errors.append("Last name required")
            if not email or "@" not in email: errors.append("Valid email required")
            if len(pw) < 8: errors.append("Password ≥ 8 characters")
            if pw != pw2: errors.append("Passwords do not match")
            if not terms: errors.append("Accept terms")
            
            if errors:
                for e in errors: st.error(e)
            else:
                user_data = {"first_name": first, "last_name": last, "email": email}
                with st.spinner("Creating account..."):
                    result = create_user_account(user_data, pw)
                    if result["success"]:
                        # send_welcome_email(...)  ← move/call if needed
                        st.session_state.user_id = result["user_id"]
                        st.session_state.user_account = result["user_record"]
                        st.session_state.logged_in = True
                        st.session_state.show_profile_setup = True
                        st.success("Account created!")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Creation failed"))

def show_profile_setup_modal():
    st.markdown('<div class="profile-setup-modal">', unsafe_allow_html=True)
    st.title("👤 Complete Your Profile")
    
    with st.form("profile_setup"):
        gender = st.radio("Gender", ["Male", "Female", "Other", "Prefer not to say"], horizontal=True)
        
        st.write("**Birthdate**")
        col1, col2, col3 = st.columns(3)
        months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
        with col1: month = st.selectbox("Month", months)
        with col2: day   = st.selectbox("Day",   list(range(1,32)))
        with col3: year  = st.selectbox("Year",  list(range(2026, 1900, -1)))
        
        account_for = st.radio("Account for", ["For me", "For someone else"], horizontal=True)
        
        col1, col2 = st.columns(2)
        submit = col1.form_submit_button("Complete Profile", type="primary")
        skip   = col2.form_submit_button("Skip for Now")
        
        if submit or skip:
            birthdate = f"{month} {day}, {year}" if submit else ""
            acc_type  = "self" if account_for == "For me" else "other"
            
            if st.session_state.user_account:
                st.session_state.user_account['profile'].update({
                    "gender": gender if submit else "",
                    "birthdate": birthdate,
                    "timeline_start": birthdate
                })
                st.session_state.user_account['account_type'] = acc_type
                save_account_data(st.session_state.user_account)  # ← assume exists
            
            st.session_state.show_profile_setup = False
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# Logout (simple version - expand if needed)
def logout_user():
    keys = ['user_id', 'user_account', 'logged_in', 'show_profile_setup',
            'current_session', 'current_question', 'responses',
            'session_conversations', 'data_loaded', 'show_image_upload']
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]
    st.query_params.clear()
    st.rerun()
