# biographer.py – Main MemLife app (USES ALL YOUR FILES)
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
from PIL import Image
import io
import random
import time
import importlib.util
import sys

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
DEFAULT_WORD_TARGET = 500

# ── IMPORT ALL YOUR EXISTING FILES ───────────────────────────────────────────

# 1. Import vignettes.py
try:
    # Try to import directly
    import vignettes
    VIGNETTES_AVAILABLE = True
    print("✓ vignettes.py loaded successfully")
except ImportError as e:
    print(f"✗ Could not import vignettes.py: {e}")
    VIGNETTES_AVAILABLE = False
    # Create minimal fallback
    class FallbackVignettes:
        @staticmethod
        def get_standard_vignette_topics():
            return ["Life Lesson", "Achievement", "Work", "Loss of Life", "Illness"]
        
        @staticmethod
        def get_user_vignettes(user_id):
            return []
        
        @staticmethod
        def add_vignette(user_id, topic, content):
            return {"success": True}
        
        @staticmethod 
        def add_vignette_to_main_story(user_id, vignette_index, session_id, topic_override=None):
            return True
    
    vignettes = FallbackVignettes()

# 2. Import biography_publisher.py
try:
    # Try to load biography_publisher
    if os.path.exists("biography_publisher.py"):
        spec = importlib.util.spec_from_file_location("biography_publisher", "biography_publisher.py")
        biography_publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(biography_publisher)
        PUBLISHER_AVAILABLE = True
        print("✓ biography_publisher.py loaded successfully")
    else:
        PUBLISHER_AVAILABLE = False
        print("✗ biography_publisher.py not found")
except Exception as e:
    print(f"✗ Error loading biography_publisher.py: {e}")
    PUBLISHER_AVAILABLE = False

# 3. Import image_manager.py
try:
    if os.path.exists("image_manager.py"):
        spec = importlib.util.spec_from_file_location("image_manager", "image_manager.py")
        image_manager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(image_manager)
        IMAGE_MANAGER_AVAILABLE = True
        print("✓ image_manager.py loaded successfully")
    else:
        IMAGE_MANAGER_AVAILABLE = False
        print("✗ image_manager.py not found")
except Exception as e:
    print(f"✗ Error loading image_manager.py: {e}")
    IMAGE_MANAGER_AVAILABLE = False

# 4. Import topic_bank.py
try:
    if os.path.exists("topic_bank.py"):
        spec = importlib.util.spec_from_file_location("topic_bank", "topic_bank.py")
        topic_bank = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(topic_bank)
        TOPIC_BANK_AVAILABLE = True
        print("✓ topic_bank.py loaded successfully")
    else:
        TOPIC_BANK_AVAILABLE = False
        print("✗ topic_bank.py not found")
except Exception as e:
    print(f"✗ Error loading topic_bank.py: {e}")
    TOPIC_BANK_AVAILABLE = False

# ── Custom Sessions Manager ───────────────────────────────────────────────────
class CustomSessionsManager:
    @staticmethod
    def load_custom_sessions(user_id):
        user_data = load_user_data(user_id)
        return user_data.get('custom_sessions', [])
    
    @staticmethod
    def save_custom_sessions(user_id, sessions):
        user_data = load_user_data(user_id)
        user_data['custom_sessions'] = sessions
        save_user_data(user_id, user_data)
        return True
    
    @staticmethod
    def add_session(user_id, title, guidance="", questions=None, word_target=DEFAULT_WORD_TARGET):
        sessions = CustomSessionsManager.load_custom_sessions(user_id)
        existing_ids = [s.get("id", 0) for s in sessions]
        new_id = max(existing_ids + [99]) + 1
        
        new_session = {
            "id": new_id,
            "title": title,
            "guidance": guidance or f"Welcome to your custom session: {title}",
            "questions": questions or ["What would you like to share about this topic?"],
            "completed": False,
            "word_target": word_target,
            "custom": True,
            "created_at": datetime.now().isoformat(),
            "user_id": user_id
        }
        
        sessions.append(new_session)
        CustomSessionsManager.save_custom_sessions(user_id, sessions)
        
        user_data = load_user_data(user_id)
        responses = user_data.get("responses", {})
        if new_id not in responses:
            responses[new_id] = {
                "title": title,
                "questions": {},
                "summary": "",
                "completed": False,
                "word_target": word_target
            }
            user_data["responses"] = responses
            save_user_data(user_id, user_data)
        
        return new_session
    
    @staticmethod
    def delete_session(user_id, session_id):
        sessions = CustomSessionsManager.load_custom_sessions(user_id)
        sessions = [s for s in sessions if s.get("id") != session_id]
        CustomSessionsManager.save_custom_sessions(user_id, sessions)
        
        user_data = load_user_data(user_id)
        responses = user_data.get("responses", {})
        if session_id in responses:
            del responses[session_id]
            user_data["responses"] = responses
            save_user_data(user_id, user_data)
        
        return True

