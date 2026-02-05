# biographer.py – MemLife main app (FULLY INTEGRATED)
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

# Import your modules
from vignettes import VignetteManager
from session_manager import SessionManager
from topic_bank import TopicBank

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

# ── Image Manager ─────────────────────────────────────────────────────────────
def get_user_image_folder(user_id):
    folder_path = f"user_images/{user_id}"
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def get_session_image_folder(user_id, session_id):
    folder_path = f"user_images/{user_id}/session_{session_id}"
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def save_image_metadata(user_id, session_id, image_info):
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    try:
        metadata = json.load(open(metadata_file, 'r')) if os.path.exists(metadata_file) else {}
        metadata.setdefault(str(session_id), []).append(image_info)
        json.dump(metadata, open(metadata_file, 'w'), indent=2)
        return True
    except Exception as e:
        print(f"Error saving metadata: {e}")
        return False

def get_session_images(user_id, session_id):
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    if os.path.exists(metadata_file):
        try:
            metadata = json.load(open(metadata_file, 'r'))
            return metadata.get(str(session_id), [])
        except:
            pass
    return []

def save_uploaded_image_simple(uploaded_file, user_id, session_id, description=""):
    try:
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_filename = uploaded_file.name
        file_ext = original_filename.split('.')[-1].lower()
        safe_filename = f"{timestamp}_{unique_id}.{file_ext}"
        session_folder = get_session_image_folder(user_id, session_id)
        file_path = os.path.join(session_folder, safe_filename)
        image_bytes = uploaded_file.read()
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
        thumbnail_path = file_path
        try:
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                img = Image.open(io.BytesIO(image_bytes))
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                thumb_path = os.path.join(session_folder, f"thumb_{safe_filename}")
                img.save(thumb_path, quality=85)
                thumbnail_path = thumb_path
        except:
            pass
        image_info = {
            "id": unique_id,
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "description": description,
            "upload_date": datetime.now().isoformat(),
            "session_id": session_id,
            "file_size_kb": len(image_bytes) / 1024,
            "paths": {"original": file_path, "thumbnail": thumbnail_path}
        }
        save_image_metadata(user_id, session_id, image_info)
        return {"success": True, "image_info": image_info, "message": f"Image '{original_filename}' uploaded successfully!"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def delete_image_simple(user_id, session_id, image_id):
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    try:
        if os.path.exists(metadata_file):
            metadata = json.load(open(metadata_file, 'r'))
            session_key = str(session_id)
            if session_key in metadata:
                for i, img in enumerate(metadata[session_key]):
                    if img["id"] == image_id:
                        for key in ["original", "thumbnail"]:
                            path = img["paths"].get(key)
                            if path and os.path.exists(path):
                                os.remove(path)
                        metadata[session_key].pop(i)
                        json.dump(metadata, open(metadata_file, 'w'), indent=2)
                        return {"success": True, "message": "Image deleted successfully"}
        return {"success": False, "error": "Image not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_image_data_url(image_path):
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
            extension = image_path.split('.')[-1].lower()
            mime_type = f"image/{'jpeg' if extension in ['jpg', 'jpeg'] else extension}"
            return f"data:{mime_type};base64,{encoded}"
    except:
        return None

def display_simple_gallery(user_id, session_id):
    images = get_session_images(user_id, session_id)
    if not images:
        return []
    st.subheader(f"📸 Your Photos ({len(images)})")
    selected_images = []
    for idx, img_info in enumerate(images):
        col1, col2 = st.columns([3, 1])
        with col1:
            thumb = img_info["paths"].get("thumbnail")
            if thumb and os.path.exists(thumb):
                data_url = get_image_data_url(thumb)
                if data_url:
                    st.markdown(f'<img src="{data_url}" style="width:100%; max-height:200px; object-fit:cover; border-radius:8px;">', unsafe_allow_html=True)
            st.caption(img_info['original_filename'])
            if img_info.get('description'):
                st.caption(f"📝 {img_info['description']}")
        with col2:
            if st.button("✨ Use", key=f"select_{img_info['id']}"):
                selected_images.append(img_info)
            if st.button("🗑️", key=f"delete_{img_info['id']}"):
                result = delete_image_simple(user_id, session_id, img_info["id"])
                if result["success"]:
                    st.success("Photo deleted")
                    st.rerun()
                else:
                    st.error(result["error"])
    return selected_images

def get_images_for_prompt_simple(user_id, session_id):
    images = get_session_images(user_id, session_id)
    if not images:
        return ""
    prompt_text = "\n\n📸 **PHOTOS UPLOADED FOR THIS MEMORY:**\n"
    for img in images[:5]:
        prompt_text += f"- Photo: {img['original_filename']}"
        if img.get('description'):
            prompt_text += f" - {img['description']}"
        prompt_text += "\n"
    prompt_text += """
**Use these photos to ask specific questions about:**
1. Who is in the photo?
2. Where was it taken?
3. When was it taken?
4. What's happening in the photo?
5. What emotions does it bring up?
6. What happened before/after this moment?**
"""
    return prompt_text

def get_total_user_images(user_id):
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    if os.path.exists(metadata_file):
        try:
            metadata = json.load(open(metadata_file, 'r'))
            return sum(len(images) for images in metadata.values())
        except:
            pass
    return 0

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
    keys = list(st.session_state.keys())
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
        return {"responses": {}, "last_loaded": datetime.now().isoformat()}
    except Exception as e:
        print(f"Error loading user data for {user_id}: {e}")
        return {"responses": {}, "last_loaded": datetime.now().isoformat()}

def save_user_data(user_id, responses_data):
    filename = get_user_filename(user_id)
    try:
        data_to_save = {
            "user_id": user_id,
            "responses": responses_data,
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
    image_context = ""
    if st.session_state.logged_in and st.session_state.user_id:
        current_session_id = current_session["id"]
        images = get_session_images(st.session_state.user_id, current_session_id)
        if images:
            image_context = get_images_for_prompt_simple(st.session_state.user_id, current_session_id)
    image_prompt_section = ""
    if st.session_state.image_prompt_mode and st.session_state.selected_images_for_prompt:
        image_prompt_section = "\n\n📸 **PHOTO STORY MODE:**\n"
        image_prompt_section += "The user has selected specific photos to write about. "
        image_prompt_section += "Ask questions about these specific photos:\n\n"
        for idx, img in enumerate(st.session_state.selected_images_for_prompt[:3]):
            image_prompt_section += f"**Photo {idx+1}: {img['original_filename']}**\n"
            if img.get('description'):
                image_prompt_section += f"Description: {img['description']}\n"
        photo_prompts = [
            "Who is in this photo?",
            "Where and when was this taken?",
            "What was happening just before/after this moment?",
            "What emotions does this photo bring up?",
            "Why was this photo taken/saved?"
        ]
        selected_prompts = random.sample(photo_prompts, min(3, len(photo_prompts)))
        for prompt in selected_prompts:
            image_prompt_section += f"• {prompt}\n"
        image_prompt_section += "\n"
    if st.session_state.ghostwriter_mode:
        return f"""ROLE: You are a senior literary biographer with multiple award-winning books to your name.
CURRENT SESSION: Session {current_session['id']}: {current_session['title']}
CURRENT TOPIC: "{current_question}"
{historical_context}{image_context}{image_prompt_section}
YOUR APPROACH:
1. Listen like an archivist
2. Think in scenes, sensory details, and emotional truth
3. Connect personal stories to historical context when relevant
4. Find the story that needs to be told
5. When photos are mentioned, ask SPECIFIC questions about them
PHOTO QUESTIONS TO ASK:
• "Who are the people in this photo?"
• "What was happening that day?"
• "Where was this taken and why were you there?"
• "What do you remember feeling when this was taken?"
• "What happened right after this photo was taken?"
Tone: Literary but not pretentious. Serious but not solemn.
IMPORTANT: When photos are mentioned, ask specific, detailed questions about them."""
    else:
        return f"""You are a warm, professional biographer helping document a life story.
CURRENT SESSION: Session {current_session['id']}: {current_session['title']}
CURRENT TOPIC: "{current_question}"
{historical_context}{image_context}{image_prompt_section}
Please:
1. Listen actively
2. Acknowledge warmly
3. Ask ONE natural follow-up question that connects to historical context or photos
4. When photos are mentioned, ask about the people, place, and emotions
PHOTO QUESTIONS:
• "Tell me about the people in this photo"
• "What's the story behind this moment?"
• "How do you feel when you look at this photo?"
Tone: Kind, curious, professional"""

# ── Core Functions ────────────────────────────────────────────────────────────
def save_response(session_id, question, answer):
    user_id = st.session_state.user_id
    if not user_id or user_id == "":
        print("DEBUG: No user_id, cannot save")
        return False
    print(f"DEBUG: Saving for user {user_id}, session {session_id}, question: {question[:50]}...")
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
    if save_user_data(user_id, st.session_state.responses):
        print(f"DEBUG: Successfully saved to JSON file for {user_id}")
        return True
    else:
        print(f"DEBUG: Failed to save to JSON file for {user_id}")
        return False

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
        color = "#2ecc71"
    else:
        progress_percent = (current_count / target) * 100 if target > 0 else 100
    if progress_percent >= 100:
        emoji = "🟢"
        color = "#2ecc71"
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

# ── Vignette Integration Functions ───────────────────────────────────────────
def show_vignette_creation_modal():
    """Modal for creating vignettes with publish options"""
    st.markdown('<div class="vignette-modal">', unsafe_allow_html=True)
    st.title("📝 Create Vignette")
    
    # Initialize vignette manager
    vignette_manager = VignetteManager(st.session_state.user_id)
    
    with st.form("create_vignette_form"):
        # Theme selection
        theme_options = vignette_manager.standard_themes + ["Custom Theme"]
        selected_theme = st.selectbox("Choose a Theme", theme_options)
        
        if selected_theme == "Custom Theme":
            custom_theme = st.text_input("Your Custom Theme")
            theme = custom_theme if custom_theme.strip() else "Personal Story"
        else:
            theme = selected_theme
        
        # Title
        title = st.text_input("Title", 
                            placeholder="Give your story a compelling title")
        
        # Content
        content = st.text_area("Your Story", 
                             height=200,
                             placeholder="Write your short story here...")
        
        # Word count display
        if content:
            word_count = len(content.split())
            st.caption(f"📝 {word_count} words")
        
        # Action buttons in a row
        col1, col2, col3 = st.columns(3)
        with col1:
            publish_button = st.form_submit_button("🚀 Publish Now", 
                                                 type="primary",
                                                 use_container_width=True)
        with col2:
            draft_button = st.form_submit_button("💾 Save as Draft",
                                               use_container_width=True)
        with col3:
            cancel_button = st.form_submit_button("Cancel",
                                                type="secondary",
                                                use_container_width=True)
        
        if publish_button and content.strip() and title.strip():
            vignette = vignette_manager.create_vignette(title, content, theme, [], is_draft=False)
            vignette_manager.publish_vignette(vignette["id"])
            st.success("🎉 Published! Your story is now live.")
            st.balloons()
            st.session_state.show_vignette_modal = False
            st.rerun()
        
        elif draft_button and content.strip():
            title_to_use = title if title.strip() else f"Draft: {theme}"
            vignette_manager.create_vignette(title_to_use, content, theme, [], is_draft=True)
            st.success("💾 Saved as draft!")
            st.session_state.show_vignette_modal = False
            st.rerun()
        
        elif cancel_button:
            st.session_state.show_vignette_modal = False
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def show_vignette_publish_options(vignette_id):
    """Show options for what to do with a vignette"""
    st.subheader("📋 What would you like to do with this vignette?")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📖 Add to Main Story", use_container_width=True):
            # Add to current session
            current_session = SESSIONS[st.session_state.current_session]
            current_session_id = current_session["id"]
            
            vignette_manager = VignetteManager(st.session_state.user_id)
            vignette = vignette_manager.get_vignette_by_id(vignette_id)
            
            if vignette:
                st.session_state.current_question_override = f"Vignette: {vignette['title']}"
                save_response(current_session_id, f"Vignette: {vignette['title']}", vignette['content'])
                st.success(f"Added to Session {current_session_id}: {current_session['title']}")
                st.session_state.show_vignette_publish_options = None
                st.rerun()
    
    with col2:
        if st.button("🆕 Create New Session", use_container_width=True):
            # Initialize session manager
            session_manager = SessionManager(SESSIONS, st.session_state.user_id)
            
            vignette_manager = VignetteManager(st.session_state.user_id)
            vignette = vignette_manager.get_vignette_by_id(vignette_id)
            
            if vignette:
                # Create custom session from vignette
                new_session = session_manager.create_custom_session(
                    title=f"Vignette: {vignette['title']}",
                    description=f"Story about {vignette['theme']}",
                    topics=[vignette['content'][:100] + "..."],
                    word_target=500
                )
                st.success(f"Created new session: {new_session['title']}")
                st.session_state.show_vignette_publish_options = None
                st.rerun()
    
    with col3:
        if st.button("❌ Just Keep in Vignettes", use_container_width=True):
            st.session_state.show_vignette_publish_options = None
            st.rerun()

def show_custom_session_creator():
    """Modal for creating custom sessions with questions"""
    st.markdown('<div class="custom-session-modal">', unsafe_allow_html=True)
    st.title("🆕 Create Custom Session")
    
    with st.form("create_custom_session_form"):
        # Session details
        session_title = st.text_input("Session Title", 
                                    placeholder="e.g., 'My College Years' or 'Career Journey'")
        
        session_description = st.text_area("Description (optional)",
                                         placeholder="Brief description of this session...",
                                         height=100)
        
        # Questions input (6 questions as requested)
        st.subheader("Questions (6 recommended)")
        questions = []
        for i in range(6):
            question = st.text_input(f"Question {i+1}", 
                                   placeholder=f"Enter question {i+1}...",
                                   key=f"custom_q_{i}")
            questions.append(question)
        
        word_target = st.number_input("Word Target", 
                                    min_value=100, 
                                    max_value=5000, 
                                    value=500)
        
        # Action buttons
        col1, col2 = st.columns(2)
        with col1:
            create_button = st.form_submit_button("✅ Create Session", 
                                                type="primary",
                                                use_container_width=True)
        with col2:
            cancel_button = st.form_submit_button("❌ Cancel",
                                                type="secondary",
                                                use_container_width=True)
        
        if create_button and session_title.strip():
            # Filter out empty questions
            valid_questions = [q for q in questions if q.strip()]
            
            # Initialize session manager
            session_manager = SessionManager(SESSIONS, st.session_state.user_id)
            
            # Create custom session
            new_session = session_manager.create_custom_session(
                title=session_title,
                description=session_description,
                topics=valid_questions,
                word_target=word_target
            )
            
            st.success(f"✅ Session '{session_title}' created with {len(valid_questions)} questions!")
            
            # Add to responses
            session_id = new_session["id"]
            if session_id not in st.session_state.responses:
                st.session_state.responses[session_id] = {
                    "title": session_title,
                    "questions": {},
                    "summary": "",
                    "completed": False,
                    "word_target": word_target,
                    "is_custom": True,
                    "custom_questions": valid_questions
                }
            
            # Switch to new session
            # Find session index
            all_sessions = session_manager.get_all_sessions()
            for i, session in enumerate(all_sessions):
                if session["id"] == session_id:
                    st.session_state.current_session = i
                    st.session_state.current_question = 0
                    st.session_state.show_custom_session_modal = False
                    st.rerun()
                    break
        
        if cancel_button:
            st.session_state.show_custom_session_modal = False
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ── Page Config & State ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state initialization
for key, value in {
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
    "show_image_upload": False,
    "image_prompt_mode": False,
    "selected_images_for_prompt": [],
    "image_description": "",
    "streak_days": 1,
    "last_active": date.today().isoformat(),
    "total_writing_days": 1,
    # Vignette states
    "show_vignette_modal": False,
    "show_vignette_publish_options": None,
    # Custom session states
    "show_custom_session_modal": False,
    # Navigation history
    "session_history": [],
    "current_history_index": -1
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

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

# ── Navigation Functions ──────────────────────────────────────────────────────
def navigate_back():
    """Navigate back in history"""
    if st.session_state.session_history and st.session_state.current_history_index > 0:
        st.session_state.current_history_index -= 1
        prev_state = st.session_state.session_history[st.session_state.current_history_index]
        
        st.session_state.current_session = prev_state["current_session"]
        st.session_state.current_question = prev_state["current_question"]
        st.session_state.current_question_override = prev_state.get("current_question_override")
        st.session_state.image_prompt_mode = prev_state.get("image_prompt_mode", False)
        st.session_state.editing = None
        
        st.rerun()

def navigate_forward():
    """Navigate forward in history"""
    if (st.session_state.session_history and 
        st.session_state.current_history_index < len(st.session_state.session_history) - 1):
        st.session_state.current_history_index += 1
        next_state = st.session_state.session_history[st.session_state.current_history_index]
        
        st.session_state.current_session = next_state["current_session"]
        st.session_state.current_question = next_state["current_question"]
        st.session_state.current_question_override = next_state.get("current_question_override")
        st.session_state.image_prompt_mode = next_state.get("image_prompt_mode", False)
        st.session_state.editing = None
        
        st.rerun()

def save_navigation_state():
    """Save current navigation state to history"""
    current_state = {
        "current_session": st.session_state.current_session,
        "current_question": st.session_state.current_question,
        "current_question_override": st.session_state.current_question_override,
        "image_prompt_mode": st.session_state.image_prompt_mode
    }
    
    # If we're navigating back/forward, don't add new state
    if (st.session_state.session_history and 
        st.session_state.current_history_index >= 0 and
        st.session_state.current_history_index < len(st.session_state.session_history) - 1):
        # We're in the middle of history, truncate forward history
        st.session_state.session_history = st.session_state.session_history[:st.session_state.current_history_index + 1]
    
    # Add new state
    st.session_state.session_history.append(current_state)
    st.session_state.current_history_index = len(st.session_state.session_history) - 1
    
    # Limit history size
    if len(st.session_state.session_history) > 20:
        st.session_state.session_history = st.session_state.session_history[-20:]
        st.session_state.current_history_index = 19

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

# Show modals if needed
if st.session_state.show_vignette_modal:
    show_vignette_creation_modal()
    st.stop()

if st.session_state.show_vignette_publish_options:
    show_vignette_publish_options(st.session_state.show_vignette_publish_options)
    st.stop()

if st.session_state.show_custom_session_modal:
    show_custom_session_creator()
    st.stop()

# Save navigation state when page loads
if "navigation_saved" not in st.session_state:
    save_navigation_state()
    st.session_state.navigation_saved = True

# Load historical events once
if not st.session_state.historical_events_loaded:
    try:
        events = load_historical_events()
        if events:
            print(f"Loaded historical events for {len(events)} decades")
        st.session_state.historical_events_loaded = True
    except Exception as e:
        print(f"Error loading historical events: {e}")

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
            try:
                birth_year = int(profile['birthdate'].split(', ')[-1])
                events = get_events_for_birth_year(birth_year)
                if events:
                    uk_events = [e for e in events if e.get('region') == 'UK']
                    global_events = len(events) - len(uk_events)
                    st.caption(f"📚 {len(events)} historical events ({len(uk_events)} UK, {global_events} global)")
            except:
                pass
        else:
            st.caption("🎂 Birthdate: Not set")
        account_type = st.session_state.user_account['account_type']
        st.caption(f"👤 Account: {account_type.title()}")
    
    if st.button("📝 Edit Profile", use_container_width=True):
        st.session_state.show_profile_setup = True
        st.rerun()
    
    if st.button("🚪 Log Out", use_container_width=True):
        logout_user()
    
    st.divider()
    
    # Streak
    st.subheader("🔥 Writing Streak")
    streak_emoji = get_streak_emoji(st.session_state.streak_days)
    st.markdown(f"<div class='streak-flame'>{streak_emoji}</div>", unsafe_allow_html=True)
    st.markdown(f"**{st.session_state.streak_days} day streak**")
    st.caption(f"Total writing days: {st.session_state.total_writing_days}")
    if st.session_state.streak_days >= 7:
        st.success("🏆 Weekly Writer!")
    if st.session_state.streak_days >= 30:
        st.success("🌟 Monthly Master!")
    
    # Photo Gallery
    st.divider()
    st.subheader("🖼️ Photo Gallery")
    if st.session_state.logged_in:
        total_images = get_total_user_images(st.session_state.user_id)
        st.metric("Total Photos", total_images)
        if total_images > 0:
            if st.button("📸 View Photos", use_container_width=True):
                st.session_state.show_image_upload = True
                st.rerun()
        else:
            st.info("No photos yet")
    
    # Quick Capture
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
                save_navigation_state()
                st.info("Ready to write about this!")
                st.rerun()
        if st.session_state.get('quick_jots'):
            st.caption(f"📝 {len(st.session_state.quick_jots)} quick notes saved")
            if st.button("View Quick Notes", key="view_jots_btn"):
                st.session_state.show_jots = True
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
        st.caption("With historical context & photo integration")
    else:
        st.info("Standard mode active")
    
    # Historical Context
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
                if st.button("📋 View All Historical Events", key="view_all_events"):
                    st.session_state.show_event_manager = True
                    st.rerun()
            else:
                st.info("No historical events loaded")
        except:
            st.info("Add birthdate to see historical context")
    else:
        st.info("Add your birthdate to enable historical context")
    
    # ── VIGNETTES & CUSTOM SESSIONS ──────────────────────────────────────────
    st.divider()
    st.header("✨ Quick Features")
    
    # Vignettes button
    if st.button("📝 Create Vignette", use_container_width=True):
        st.session_state.show_vignette_modal = True
        save_navigation_state()
        st.rerun()
    
    # Custom session button
    if st.button("🆕 Create Custom Session", use_container_width=True):
        st.session_state.show_custom_session_modal = True
        save_navigation_state()
        st.rerun()
    
# Show saved vignettes
if st.session_state.logged_in:
    vignette_manager = VignetteManager(st.session_state.user_id)
    user_vignettes = vignette_manager.get_all_vignettes(include_drafts=True)
    
    if user_vignettes:
        with st.expander(f"📚 Your Vignettes ({len(user_vignettes)})", expanded=False):
            for idx, vignette in enumerate(user_vignettes[:3]):  # Show first 3
                col1, col2 = st.columns([3, 1])
                with col1:
                    status = "📝 Draft" if vignette.get('is_draft') else "🚀 Published"
                    st.write(f"**{vignette['title']}**")
                    st.caption(f"{status} • {vignette['theme']}")
                with col2:
                    # REMOVED size="small"
                    if st.button("Open", key=f"open_v_{idx}"):
                        st.session_state.show_vignette_publish_options = vignette["id"]
                        save_navigation_state()
                        st.rerun()
                
                if idx < len(user_vignettes[:3]) - 1:
                    st.divider()

# Show custom sessions
if st.session_state.logged_in:
    session_manager = SessionManager(SESSIONS, st.session_state.user_id)
    custom_sessions = session_manager.custom_sessions
    
    if custom_sessions:
        with st.expander(f"🆕 Custom Sessions ({len(custom_sessions)})", expanded=False):
            for idx, session in enumerate(custom_sessions[:3]):  # Show first 3
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{session['title']}**")
                    st.caption(f"{len(session.get('topics', []))} topics")
                with col2:
                    # REMOVED size="small"
                    if st.button("Enter", key=f"enter_cs_{idx}"):
                        # Find session index
                        all_sessions = session_manager.get_all_sessions()
                        for i, s in enumerate(all_sessions):
                            if s["id"] == session["id"]:
                                st.session_state.current_session = i
                                st.session_state.current_question = 0
                                save_navigation_state()
                                st.rerun()
                                break
                
                if idx < len(custom_sessions[:3]) - 1:
                    st.divider()
    
    # ── SESSION NAVIGATION ────────────────────────────────────────────────────
    st.divider()
    st.header("📖 Sessions")
    
    # Initialize session manager for progress
    if st.session_state.logged_in:
        session_manager = SessionManager(SESSIONS, st.session_state.user_id)
        all_sessions = session_manager.get_all_sessions()
    else:
        all_sessions = SESSIONS
    
    for i, session in enumerate(all_sessions):
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        responses_count = len(session_data.get("questions", {}))
        
        # Get total questions
        if session.get("is_custom"):
            total_questions = len(session.get("topics", []))
        else:
            total_questions = len(session.get("questions", []))
        
        # Status indicator
        if i == st.session_state.current_session:
            status = "▶️"
        elif responses_count == total_questions and total_questions > 0:
            status = "✅"
        elif responses_count > 0:
            status = "🟡"
        else:
            status = "●"
        
        # Custom indicator
        custom_indicator = "✨ " if session.get("is_custom") else ""
        
        button_text = f"{status} {custom_indicator}{session['title']} ({responses_count}/{total_questions})"
        
        if st.button(button_text, key=f"select_session_{i}", use_container_width=True):
            st.session_state.current_session = i
            st.session_state.current_question = 0
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            save_navigation_state()
            st.rerun()
    
    # ── TOPIC NAVIGATION ──────────────────────────────────────────────────────
    st.divider()
    st.subheader("📝 Topic Navigation")
    
    current_session_obj = all_sessions[st.session_state.current_session]
    
    # Get questions based on session type
    if current_session_obj.get("is_custom"):
        questions = current_session_obj.get("topics", [])
    else:
        questions = current_session_obj.get("questions", [])
    
    current_topic = st.session_state.current_question + 1
    total_topics = len(questions)
    
    st.markdown(f'<div class="question-counter">Topic {current_topic} of {total_topics}</div>', unsafe_allow_html=True)
    
    # Navigation buttons with history
    nav_col1, nav_col2, nav_col3 = st.columns(3)
    
    with nav_col1:
        # Back in history button
        has_history_back = (st.session_state.session_history and 
                          st.session_state.current_history_index > 0)
        if st.button("⏪ Back", 
                    disabled=not has_history_back,
                    key="history_back_btn",
                    use_container_width=True,
                    help="Go back to previous screen"):
            navigate_back()
    
    with nav_col2:
        # Previous topic button
        prev_disabled = st.session_state.current_question == 0
        if st.button("← Previous", 
                    disabled=prev_disabled, 
                    key="prev_topic_sidebar",
                    use_container_width=True,
                    help="Go to previous topic"):
            if not prev_disabled:
                st.session_state.current_question -= 1
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.session_state.image_prompt_mode = False
                save_navigation_state()
                st.rerun()
    
    with nav_col3:
        # Next topic button
        next_disabled = st.session_state.current_question >= total_topics - 1
        if st.button("Next →", 
                    disabled=next_disabled, 
                    key="next_topic_sidebar",
                    use_container_width=True,
                    help="Go to next topic"):
            if not next_disabled:
                st.session_state.current_question += 1
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.session_state.image_prompt_mode = False
                save_navigation_state()
                st.rerun()
    
    # ── SESSION NAVIGATION ────────────────────────────────────────────────────
    st.divider()
    st.subheader("🔀 Session Navigation")
    
    nav_col1, nav_col2, nav_col3 = st.columns(3)
    
    with nav_col1:
        # Forward in history button
        has_history_forward = (st.session_state.session_history and 
                             st.session_state.current_history_index < len(st.session_state.session_history) - 1)
        if st.button("Forward ⏩", 
                    disabled=not has_history_forward,
                    key="history_forward_btn",
                    use_container_width=True,
                    help="Go forward to next screen"):
            navigate_forward()
    
    with nav_col2:
        prev_session_disabled = st.session_state.current_session == 0
        if st.button("← Previous Session", 
                    disabled=prev_session_disabled,
                    key="prev_session_sidebar",
                    use_container_width=True,
                    help="Go to previous session"):
            if not prev_session_disabled:
                st.session_state.current_session -= 1
                st.session_state.current_question = 0
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.session_state.image_prompt_mode = False
                save_navigation_state()
                st.rerun()
    
    with nav_col3:
        next_session_disabled = st.session_state.current_session >= len(all_sessions) - 1
        if st.button("Next Session →", 
                    disabled=next_session_disabled,
                    key="next_session_sidebar",
                    use_container_width=True,
                    help="Go to next session"):
            if not next_session_disabled:
                st.session_state.current_session += 1
                st.session_state.current_question = 0
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.session_state.image_prompt_mode = False
                save_navigation_state()
                st.rerun()
    
    # Session Selector
    session_options = []
    for session in all_sessions:
        custom_indicator = "✨ " if session.get("is_custom") else ""
        session_options.append(f"{custom_indicator}{session['title']}")
    
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
        st.session_state.image_prompt_mode = False
        save_navigation_state()
        st.rerun()
    
    st.divider()
    
    # Export Options
    st.subheader("📤 Export Options")
    total_answers = sum(len(session.get("questions", {})) for session in st.session_state.responses.values())
    total_images = get_total_user_images(st.session_state.user_id) if st.session_state.logged_in else 0
    st.caption(f"Total answers: {total_answers} • Total photos: {total_images}")
    
    if st.session_state.logged_in and st.session_state.user_id:
        export_data = {}
        for session in all_sessions:
            session_id = session["id"]
            session_data = st.session_state.responses.get(session_id, {})
            if session_data.get("questions"):
                export_data[str(session_id)] = {
                    "title": session["title"],
                    "questions": session_data["questions"]
                }
        
        image_data = {}
        for session in all_sessions:
            session_id = session["id"]
            images = get_session_images(st.session_state.user_id, session_id)
            if images:
                image_data[str(session_id)] = []
                for img in images:
                    image_data[str(session_id)].append({
                        "filename": img["original_filename"],
                        "description": img.get("description", ""),
                        "upload_date": img["upload_date"],
                        "session_id": session_id
                    })
        
        if export_data or image_data:
            complete_data = {
                "user": st.session_state.user_id,
                "stories": export_data,
                "images": image_data,
                "export_date": datetime.now().isoformat(),
                "summary": {
                    "total_stories": sum(len(session['questions']) for session in export_data.values()),
                    "total_images": sum(len(images) for images in image_data.values())
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
            
            if total_images > 0:
                st.divider()
                st.write("**📸 Photo Export**")
                all_images = []
                for session in all_sessions:
                    session_id = session["id"]
                    images = get_session_images(st.session_state.user_id, session_id)
                    for img in images:
                        all_images.append({
                            "session": session_id,
                            "session_title": session["title"],
                            "filename": img["original_filename"],
                            "description": img.get("description", ""),
                            "upload_date": img["upload_date"]
                        })
                if all_images:
                    image_list_json = json.dumps(all_images, indent=2)
                    if st.button("📋 Export Image List", use_container_width=True):
                        st.download_button(
                            label="⬇️ Download Image Catalog",
                            data=image_list_json,
                            file_name=f"MemLife_Images_{st.session_state.user_id}.json",
                            mime="application/json",
                            use_container_width=True,
                            key="download_image_catalog"
                        )
            
            st.divider()
            st.markdown(f'''
            <a href="{publisher_url}" target="_blank">
            <button class="html-link-btn">
            🖨️ Publish Biography (with Photos)
            </button>
            </a>
            ''', unsafe_allow_html=True)
            st.caption("Create a beautiful book with your stories and photo references")
        else:
            st.warning("No data to export yet! Start by answering some questions or uploading photos.")
    else:
        st.warning("Please log in to export your data.")
    
    st.divider()
    
    # Clear Data
    st.subheader("⚠️ Clear Data")
    if st.session_state.confirming_clear == "session":
        st.markdown('<div class="warning-box">', unsafe_allow_html=True)
        st.warning("**WARNING: This will delete ALL answers in the current session!**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm Delete Session", type="primary", use_container_width=True, key="confirm_delete_session"):
                current_session_id = all_sessions[st.session_state.current_session]["id"]
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
                    for session in all_sessions:
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
# Get current session object
if st.session_state.logged_in:
    session_manager = SessionManager(SESSIONS, st.session_state.user_id)
    all_sessions = session_manager.get_all_sessions()
else:
    all_sessions = SESSIONS

current_session_obj = all_sessions[st.session_state.current_session]
current_session_id = current_session_obj["id"]

# Get current question text
if st.session_state.current_question_override:
    current_question_text = st.session_state.current_question_override
    question_source = "custom"
else:
    # Get questions based on session type
    if current_session_obj.get("is_custom"):
        questions = current_session_obj.get("topics", [])
    else:
        questions = current_session_obj.get("questions", [])
    
    if st.session_state.current_question < len(questions):
        current_question_text = questions[st.session_state.current_question]
        question_source = "regular"
    else:
        current_question_text = "No question available"
        question_source = "regular"

st.markdown("---")

# Main navigation header with back buttons
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    # Custom session indicator
    custom_indicator = "✨ " if current_session_obj.get("is_custom") else ""
    
    st.subheader(f"{custom_indicator}Session {current_session_id}: {current_session_obj['title']}")
    
    session_responses = len(st.session_state.responses.get(current_session_id, {}).get("questions", {}))
    
    # Get total questions
    if current_session_obj.get("is_custom"):
        total_questions = len(current_session_obj.get("topics", []))
    else:
        total_questions = len(current_session_obj.get("questions", []))
    
    st.caption(f"📝 {session_responses}/{total_questions} topics answered")
    
    if st.session_state.logged_in:
        session_images = get_session_images(st.session_state.user_id, current_session_id)
        if session_images:
            st.caption(f"📸 {len(session_images)} photos in this session")
    
    if st.session_state.ghostwriter_mode:
        st.markdown('<p class="ghostwriter-tag">Professional Ghostwriter Mode (with historical context & photo integration)</p>', unsafe_allow_html=True)

with col2:
    if question_source == "custom":
        if st.session_state.current_question_override.startswith("Vignette:"):
            st.markdown(f'<div class="question-counter" style="margin-top: 1rem; color: #9b59b6;">📝 Vignette</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="question-counter" style="margin-top: 1rem; color: #ff6b00;">✨ Custom Topic</div>', unsafe_allow_html=True)
    else:
        current_topic = st.session_state.current_question + 1
        st.markdown(f'<div class="question-counter" style="margin-top: 1rem;">Topic {current_topic} of {total_questions}</div>', unsafe_allow_html=True)

with col3:
    # Main content back/next buttons
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
                st.session_state.image_prompt_mode = False
                save_navigation_state()
                st.rerun()
    
    with nav_col2:
        next_disabled = st.session_state.current_question >= total_questions - 1
        if st.button("Next Topic →", 
                    disabled=next_disabled,
                    key="main_next_btn",
                    use_container_width=True):
            if not next_disabled:
                st.session_state.current_question += 1
                st.session_state.editing = None
                st.session_state.current_question_override = None
                st.session_state.image_prompt_mode = False
                save_navigation_state()
                st.rerun()

# Question display
st.markdown(f"""
<div class="question-box">
{current_question_text}
</div>
""", unsafe_allow_html=True)

# ── Image Controls ────────────────────────────────────────────────────────────
st.write("")
image_controls_container = st.container()
with image_controls_container:
    has_images = False
    if st.session_state.logged_in:
        session_images = get_session_images(st.session_state.user_id, current_session_id)
        has_images = len(session_images) > 0
    
    img_col1, img_col2 = st.columns(2)
    with img_col1:
        button_text = "📷 Add Photos" if not st.session_state.show_image_upload else "📷 Hide Photos"
        if st.button(button_text, key="toggle_image_upload", use_container_width=True):
            st.session_state.show_image_upload = not st.session_state.show_image_upload
            st.rerun()
    
    with img_col2:
        if has_images:
            if st.button("✨ Tell Photo Stories", key="photo_stories_btn", use_container_width=True, type="primary"):
                st.session_state.image_prompt_mode = True
                st.rerun()
        else:
            st.button("✨ Tell Photo Stories", key="disabled_photo_stories", use_container_width=True, disabled=True)
    
    if st.session_state.show_image_upload and st.session_state.logged_in:
        st.markdown("---")
        st.subheader("📤 Upload Photos for This Memory")
        uploaded_files = st.file_uploader(
            "Choose photos to upload",
            type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
            accept_multiple_files=True,
            key=f"simple_uploader_{current_session_id}"
        )
        
        if uploaded_files:
            description = st.text_input(
                "Add a description for these photos (optional):",
                placeholder="E.g., 'Family vacation, 1985'",
                key=f"simple_desc_{current_session_id}"
            )
            
            if st.button("Upload Photos", key=f"simple_upload_btn_{current_session_id}", type="primary"):
                success_count = 0
                error_count = 0
                for uploaded_file in uploaded_files:
                    result = save_uploaded_image_simple(uploaded_file, st.session_state.user_id, current_session_id, description)
                    if result["success"]:
                        success_count += 1
                    else:
                        error_count += 1
                        st.error(f"Error uploading {uploaded_file.name}: {result['error']}")
                
                if success_count > 0:
                    st.success(f"Successfully uploaded {success_count} photo(s)!")
                    st.rerun()
                if error_count > 0:
                    st.warning(f"Failed to upload {error_count} photo(s).")
        
        session_images = get_session_images(st.session_state.user_id, current_session_id)
        if session_images:
            st.divider()
            st.subheader("📷 Your Photos")
            selected_images = display_simple_gallery(st.session_state.user_id, current_session_id)
            if selected_images:
                st.session_state.selected_images_for_prompt = selected_images
                st.success(f"✅ Selected {len(selected_images)} photo(s)! Click 'Tell Photo Stories' to write about them.")
            else:
                st.info("No photos uploaded for this session yet.")
    
    st.markdown("---")
    
    if st.session_state.image_prompt_mode:
        if st.session_state.selected_images_for_prompt:
            selected_count = len(st.session_state.selected_images_for_prompt)
            st.success(f"📸 **Photo Story Mode**: Writing about {selected_count} selected photo(s)")
            st.info("The AI will ask you specific questions about each photo!")
        else:
            st.info("📸 **Photo Story Mode**: Select photos from the gallery to write about them")
    
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            if events and st.session_state.ghostwriter_mode:
                uk_count = len([e for e in events if e.get('region') == 'UK'])
                global_count = len(events) - uk_count
                st.info(f"📜 **Historical Context Enabled:** Your responses will be enriched with {len(events)} historical events ({uk_count} UK, {global_count} global) from your lifetime.")
        except:
            pass
    
    # Guidance based on session type
    if question_source == "regular":
        if current_session_obj.get("is_custom"):
            # Custom session guidance
            st.info("✨ **Custom Session** - This is a session you created with your own questions. Take your time with each topic.")
        else:
            # Standard session guidance
            st.markdown(f"""
            <div class="chapter-guidance">
            {current_session_obj.get('guidance', '')}
            </div>
            """, unsafe_allow_html=True)
    elif st.session_state.image_prompt_mode:
        st.info("✨ **Photo Story Mode** - The AI will ask you questions about your selected photos. Describe what you see, who's in them, and what memories they bring up!")
    else:
        if st.session_state.current_question_override.startswith("Vignette:"):
            st.info("📝 **Vignette Mode** - Write a short, focused story about a specific moment or memory.")
        else:
            st.info("✨ **Custom Topic** - Write about whatever comes to mind!")
    
    # Progress bar for regular sessions
    if question_source == "regular":
        session_data = st.session_state.responses.get(current_session_id, {})
        topics_answered = len(session_data.get("questions", {}))
        if total_questions > 0:
            topic_progress = topics_answered / total_questions
            st.progress(min(topic_progress, 1.0))
            st.caption(f"📝 Topics explored: {topics_answered}/{total_questions} ({topic_progress*100:.0f}%)")

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
            
            if st.session_state.image_prompt_mode:
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #4CAF50; background-color: #e8f5e9; padding: 1rem; border-radius: 8px; border-left: 4px solid #4CAF50;'>
                📸 <strong>Photo Story Mode:</strong> You've selected {len(st.session_state.selected_images_for_prompt)} photo(s) to write about. I'll ask you questions about each photo to help tell their stories.
                </div>"""
            elif question_source == "custom" and st.session_state.current_question_override.startswith("Vignette:"):
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #9b59b6; background-color: #f4ecf7; padding: 1rem; border-radius: 8px; border-left: 4px solid #9b59b6;'>
                📝 <strong>Vignette Mode:</strong> Write a short, focused story about this specific moment or memory.
                </div>"""
            elif question_source == "custom":
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #ff6b00; background-color: #fff5e6; padding: 1rem; border-radius: 8px; border-left: 4px solid #ff6b00;'>
                ✨ <strong>Custom Topic:</strong> Write about whatever comes to mind!
                </div>"""
            elif current_session_obj.get("is_custom"):
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #3498db; background-color: #e8f4f8; padding: 1rem; border-radius: 8px; border-left: 4px solid #3498db;'>
                🆕 <strong>Custom Session:</strong> This is one of your own questions. Take your time with your response.
                </div>"""
            else:
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #555;'>
                Take your time with this—good biographies are built from thoughtful reflection.
                </div>"""
            
            st.markdown(welcome_msg, unsafe_allow_html=True)
        
        conv_text = f"Let's explore this topic in detail: {current_question_text}\n\n"
        
        if st.session_state.image_prompt_mode:
            conv_text += f"📸 Photo Story Mode: You've selected {len(st.session_state.selected_images_for_prompt)} photo(s) to write about. I'll ask you questions about each photo to help tell their stories."
        elif question_source == "custom" and st.session_state.current_question_override.startswith("Vignette:"):
            conv_text += "📝 Vignette Mode: Write a short, focused story about this specific moment or memory."
        elif question_source == "custom":
            conv_text += "✨ Custom Topic: Write about whatever comes to mind!"
        elif current_session_obj.get("is_custom"):
            conv_text += "🆕 Custom Session: This is one of your own questions. Take your time with your response."
        else:
            conv_text += "Take your time with this—good biographies are built from thoughtful reflection."
        
        conversation.append({"role": "assistant", "content": conv_text})
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation

# Display conversation
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

# Chat input
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
                    
                    # Add context-specific note
                    if st.session_state.image_prompt_mode:
                        ai_response += f"\n\n📸 **Photo Note:** Keep describing your photos! Who, what, where, when, and why?"
                    elif question_source == "custom" and st.session_state.current_question_override.startswith("Vignette:"):
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
    total_words_all_sessions = sum(calculate_author_word_count(s["id"]) for s in all_sessions if s["id"] in st.session_state.responses)
    st.metric("Total Words", f"{total_words_all_sessions}")
with col2:
    completed_sessions = sum(1 for s in all_sessions if len(st.session_state.responses.get(s["id"], {}).get("questions", {})) == len(s.get("questions", s.get("topics", []))))
    st.metric("Completed Sessions", f"{completed_sessions}/{len(all_sessions)}")
with col3:
    total_topics_answered = sum(len(st.session_state.responses.get(s["id"], {}).get("questions", {})) for s in all_sessions)
    total_all_topics = sum(len(s.get("questions", s.get("topics", []))) for s in all_sessions)
    st.metric("Topics Explored", f"{total_topics_answered}/{total_all_topics}")
with col4:
    if st.session_state.logged_in:
        total_images = get_total_user_images(st.session_state.user_id)
        st.metric("Total Photos", f"{total_images}")

# ── Publish & Vault ───────────────────────────────────────────────────────────
st.divider()
st.subheader("📘 Publish & Save Your Biography")
current_user = st.session_state.get('user_id', '')
if current_user and current_user != "":
    export_data = {}
    for session in all_sessions:
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        if session_data.get("questions"):
            export_data[str(session_id)] = {
                "title": session["title"],
                "questions": session_data["questions"]
            }
    image_data = {}
    if st.session_state.logged_in:
        for session in all_sessions:
            session_id = session["id"]
            images = get_session_images(st.session_state.user_id, session_id)
            if images:
                image_data[str(session_id)] = []
                for img in images:
                    image_data[str(session_id)].append({
                        "filename": img["original_filename"],
                        "description": img.get("description", ""),
                        "upload_date": img["upload_date"]
                    })
    if export_data or image_data:
        total_stories = sum(len(session['questions']) for session in export_data.values())
        total_images = sum(len(images) for images in image_data.values())
        enhanced_data = {
            "user": current_user,
            "stories": export_data,
            "images": image_data,
            "export_date": datetime.now().isoformat(),
            "summary": {
                "total_stories": total_stories,
                "total_images": total_images,
                "total_sessions": len(export_data)
            }
        }
        json_data = json.dumps(enhanced_data, indent=2)
        encoded_data = base64.b64encode(json_data.encode()).decode()
        publisher_url = f"https://deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/?data={encoded_data}"
        st.success(f"✅ **{total_stories} stories**" + (f" + {total_images} photos" if total_images > 0 else "") + " ready to publish!")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🖨️ Create Your Book")
            st.markdown("""
            Generate a beautiful, formatted biography including your photos.
            Your enhanced book will include:
            • Professional formatting with images
            • Table of contents
            • All your stories organized
            • Photo captions and references
            • Ready to print or share
            """)
            st.markdown(f'''
            <a href="{publisher_url}" target="_blank">
            <button class="html-link-btn">
            🖨️ Publish Biography
            </button>
            </a>
            ''', unsafe_allow_html=True)
            if total_images > 0:
                st.info(f"📸 {total_images} photos will be included as references in your book")
        with col2:
            st.markdown("#### 🔐 Save to Your Vault")
            st.markdown("""
            **Complete preservation:**
            1. Generate your enhanced biography
            2. Download the formatted PDF
            3. Save all your stories and photos
            4. Store in your secure digital vault
            Your vault preserves everything forever.
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
                st.caption("Includes stories + photo metadata")
    else:
        st.info("📝 **Start writing your story!** Answer some questions first, then come back here.")
else:
    st.info("👤 **Please log in to publish your biography**")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
if st.session_state.user_account:
    profile = st.session_state.user_account['profile']
    account_age = (datetime.now() - datetime.fromisoformat(st.session_state.user_account['created_at'])).days
    total_images = get_total_user_images(st.session_state.user_id) if st.session_state.logged_in else 0
    
    # Get vignette count
    if st.session_state.logged_in:
        vignette_manager = VignetteManager(st.session_state.user_id)
        vignette_count = len(vignette_manager.get_all_vignettes(include_drafts=True))
    else:
        vignette_count = 0
    
    # Get custom session count
    if st.session_state.logged_in:
        session_manager = SessionManager(SESSIONS, st.session_state.user_id)
        custom_session_count = len(session_manager.custom_sessions)
    else:
        custom_session_count = 0
    
    footer_info = f"""
MemLife Timeline • 👤 {profile['first_name']} {profile['last_name']} • 📧 {profile['email']} •
🎂 {profile.get('birthdate', 'Not specified')} • 🔥 {st.session_state.streak_days} day streak •
📷 {total_images} photos • 📝 {vignette_count} vignettes • 🆕 {custom_session_count} custom sessions
"""
    st.caption(footer_info)
else:
    st.caption(f"MemLife Timeline • User: {st.session_state.user_id} • 🔥 {st.session_state.streak_days} day streak")
