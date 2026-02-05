# biographer.py – MemLife main app
import streamlit as st
import json
from datetime import datetime, date
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
import sys

# Add current directory to path to import modules
sys.path.append('.')

# Import the modules you created
try:
    from topic_bank import TopicBank
    from session_manager import SessionManager
    from vignettes import VignetteManager
except ImportError as e:
    st.error(f"Error importing modules: {e}")
    st.info("Please ensure topic_bank.py, session_manager.py, and vignettes.py are in the same directory")
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
        "word_target": 800
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
        "word_target": 700
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
        "word_target": 600
    }
]

# ── Helper Functions ──────────────────────────────────────────────────────────
def load_historical_events():
    """Load historical events from CSV"""
    try:
        if not os.path.exists("historical_events.csv"):
            with open("historical_events.csv", "w", encoding="utf-8") as f:
                f.write("year_range,event,category,region,description\n")
            return {}
        
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

# ── Image Functions ───────────────────────────────────────────────────────────
def get_session_images(user_id, session_id):
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    if os.path.exists(metadata_file):
        try:
            metadata = json.load(open(metadata_file, 'r'))
            return metadata.get(str(session_id), [])
        except:
            pass
    return []

def get_total_user_images(user_id):
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    if os.path.exists(metadata_file):
        try:
            metadata = json.load(open(metadata_file, 'r'))
            return sum(len(images) for images in metadata.values())
        except:
            pass
    return 0

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
        return True
    except Exception as e:
        print(f"Error saving account: {e}")
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

# ── Module Integration Functions ──────────────────────────────────────────────
def switch_to_vignette(vignette_topic, content=""):
    """Switch to writing a vignette"""
    st.session_state.current_question_override = f"Vignette: {vignette_topic}"
    st.session_state.image_prompt_mode = False
    if content:
        current_session = SESSIONS[st.session_state.current_session]
        current_session_id = current_session["id"]
        save_response(current_session_id, f"Vignette: {vignette_topic}", content)
    st.rerun()

def switch_to_custom_topic(topic_text):
    """Switch to a custom topic"""
    st.session_state.current_question_override = topic_text
    st.session_state.image_prompt_mode = False
    st.rerun()