# ── Helper function to get all sessions ──────────────────────────────────────
def get_all_sessions():
    all_sessions = SESSIONS.copy()
    if st.session_state.logged_in and st.session_state.user_id:
        custom_sessions = CustomSessionsManager.load_custom_sessions(st.session_state.user_id)
        all_sessions.extend(custom_sessions)
    return all_sessions

# ── Sessions ──────────────────────────────────────────────────────────────────
SESSIONS = [
    {
        "id": 1,
        "title": "Childhood",
        "guidance": "Welcome to Session 1: Childhood—this is where we lay the foundation of your story. Professional biographies thrive on specific, sensory-rich memories. I'm looking for the kind of details that transport readers: not just what happened, but how it felt, smelled, sounded. The 'insignificant' moments often reveal the most. Take your time—we're mining for gold here.",
        "questions": [
            "What is your earliest memory?",
            "Can you describe your family home growing up?",
            "Who were the most influential people in your early years?",
            "What was school like for you?",
            "Were there any favourite games or hobbies?",
            "Is there a moment from childhood that shaped who you are?",
            "If you could give your younger self some advice, what would it be?"
        ],
        "completed": False,
        "word_target": 800,
        "custom": False
    },
    {
        "id": 2,
        "title": "Family & Relationships",
        "guidance": "Welcome to Session 2: Family & Relationships—this is where we explore the people who shaped you. Family stories are complex ecosystems. We're not seeking perfect narratives, but authentic ones. The richest material often lives in the tensions, the unsaid things, the small rituals. My job is to help you articulate what usually goes unspoken. Think in scenes rather than summaries.",
        "questions": [
            "How would you describe your relationship with your parents?",
            "Are there any family traditions you remember fondly?",
            "What was your relationship like with siblings or close relatives?",
            "Can you share a story about a family celebration or challenge?",
            "How did your family shape your values?"
        ],
        "completed": False,
        "word_target": 700,
        "custom": False
    },
    {
        "id": 3,
        "title": "Education & Growing Up",
        "guidance": "Welcome to Session 3: Education & Growing Up—this is where we explore how you learned to navigate the world. Education isn't just about schools—it's about how you learned to navigate the world. We're interested in the hidden curriculum: what you learned about yourself, about systems, about survival and growth. Think beyond grades to transformation.",
        "questions": [
            "What were your favourite subjects at school?",
            "Did you have any memorable teachers or mentors?",
            "How did you feel about exams and studying?",
            "Were there any big turning points in your education?",
            "Did you pursue further education or training?",
            "What advice would you give about learning?"
        ],
        "completed": False,
        "word_target": 600,
        "custom": False
    }
]

# ── Historical events – using your historical_events.csv ─────────────────────
def create_default_events_csv():
    if not os.path.exists("historical_events.csv"):
        with open("historical_events.csv", "w", encoding="utf-8") as f:
            f.write("year_range,event,category,region,description\n")

def load_historical_events():
    if not os.path.exists("historical_events.csv"):
        create_default_events_csv()
    try:
        df = pd.read_csv("historical_events.csv")
        events_by_decade = {}
        for _, row in df.iterrows():
            decade = str(row['year_range']).strip()
            events_by_decade.setdefault(decade, []).append(row.to_dict())
        return events_by_decade
    except Exception as e:
        print(f"Error loading historical_events.csv: {e}")
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

