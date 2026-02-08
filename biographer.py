# biographer.py – MemLife main app (FIXED VERSION)
import streamlit as st
import json
from datetime import datetime, date, timedelta
from openai import OpenAI
import os
import re
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import string
import base64
import pandas as pd
import uuid
import sys
import random

# Add current directory to path to import modules
sys.path.append('.')

# Import ALL modules (REMOVED image_manager import)
try:
    from topic_bank import TopicBank
    from session_manager import SessionManager
    from vignettes import VignetteManager
except ImportError as e:
    st.error(f"Error importing modules: {e}")
    st.info("Please ensure all .py files are in the same directory")
    # Set to None if import fails
    TopicBank = None
    SessionManager = None
    VignetteManager = None

DEFAULT_WORD_TARGET = 500

# ── OpenAI client ─────────────────────────────────────────────────────────────
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")))

# ── Load external CSS ─────────────────────────────────────────────────────────
try:
    with open("styles.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("styles.css not found – layout may look broken")

# ── Constants ─────────────────────────────────────────────────────────────────
LOGO_URL = "https://menuhunterai.com/wp-content/uploads/2026/01/logo.png"

# ── Sessions (LOAD FROM CSV ONLY - NO HARDCODING) ─────────────────────────────
def load_sessions_from_csv(csv_path="sessions/sessions.csv"):
    """Load sessions ONLY from CSV file - NO hardcoded fallback"""
    try:
        import pandas as pd
        import os
        
        # Create sessions directory if it doesn't exist
        os.makedirs(os.path.dirname(csv_path) if os.path.dirname(csv_path) else '.', exist_ok=True)
        
        if not os.path.exists(csv_path):
            # CSV doesn't exist - show error and return empty list
            st.error(f"❌ Sessions CSV file not found: {csv_path}")
            st.info("""
            Please create a `sessions/sessions.csv` file with this format:
            
            session_id,title,guidance,question,word_target
            1,Childhood,"Welcome to Session 1...","What is your earliest memory?",500
            1,Childhood,,"Can you describe your family home?",500
            
            Guidance only needs to be in the first row of each session.
            """)
            return []
        
        df = pd.read_csv(csv_path)
        
        # Check required columns
        required_columns = ['session_id', 'question']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"❌ Missing required columns in CSV: {missing_columns}")
            st.info("CSV must have at least: session_id, question")
            return []
        
        # Group by session_id
        sessions_dict = {}
        
        for session_id, group in df.groupby('session_id'):
            session_id_int = int(session_id)
            group = group.reset_index(drop=True)
            
            # Get title (use first row's title or default)
            title = f"Session {session_id_int}"
            if 'title' in group.columns and not group.empty:
                first_title = group.iloc[0]['title']
                if pd.notna(first_title) and str(first_title).strip():
                    title = str(first_title).strip()
            
            # Get guidance (use first row's guidance)
            guidance = ""
            if 'guidance' in group.columns and not group.empty:
                first_guidance = group.iloc[0]['guidance']
                if pd.notna(first_guidance) and str(first_guidance).strip():
                    guidance = str(first_guidance).strip()
            
            # Get word target (use first row's word_target or default to 500)
            word_target = DEFAULT_WORD_TARGET
            if 'word_target' in group.columns and not group.empty:
                first_target = group.iloc[0]['word_target']
                if pd.notna(first_target):
                    try:
                        word_target = int(float(first_target))
                    except:
                        word_target = DEFAULT_WORD_TARGET
            
            # Get all questions
            questions = []
            for _, row in group.iterrows():
                if 'question' in row and pd.notna(row['question']) and str(row['question']).strip():
                    questions.append(str(row['question']).strip())
            
            # Only add session if it has questions
            if questions:
                sessions_dict[session_id_int] = {
                    "id": session_id_int,
                    "title": title,
                    "guidance": guidance,
                    "questions": questions,
                    "completed": False,
                    "word_target": word_target
                }
        
        # Convert to list and sort by session_id
        sessions_list = list(sessions_dict.values())
        sessions_list.sort(key=lambda x: x['id'])
        
        if not sessions_list:
            st.warning("⚠️ No sessions found in CSV file")
            return []
        
        return sessions_list
        
    except Exception as e:
        st.error(f"❌ Error loading sessions from CSV: {e}")
        return []

# Load sessions ONCE at startup
SESSIONS = load_sessions_from_csv()

# ── Historical events – CSV only ──────────────────────────────────────────────
def create_default_events_csv():
    if not os.path.exists("historical_events.csv"):
        with open("historical_events.csv", "w", encoding="utf-8") as f:
            f.write("year_range,event,category,region,description\n")

def load_historical_events():
    create_default_events_csv()
    try:
        df = pd.read_csv("historical_events.csv")
        events_by_decade = {}
        for _, row in df.iterrows():
            decade = str(row['year_range']).strip()
            events_by_decade.setdefault(decade, []).append(row.to_dict())
        return events_by_decade
    except:
        return {}

def get_events_for_birth_year(birth_year):
    events_by_decade = load_historical_events()
    relevant = []
    start_decade = (birth_year // 10) * 10
    current_year = datetime.now().year
    for decade in range(start_decade, current_year + 10, 10):
        key = f"{decade}s"
        if key in events_by_decade:
            for ev in events_by_decade[key]:
                approx_year = int(key.replace('s', '')) + 5
                age = approx_year - birth_year
                if age >= 0:
                    ev_copy = ev.copy()
                    ev_copy['approx_age'] = age
                    relevant.append(ev_copy)
    relevant.sort(key=lambda x: x.get('year_range', '9999'))
    return relevant[:20]

# ── Email Configuration ───────────────────────────────────────────────────────
EMAIL_CONFIG = {
    "smtp_server": st.secrets.get("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(st.secrets.get("SMTP_PORT", 587)),
    "sender_email": st.secrets.get("SENDER_EMAIL", ""),
    "sender_password": st.secrets.get("SENDER_PASSWORD", ""),
    "use_tls": True
}

# ── Authentication Functions ──────────────────────────────────────────────────
def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, password):
    return stored_hash == hash_password(password)

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
            "settings": {
                "email_notifications": True,
                "auto_save": True,
                "privacy_level": "private",
                "theme": "light",
                "email_verified": False
            },
            "stats": {
                "total_sessions": 0,
                "total_words": 0,
                "current_streak": 0,
                "longest_streak": 0,
                "account_age_days": 0,
                "last_active": datetime.now().isoformat()
            }
        }
        save_account_data(user_record)
        return {"success": True, "user_id": user_id, "password": password, "user_record": user_record}
    except Exception as e:
        print(f"Error creating account: {e}")
        return {"success": False, "error": str(e)}

def save_account_data(user_record):
    try:
        os.makedirs("accounts", exist_ok=True)
        filename = f"accounts/{user_record['user_id']}_account.json"
        json.dump(user_record, open(filename, 'w'), indent=2)
        update_accounts_index(user_record)
        return True
    except Exception as e:
        print(f"Error saving account: {e}")
        return False

def update_accounts_index(user_record):
    try:
        index_file = "accounts/accounts_index.json"
        os.makedirs("accounts", exist_ok=True)
        index = json.load(open(index_file, 'r')) if os.path.exists(index_file) else {}
        index[user_record['user_id']] = {
            "email": user_record['email'],
            "first_name": user_record['profile']['first_name'],
            "last_name": user_record['profile']['last_name'],
            "created_at": user_record['created_at'],
            "account_type": user_record['account_type']
        }
        json.dump(index, open(index_file, 'w'), indent=2)
        return True
    except Exception as e:
        print(f"Error updating index: {e}")
        return False