def show_vignette_modal():
    """Show vignette creation modal"""
    if not VignetteManager:
        st.error("Vignette module not available")
        st.session_state.show_vignette_modal = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back", key="vignette_back"):
        st.session_state.show_vignette_modal = False
        st.rerun()
    
    # Create vignette manager
    vignette_manager = VignetteManager(st.session_state.user_id)
    
    # Define what happens after publish
    def on_publish(vignette):
        st.success(f"🎉 Vignette '{vignette['title']}' published!")
        
        # Ask if user wants to add to session
        st.write("What would you like to do next?")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📚 Add to Session", key="add_to_session"):
                # Show session selection
                st.session_state.selected_vignette_for_session = vignette
                st.rerun()
        
        with col2:
            if st.button("📝 Keep Writing", key="keep_writing"):
                st.session_state.show_vignette_modal = False
                st.rerun()
        
        with col3:
            if st.button("📖 View All", key="view_all"):
                st.session_state.show_vignette_modal = False
                st.session_state.show_vignette_manager = True
                st.rerun()
    
    # Use the module's vignette creator
    vignette_manager.display_vignette_creator(on_publish=on_publish)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_vignette_manager():
    """Show vignette manager"""
    if not VignetteManager:
        st.error("Vignette module not available")
        st.session_state.show_vignette_manager = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back", key="vignette_manager_back"):
        st.session_state.show_vignette_manager = False
        st.rerun()
    
    st.title("📚 Your Vignettes")
    
    # Create vignette manager
    vignette_manager = VignetteManager(st.session_state.user_id)
    
    # Filter options
    filter_option = st.radio(
        "Show:",
        ["All Stories", "Published", "Drafts"],
        horizontal=True,
        key="vignette_filter"
    )
    
    # Get vignettes based on filter
    if filter_option == "Published":
        vignettes = vignette_manager.get_published_vignettes()
    elif filter_option == "Drafts":
        vignettes = [v for v in vignette_manager.get_all_vignettes(include_drafts=True) 
                    if v.get("is_draft", False)]
    else:
        vignettes = vignette_manager.get_all_vignettes(include_drafts=True)
    
    if not vignettes:
        st.info(f"No {filter_option.lower()} vignettes yet.")
        st.markdown('</div>', unsafe_allow_html=True)
        return
    
    # Display vignettes using module's gallery
    def on_vignette_select(vignette_id):
        st.session_state.show_vignette_detail = True
        st.session_state.selected_vignette_id = vignette_id
        st.rerun()
    
    # Map filter option to module's parameter
    filter_map = {
        "All Stories": "all",
        "Published": "published",
        "Drafts": "drafts"
    }
    
    vignette_manager.display_vignette_gallery(
        filter_by=filter_map[filter_option],
        on_select=on_vignette_select
    )
    
    # Add create new button
    st.divider()
    if st.button("➕ Create New Vignette", type="primary", use_container_width=True):
        st.session_state.show_vignette_manager = False
        st.session_state.show_vignette_modal = True
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_vignette_detail():
    """Show vignette detail"""
    if not VignetteManager or not st.session_state.get('selected_vignette_id'):
        st.session_state.show_vignette_detail = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back", key="vignette_detail_back"):
        st.session_state.show_vignette_detail = False
        st.rerun()
    
    # Get vignette
    vignette_manager = VignetteManager(st.session_state.user_id)
    vignette = vignette_manager.get_vignette_by_id(st.session_state.selected_vignette_id)
    
    if not vignette:
        st.error("Vignette not found")
        st.session_state.show_vignette_detail = False
        return
    
    # Display vignette
    st.title(vignette['title'])
    st.caption(f"Theme: {vignette.get('theme', 'Uncategorized')}")
    
    if vignette.get('tags'):
        tags = " ".join([f"`{tag}`" for tag in vignette.get('tags', [])])
        st.caption(f"Tags: {tags}")
    
    st.divider()
    st.write(vignette['content'])
    st.divider()
    
    # Stats and actions
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Words", vignette.get('word_count', 0))
    with col2:
        st.metric("Views", vignette.get('views', 0))
    with col3:
        st.metric("Likes", vignette.get('likes', 0))
    with col4:
        if vignette.get('is_draft'):
            if st.button("🚀 Publish", use_container_width=True):
                if vignette_manager.publish_vignette(vignette['id']):
                    st.success("Published!")
                    st.rerun()
    
    # Action buttons
    col1, col2 = st.columns(2)
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
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_custom_topic_modal():
    """Show custom topic creation"""
    if not TopicBank:
        st.error("Topic module not available")
        st.session_state.show_custom_topic_modal = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back", key="custom_topic_back"):
        st.session_state.show_custom_topic_modal = False
        st.rerun()
    
    st.title("✨ Custom Topic")
    
    # Create topic bank
    topic_bank = TopicBank(st.session_state.user_id)
    
    # Use the module's topic creator
    topic_bank.display_topic_creator()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_topic_browser():
    """Show topic browser"""
    if not TopicBank:
        st.error("Topic module not available")
        st.session_state.show_topic_browser = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back", key="topic_browser_back"):
        st.session_state.show_topic_browser = False
        st.rerun()
    
    st.title("📚 Topic Browser")
    
    # Create topic bank
    topic_bank = TopicBank(st.session_state.user_id)
    
    # Define callback for topic selection
    def on_topic_select(topic_text):
        switch_to_custom_topic(topic_text)
        st.session_state.show_topic_browser = False
    
    # Use the module's browser
    topic_bank.display_topic_browser(on_topic_select=on_topic_select)
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_session_creator():
    """Show session creator"""
    if not SessionManager:
        st.error("Session module not available")
        st.session_state.show_session_creator = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back", key="session_creator_back"):
        st.session_state.show_session_creator = False
        st.rerun()
    
    st.title("📋 Create Custom Session")
    
    # Create session manager
    session_manager = SessionManager(SESSIONS, st.session_state.user_id)
    
    # Use the module's session creator
    session_manager.display_session_creator()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_session_manager():
    """Show session manager"""
    if not SessionManager:
        st.error("Session module not available")
        st.session_state.show_session_manager = False
        return
    
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    # Back button
    if st.button("← Back", key="session_manager_back"):
        st.session_state.show_session_manager = False
        st.rerun()
    
    st.title("📖 Session Manager")
    
    # Create session manager
    session_manager = SessionManager(SESSIONS, st.session_state.user_id)
    
    # Define callback for session selection
    def on_session_select(session_id):
        # Find the session
        all_sessions = session_manager.get_all_sessions()
        for i, session in enumerate(all_sessions):
            if session["id"] == session_id:
                if i < len(SESSIONS):  # Standard session
                    st.session_state.current_session = i
                else:  # Custom session
                    # For now, just show a message
                    st.info(f"Selected custom session: {session['title']}")
                break
        
        st.session_state.show_session_manager = False
        st.session_state.current_question = 0
        st.rerun()
    
    # Add create button
    if st.button("➕ Create New Session", type="primary", use_container_width=True):
        st.session_state.show_session_manager = False
        st.session_state.show_session_creator = True
        st.rerun()
    
    st.divider()
    
    # Use the module's grid display
    session_manager.display_session_grid(cols=2, on_session_select=on_session_select)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ── Core Writing Functions ────────────────────────────────────────────────────