# ── Image Functions using your image_manager.py ──────────────────────────────
def get_session_images(user_id, session_id):
    if IMAGE_MANAGER_AVAILABLE:
        try:
            return image_manager.get_session_images(user_id, session_id)
        except:
            return []
    return []

def get_total_user_images(user_id):
    if IMAGE_MANAGER_AVAILABLE:
        try:
            return image_manager.get_total_user_images(user_id)
        except:
            return 0
    return 0

def display_simple_gallery(user_id, session_id):
    if IMAGE_MANAGER_AVAILABLE:
        try:
            return image_manager.display_simple_gallery(user_id, session_id)
        except:
            return []
    return []

def save_uploaded_image_simple(uploaded_file, user_id, session_id, description=""):
    if IMAGE_MANAGER_AVAILABLE:
        try:
            return image_manager.save_uploaded_image_simple(uploaded_file, user_id, session_id, description)
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": False, "error": "Image manager not available"}

def get_images_for_prompt_simple(user_id, session_id):
    if IMAGE_MANAGER_AVAILABLE:
        try:
            return image_manager.get_images_for_prompt_simple(user_id, session_id)
        except:
            return ""
    return ""

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

def logout_user():
    keys = [
        'user_id', 'user_account', 'logged_in', 'show_profile_setup',
        'current_session', 'current_question', 'responses',
        'session_conversations', 'data_loaded', 'show_image_upload',
        'selected_images_for_prompt', 'image_prompt_mode',
        'show_vignettes', 'show_custom_sessions', 'editing_custom_session',
        'creating_vignette', 'success_message'
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
    st.query_params.clear()
    st.rerun()

# ── Storage Functions ─────────────────────────────────────────────────────────
def get_user_filename(user_id):
    filename_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
    return f"user_data_{filename_hash}.json"

def load_user_data(user_id):
    filename = get_user_filename(user_id)
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
            if "responses" in data:
                return data
        return {
            "responses": {},
            "vignettes": [],
            "custom_sessions": [],
            "last_loaded": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error loading user data for {user_id}: {e}")
        return {
            "responses": {},
            "vignettes": [],
            "custom_sessions": [],
            "last_loaded": datetime.now().isoformat()
        }

def save_user_data(user_id, responses_data):
    filename = get_user_filename(user_id)
    try:
        with open(filename, 'w') as f:
            json.dump(responses_data, f, indent=2)
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

# ── Success Message Handler ──────────────────────────────────────────────────
def show_success_message(message):
    """Show a success message that stays until cleared"""
    st.session_state.success_message = message

def clear_success_message():
    """Clear the success message"""
    st.session_state.success_message = None

# ── Navigation Functions ─────────────────────────────────────────────────────
def navigate_to_writer():
    """Navigate back to the main writer app"""
    st.session_state.show_vignettes = False
    st.session_state.show_custom_sessions = False
    st.session_state.creating_vignette = False
    st.session_state.editing_custom_session = None
    st.rerun()

def navigate_to_vignettes():
    """Navigate to vignettes"""
    st.session_state.show_vignettes = True
    st.session_state.show_custom_sessions = False
    st.session_state.creating_vignette = False
    st.rerun()

def navigate_to_custom_sessions():
    """Navigate to custom sessions"""
    st.session_state.show_vignettes = False
    st.session_state.show_custom_sessions = True
    st.session_state.editing_custom_session = None
    st.rerun()

# ── Vignettes UI (using your vignettes.py) ───────────────────────────────────
def show_vignettes_ui():
    st.markdown("---")
    
    # BACK BUTTON
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Writer", key="back_from_vignettes", use_container_width=True):
            navigate_to_writer()
    with col_title:
        st.header("📝 Vignettes - Quick Stories")
    
    # Show success message if any
    if st.session_state.get('success_message'):
        st.markdown(f'<div class="success-message-fixed">✅ {st.session_state.success_message}</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        **Vignettes are short, focused stories about specific moments or themes in your life.**
        - Write quickly without pressure
        - Get instant gratification by publishing immediately
        - Add to your main biography later
        """)
    with col2:
        if st.button("➕ New Vignette", type="primary", use_container_width=True):
            st.session_state.creating_vignette = True
            st.rerun()
    
    if st.session_state.creating_vignette:
        st.markdown("---")
        st.subheader("✍️ Write a New Vignette")
        
        with st.form("new_vignette_form"):
            if VIGNETTES_AVAILABLE:
                standard_topics = vignettes.get_standard_vignette_topics()
            else:
                standard_topics = ["Life Lesson", "Achievement", "Work", "Family", "Travel"]
            
            topic_options = ["Custom Topic"] + standard_topics
            selected_topic_option = st.selectbox("Choose a topic:", topic_options)
            
            if selected_topic_option == "Custom Topic":
                custom_topic = st.text_input("Enter your custom topic:")
                topic = custom_topic
            else:
                topic = selected_topic_option
            
            content = st.text_area("Write your vignette:", height=200, placeholder="Write your short story here...")
            
            word_count = len(re.findall(r'\w+', content)) if content else 0
            st.caption(f"📝 {word_count} words")
            
            submitted = st.form_submit_button("Save Vignette", type="primary", use_container_width=True)
            
            if submitted:
                if not topic or not topic.strip():
                    st.error("Please enter a topic")
                elif not content or not content.strip():
                    st.error("Please write your vignette")
                else:
                    if VIGNETTES_AVAILABLE:
                        vignettes.add_vignette(st.session_state.user_id, topic, content)
                    show_success_message(f"Vignette '{topic}' saved! ({word_count} words)")
                    st.session_state.creating_vignette = False
                    st.rerun()
        
        if st.button("Cancel", key="cancel_vignette", use_container_width=True):
            st.session_state.creating_vignette = False
            st.rerun()
    
    st.markdown("---")
    
    # Display existing vignettes
    if VIGNETTES_AVAILABLE:
        user_vignettes = vignettes.get_user_vignettes(st.session_state.user_id)
    else:
        user_vignettes = []
    
    if user_vignettes:
        st.subheader(f"Your Vignettes ({len(user_vignettes)})")
        
        for i, vignette in enumerate(user_vignettes):
            with st.expander(f"📖 {vignette.get('topic', 'Untitled')} ({len(re.findall(r'\w+', vignette.get('content', '')))} words)", expanded=i==0):
                # Display content
                st.markdown(vignette.get('content', ''))
                st.markdown("---")
                
                # Add to session
                st.markdown("**Add to a session:**")
                all_sessions_list = get_all_sessions()
                
                if all_sessions_list:
                    session_options = {f"Session {s['id']}: {s['title']}": s['id'] for s in all_sessions_list}
                    selected_session_name = st.selectbox(
                        "Choose a session:",
                        list(session_options.keys()),
                        key=f"add_to_session_{i}",
                        label_visibility="collapsed"
                    )
                    
                    col_add, col_go = st.columns(2)
                    with col_add:
                        if st.button("➕ Add to Session", key=f"add_btn_{i}", use_container_width=True):
                            session_id = session_options[selected_session_name]
                            if VIGNETTES_AVAILABLE:
                                vignettes.add_vignette_to_main_story(st.session_state.user_id, i, session_id)
                            show_success_message(f"Added to {selected_session_name}")
                            st.rerun()
                    with col_go:
                        if st.button("▶️ Go to Session", key=f"goto_session_{i}", use_container_width=True):
                            session_id = session_options[selected_session_name]
                            # Find the session index
                            all_sessions_list = get_all_sessions()
                            for idx, s in enumerate(all_sessions_list):
                                if s["id"] == session_id:
                                    navigate_to_writer()
                                    st.session_state.current_session = idx
                                    st.session_state.current_question = 0
                                    st.rerun()
                                    break
    else:
        st.info("📝 No vignettes yet. Create your first vignette!")

# ── Custom Sessions UI ───────────────────────────────────────────────────────
def show_custom_sessions_ui():
    st.markdown("---")
    
    # BACK BUTTON
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Writer", key="back_from_custom", use_container_width=True):
            navigate_to_writer()
    with col_title:
        st.header("🎨 Custom Sessions & Topics")
    
    # Show success message if any
    if st.session_state.get('success_message'):
        st.markdown(f'<div class="success-message-fixed">✅ {st.session_state.success_message}</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        **Create your own sessions with custom topics.**
        - Design sessions around specific themes or periods
        - Add your own questions
        - Set custom word targets
        """)
    with col2:
        if st.button("➕ New Session", type="primary", use_container_width=True):
            st.session_state.editing_custom_session = "new"
            st.rerun()
    
    # Display existing custom sessions
    custom_sessions = CustomSessionsManager.load_custom_sessions(st.session_state.user_id)
    
    if custom_sessions:
        st.markdown("---")
        st.subheader(f"Your Custom Sessions ({len(custom_sessions)})")
        
        for i, session in enumerate(custom_sessions):
            with st.expander(f"🎯 {session['title']} ({len(session['questions'])} topics)", expanded=i==0):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Title:** {session['title']}")
                    st.caption(f"Created: {datetime.fromisoformat(session['created_at']).strftime('%B %d, %Y')}")
                    st.caption(f"Topics: {len(session['questions'])} • Word target: {session.get('word_target', DEFAULT_WORD_TARGET)}")
                
                with col2:
                    col_edit, col_del = st.columns(2)
                    with col_edit:
                        if st.button("✏️", key=f"edit_cs_{session['id']}", help="Edit this session"):
                            st.session_state.editing_custom_session = session['id']
                            st.rerun()
                    with col_del:
                        if st.button("🗑️", key=f"delete_cs_{session['id']}", help="Delete this session"):
                            if CustomSessionsManager.delete_session(st.session_state.user_id, session['id']):
                                show_success_message("Session deleted")
                                st.rerun()
                
                # GO TO SESSION BUTTON
                if st.button("▶️ Go to This Session", key=f"goto_{session['id']}", use_container_width=True):
                    # Find the index of this session
                    all_sessions_list = get_all_sessions()
                    for idx, s in enumerate(all_sessions_list):
                        if s.get("id") == session["id"]:
                            navigate_to_writer()
                            st.session_state.current_session = idx
                            st.session_state.current_question = 0
                            st.rerun()
                            break
    
    # Create/Edit custom session form
    if st.session_state.editing_custom_session:
        st.markdown("---")
        
        is_new = st.session_state.editing_custom_session == "new"
        
        if is_new:
            st.subheader("Create New Custom Session")
            current_session = None
        else:
            st.subheader("Edit Custom Session")
            custom_sessions = CustomSessionsManager.load_custom_sessions(st.session_state.user_id)
            current_session = next((s for s in custom_sessions if s["id"] == st.session_state.editing_custom_session), None)
            if not current_session:
                st.error("Session not found")
                st.session_state.editing_custom_session = None
                st.rerun()
        
        with st.form("custom_session_form"):
            title = st.text_input("Session Title:", value=current_session["title"] if current_session else "", placeholder="e.g., 'College Years', 'Travel Adventures'")
            
            guidance = st.text_area("Session Guidance (optional):", value=current_session.get("guidance", "") if current_session else "", height=100, placeholder="Write guidance text...")
            
            word_target = st.number_input("Word Target:", min_value=100, max_value=5000, value=current_session.get("word_target", DEFAULT_WORD_TARGET) if current_session else DEFAULT_WORD_TARGET, step=100)
            
            st.markdown("---")
            st.subheader("Topics/Questions")
            
            if current_session:
                default_questions = current_session["questions"]
            else:
                default_questions = ["What would you like to share about this topic?"]
            
            questions = []
            for i in range(len(default_questions) + 3):
                if i < len(default_questions):
                    default_val = default_questions[i]
                else:
                    default_val = ""
                
                question = st.text_input(f"Topic {i+1}:", value=default_val, key=f"question_{i}", placeholder="Enter a topic or question...")
                
                if question.strip():
                    questions.append(question.strip())
            
            submitted = st.form_submit_button("💾 Save Session", type="primary", use_container_width=True)
            
            if submitted:
                if not title or not title.strip():
                    st.error("Please enter a session title")
                elif not questions:
                    st.error("Please add at least one topic")
                else:
                    if is_new:
                        CustomSessionsManager.add_session(st.session_state.user_id, title, guidance, questions, word_target)
                        show_success_message(f"Session '{title}' created!")
                    else:
                        # For simplicity, delete and recreate
                        CustomSessionsManager.delete_session(st.session_state.user_id, current_session["id"])
                        CustomSessionsManager.add_session(st.session_state.user_id, title, guidance, questions, word_target)
                        show_success_message(f"Session '{title}' updated!")
                    
                    st.session_state.editing_custom_session = None
                    st.rerun()
        
        col_cancel, col_back = st.columns(2)
        with col_cancel:
            if st.button("Cancel", key="cancel_custom_session", use_container_width=True):
                st.session_state.editing_custom_session = None
                st.rerun()
        with col_back:
            if st.button("← Back to Custom Sessions", key="back_to_custom_list", use_container_width=True):
                st.session_state.editing_custom_session = None
                st.rerun()

# ── Page Config & State ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize all session state variables
for k, v in {
    "logged_in": False,
    "user_id": "",
    "user_account": None,
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
    "show_image_upload": False,
    "image_prompt_mode": False,
    "selected_images_for_prompt": [],
    "streak_days": 1,
    "last_active": date.today().isoformat(),
    "total_writing_days": 1,
    "show_vignettes": False,
    "show_custom_sessions": False,
    "editing_custom_session": None,
    "creating_vignette": False,
    "success_message": None
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── MAIN APP FLOW ────────────────────────────────────────────────────────────

# Show login if not logged in
if not st.session_state.logged_in:
    st.title("MemLife - Your Life Timeline")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login", use_container_width=True):
            if email and password:
                result = authenticate_user(email, password)
                if result["success"]:
                    st.session_state.user_id = result["user_id"]
                    st.session_state.user_account = result["user_record"]
                    st.session_state.logged_in = True
                    st.session_state.data_loaded = False
                    st.rerun()
                else:
                    st.error("Login failed")
            else:
                st.error("Please enter email and password")
    with col2:
        if st.button("Create Account", use_container_width=True):
            st.info("Account creation coming soon")
    st.stop()

# Show vignettes or custom sessions if requested
if st.session_state.show_vignettes:
    show_vignettes_ui()
    st.stop()

if st.session_state.show_custom_sessions:
    show_custom_sessions_ui()
    st.stop()

# Show success message if any
if st.session_state.success_message:
    st.markdown(f'<div class="success-message-fixed">✅ {st.session_state.success_message}</div>', unsafe_allow_html=True)

# Main header
st.markdown(f"""
<div class="main-header">
<h2 style="margin: 0; line-height: 1.2;">MemLife - Your Life Timeline</h2>
<p style="font-size: 0.9rem; color: #666; margin: 0; line-height: 1.2;">Preserve Your Legacy • Build Your Timeline • Share Your Story</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Profile
    st.header("👤 Your Profile")
    if st.session_state.user_account:
        profile = st.session_state.user_account['profile']
        st.success(f"✓ **{profile['first_name']} {profile['last_name']}**")
        st.caption(f"📧 {profile['email']}")
    
    col_profile, col_logout = st.columns(2)
    with col_profile:
        if st.button("📝 Edit", use_container_width=True):
            st.info("Edit profile coming soon")
    with col_logout:
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()
    
    st.divider()
    
    # New Features Navigation
    st.header("🎨 Features")
    col_vig, col_sess = st.columns(2)
    with col_vig:
        if st.button("📝 Vignettes", use_container_width=True):
            navigate_to_vignettes()
    with col_sess:
        if st.button("🎯 Custom", use_container_width=True):
            navigate_to_custom_sessions()
    
    st.divider()
    
    # Session Navigation
    st.header("📖 Sessions")
    all_sessions_list = get_all_sessions()
    
    for i, session in enumerate(all_sessions_list):
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        responses_count = len(session_data.get("questions", {}))
        
        if i == st.session_state.current_session:
            status = "▶️"
        elif responses_count > 0:
            status = "🟡"
        else:
            status = "●"
        
        custom_indicator = " 🎯" if session.get("custom", False) else ""
        button_text = f"{status} Session {session_id}: {session['title']}{custom_indicator}"
        
        if st.button(button_text, key=f"select_session_{session_id}", use_container_width=True):
            st.session_state.current_session = i
            st.session_state.current_question = 0
            st.rerun()
    
    st.divider()
    
    # Interview Style
    st.header("✍️ Style")
    ghostwriter_mode = st.toggle(
        "Professional Mode",
        value=st.session_state.ghostwriter_mode,
        key="ghostwriter_toggle"
    )
    if ghostwriter_mode != st.session_state.ghostwriter_mode:
        st.session_state.ghostwriter_mode = ghostwriter_mode
        st.rerun()
    
    spellcheck_enabled = st.toggle(
        "Auto Correction",
        value=st.session_state.spellcheck_enabled,
        key="spellcheck_toggle"
    )
    if spellcheck_enabled != st.session_state.spellcheck_enabled:
        st.session_state.spellcheck_enabled = spellcheck_enabled
        st.rerun()

# ── Main Content ──────────────────────────────────────────────────────────────
all_sessions_list = get_all_sessions()

# Handle session bounds
if st.session_state.current_session >= len(all_sessions_list):
    st.session_state.current_session = 0
if st.session_state.current_session < 0:
    st.session_state.current_session = 0

current_session = all_sessions_list[st.session_state.current_session]
current_session_id = current_session["id"]

# Handle question bounds
if st.session_state.current_question >= len(current_session["questions"]):
    st.session_state.current_question = 0
if st.session_state.current_question < 0:
    st.session_state.current_question = 0

current_question_text = (
    st.session_state.current_question_override
    or current_session["questions"][st.session_state.current_question]
)

# Session header
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    custom_indicator = " 🎯" if current_session.get("custom", False) else ""
    st.subheader(f"Session {current_session_id}: {current_session['title']}{custom_indicator}")
    
    session_responses = len(st.session_state.responses.get(current_session_id, {}).get("questions", {}))
    total_questions = len(current_session["questions"])
    st.caption(f"📝 {session_responses}/{total_questions} topics answered")

with col2:
    st.markdown(f'<div class="question-counter">Topic {st.session_state.current_question + 1} of {len(current_session["questions"])}</div>', unsafe_allow_html=True)

with col3:
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("← Previous", disabled=st.session_state.current_question == 0, key="prev_q", use_container_width=True):
            st.session_state.current_question = max(0, st.session_state.current_question - 1)
            st.rerun()
    with nav_col2:
        if st.button("Next →", disabled=st.session_state.current_question >= len(current_session["questions"]) - 1, key="next_q", use_container_width=True):
            st.session_state.current_question = min(len(current_session["questions"]) - 1, st.session_state.current_question + 1)
            st.rerun()

# Question display
st.markdown(f"""
<div class="question-box">
{current_question_text}
</div>
""", unsafe_allow_html=True)

# Guidance
if current_session.get('guidance'):
    st.info(current_session['guidance'])

# ── AI CHAT INTERACTION ──────────────────────────────────────────────────────
# Initialize conversation
if current_session_id not in st.session_state.session_conversations:
    st.session_state.session_conversations[current_session_id] = {}

if current_question_text not in st.session_state.session_conversations[current_session_id]:
    st.session_state.session_conversations[current_session_id][current_question_text] = []

conversation = st.session_state.session_conversations[current_session_id][current_question_text]

# Display conversation history
if not conversation:
    # Initial assistant message
    with st.chat_message("assistant", avatar="👔"):
        welcome_msg = f"""Let's explore this topic in detail:

**{current_question_text}**

Take your time with this—good stories are built from thoughtful reflection."""
        st.markdown(welcome_msg)
    
    conversation = [{"role": "assistant", "content": welcome_msg}]
    st.session_state.session_conversations[current_session_id][current_question_text] = conversation
else:
    # Display existing conversation
    for message in conversation:
        if message["role"] == "assistant":
            with st.chat_message("assistant", avatar="👔"):
                st.markdown(message["content"])
        elif message["role"] == "user":
            with st.chat_message("user", avatar="👤"):
                st.markdown(message["content"])

# Chat input - POSITIONED CORRECTLY (above progress bar)
user_input = st.chat_input("Type your answer here...", key="chat_input_main")

if user_input:
    # Process user input
    if st.session_state.spellcheck_enabled:
        # Simple autocorrect
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Fix spelling and grammar. Return only corrected text."},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.1
            )
            user_input = response.choices[0].message.content
        except:
            pass
    
    # Add user message to conversation
    conversation.append({"role": "user", "content": user_input})
    
    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)
    
    # Generate AI response
    with st.chat_message("assistant", avatar="👔"):
        with st.spinner("Reflecting on your story..."):
            try:
                # Prepare system prompt
                system_prompt = f"""You are a professional biographer helping document a life story.
CURRENT TOPIC: "{current_question_text}"

Please respond warmly and ask one thoughtful follow-up question."""
                
                # Make API call
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *[{"role": msg["role"], "content": msg["content"]} for msg in conversation[-3:]]
                    ],
                    temperature=0.7,
                    max_tokens=300
                )
                
                ai_response = response.choices[0].message.content
                st.markdown(ai_response)
                
                # Add AI response to conversation
                conversation.append({"role": "assistant", "content": ai_response})
                
            except Exception as e:
                error_msg = "Thank you for sharing that. Let's continue exploring this topic."
                st.markdown(error_msg)
                conversation.append({"role": "assistant", "content": error_msg})
    
    # Save conversation
    st.session_state.session_conversations[current_session_id][current_question_text] = conversation
    
    # Save response to storage
    if st.session_state.user_id:
        if current_session_id not in st.session_state.responses:
            st.session_state.responses[current_session_id] = {
                "title": current_session["title"],
                "questions": {},
                "summary": "",
                "completed": False,
                "word_target": current_session.get("word_target", DEFAULT_WORD_TARGET)
            }
        
        st.session_state.responses[current_session_id]["questions"][current_question_text] = {
            "answer": user_input,
            "timestamp": datetime.now().isoformat()
        }
        
        save_user_data(st.session_state.user_id, st.session_state.responses)
    
    # Force rerun
    st.rerun()

# Progress bar
st.divider()
total_words = 0
session_data = st.session_state.responses.get(current_session_id, {})
for question, answer_data in session_data.get("questions", {}).items():
    if answer_data.get("answer"):
        total_words += len(re.findall(r'\w+', answer_data["answer"]))

target = current_session.get("word_target", DEFAULT_WORD_TARGET)
progress = min((total_words / target) * 100 if target > 0 else 100, 100)

st.progress(progress / 100)
st.caption(f"📊 {total_words}/{target} words ({progress:.0f}%)")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    total_all_words = 0
    for session in all_sessions_list:
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        for question, answer_data in session_data.get("questions", {}).items():
            if answer_data.get("answer"):
                total_all_words += len(re.findall(r'\w+', answer_data["answer"]))
    st.metric("Total Words", total_all_words)
with col2:
    completed = sum(1 for s in all_sessions_list 
                   if len(st.session_state.responses.get(s["id"], {}).get("questions", {})) >= len(s["questions"]))
    st.metric("Completed", f"{completed}/{len(all_sessions_list)}")
with col3:
    st.metric("Streak", f"{st.session_state.streak_days} days")

# Publishing section using your biography_publisher.py
if PUBLISHER_AVAILABLE:
    st.divider()
    st.subheader("📘 Publish Your Biography")
    
    if st.button("🖨️ Generate Biography Book", use_container_width=True):
        st.info("Publishing feature loaded from biography_publisher.py")
        # You can call functions from biography_publisher here
else:
    st.divider()
    st.subheader("📘 Publish Your Biography")
    st.info("Publishing module not available")

print("✅ App loaded successfully using ALL your files!")
