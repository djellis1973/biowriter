# biographer.py – MemLife main app with Custom Sessions & Vignettes (FIXED VERSION)
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

# ── OpenAI client ─────────────────────────────────────────────────────────────
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")))

# ── Load external CSS ─────────────────────────────────────────────────────────
try:
    with open("styles.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("styles.css not found – layout may look broken")

# Add custom CSS for success messages
st.markdown("""
<style>
.success-message {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
    border-radius: 4px;
    padding: 10px;
    margin: 10px 0;
    font-weight: 500;
}
.success-message-fixed {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
    border-radius: 4px;
    padding: 15px;
    font-weight: 500;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
LOGO_URL = "https://menuhunterai.com/wp-content/uploads/2026/01/logo.png"
DEFAULT_WORD_TARGET = 500

# ── Vignettes Module ──────────────────────────────────────────────────────────
class VignettesManager:
    @staticmethod
    def get_standard_topics():
        return [
            "Life Lesson", "Achievement", "Work", "Loss of Life", "Illness",
            "New Child", "Marriage", "Travel", "Relationship", "Interests",
            "Education", "Family", "Friendship", "Career", "Spiritual",
            "Challenge", "Success", "Failure", "Adventure", "Home"
        ]
    
    @staticmethod
    def load_user_vignettes(user_id):
        user_data = load_user_data(user_id)
        return user_data.get('vignettes', [])
    
    @staticmethod
    def save_user_vignettes(user_id, vignettes):
        user_data = load_user_data(user_id)
        user_data['vignettes'] = vignettes
        save_user_data(user_id, user_data)
        return True
    
    @staticmethod
    def add_vignette(user_id, topic, content, published=True):
        vignettes = VignettesManager.load_user_vignettes(user_id)
        new_vignette = {
            "id": str(uuid.uuid4())[:8],
            "topic": topic,
            "content": content,
            "created_at": datetime.now().isoformat(),
            "published": published,
            "word_count": len(re.findall(r'\w+', content))
        }
        vignettes.append(new_vignette)
        VignettesManager.save_user_vignettes(user_id, vignettes)
        return new_vignette
    
    @staticmethod
    def delete_vignette(user_id, vignette_id):
        vignettes = VignettesManager.load_user_vignettes(user_id)
        vignettes = [v for v in vignettes if v.get('id') != vignette_id]
        VignettesManager.save_user_vignettes(user_id, vignettes)
        return True
    
    @staticmethod
    def add_to_main_story(user_id, vignette_id, session_id):
        vignettes = VignettesManager.load_user_vignettes(user_id)
        vignette = next((v for v in vignettes if v.get('id') == vignette_id), None)
        
        if not vignette:
            return False
        
        topic = f"Vignette: {vignette['topic']}"
        user_data = load_user_data(user_id)
        responses = user_data.get("responses", {})
        
        if session_id not in responses:
            responses[session_id] = {
                "title": f"Session {session_id}",
                "questions": {},
                "summary": "",
                "completed": False,
                "word_target": DEFAULT_WORD_TARGET,
            }
        
        responses[session_id]["questions"][topic] = {
            "answer": vignette['content'],
            "timestamp": datetime.now().isoformat(),
            "source": "vignette",
            "vignette_id": vignette_id
        }
        
        user_data["responses"] = responses
        save_user_data(user_id, user_data)
        return True

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
        "guidance": "Welcome to Session 1: Childhood—this is where we lay the foundation of your story.",
        "questions": [
            "What is your earliest memory?",
            "Can you describe your family home growing up?",
            "Who were the most influential people in your early years?"
        ],
        "completed": False,
        "word_target": 800,
        "custom": False
    },
    {
        "id": 2,
        "title": "Family & Relationships",
        "guidance": "Welcome to Session 2: Family & Relationships—this is where we explore the people who shaped you.",
        "questions": [
            "How would you describe your relationship with your parents?",
            "Are there any family traditions you remember fondly?"
        ],
        "completed": False,
        "word_target": 700,
        "custom": False
    }
]

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
        print(f"Error loading user data: {e}")
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
        print(f"Error saving user data: {e}")
        return False

# ── Authentication Functions ──────────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, password):
    return stored_hash == hash_password(password)

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
            return {"success": True, "user_id": account['user_id'], "user_record": account}
        return {"success": False, "error": "Invalid email or password"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── State Initialization ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize ALL session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = ""
if 'user_account' not in st.session_state:
    st.session_state.user_account = None
if 'current_session' not in st.session_state:
    st.session_state.current_session = 0
if 'current_question' not in st.session_state:
    st.session_state.current_question = 0
if 'responses' not in st.session_state:
    st.session_state.responses = {}
if 'session_conversations' not in st.session_state:
    st.session_state.session_conversations = {}
if 'show_vignettes' not in st.session_state:
    st.session_state.show_vignettes = False
if 'show_custom_sessions' not in st.session_state:
    st.session_state.show_custom_sessions = False
if 'creating_vignette' not in st.session_state:
    st.session_state.creating_vignette = False
if 'editing_custom_session' not in st.session_state:
    st.session_state.editing_custom_session = None
if 'ghostwriter_mode' not in st.session_state:
    st.session_state.ghostwriter_mode = True
if 'spellcheck_enabled' not in st.session_state:
    st.session_state.spellcheck_enabled = True
if 'success_message' not in st.session_state:
    st.session_state.success_message = None
if 'show_image_upload' not in st.session_state:
    st.session_state.show_image_upload = False
if 'image_prompt_mode' not in st.session_state:
    st.session_state.image_prompt_mode = False
if 'selected_images_for_prompt' not in st.session_state:
    st.session_state.selected_images_for_prompt = []
if 'current_question_override' not in st.session_state:
    st.session_state.current_question_override = None
if 'streak_days' not in st.session_state:
    st.session_state.streak_days = 1

# Initialize responses structure
all_sessions = get_all_sessions()
for session in all_sessions:
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

# ── Success Message Handler ──────────────────────────────────────────────────
def show_success_message(message):
    """Show a success message that stays until cleared"""
    st.session_state.success_message = message
    st.rerun()

def clear_success_message():
    """Clear the success message"""
    st.session_state.success_message = None

# ── Navigation Fixes ─────────────────────────────────────────────────────────
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

# ── Vignettes UI (WITH BACK BUTTON) ──────────────────────────────────────────
def show_vignettes_ui():
    st.markdown("---")
    
    # BACK BUTTON - FIXED
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Writer", key="back_from_vignettes"):
            navigate_to_writer()
    with col_title:
        st.header("📝 Vignettes - Quick Stories")
    
    # Show success message if any
    if st.session_state.success_message:
        st.markdown(f'<div class="success-message">✅ {st.session_state.success_message}</div>', unsafe_allow_html=True)
        if st.button("Clear Message", key="clear_vignette_msg"):
            clear_success_message()
            st.rerun()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        **Write short stories for instant gratification.**
        - Quick writing without pressure
        - Publish immediately
        - Add to main biography later
        """)
    with col2:
        if st.button("➕ New Vignette", type="primary", use_container_width=True):
            st.session_state.creating_vignette = True
            st.rerun()
    
    if st.session_state.creating_vignette:
        st.markdown("---")
        st.subheader("✍️ Write a New Vignette")
        
        with st.form("new_vignette_form"):
            standard_topics = VignettesManager.get_standard_topics()
            topic_options = ["Custom Topic"] + standard_topics
            selected_topic_option = st.selectbox("Choose a topic:", topic_options)
            
            if selected_topic_option == "Custom Topic":
                custom_topic = st.text_input("Enter your custom topic:")
                topic = custom_topic
            else:
                topic = selected_topic_option
            
            content = st.text_area(
                "Write your vignette:",
                height=200,
                placeholder="Write your short story here..."
            )
            
            word_count = len(re.findall(r'\w+', content)) if content else 0
            st.caption(f"📝 {word_count} words")
            
            submitted = st.form_submit_button("Save Vignette", type="primary", use_container_width=True)
            
            if submitted:
                if not topic or not topic.strip():
                    st.error("Please enter a topic")
                elif not content or not content.strip():
                    st.error("Please write your vignette")
                else:
                    new_vignette = VignettesManager.add_vignette(
                        st.session_state.user_id,
                        topic,
                        content,
                        True
                    )
                    show_success_message(f"Vignette '{topic}' saved! ({word_count} words)")
                    st.session_state.creating_vignette = False
                    st.rerun()
        
        if st.button("Cancel", key="cancel_vignette"):
            st.session_state.creating_vignette = False
            st.rerun()
    
    st.markdown("---")
    
    # Display existing vignettes
    vignettes = VignettesManager.load_user_vignettes(st.session_state.user_id)
    
    if vignettes:
        st.subheader(f"Your Vignettes ({len(vignettes)})")
        
        for i, vignette in enumerate(vignettes):
            with st.expander(f"📖 {vignette['topic']} ({vignette.get('word_count', 0)} words)", expanded=i==0):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**Topic:** {vignette['topic']}")
                    st.caption(f"Created: {datetime.fromisoformat(vignette['created_at']).strftime('%B %d, %Y')}")
                    status = "✅ Published" if vignette.get('published', True) else "📝 Draft"
                    st.caption(f"Status: {status}")
                
                with col2:
                    if st.button("🗑️", key=f"delete_v_{vignette['id']}", help="Delete this vignette"):
                        if VignettesManager.delete_vignette(st.session_state.user_id, vignette['id']):
                            show_success_message("Vignette deleted")
                            st.rerun()
                
                st.markdown("---")
                st.markdown(vignette['content'])
                st.markdown("---")
                
                # Add to session - FIXED GO TO SESSION BUTTON
                st.markdown("**Add to a session:**")
                all_sessions = get_all_sessions()
                
                if all_sessions:
                    session_options = {f"Session {s['id']}: {s['title']}": s['id'] for s in all_sessions}
                    selected_session_name = st.selectbox(
                        "Choose a session:",
                        list(session_options.keys()),
                        key=f"add_to_session_{vignette['id']}",
                        label_visibility="collapsed"
                    )
                    
                    col_add, col_go = st.columns(2)
                    with col_add:
                        if st.button("➕ Add to Session", key=f"add_btn_{vignette['id']}"):
                            session_id = session_options[selected_session_name]
                            if VignettesManager.add_to_main_story(st.session_state.user_id, vignette['id'], session_id):
                                show_success_message(f"Added to {selected_session_name}")
                                st.rerun()
                    with col_go:
                        if st.button("▶️ Go to Session", key=f"goto_session_{vignette['id']}"):
                            session_id = session_options[selected_session_name]
                            # Find the session index
                            all_sessions = get_all_sessions()
                            for idx, s in enumerate(all_sessions):
                                if s["id"] == session_id:
                                    navigate_to_writer()
                                    st.session_state.current_session = idx
                                    st.session_state.current_question = 0
                                    # Give it a moment to navigate
                                    time.sleep(0.1)
                                    st.rerun()
                                    break
    else:
        st.info("📝 No vignettes yet. Create your first vignette!")

# ── Custom Sessions UI (WITH BACK BUTTON) ─────────────────────────────────────
def show_custom_sessions_ui():
    st.markdown("---")
    
    # BACK BUTTON - FIXED
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("← Back to Writer", key="back_from_custom"):
            navigate_to_writer()
    with col_title:
        st.header("🎨 Custom Sessions & Topics")
    
    # Show success message if any
    if st.session_state.success_message:
        st.markdown(f'<div class="success-message">✅ {st.session_state.success_message}</div>', unsafe_allow_html=True)
        if st.button("Clear Message", key="clear_custom_msg"):
            clear_success_message()
            st.rerun()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("""
        **Create your own sessions with custom topics.**
        - Design sessions around specific themes
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
                
                # FIXED GO TO SESSION BUTTON
                if st.button("▶️ Go to This Session", key=f"goto_{session['id']}", use_container_width=True):
                    # Find the index of this session
                    all_sessions = get_all_sessions()
                    for idx, s in enumerate(all_sessions):
                        if s.get("id") == session["id"]:
                            navigate_to_writer()
                            st.session_state.current_session = idx
                            st.session_state.current_question = 0
                            # Give it a moment to navigate
                            time.sleep(0.1)
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
            title = st.text_input(
                "Session Title:",
                value=current_session["title"] if current_session else "",
                placeholder="e.g., 'College Years', 'Travel Adventures'"
            )
            
            guidance = st.text_area(
                "Session Guidance (optional):",
                value=current_session.get("guidance", "") if current_session else "",
                height=100,
                placeholder="Write guidance text..."
            )
            
            word_target = st.number_input(
                "Word Target:",
                min_value=100,
                max_value=5000,
                value=current_session.get("word_target", DEFAULT_WORD_TARGET) if current_session else DEFAULT_WORD_TARGET,
                step=100
            )
            
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
                
                question = st.text_input(
                    f"Topic {i+1}:",
                    value=default_val,
                    key=f"question_{i}",
                    placeholder="Enter a topic or question..."
                )
                
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
                        CustomSessionsManager.add_session(
                            st.session_state.user_id,
                            title,
                            guidance,
                            questions,
                            word_target
                        )
                        show_success_message(f"Session '{title}' created!")
                    else:
                        # For simplicity in this fix, delete and recreate
                        CustomSessionsManager.delete_session(st.session_state.user_id, current_session["id"])
                        CustomSessionsManager.add_session(
                            st.session_state.user_id,
                            title,
                            guidance,
                            questions,
                            word_target
                        )
                        show_success_message(f"Session '{title}' updated!")
                    
                    st.session_state.editing_custom_session = None
                    st.rerun()
        
        col_cancel, col_back = st.columns(2)
        with col_cancel:
            if st.button("Cancel", key="cancel_custom_session"):
                st.session_state.editing_custom_session = None
                st.rerun()
        with col_back:
            if st.button("← Back to Custom Sessions", key="back_to_custom_list"):
                st.session_state.editing_custom_session = None
                st.rerun()

# ── Authentication UI ─────────────────────────────────────────────────────────
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
                            st.success("✅ Login successful!")
                            st.rerun()
                        else:
                            st.error(f"Login failed: {result.get('error', 'Unknown error')}")
    else:
        with st.form("signup_form"):
            st.subheader("Create New Account")
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name*", key="signup_first_name")
            with col2:
                last_name = st.text_input("Last Name*", key="signup_last_name")
            email = st.text_input("Email Address*", key="signup_email")
            password = st.text_input("Password*", type="password", key="signup_password")
            signup_button = st.form_submit_button("Create My Account", type="primary", use_container_width=True)
            if signup_button:
                if not first_name or not last_name or not email or not password:
                    st.error("Please fill all required fields")
                else:
                    st.success("Account created! Please use the login form.")
                    st.session_state.auth_tab = 'login'
                    st.rerun()

# ── AI Interaction Functions ─────────────────────────────────────────────────
def get_system_prompt():
    all_sessions = get_all_sessions()
    if st.session_state.current_session < len(all_sessions):
        current_session = all_sessions[st.session_state.current_session]
    else:
        current_session = all_sessions[0]
    
    current_question = (
        st.session_state.current_question_override
        or current_session["questions"][st.session_state.current_question]
    )
    
    if st.session_state.ghostwriter_mode:
        return f"""You are a professional biographer helping document a life story.
CURRENT SESSION: Session {current_session['id']}: {current_session['title']}
CURRENT TOPIC: "{current_question}"

Please:
1. Listen actively and acknowledge the response
2. Ask ONE natural follow-up question
3. Be warm, curious, and professional

Tone: Kind, curious, professional"""
    else:
        return f"""You are a warm assistant helping someone write their life story.
CURRENT TOPIC: "{current_question}"

Please respond warmly and ask one follow-up question."""

def save_response(session_id, question, answer):
    user_id = st.session_state.user_id
    if not user_id:
        return False
    
    if session_id not in st.session_state.responses:
        st.session_state.responses[session_id] = {
            "title": f"Session {session_id}",
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": DEFAULT_WORD_TARGET
        }
    
    st.session_state.responses[session_id]["questions"][question] = {
        "answer": answer,
        "timestamp": datetime.now().isoformat()
    }
    
    if save_user_data(user_id, st.session_state.responses):
        return True
    return False

def auto_correct_text(text):
    if not text or not st.session_state.spellcheck_enabled:
        return text
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Fix spelling and grammar mistakes. Return only corrected text."},
                {"role": "user", "content": text}
            ],
            max_tokens=len(text) + 100,
            temperature=0.1
        )
        return response.choices[0].message.content
    except:
        return text

# ── Main App Flow ─────────────────────────────────────────────────────────────
# Show login if not logged in
if not st.session_state.logged_in:
    show_login_signup()
    st.stop()

# Show vignettes or custom sessions if requested
if st.session_state.show_vignettes:
    show_vignettes_ui()
    st.stop()

if st.session_state.show_custom_sessions:
    show_custom_sessions_ui()
    st.stop()

# ── MAIN WRITER APP ──────────────────────────────────────────────────────────
# Show success message if any (FIXED to stay visible)
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
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
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
    all_sessions = get_all_sessions()
    
    for i, session in enumerate(all_sessions):
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

# ── Main Content Area ────────────────────────────────────────────────────────
all_sessions = get_all_sessions()

# Handle session bounds
if st.session_state.current_session >= len(all_sessions):
    st.session_state.current_session = 0
if st.session_state.current_session < 0:
    st.session_state.current_session = 0

current_session = all_sessions[st.session_state.current_session]
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
        if st.button("← Previous", disabled=st.session_state.current_question == 0, key="prev_q"):
            st.session_state.current_question = max(0, st.session_state.current_question - 1)
            st.rerun()
    with nav_col2:
        if st.button("Next →", disabled=st.session_state.current_question >= len(current_session["questions"]) - 1, key="next_q"):
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

# ── AI CHAT INTERACTION (FIXED) ──────────────────────────────────────────────
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

# Chat input - MOVED OUTSIDE OF ANY CONTAINER FOR RELIABILITY
user_input = st.chat_input("Type your answer here...", key="chat_input_main")

if user_input:
    # Process user input
    if st.session_state.spellcheck_enabled:
        user_input = auto_correct_text(user_input)
    
    # Add user message to conversation
    conversation.append({"role": "user", "content": user_input})
    
    # Display user message immediately
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)
    
    # Generate AI response
    with st.chat_message("assistant", avatar="👔"):
        with st.spinner("Reflecting on your story..."):
            try:
                # Prepare messages for API
                messages_for_api = [
                    {"role": "system", "content": get_system_prompt()},
                ]
                
                # Add conversation history (last 4 messages max)
                for msg in conversation[-4:]:
                    messages_for_api.append({"role": msg["role"], "content": msg["content"]})
                
                # Make API call
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_for_api,
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
                print(f"API Error: {e}")
    
    # Save conversation
    st.session_state.session_conversations[current_session_id][current_question_text] = conversation
    
    # Save response to storage
    save_response(current_session_id, current_question_text, user_input)
    
    # Force rerun to update UI
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
    for session in all_sessions:
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        for question, answer_data in session_data.get("questions", {}).items():
            if answer_data.get("answer"):
                total_all_words += len(re.findall(r'\w+', answer_data["answer"]))
    st.metric("Total Words", total_all_words)
with col2:
    completed = sum(1 for s in all_sessions 
                   if len(st.session_state.responses.get(s["id"], {}).get("questions", {})) >= len(s["questions"]))
    st.metric("Completed", f"{completed}/{len(all_sessions)}")
with col3:
    st.metric("Streak", f"{st.session_state.streak_days} days")