def save_response(session_id, question, answer):
    """Save response to storage"""
    user_id = st.session_state.user_id
    if not user_id:
        return False
    
    if session_id not in st.session_state.responses:
        s = SESSIONS[session_id-1]
        st.session_state.responses[session_id] = {
            "title": s["title"],
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": s.get("word_target", DEFAULT_WORD_TARGET)
        }
    
    st.session_state.responses[session_id]["questions"][question] = {
        "answer": answer,
        "timestamp": datetime.now().isoformat()
    }
    
    return save_user_data(user_id, st.session_state.responses)

def get_system_prompt():
    """Generate system prompt for AI"""
    current_session = SESSIONS[st.session_state.current_session]
    current_question = (
        st.session_state.current_question_override
        or current_session["questions"][st.session_state.current_question]
    )
    
    # Add historical context if available
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
        except:
            pass
    
    if st.session_state.ghostwriter_mode:
        return f"""ROLE: You are a senior literary biographer.
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
Please:
1. Listen actively
2. Acknowledge warmly
3. Ask ONE natural follow-up question
Tone: Kind, curious, professional"""

# ── Page Config & State ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state initialization
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
    "image_prompt_mode": False,
    "selected_images_for_prompt": [],
    "streak_days": 1,
    "last_active": date.today().isoformat(),
    "total_writing_days": 1,
    # Module states
    "show_vignette_modal": False,
    "show_vignette_manager": False,
    "show_vignette_detail": False,
    "selected_vignette_id": None,
    "editing_vignette_id": None,
    "selected_vignette_for_session": None,
    "show_custom_topic_modal": False,
    "show_topic_browser": False,
    "show_session_manager": False,
    "show_session_creator": False,
}

for key, value in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Initialize responses
if not st.session_state.responses:
    for session in SESSIONS:
        session_id = session["id"]
        st.session_state.responses[session_id] = {
            "title": session["title"],
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": session.get("word_target", DEFAULT_WORD_TARGET)
        }
        st.session_state.session_conversations[session_id] = {}

# Load user data if logged in
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
                        st.session_state.user_id = result["user_id"]
                        st.session_state.user_account = result["user_record"]
                        st.session_state.logged_in = True
                        st.session_state.data_loaded = False
                        st.session_state.show_profile_setup = True
                        st.success("✅ Account created successfully!")
                        st.balloons()
                        st.rerun()
                    else:
                        st.error(f"Error creating account: {result.get('error', 'Unknown error')}")

# ── Main App Flow ─────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    show_login_signup()
    st.stop()

# Show modals if needed
if st.session_state.show_vignette_detail:
    show_vignette_detail()
    st.stop()

if st.session_state.show_vignette_manager:
    show_vignette_manager()
    st.stop()

if st.session_state.show_vignette_modal:
    show_vignette_modal()
    st.stop()