def get_account_data(user_id=None, email=None):
    try:
        os.makedirs("accounts", exist_ok=True)
        if user_id:
            filename = f"accounts/{user_id}_account.json"
            if os.path.exists(filename):
                return json.load(open(filename, 'r'))
        if email:
            email = email.lower().strip()
            index_file = "accounts/accounts_index.json"
            if os.path.exists(index_file):
                index = json.load(open(index_file, 'r'))
                for uid, data in index.items():
                    if data.get("email", "").lower() == email:
                        filename = f"accounts/{uid}_account.json"
                        if os.path.exists(filename):
                            return json.load(open(filename, 'r'))
    except Exception as e:
        print(f"Error loading account: {e}")
    return None

def authenticate_user(email, password):
    try:
        account = get_account_data(email=email)
        if account and verify_password(account['password_hash'], password):
            account['last_login'] = datetime.now().isoformat()
            save_account_data(account)
            return {"success": True, "user_id": account['user_id'], "user_record": account}
        return {"success": False, "error": "Invalid email or password"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_welcome_email(user_data, credentials):
    try:
        if not EMAIL_CONFIG['sender_email'] or not EMAIL_CONFIG['sender_password']:
            print("Email not configured")
            return False
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = user_data['email']
        msg['Subject'] = "Welcome to MemLife - Your Account Details"
        body = f"""
        <html>
        <body style="font-family: Arial; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Welcome to MemLife, {user_data['first_name']}!</h2>
            <p>Thank you for creating your account.</p>
            <div style="background-color: #f8f9fa; border-left: 4px solid #3498db; padding: 15px; margin: 20px 0;">
                <h3 style="color: #2c3e50; margin-top: 0;">Your Account Details:</h3>
                <p><strong>Account ID:</strong> {credentials['user_id']}</p>
                <p><strong>Email:</strong> {user_data['email']}</p>
                <p><strong>Password:</strong> {credentials['password']}</p>
            </div>
            <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h4 style="color: #2c3e50; margin-top: 0;">Getting Started:</h4>
                <ol>
                    <li>Log in with your email and password</li>
                    <li>Start building your timeline from your birthdate: {user_data.get('birthdate', 'Not specified')}</li>
                    <li>Add memories, photos, and stories to your timeline</li>
                    <li>Share with family and friends</li>
                </ol>
            </div>
            <p>Your MemLife timeline starts from your birthdate and grows with you as you add more memories and milestones.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="#" style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Start Your MemLife Journey</a>
            </div>
            <p style="color: #7f8c8d; font-size: 0.9em; border-top: 1px solid #eee; padding-top: 20px;">
                If you didn't create this account, please ignore this email or contact support.<br>
                This is an automated message, please do not reply directly.
            </p>
        </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            if EMAIL_CONFIG['use_tls']:
                server.starttls()
            server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
            server.send_message(msg)
        print(f"Welcome email sent to {user_data['email']}")
        return True
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False

def logout_user():
    keys = [
        'user_id', 'user_account', 'logged_in', 'show_profile_setup',
        'current_session', 'current_question', 'responses',
        'session_conversations', 'data_loaded', 'show_image_upload',
        'selected_images_for_prompt', 'image_prompt_mode',
        'show_vignette_modal', 'vignette_topic', 'vignette_content',
        'selected_vignette_type', 'current_vignette_list', 'editing_vignette_index',
        'show_vignette_manager', 'custom_topic_input', 'show_custom_topic_modal',
        'show_topic_browser', 'show_session_manager', 'show_session_creator',
        'editing_custom_session', 'show_vignette_detail', 'selected_vignette_id',
        'editing_vignette_id', 'selected_vignette_for_session'
    ]
    for key in keys:
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()

# ── Storage & Streak ──────────────────────────────────────────────────────────
def get_user_filename(user_id):
    filename_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
    return f"user_data_{filename_hash}.json"

def load_user_data(user_id):
    filename = get_user_filename(user_id)
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
            return data
        return {"responses": {}, "vignettes": [], "last_loaded": datetime.now().isoformat()}
    except Exception as e:
        print(f"Error loading user data for {user_id}: {e}")
        return {"responses": {}, "vignettes": [], "last_loaded": datetime.now().isoformat()}

def save_user_data(user_id, responses_data):
    filename = get_user_filename(user_id)
    try:
        existing_data = load_user_data(user_id)
        data_to_save = {
            "user_id": user_id,
            "responses": responses_data,
            "vignettes": existing_data.get("vignettes", []),
            "last_saved": datetime.now().isoformat()
        }
        with open(filename, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving user data for {user_id}: {e}")
        return False

def update_streak():
    if "streak_days" not in st.session_state:
        st.session_state.streak_days = 1
    if "last_active" not in st.session_state:
        st.session_state.last_active = date.today().isoformat()
    if "total_writing_days" not in st.session_state:
        st.session_state.total_writing_days = 1
    today = date.today().isoformat()
    if st.session_state.last_active != today:
        try:
            last_date = date.fromisoformat(st.session_state.last_active)
            today_date = date.today()
            days_diff = (today_date - last_date).days
            if days_diff == 1:
                st.session_state.streak_days += 1
            elif days_diff > 1:
                st.session_state.streak_days = 1
            st.session_state.total_writing_days += 1
            st.session_state.last_active = today
        except:
            st.session_state.last_active = today

def get_streak_emoji(streak_days):
    if streak_days >= 30:
        return "🔥🔥🔥"
    elif streak_days >= 7:
        return "🔥🔥"
    elif streak_days >= 3:
        return "🔥"
    else:
        return "✨"

def estimate_year_from_text(text):
    try:
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
        if years:
            return int(years[0])
    except:
        pass
    return None

def save_jot(text, estimated_year=None):
    if "quick_jots" not in st.session_state:
        st.session_state.quick_jots = []
    jot_data = {
        "text": text,
        "year": estimated_year,
        "date": datetime.now().isoformat(),
        "word_count": len(re.findall(r'\w+', text))
    }
    st.session_state.quick_jots.append(jot_data)
    return True

# ── Prompt Builder ────────────────────────────────────────────────────────────
def get_system_prompt():
    # Check if we have sessions loaded
    if not SESSIONS or st.session_state.current_session >= len(SESSIONS):
        return "No sessions available. Please check your CSV file."
    
    current_session = SESSIONS[st.session_state.current_session]
    current_question = (
        st.session_state.current_question_override
        or current_session["questions"][st.session_state.current_question]
    )
    historical_context = ""
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            if events:
                context_lines = []
                for event in events[:5]:
                    event_text = f"- {event['event']} ({event['year_range']})"
                    if event.get('region') == 'UK':
                        event_text += " [UK]"
                    if 'approx_age' in event and event['approx_age'] >= 0:
                        event_text += f" (Age {event['approx_age']})"
                    context_lines.append(event_text)
                historical_context = f"""
HISTORICAL CONTEXT (Born {birth_year}):
During their lifetime, these major events occurred:
{chr(10).join(context_lines)}
Consider how these historical moments might have shaped their experiences and perspectives.
"""
        except Exception as e:
            print(f"Error generating historical context: {e}")
    
    if st.session_state.ghostwriter_mode:
        return f"""ROLE: You are a senior literary biographer with multiple award-winning books to your name.
CURRENT SESSION: Session {current_session['id']}: {current_session['title']}
CURRENT TOPIC: "{current_question}"
{historical_context}
YOUR APPROACH:
1. Listen like an archivist
2. Think in scenes, sensory details, and emotional truth
3. Connect personal stories to historical context when relevant
4. Find the story that needs to be told

Tone: Literary but not pretentious. Serious but not solemn."""
    else:
        return f"""You are a warm, professional biographer helping document a life story.
CURRENT SESSION: Session {current_session['id']}: {current_session['title']}
CURRENT TOPIC: "{current_question}"
{historical_context}

Tone: Kind, curious, professional"""

# ── Core Functions ────────────────────────────────────────────────────────────
def save_response(session_id, question, answer):
    user_id = st.session_state.user_id
    if not user_id or user_id == "":
        return False
    
    update_streak()
    
    if st.session_state.user_account:
        word_count = len(re.findall(r'\w+', answer))
        if "stats" not in st.session_state.user_account:
            st.session_state.user_account["stats"] = {}
        st.session_state.user_account["stats"]["total_words"] = st.session_state.user_account["stats"].get("total_words", 0) + word_count
        st.session_state.user_account["stats"]["total_sessions"] = len(st.session_state.responses[session_id].get("questions", {}))
        st.session_state.user_account["stats"]["last_active"] = datetime.now().isoformat()
        save_account_data(st.session_state.user_account)
    
    if session_id not in st.session_state.responses:
        # Find the session in SESSIONS
        session_data = None
        for s in SESSIONS:
            if s["id"] == session_id:
                session_data = s
                break
        
        if not session_data:
            # Create a basic session entry if not found
            session_data = {
                "title": f"Session {session_id}",
                "word_target": DEFAULT_WORD_TARGET
            }
        
        st.session_state.responses[session_id] = {
            "title": session_data.get("title", f"Session {session_id}"),
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": session_data.get("word_target", DEFAULT_WORD_TARGET)
        }
    
    st.session_state.responses[session_id]["questions"][question] = {
        "answer": answer,
        "timestamp": datetime.now().isoformat()
    }
    
    return save_user_data(user_id, st.session_state.responses)

def calculate_author_word_count(session_id):
    total_words = 0
    session_data = st.session_state.responses.get(session_id, {})
    for question, answer_data in session_data.get("questions", {}).items():
        if answer_data.get("answer"):
            total_words += len(re.findall(r'\w+', answer_data["answer"]))
    return total_words

def get_progress_info(session_id):
    current_count = calculate_author_word_count(session_id)
    target = st.session_state.responses[session_id].get("word_target", DEFAULT_WORD_TARGET)
    if target == 0:
        progress_percent = 100
        emoji = "🟢"
        color = "#27ae60"
    else:
        progress_percent = (current_count / target) * 100 if target > 0 else 100
    if progress_percent >= 100:
        emoji = "🟢"
        color = "#27ae60"
    elif progress_percent >= 70:
        emoji = "🟡"
        color = "#f39c12"
    else:
        emoji = "🔴"
        color = "#e74c3c"
    remaining_words = max(0, target - current_count)
    status_text = f"{remaining_words} words remaining" if remaining_words > 0 else "Target achieved!"
    return {
        "current_count": current_count,
        "target": target,
        "progress_percent": progress_percent,
        "emoji": emoji,
        "color": color,
        "remaining_words": remaining_words,
        "status_text": status_text
    }
    
def auto_correct_text(text):
    if not text or not st.session_state.spellcheck_enabled:
        return text
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Fix spelling and grammar mistakes in the following text. Return only the corrected text."},
                {"role": "user", "content": text}
            ],
            max_tokens=len(text) + 100,
            temperature=0.1
        )
        return response.choices[0].message.content
    except:
        return text

# ── Module Integration Functions ──────────────────────────────────────────────
def switch_to_vignette(vignette_topic, content=""):
    st.session_state.current_question_override = f"Vignette: {vignette_topic}"
    st.session_state.image_prompt_mode = False
    if content:
        current_session = SESSIONS[st.session_state.current_session]
        current_session_id = current_session["id"]
        save_response(current_session_id, f"Vignette: {vignette_topic}", content)
    st.rerun()

def switch_to_custom_topic(topic_text):
    st.session_state.current_question_override = topic_text
    st.session_state.image_prompt_mode = False
    st.rerun()

def show_vignette_modal():
    if not VignetteManager:
        st.error("Vignette module not available")
        st.session_state.show_vignette_modal = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    if st.button("← Back", key="vignette_modal_back"):
        st.session_state.show_vignette_modal = False
        if 'editing_vignette_id' in st.session_state:
            st.session_state.pop('editing_vignette_id')
        st.rerun()
    
    vignette_manager = VignetteManager(st.session_state.user_id)
    
    # Store publish callback outside the form context
    if 'published_vignette' not in st.session_state:
        st.session_state.published_vignette = None
    
    def on_publish(vignette):
        # Store vignette in session state instead of creating buttons here
        st.session_state.published_vignette = vignette
        st.success(f"🎉 Vignette '{vignette['title']}' published!")
        st.rerun()
    
    vignette_manager.display_vignette_creator(on_publish=on_publish)
    
    # Show publish options after vignette is published (outside form context)
    if st.session_state.published_vignette:
        vignette = st.session_state.published_vignette
        st.write("### What would you like to do?")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📚 Add to Session", key="add_to_session_after", use_container_width=True):
                st.session_state.selected_vignette_for_session = vignette
                st.session_state.show_vignette_modal = False
                st.session_state.published_vignette = None
                st.rerun()
        
        with col2:
            if st.button("📖 View All Vignettes", key="view_all_after", use_container_width=True):
                st.session_state.show_vignette_modal = False
                st.session_state.show_vignette_manager = True
                st.session_state.published_vignette = None
                st.rerun()
        
        with col3:
            if st.button("✏️ Keep Writing", key="keep_writing", use_container_width=True):
                st.session_state.show_vignette_modal = False
                st.session_state.published_vignette = None
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_vignette_manager():
    if not VignetteManager:
        st.error("Vignette module not available")
        st.session_state.show_vignette_manager = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    if st.button("← Back", key="vignette_manager_back"):
        st.session_state.show_vignette_manager = False
        st.rerun()
    
    st.title("📚 Your Vignettes")
    
    vignette_manager = VignetteManager(st.session_state.user_id)
    
    filter_option = st.radio(
        "Show:",
        ["All Stories", "Published", "Drafts", "Most Popular"],
        horizontal=True,
        key="vignette_filter"
    )
    
    def on_vignette_select(vignette_id):
        st.session_state.show_vignette_detail = True
        st.session_state.selected_vignette_id = vignette_id
        st.rerun()
    
    filter_map = {
        "All Stories": "all",
        "Published": "published",
        "Drafts": "drafts",
        "Most Popular": "popular"
    }
    
    vignette_manager.display_vignette_gallery(
        filter_by=filter_map.get(filter_option, "all"),
        on_select=on_vignette_select
    )
    
    st.divider()
    if st.button("➕ Create New Vignette", type="primary", use_container_width=True):
        st.session_state.show_vignette_manager = False
        st.session_state.show_vignette_modal = True
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_vignette_detail():
    if not VignetteManager or not st.session_state.get('selected_vignette_id'):
        st.session_state.show_vignette_detail = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    if st.button("← Back", key="vignette_detail_back"):
        st.session_state.show_vignette_detail = False
        st.rerun()
    
    vignette_manager = VignetteManager(st.session_state.user_id)
    vignette = vignette_manager.get_vignette_by_id(st.session_state.selected_vignette_id)
    
    if not vignette:
        st.error("Vignette not found")
        st.session_state.show_vignette_detail = False
        return
    
    st.title(vignette['title'])
    st.caption(f"Theme: {vignette.get('theme', 'Uncategorized')}")
    
    if vignette.get('tags'):
        tags = " ".join([f"`{tag}`" for tag in vignette.get('tags', [])])
        st.caption(f"Tags: {tags}")
    
    st.divider()
    st.write(vignette['content'])
    st.divider()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Words", vignette.get('word_count', 0))
    with col2:
        st.metric("Views", vignette.get('views', 0))
    with col3:
        st.metric("Likes", vignette.get('likes', 0))
    with col4:
        if vignette.get('is_draft'):
            if st.button("🚀 Publish", use_container_width=True, type="primary"):
                if vignette_manager.publish_vignette(vignette['id']):
                    st.success("Published!")
                    st.rerun()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📚 Add to Session", type="primary", use_container_width=True):
            st.session_state.selected_vignette_for_session = vignette
            st.session_state.show_vignette_detail = False
            st.rerun()
    
    with col2:
        if st.button("✏️ Edit", use_container_width=True):
            st.session_state.editing_vignette_id = vignette['id']
            st.session_state.show_vignette_detail = False
            st.session_state.show_vignette_modal = True
            st.rerun()
    
    with col3:
        if st.button("🗑️ Delete", type="secondary", use_container_width=True):
            st.warning("Delete functionality to be implemented")
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_topic_browser():
    if not TopicBank:
        st.error("Topic module not available")
        st.session_state.show_topic_browser = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    if st.button("← Back", key="topic_browser_back"):
        st.session_state.show_topic_browser = False
        st.rerun()
    
    st.title("📚 Topic Browser")
    
    topic_bank = TopicBank(st.session_state.user_id)
    
    def on_topic_select(topic_text):
        switch_to_custom_topic(topic_text)
        st.session_state.show_topic_browser = False
    
    # FIX: Use a unique key that won't cause duplicates
    import time
    topic_bank.display_topic_browser(on_topic_select=on_topic_select, unique_key=str(time.time()))
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_session_creator():
    if not SessionManager:
        st.error("Session module not available")
        st.session_state.show_session_creator = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    if st.button("← Back", key="session_creator_back"):
        st.session_state.show_session_creator = False
        st.rerun()
    
    st.title("📋 Create Custom Session")
    
    # Initialize SessionManager with CSV path
    session_manager = SessionManager(st.session_state.user_id, "sessions/sessions.csv")
    session_manager.display_session_creator()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_session_manager():
    if not SessionManager:
        st.error("Session module not available")
        st.session_state.show_session_manager = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    if st.button("← Back", key="session_manager_back"):
        st.session_state.show_session_manager = False
        st.rerun()
    
    st.title("📖 Session Manager")
    
    # Initialize SessionManager with CSV path
    session_manager = SessionManager(st.session_state.user_id, "sessions/sessions.csv")
    
    def on_session_select(session_id):
        all_sessions = session_manager.get_all_sessions()
        for i, session in enumerate(all_sessions):
            if session["id"] == session_id:
                # Find session index in SESSIONS
                for j, standard_session in enumerate(SESSIONS):
                    if standard_session["id"] == session_id:
                        st.session_state.current_session = j
                        break
                else:
                    # It's a custom session
                    custom_sessions = all_sessions[len(SESSIONS):]
                    if session in custom_sessions:
                        custom_index = custom_sessions.index(session)
                        st.session_state.current_session = len(SESSIONS) + custom_index
                
                st.session_state.current_question = 0
                st.session_state.current_question_override = None
                st.rerun()
                break
    
    if st.button("➕ Create New Session", type="primary", use_container_width=True):
        st.session_state.show_session_manager = False
        st.session_state.show_session_creator = True
        st.rerun()
    
    st.divider()
    
    session_manager.display_session_grid(cols=2, on_session_select=on_session_select)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ── Page Config & State ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

default_state = {
    "logged_in": False,
    "user_id": "",
    "user_account": None,
    "show_profile_setup": False,
    "current_session": 0,
    "current_question": 0,
    "responses": {},
    "session_conversations": {},
    "editing": None,
    "edit_text": "",
    "ghostwriter_mode": True,
    "spellcheck_enabled": True,
    "editing_word_target": False,
    "confirming_clear": None,
    "data_loaded": False,
    "current_question_override": None,
    "quick_jots": [],
    "current_jot": "",
    "show_jots": False,
    "historical_events_loaded": False,
    "streak_days": 1,
    "last_active": date.today().isoformat(),
    "total_writing_days": 1,
    "show_vignette_modal": False,
    "vignette_topic": "",
    "vignette_content": "",
    "selected_vignette_type": "Standard Topic",
    "current_vignette_list": [],
    "editing_vignette_index": None,
    "show_vignette_manager": False,
    "custom_topic_input": "",
    "show_custom_topic_modal": False,
    "show_topic_browser": False,
    "show_session_manager": False,
    "show_session_creator": False,
    "editing_custom_session": None,
    "show_vignette_detail": False,
    "selected_vignette_id": None,
    "editing_vignette_id": None,
    "selected_vignette_for_session": None,
    "published_vignette": None,
}

for key, value in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Check if sessions are loaded
if not SESSIONS:
    st.error("❌ No sessions loaded. Please create a sessions/sessions.csv file.")
    st.info("""
    Create a CSV file with this format:
    
    session_id,title,guidance,question,word_target
    1,Childhood,"Welcome to Session 1...","What is your earliest memory?",500
    1,Childhood,,"Can you describe your family home?",500
    2,Family,"Welcome to Session 2...","How would you describe your relationship?",500
    
    Save it as: sessions/sessions.csv
    """)
    st.stop()

# Initialize responses for loaded sessions
if SESSIONS:
    for session in SESSIONS:
        session_id = session["id"]
        if session_id not in st.session_state.responses:
            st.session_state.responses[session_id] = {
                "title": session["title"],
                "questions": {},
                "summary": "",
                "completed": False,
                "word_target": session.get("word_target", DEFAULT_WORD_TARGET)
            }
        if session_id not in st.session_state.session_conversations:
            st.session_state.session_conversations[session_id] = {}

if st.session_state.logged_in and st.session_state.user_id and not st.session_state.data_loaded:
    user_data = load_user_data(st.session_state.user_id)
    if "responses" in user_data:
        for session_id_str, session_data in user_data["responses"].items():
            try:
                session_id = int(session_id_str)
                if session_id in st.session_state.responses:
                    if "questions" in session_data:
                        st.session_state.responses[session_id]["questions"] = session_data["questions"]
            except ValueError:
                continue
    st.session_state.data_loaded = True

# ── Authentication Components ─────────────────────────────────────────────────
def show_login_signup():
    st.markdown("""
    <div class="auth-container">
    <h1 class="auth-title">MemLife</h1>
    <p class="auth-subtitle">Your Life Timeline • Preserve Your Legacy</p>
    </div>
    """, unsafe_allow_html=True)

    if 'auth_tab' not in st.session_state:
        st.session_state.auth_tab = 'login'

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔐 Login", use_container_width=True,
                     type="primary" if st.session_state.auth_tab == 'login' else "secondary"):
            st.session_state.auth_tab = 'login'
            st.rerun()
    with col2:
        if st.button("📝 Sign Up", use_container_width=True,
                     type="primary" if st.session_state.auth_tab == 'signup' else "secondary"):
            st.session_state.auth_tab = 'signup'
            st.rerun()

    st.divider()

    if st.session_state.auth_tab == 'login':
        show_login_form()
    else:
        show_signup_form()

def show_login_form():
    with st.form("login_form"):
        st.subheader("Welcome Back")
        email = st.text_input("Email Address", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        col1, col2 = st.columns([2, 1])
        with col1:
            remember_me = st.checkbox("Remember me", value=True)
        with col2:
            st.markdown('<div class="forgot-password"><a href="#">Forgot password?</a></div>', unsafe_allow_html=True)
        login_button = st.form_submit_button("Login to My Account", type="primary", use_container_width=True)
        if login_button:
            if not email or not password:
                st.error("Please enter both email and password")
            else:
                with st.spinner("Signing in..."):
                    result = authenticate_user(email, password)
                    if result["success"]:
                        st.session_state.user_id = result["user_id"]
                        st.session_state.user_account = result["user_record"]
                        st.session_state.logged_in = True
                        st.session_state.data_loaded = False
                        if remember_me:
                            st.query_params['user'] = result['user_id']
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error(f"Login failed: {result.get('error', 'Unknown error')}")

def show_signup_form():
    with st.form("signup_form"):
        st.subheader("Create New Account")
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name*", key="signup_first_name")
        with col2:
            last_name = st.text_input("Last Name*", key="signup_last_name")
        email = st.text_input("Email Address*", key="signup_email")
        col1, col2 = st.columns(2)
        with col1:
            password = st.text_input("Password*", type="password", key="signup_password")
        with col2:
            confirm_password = st.text_input("Confirm Password*", type="password", key="signup_confirm_password")
        accept_terms = st.checkbox("I agree to the Terms of Service and Privacy Policy*", key="signup_terms")
        signup_button = st.form_submit_button("Create My Account", type="primary", use_container_width=True)
        if signup_button:
            errors = []
            if not first_name:
                errors.append("First name is required")
            if not last_name:
                errors.append("Last name is required")
            if not email or "@" not in email:
                errors.append("Valid email is required")
            if not password or len(password) < 8:
                errors.append("Password must be at least 8 characters")
            if password != confirm_password:
                errors.append("Passwords do not match")
            if not accept_terms:
                errors.append("You must accept the terms and conditions")
            if email and "@" in email:
                existing_account = get_account_data(email=email)
                if existing_account:
                    errors.append("An account with this email already exists")
            if errors:
                for error in errors:
                    st.error(error)
            else:
                user_data = {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "account_for": "self"
                }
                with st.spinner("Creating your account..."):
                    result = create_user_account(user_data, password)
                    if result["success"]:
                        email_sent = send_welcome_email(user_data, {
                            "user_id": result["user_id"],
                            "password": password
                        })
                        st.session_state.user_id = result["user_id"]
                        st.session_state.user_account = result["user_record"]
                        st.session_state.logged_in = True
                        st.session_state.data_loaded = False
                        st.session_state.show_profile_setup = True
                        st.success("✅ Account created successfully!")
                        if email_sent:
                            st.info(f"📧 Welcome email sent to {email}")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"Error creating account: {result.get('error', 'Unknown error')}")

def show_profile_setup_modal():
    st.markdown('<div class="profile-setup-modal">', unsafe_allow_html=True)
    st.title("👤 Complete Your Profile")
    st.write("Please complete your profile to start building your timeline:")
    with st.form("profile_setup_form"):
        st.write("**Gender**")
        gender = st.radio(
            "Gender",
            ["Male", "Female", "Other", "Prefer not to say"],
            horizontal=True,
            key="modal_gender",
            label_visibility="collapsed"
        )
        st.write("**Birthdate**")
        col1, col2, col3 = st.columns(3)
        with col1:
            months = ["January", "February", "March", "April", "May", "June",
                      "July", "August", "September", "October", "November", "December"]
            birth_month = st.selectbox("Month", months, key="modal_month", label_visibility="collapsed")
        with col2:
            days = list(range(1, 32))
            birth_day = st.selectbox("Day", days, key="modal_day", label_visibility="collapsed")
        with col3:
            current_year = datetime.now().year
            years = list(range(current_year, current_year - 120, -1))
            birth_year = st.selectbox("Year", years, key="modal_year", label_visibility="collapsed")
        st.write("**Is this account for you or someone else?**")
        account_for = st.radio(
            "Account Type",
            ["For me", "For someone else"],
            key="modal_account_type",
            horizontal=True,
            label_visibility="collapsed"
        )
        col1, col2 = st.columns(2)
        with col1:
            submit_button = st.form_submit_button("Complete Profile", type="primary", use_container_width=True)
        with col2:
            skip_button = st.form_submit_button("Skip for Now", type="secondary", use_container_width=True)
        if submit_button or skip_button:
            if submit_button:
                if not birth_month or not birth_day or not birth_year:
                    st.error("Please complete your birthdate or click 'Skip for Now'")
                    st.markdown('</div>', unsafe_allow_html=True)
                    return
            birthdate = f"{birth_month} {birth_day}, {birth_year}" if submit_button else ""
            account_for_value = "self" if account_for == "For me" else "other"
            if st.session_state.user_account:
                st.session_state.user_account['profile']['gender'] = gender if submit_button else ""
                st.session_state.user_account['profile']['birthdate'] = birthdate
                st.session_state.user_account['profile']['timeline_start'] = birthdate
                st.session_state.user_account['account_type'] = account_for_value
                save_account_data(st.session_state.user_account)
                st.success("Profile updated successfully!")
            st.session_state.show_profile_setup = False
            st.markdown('</div>', unsafe_allow_html=True)
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ── Main App Flow ─────────────────────────────────────────────────────────────
if st.session_state.get('show_profile_setup', False):
    show_profile_setup_modal()
    st.stop()

if not st.session_state.logged_in:
    show_login_signup()
    st.stop()

if not st.session_state.historical_events_loaded:
    try:
        events = load_historical_events()
        st.session_state.historical_events_loaded = True
    except:
        pass

# Show modals in priority order
if st.session_state.show_vignette_detail:
    show_vignette_detail()
    st.stop()

if st.session_state.show_vignette_manager:
    show_vignette_manager()
    st.stop()

if st.session_state.show_vignette_modal:
    show_vignette_modal()
    st.stop()

if st.session_state.show_topic_browser:
    show_topic_browser()
    st.stop()

if st.session_state.show_session_manager:
    show_session_manager()
    st.stop()

if st.session_state.show_session_creator:
    show_session_creator()
    st.stop()

# Main header
st.markdown(f"""
<div class="main-header">
<img src="{LOGO_URL}" class="logo-img" alt="MemLife Logo">
<h2 style="margin: 0; line-height: 1.2;">MemLife - Your Life Timeline</h2>
<p style="font-size: 0.9rem; color: #666; margin: 0; line-height: 1.2;">Preserve Your Legacy • Build Your Timeline • Share Your Story</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("👤 Your Profile")
    if st.session_state.user_account:
        profile = st.session_state.user_account['profile']
        st.success(f"✓ **{profile['first_name']} {profile['last_name']}**")
        st.caption(f"📧 {profile['email']}")
        if profile.get('birthdate'):
            st.caption(f"🎂 Born: {profile['birthdate']}")
            try:
                birth_year = int(profile['birthdate'].split(', ')[-1])
                events = get_events_for_birth_year(birth_year)
                if events:
                    uk_events = [e for e in events if e.get('region') == 'UK']
                    global_events = len(events) - len(uk_events)
                    st.caption(f"📚 {len(events)} historical events ({len(uk_events)} UK, {global_events} global)")
            except:
                pass
        account_type = st.session_state.user_account['account_type']
        st.caption(f"👤 Account: {account_type.title()}")
    if st.button("📝 Edit Profile", use_container_width=True):
        st.session_state.show_profile_setup = True
        st.rerun()
    if st.button("🚪 Log Out", use_container_width=True):
        logout_user()
    
    st.divider()
    
    st.subheader("🔥 Writing Streak")
    streak_emoji = get_streak_emoji(st.session_state.streak_days)
    st.markdown(f"<div class='streak-flame'>{streak_emoji}</div>", unsafe_allow_html=True)
    st.markdown(f"**{st.session_state.streak_days} day streak**")
    st.caption(f"Total writing days: {st.session_state.total_writing_days}")
    if st.session_state.streak_days >= 7:
        st.success("🏆 Weekly Writer!")
    if st.session_state.streak_days >= 30:
        st.success("🌟 Monthly Master!")
    
    st.divider()
    
    # REMOVED PHOTO GALLERY SECTION
    
    st.divider()
    st.subheader("⚡ Quick Capture")
    with st.expander("💭 **Jot Now - Quick Memory**", expanded=False):
        quick_note = st.text_area(
            "Got a memory? Jot it down:",
            value="",
            height=120,
            placeholder="E.g., 'That summer at grandma's house in 1995...'",
            key="jot_text_area",
            label_visibility="collapsed"
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Jot", key="save_jot_btn", use_container_width=True):
                if quick_note and quick_note.strip():
                    estimated_year = estimate_year_from_text(quick_note)
                    save_jot(quick_note, estimated_year)
                    st.success("Saved! ✨")
                    st.rerun()
                else:
                    st.warning("Please write something first!")
        with col2:
            use_disabled = not quick_note or not quick_note.strip()
            if st.button("📝 Use as Prompt", key="use_jot_btn", use_container_width=True, disabled=use_disabled):
                st.session_state.current_question_override = quick_note
                st.info("Ready to write about this!")
                st.rerun()
        if st.session_state.get('quick_jots'):
            st.caption(f"📝 {len(st.session_state.quick_jots)} quick notes saved")
            if st.button("View Quick Notes", key="view_jots_btn"):
                st.session_state.show_jots = True
                st.rerun()
    
    st.divider()
    st.header("✍️ Interview Style")
    ghostwriter_mode = st.toggle(
        "Professional Ghostwriter Mode",
        value=st.session_state.ghostwriter_mode,
        key="ghostwriter_toggle"
    )
    if ghostwriter_mode != st.session_state.ghostwriter_mode:
        st.session_state.ghostwriter_mode = ghostwriter_mode
        st.rerun()
    spellcheck_enabled = st.toggle(
        "Auto Spelling Correction",
        value=st.session_state.spellcheck_enabled,
        key="spellcheck_toggle"
    )
    if spellcheck_enabled != st.session_state.spellcheck_enabled:
        st.session_state.spellcheck_enabled = spellcheck_enabled
        st.rerun()
    if st.session_state.ghostwriter_mode:
        st.success("✓ Professional mode active")
        st.caption("With historical context")
    else:
        st.info("Standard mode active")
    
    st.divider()
    st.header("📜 Historical Context")
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            if events:
                st.success(f"✓ {len(events)} historical events loaded")
                st.caption(f"From {birth_year} to present")
                with st.expander("View Sample Events", expanded=False):
                    for i, event in enumerate(events[:5]):
                        region_emoji = "🇬🇧" if event.get('region') == 'UK' else "🌍"
                        st.markdown(f"**{region_emoji} {event['event']}**")
                        st.caption(f"{event['year_range']} • {event.get('category', 'General')}")
                        if i < 4:
                            st.divider()
        except:
            st.info("Add birthdate to see historical context")
    else:
        st.info("Add your birthdate to enable historical context")
    
    st.divider()
    st.header("✨ Vignettes")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 New Vignette", use_container_width=True):
            st.session_state.show_vignette_modal = True
            st.rerun()
    with col2:
        if st.button("📖 View All", use_container_width=True):
            st.session_state.show_vignette_manager = True
            st.rerun()
    
    st.divider()
    st.header("📖 Session Management")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 All Sessions", use_container_width=True):
            st.session_state.show_session_manager = True
            st.rerun()
    with col2:
        if st.button("➕ Custom Session", use_container_width=True):
            st.session_state.show_session_creator = True
            st.rerun()
    
    st.divider()
    st.header("📚 Topic Management")
    
    if st.button("🔍 Browse Topics", use_container_width=True):
        st.session_state.show_topic_browser = True
        st.rerun()
    
    # Note: Custom Topic button removed - you wanted only Browse Topics
    
    st.divider()
    st.header("📖 Sessions")
    for i, session in enumerate(SESSIONS):
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        responses_count = len(session_data.get("questions", {}))
        total_questions = len(session["questions"])
        if i == st.session_state.current_session:
            status = "▶️"
        elif responses_count == total_questions:
            status = "✅"
        elif responses_count > 0:
            status = "🟡"
        else:
            status = "●"
        button_text = f"{status} Session {session_id}: {session['title']} ({responses_count}/{total_questions})"
        if st.button(button_text, key=f"select_session_{i}", use_container_width=True):
            st.session_state.current_session = i
            st.session_state.current_question = 0
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.rerun()
    
    st.divider()
    st.subheader("📝 Topic Navigation")
    current_session = SESSIONS[st.session_state.current_session]
    current_topic = st.session_state.current_question + 1
    total_topics = len(current_session["questions"])
    
    st.markdown(f'<div class="question-counter">Topic {current_topic} of {total_topics}</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        prev_disabled = st.session_state.current_question == 0
        if st.button("← Previous", 
                    disabled=prev_disabled, 
                    key="prev_topic_sidebar",
                    use_container_width=True):
            if not prev_disabled:
                st.session_state.current_question = st.session_state.current_question - 1
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.rerun()
    
    with col2:
        next_disabled = st.session_state.current_question >= total_topics - 1
        if st.button("Next →", 
                    disabled=next_disabled, 
                    key="next_topic_sidebar",
                    use_container_width=True):
            if not next_disabled:
                st.session_state.current_question = st.session_state.current_question + 1
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.rerun()
    
    st.divider()
    st.subheader("🔀 Session Navigation")
    nav_col1, nav_col2 = st.columns(2)
    
    with nav_col1:
        prev_session_disabled = st.session_state.current_session == 0
        if st.button("← Previous Session", 
                    disabled=prev_session_disabled,
                    key="prev_session_sidebar",
                    use_container_width=True):
            if not prev_session_disabled:
                st.session_state.current_session = st.session_state.current_session - 1
                st.session_state.current_question = 0
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.rerun()
    
    with nav_col2:
        next_session_disabled = st.session_state.current_session >= len(SESSIONS) - 1
        if st.button("Next Session →", 
                    disabled=next_session_disabled,
                    key="next_session_sidebar",
                    use_container_width=True):
            if not next_session_disabled:
                st.session_state.current_session = st.session_state.current_session + 1
                st.session_state.current_question = 0
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.rerun()
    
    session_options = [f"Session {s['id']}: {s['title']}" for s in SESSIONS]
    selected_session = st.selectbox(
        "Jump to session:",
        session_options, 
        index=st.session_state.current_session, 
        key="session_selectbox",
        label_visibility="collapsed"
    )
    
    if session_options.index(selected_session) != st.session_state.current_session:
        st.session_state.current_session = session_options.index(selected_session)
        st.session_state.current_question = 0
        st.session_state.editing = None
        st.session_state.current_question_override = None
        st.rerun()
    
    st.divider()
    
    st.subheader("📤 Export Options")
    total_answers = sum(len(session.get("questions", {})) for session in st.session_state.responses.values())
    st.caption(f"Total answers: {total_answers}")
    
    if st.session_state.logged_in and st.session_state.user_id:
        export_data = {}
        for session in SESSIONS:
            session_id = session["id"]
            session_data = st.session_state.responses.get(session_id, {})
            if session_data.get("questions"):
                export_data[str(session_id)] = {
                    "title": session["title"],
                    "questions": session_data["questions"]
                }
        
        if export_data:
            complete_data = {
                "user": st.session_state.user_id,
                "stories": export_data,
                "export_date": datetime.now().isoformat(),
                "summary": {
                    "total_stories": sum(len(session['questions']) for session in export_data.values())
                }
            }
            json_data = json.dumps(complete_data, indent=2)
            encoded_data = base64.b64encode(json_data.encode()).decode()
            publisher_url = f"{LOGO_URL.replace('logo.png', '')}deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/?data={encoded_data}"
            
            col1, col2 = st.columns(2)
            with col1:
                stories_only = {
                    "user": st.session_state.user_id,
                    "stories": export_data,
                    "export_date": datetime.now().isoformat()
                }
                stories_json = json.dumps(stories_only, indent=2)
                st.download_button(
                    label="📥 Stories Only",
                    data=stories_json,
                    file_name=f"MemLife_Stories_{st.session_state.user_id}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="download_stories_btn"
                )
            with col2:
                st.download_button(
                    label="📊 Complete Data",
                    data=json_data,
                    file_name=f"MemLife_Complete_{st.session_state.user_id}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="download_complete_btn"
                )
            
            st.divider()
            st.markdown(f'''
            <a href="{publisher_url}" target="_blank">
            <button class="html-link-btn">
            🖨️ Publish Biography
            </button>
            </a>
            ''', unsafe_allow_html=True)
            st.caption("Create a beautiful book with your stories")
        else:
            st.warning("No data to export yet! Start by answering some questions.")
    else:
        st.warning("Please log in to export your data.")
    
    st.divider()
    
    st.subheader("⚠️ Clear Data")
    if st.session_state.confirming_clear == "session":
        st.markdown('<div class="warning-box">', unsafe_allow_html=True)
        st.warning("**WARNING: This will delete ALL answers in the current session!**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Delete Session", type="primary", use_container_width=True, key="confirm_delete_session"):
                current_session_id = SESSIONS[st.session_state.current_session]["id"]
                try:
                    st.session_state.responses[current_session_id]["questions"] = {}
                    save_user_data(st.session_state.user_id, st.session_state.responses)
                    st.session_state.confirming_clear = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        with col2:
            if st.button("❌ Cancel", type="secondary", use_container_width=True, key="cancel_delete_session"):
                st.session_state.confirming_clear = None
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    elif st.session_state.confirming_clear == "all":
        st.markdown('<div class="warning-box">', unsafe_allow_html=True)
        st.warning("**WARNING: This will delete ALL answers for ALL sessions!**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Delete All", type="primary", use_container_width=True, key="confirm_delete_all"):
                try:
                    for session in SESSIONS:
                        session_id = session["id"]
                        st.session_state.responses[session_id]["questions"] = {}
                    save_user_data(st.session_state.user_id, st.session_state.responses)
                    st.session_state.confirming_clear = None
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        with col2:
            if st.button("❌ Cancel", type="secondary", use_container_width=True, key="cancel_delete_all"):
                st.session_state.confirming_clear = None
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Clear Session", type="secondary", use_container_width=True, key="clear_session_btn"):
                st.session_state.confirming_clear = "session"
                st.rerun()
        with col2:
            if st.button("🔥 Clear All", type="secondary", use_container_width=True, key="clear_all_btn"):
                st.session_state.confirming_clear = "all"
                st.rerun()

# ── Main Content ──────────────────────────────────────────────────────────────
current_session = SESSIONS[st.session_state.current_session]
current_session_id = current_session["id"]

if st.session_state.current_question_override:
    current_question_text = st.session_state.current_question_override
    question_source = "custom"
else:
    current_question_text = current_session["questions"][st.session_state.current_question]
    question_source = "regular"

st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.subheader(f"Session {current_session_id}: {current_session['title']}")
    session_responses = len(st.session_state.responses.get(current_session_id, {}).get("questions", {}))
    total_questions = len(current_session["questions"])
    st.caption(f"📝 {session_responses}/{total_questions} topics answered")
    
    if st.session_state.ghostwriter_mode:
        st.markdown('<p class="ghostwriter-tag">Professional Ghostwriter Mode (with historical context)</p>', unsafe_allow_html=True)

with col2:
    if question_source == "custom":
        if st.session_state.current_question_override.startswith("Vignette:"):
            st.markdown(f'<div class="question-counter" style="margin-top: 1rem; color: #9b59b6;">📝 Vignette</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="question-counter" style="margin-top: 1rem; color: #ff6b00;">✨ Custom Topic</div>', unsafe_allow_html=True)
    else:
        current_topic = st.session_state.current_question + 1
        total_topics = len(current_session["questions"])
        st.markdown(f'<div class="question-counter" style="margin-top: 1rem;">Topic {current_topic} of {total_topics}</div>', unsafe_allow_html=True)

with col3:
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        prev_disabled = st.session_state.current_question == 0
        if st.button("← Previous Topic", 
                    disabled=prev_disabled,
                    key="main_prev_btn",
                    use_container_width=True):
            if not prev_disabled:
                st.session_state.current_question -= 1
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.rerun()
    
    with nav_col2:
        next_disabled = st.session_state.current_question >= len(current_session["questions"]) - 1
        if st.button("Next Topic →", 
                    disabled=next_disabled,
                    key="main_next_btn",
                    use_container_width=True):
            if not next_disabled:
                st.session_state.current_question += 1
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.rerun()

st.markdown(f"""
<div class="question-box">
{current_question_text}
</div>
""", unsafe_allow_html=True)

# REMOVED ALL IMAGE CONTROLS SECTION

if question_source == "regular":
    st.markdown(f"""
    <div class="chapter-guidance">
    {current_session.get('guidance', '')}
    </div>
    """, unsafe_allow_html=True)
else:
    if st.session_state.current_question_override.startswith("Vignette:"):
        st.info("📝 **Vignette Mode** - Write a short, focused story about a specific moment or memory.")
    else:
        st.info("✨ **Custom Topic** - Write about whatever comes to mind!")
    
    if question_source == "regular":
        session_data = st.session_state.responses.get(current_session_id, {})
        topics_answered = len(session_data.get("questions", {}))
        total_topics = len(current_session["questions"])
        if total_topics > 0:
            topic_progress = topics_answered / total_topics
            st.progress(min(topic_progress, 1.0))
            st.caption(f"📝 Topics explored: {topics_answered}/{total_topics} ({topic_progress*100:.0f}%)")

# ── Conversation & Chat ───────────────────────────────────────────────────────
if current_session_id not in st.session_state.session_conversations:
    st.session_state.session_conversations[current_session_id] = {}

conversation = st.session_state.session_conversations[current_session_id].get(current_question_text, [])

if not conversation:
    saved_response = st.session_state.responses[current_session_id]["questions"].get(current_question_text)
    if saved_response:
        conversation = [
            {"role": "assistant", "content": f"Let's explore this topic in detail: {current_question_text}"},
            {"role": "user", "content": saved_response["answer"]}
        ]
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation
    else:
        with st.chat_message("assistant", avatar="👔"):
            welcome_msg = f"""<div style='font-size: 1.4rem; margin-bottom: 1rem;'>
            Let's explore this topic in detail:
            </div>
            <div style='font-size: 1.8rem; font-weight: bold; color: #2c3e50; line-height: 1.3;'>
            {current_question_text}
            </div>"""
            if question_source == "custom" and st.session_state.current_question_override.startswith("Vignette:"):
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #9b59b6; background-color: #f4ecf7; padding: 1rem; border-radius: 8px; border-left: 4px solid #9b59b6;'>
                📝 <strong>Vignette Mode:</strong> Write a short, focused story about this specific moment or memory.
                </div>"""
            elif question_source == "custom":
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #ff6b00; background-color: #fff5e6; padding: 1rem; border-radius: 8px; border-left: 4px solid #ff6b00;'>
                ✨ <strong>Custom Topic:</strong> Write about whatever comes to mind!
                </div>"""
            else:
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #555;'>
                Take your time with this—good biographies are built from thoughtful reflection.
                </div>"""
            st.markdown(welcome_msg, unsafe_allow_html=True)
        conv_text = f"Let's explore this topic in detail: {current_question_text}\n\n"
        if question_source == "custom" and st.session_state.current_question_override.startswith("Vignette:"):
            conv_text += "📝 Vignette Mode: Write a short, focused story about this specific moment or memory."
        elif question_source == "custom":
            conv_text += "✨ Custom Topic: Write about whatever comes to mind!"
        else:
            conv_text += "Take your time with this—good biographies are built from thoughtful reflection."
        conversation.append({"role": "assistant", "content": conv_text})
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation

for i, message in enumerate(conversation):
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="👔"):
            st.markdown(message["content"])
    elif message["role"] == "user":
        is_editing = (st.session_state.editing == (current_session_id, current_question_text, i))
        with st.chat_message("user", avatar="👤"):
            if is_editing:
                new_text = st.text_area(
                    "Edit your answer:",
                    value=st.session_state.edit_text,
                    key=f"edit_area_{current_session_id}_{hash(current_question_text)}_{i}",
                    height=150,
                    label_visibility="collapsed"
                )
                if new_text:
                    edit_word_count = len(re.findall(r'\w+', new_text))
                    st.caption(f"📝 Editing: {edit_word_count} words")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✓ Save", key=f"save_{current_session_id}_{hash(current_question_text)}_{i}", type="primary"):
                            if st.session_state.spellcheck_enabled:
                                new_text = auto_correct_text(new_text)
                            conversation[i]["content"] = new_text
                            st.session_state.session_conversations[current_session_id][current_question_text] = conversation
                            save_response(current_session_id, current_question_text, new_text)
                            st.session_state.editing = None
                            st.rerun()
                    with col2:
                        if st.button("✕ Cancel", key=f"cancel_{current_session_id}_{hash(current_question_text)}_{i}"):
                            st.session_state.editing = None
                            st.rerun()
            else:
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(message["content"])
                    word_count = len(re.findall(r'\w+', message["content"]))
                    st.caption(f"📝 {word_count} words • Click ✏️ to edit")
                with col2:
                    if st.button("✏️", key=f"edit_{st.session_state.current_session}_{hash(current_question_text)}_{i}"):
                        st.session_state.editing = (current_session_id, current_question_text, i)
                        st.session_state.edit_text = message["content"]
                        st.rerun()

input_container = st.container()
with input_container:
    st.write("")
    st.write("")
    user_input = st.chat_input("Type your answer here...", key="chat_input")
    if user_input:
        if st.session_state.spellcheck_enabled:
            user_input = auto_correct_text(user_input)
        conversation.append({"role": "user", "content": user_input})
        with st.chat_message("assistant", avatar="👔"):
            with st.spinner("Reflecting on your story..."):
                try:
                    conversation_history = conversation[:-1]
                    messages_for_api = [
                        {"role": "system", "content": get_system_prompt()},
                        *conversation_history,
                        {"role": "user", "content": user_input}
                    ]
                    temperature = 0.8 if st.session_state.ghostwriter_mode else 0.7
                    max_tokens = 400 if st.session_state.ghostwriter_mode else 300
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    ai_response = response.choices[0].message.content
                    if question_source == "custom" and st.session_state.current_question_override.startswith("Vignette:"):
                        ai_response += f"\n\n📝 **Vignette Note:** This is a great start for your vignette! Keep adding details about this specific memory."
                    st.markdown(ai_response)
                    conversation.append({"role": "assistant", "content": ai_response})
                except Exception as e:
                    error_msg = "Thank you for sharing that. Your response has been saved."
                    st.markdown(error_msg)
                    conversation.append({"role": "assistant", "content": error_msg})
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation
        save_response(current_session_id, current_question_text, user_input)
        st.rerun()

# ── Word Progress ─────────────────────────────────────────────────────────────
st.divider()
progress_info = get_progress_info(current_session_id)
st.markdown(f"""
<div class="progress-container">
<div class="progress-header">📊 Session Progress</div>
<div class="progress-status">{progress_info['emoji']} {progress_info['progress_percent']:.0f}% complete • {progress_info['status_text']}</div>
<div class="progress-bar-container">
<div class="progress-bar-fill" style="width: {min(progress_info['progress_percent'], 100)}%; background-color: {progress_info['color']};"></div>
</div>
<div style="text-align: center; font-size: 0.9rem; color: #666; margin-top: 0.5rem;">
{progress_info['current_count']} / {progress_info['target']} words
</div>
</div>
""", unsafe_allow_html=True)

if st.button("✏️ Change Word Target", key="edit_word_target_bottom", use_container_width=True):
    st.session_state.editing_word_target = not st.session_state.editing_word_target
    st.rerun()

if st.session_state.editing_word_target:
    st.markdown('<div class="edit-target-box">', unsafe_allow_html=True)
    st.write("**Change Word Target**")
    new_target = st.number_input(
        "Target words for this session:",
        min_value=100,
        max_value=5000,
        value=progress_info['target'],
        key="target_edit_input_bottom",
        label_visibility="collapsed"
    )
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Save", key="save_word_target_bottom", type="primary", use_container_width=True):
            st.session_state.responses[current_session_id]["word_target"] = new_target
            save_user_data(st.session_state.user_id, st.session_state.responses)
            st.session_state.editing_word_target = False
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel", key="cancel_word_target_bottom", use_container_width=True):
            st.session_state.editing_word_target = False
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
col1, col2, col3, col4 = st.columns(4)
with col1:
    total_words_all_sessions = sum(calculate_author_word_count(s["id"]) for s in SESSIONS)
    st.metric("Total Words", f"{total_words_all_sessions}")
with col2:
    completed_sessions = sum(1 for s in SESSIONS if len(st.session_state.responses[s["id"]].get("questions", {})) == len(s["questions"]))
    st.metric("Completed Sessions", f"{completed_sessions}/{len(SESSIONS)}")
with col3:
    total_topics_answered = sum(len(st.session_state.responses[s["id"]].get("questions", {})) for s in SESSIONS)
    total_all_topics = sum(len(s["questions"]) for s in SESSIONS)
    st.metric("Topics Explored", f"{total_topics_answered}/{total_all_topics}")
with col4:
    st.metric("Total Stories", f"{total_topics_answered}")

st.divider()
st.subheader("📘 Publish & Save Your Biography")
current_user = st.session_state.get('user_id', '')
if current_user:
    export_data = {}
    for session in SESSIONS:
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        if session_data.get("questions"):
            export_data[str(session_id)] = {
                "title": session["title"],
                "questions": session_data["questions"]
            }
    
    if export_data:
        total_stories = sum(len(session['questions']) for session in export_data.values())
        enhanced_data = {
            "user": current_user,
            "stories": export_data,
            "export_date": datetime.now().isoformat(),
            "summary": {
                "total_stories": total_stories,
                "total_sessions": len(export_data)
            }
        }
        json_data = json.dumps(enhanced_data, indent=2)
        encoded_data = base64.b64encode(json_data.encode()).decode()
        publisher_url = f"https://deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/?data={encoded_data}"
        st.success(f"✅ **{total_stories} stories** ready to publish!")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🖨️ Create Your Book")
            st.markdown("""
            Generate a beautiful, formatted biography.
            Your book will include:
            • Professional formatting
            • Table of contents
            • All your stories organized
            • Ready to print or share
            """)
            st.markdown(f'''
            <a href="{publisher_url}" target="_blank">
            <button class="html-link-btn">
            🖨️ Publish Biography
            </button>
            </a>
            ''', unsafe_allow_html=True)
        
        with col2:
            st.markdown("#### 🔐 Save to Your Vault")
            st.markdown("""
            **Complete preservation:**
            1. Generate your enhanced biography
            2. Download the formatted PDF
            3. Save all your stories
            4. Store in your secure digital vault
            """)
            vault_url = "https://digital-legacy-vault-vwvd4eclaeq4hxtcbbshr2.streamlit.app/"
            st.markdown(f'''
            <a href="{vault_url}" target="_blank">
            <button style="background: #3498db; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer; width: 100%; margin-top: 1rem;">
            💾 Go to Secure Vault
            </button>
            </a>
            ''', unsafe_allow_html=True)
            with st.expander("📥 Download Backup"):
                st.download_button(
                    label="Download Complete Data",
                    data=json_data,
                    file_name=f"{current_user}_complete_backup.json",
                    mime="application/json",
                    use_container_width=True,
                    key="backup_download_btn"
                )
                st.caption("Includes all your stories")
    else:
        st.info("📝 **Start writing your story!** Answer some questions first, then come back here.")
else:
    st.info("👤 **Please log in to publish your biography**")

st.markdown("---")
if st.session_state.user_account:
    profile = st.session_state.user_account['profile']
    account_age = (datetime.now() - datetime.fromisoformat(st.session_state.user_account['created_at'])).days
    
    footer_info = f"""
MemLife Timeline • 👤 {profile['first_name']} {profile['last_name']} • 📧 {profile['email']} •
🎂 {profile.get('birthdate', 'Not specified')} • 🔥 {st.session_state.streak_days} day streak •
📅 Account Age: {account_age} days
"""
    st.caption(footer_info)
else:
    st.caption(f"MemLife Timeline • User: {st.session_state.user_id} • 🔥 {st.session_state.streak_days} day streak")