if st.session_state.show_custom_topic_modal:
    show_custom_topic_modal()
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
    # Profile
    st.header("👤 Your Profile")
    if st.session_state.user_account:
        profile = st.session_state.user_account['profile']
        st.success(f"✓ **{profile['first_name']} {profile['last_name']}**")
        st.caption(f"📧 {profile['email']}")
        if profile.get('birthdate'):
            st.caption(f"🎂 Born: {profile['birthdate']}")
        account_type = st.session_state.user_account['account_type']
        st.caption(f"👤 Account: {account_type.title()}")
    
    if st.button("🚪 Log Out", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.divider()
    
    # Session Management
    st.header("📖 Session Management")
    
    if st.button("📋 View All Sessions", use_container_width=True, type="primary"):
        st.session_state.show_session_manager = True
        st.rerun()
    
    if st.button("➕ Create Custom Session", use_container_width=True):
        st.session_state.show_session_creator = True
        st.rerun()
    
    # Topic Management
    st.divider()
    st.header("💡 Topic Management")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📚 Browse Topics", use_container_width=True):
            st.session_state.show_topic_browser = True
            st.rerun()
    
    with col2:
        if st.button("✨ Custom Topic", use_container_width=True):
            st.session_state.show_custom_topic_modal = True
            st.rerun()
    
    # Vignettes
    st.divider()
    st.header("📝 Vignettes")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 New Vignette", use_container_width=True):
            st.session_state.show_vignette_modal = True
            st.rerun()
    
    with col2:
        if st.button("📖 View Vignettes", use_container_width=True):
            st.session_state.show_vignette_manager = True
            st.rerun()
    
    # Show vignette stats
    if st.session_state.logged_in and VignetteManager:
        try:
            vignette_manager = VignetteManager(st.session_state.user_id)
            all_vignettes = vignette_manager.get_all_vignettes(include_drafts=True)
            published = vignette_manager.get_published_vignettes()
            
            with st.expander(f"📊 Vignette Stats ({len(all_vignettes)})", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Published", len(published))
                with col2:
                    st.metric("Drafts", len(all_vignettes) - len(published))
                
                if all_vignettes:
                    total_words = sum(v.get('word_count', 0) for v in all_vignettes)
                    st.caption(f"Total words: {total_words}")
        except:
            pass
    
    # Session Navigation
    st.divider()
    st.header("📚 Current Sessions")
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
            st.session_state.current_question_override = None
            st.rerun()
    
    # Interview Style
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

# ── Main Content ──────────────────────────────────────────────────────────────
current_session = SESSIONS[st.session_state.current_session]
current_session_id = current_session["id"]

if st.session_state.current_question_override:
    current_question_text = st.session_state.current_question_override
else:
    current_question_text = current_session["questions"][st.session_state.current_question]

st.markdown("---")

# Navigation
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.subheader(f"Session {current_session_id}: {current_session['title']}")
    session_responses = len(st.session_state.responses.get(current_session_id, {}).get("questions", {}))
    total_questions = len(current_session["questions"])
    st.caption(f"📝 {session_responses}/{total_questions} topics answered")

with col2:
    current_topic = st.session_state.current_question + 1
    total_topics = len(current_session["questions"])
    st.markdown(f'<div class="question-counter">Topic {current_topic} of {total_topics}</div>', unsafe_allow_html=True)

with col3:
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        prev_disabled = st.session_state.current_question == 0
        if st.button("← Previous", disabled=prev_disabled, key="main_prev_btn", use_container_width=True):
            if not prev_disabled:
                st.session_state.current_question -= 1
                st.session_state.current_question_override = None
                st.rerun()
    
    with nav_col2:
        next_disabled = st.session_state.current_question >= len(current_session["questions"]) - 1
        if st.button("Next →", disabled=next_disabled, key="main_next_btn", use_container_width=True):
            if not next_disabled:
                st.session_state.current_question += 1
                st.session_state.current_question_override = None
                st.rerun()

# Question display
st.markdown(f"""
<div class="question-box">
{current_question_text}
</div>
""", unsafe_allow_html=True)

# Guidance
if not st.session_state.current_question_override:
    st.markdown(f"""
    <div class="chapter-guidance">
    {current_session.get('guidance', '')}
    </div>
    """, unsafe_allow_html=True)

# Conversation
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
            </div>
            <div style='font-size: 1.1rem; margin-top: 1.5rem; color: #555;'>
            Take your time with this—good biographies are built from thoughtful reflection.
            </div>"""
            st.markdown(welcome_msg, unsafe_allow_html=True)
        
        conversation = [{"role": "assistant", "content": f"Let's explore this topic in detail: {current_question_text}"}]
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation

# Display conversation
for i, message in enumerate(conversation):
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="👔"):
            st.markdown(message["content"])
    elif message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])
            word_count = len(re.findall(r'\w+', message["content"]))
            st.caption(f"📝 {word_count} words")

# Input
user_input = st.chat_input("Type your answer here...", key="chat_input")
if user_input:
    conversation.append({"role": "user", "content": user_input})
    
    with st.chat_message("assistant", avatar="👔"):
        with st.spinner("Reflecting on your story..."):
            try:
                messages_for_api = [
                    {"role": "system", "content": get_system_prompt()},
                    *conversation[:-1],
                    {"role": "user", "content": user_input}
                ]
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_for_api,
                    temperature=0.8 if st.session_state.ghostwriter_mode else 0.7,
                    max_tokens=400 if st.session_state.ghostwriter_mode else 300
                )
                
                ai_response = response.choices[0].message.content
                st.markdown(ai_response)
                conversation.append({"role": "assistant", "content": ai_response})
            except Exception as e:
                error_msg = "Thank you for sharing that. Your response has been saved."
                st.markdown(error_msg)
                conversation.append({"role": "assistant", "content": error_msg})
    
    st.session_state.session_conversations[current_session_id][current_question_text] = conversation
    save_response(current_session_id, current_question_text, user_input)
    st.rerun()

# Footer
st.divider()
st.caption("MemLife Timeline • Preserve Your Legacy")
