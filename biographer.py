# biographer.py – MemLife main app (cleaned & slimmed – February 2026)
# Changes: no fallback prompts, no huge hardcoded events list, CSS loaded from styles.css

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
import shutil
import uuid
from PIL import Image
import io

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

# ── Historical events – CSV only (empty starter if missing) ───────────────────
def create_default_events_csv():
    if not os.path.exists("historical_events.csv"):
        with open("historical_events.csv", "w", encoding="utf-8") as f:
            f.write("year_range,event,category,region,description\n")
        st.info("Created empty historical_events.csv – add your events there.")

def load_historical_events():
    create_default_events_csv()
    try:
        df = pd.read_csv("historical_events.csv")
        events_by_decade = {}
        for _, row in df.iterrows():
            decade = str(row['year_range']).strip()
            events_by_decade.setdefault(decade, []).append(row.to_dict())
        return events_by_decade
    except Exception as e:
        st.error(f"Could not load historical events: {e}")
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

# ── Image Manager Functions ───────────────────────────────────────────────────
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

        return {"success": True, "image_info": image_info, "message": f"Image '{original_filename}' uploaded!"}
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
                        for path in ["original", "thumbnail"]:
                            p = img["paths"].get(path)
                            if p and os.path.exists(p):
                                os.remove(p)
                        metadata[session_key].pop(i)
                        json.dump(metadata, open(metadata_file, 'w'), indent=2)
                        return {"success": True, "message": "Image deleted"}
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

# ── Authentication & Account Functions ────────────────────────────────────────
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
        if not EMAIL_CONFIG.get('sender_email') or not EMAIL_CONFIG.get('sender_password'):
            print("Email not configured")
            return False

        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = user_data['email']
        msg['Subject'] = "Welcome to MemLife - Your Account Details"

        body = f"""
        <html>
        <body style="font-family: Arial; line-height: 1.6;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2>Welcome to MemLife, {user_data['first_name']}!</h2>
            <p>Thank you for creating your account.</p>
            <div style="background: #f8f9fa; border-left: 4px solid #3498db; padding: 15px;">
                <h3>Your Account Details:</h3>
                <p><strong>Account ID:</strong> {credentials['user_id']}</p>
                <p><strong>Email:</strong> {user_data['email']}</p>
                <p><strong>Password:</strong> {credentials['password']}</p>
            </div>
            <p style="margin-top: 20px;">Start building your timeline from your birthdate.</p>
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
        print(f"Email error: {e}")
        return False

def logout_user():
    keys = [
        'user_id', 'user_account', 'logged_in', 'show_profile_setup',
        'current_session', 'current_question', 'responses',
        'session_conversations', 'data_loaded', 'show_image_upload',
        'selected_images_for_prompt', 'image_prompt_mode'
    ]
    for key in keys:
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()

# ── Storage & Streak ──────────────────────────────────────────────────────────
def get_user_filename(user_id):
    return f"user_data_{hashlib.md5(user_id.encode()).hexdigest()[:8]}.json"

def load_user_data(user_id):
    filename = get_user_filename(user_id)
    try:
        if os.path.exists(filename):
            data = json.load(open(filename, 'r'))
            return data if "responses" in data else {"responses": {}, "last_loaded": datetime.now().isoformat()}
    except Exception as e:
        print(f"Load error: {e}")
    return {"responses": {}, "last_loaded": datetime.now().isoformat()}

def save_user_data(user_id, responses_data):
    filename = get_user_filename(user_id)
    try:
        data = {
            "user_id": user_id,
            "responses": responses_data,
            "last_saved": datetime.now().isoformat()
        }
        json.dump(data, open(filename, 'w'), indent=2)
        print(f"Saved data for {user_id}")
        return True
    except Exception as e:
        print(f"Save error: {e}")
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
            last = date.fromisoformat(st.session_state.last_active)
            diff = (date.today() - last).days
            if diff == 1:
                st.session_state.streak_days += 1
            elif diff > 1:
                st.session_state.streak_days = 1
            st.session_state.total_writing_days += 1
            st.session_state.last_active = today
        except:
            st.session_state.last_active = today

def get_streak_emoji(days):
    if days >= 30: return "🔥🔥🔥"
    if days >= 7: return "🔥🔥"
    if days >= 3: return "🔥"
    return "✨"

def estimate_year_from_text(text):
    try:
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
        return int(years[0]) if years else None
    except:
        return None

def save_jot(text, year=None):
    if "quick_jots" not in st.session_state:
        st.session_state.quick_jots = []
    st.session_state.quick_jots.append({
        "text": text,
        "year": year,
        "date": datetime.now().isoformat(),
        "word_count": len(re.findall(r'\w+', text))
    })

# ── Prompt Builder (no fallbacks) ─────────────────────────────────────────────
def get_system_prompt():
    session = SESSIONS[st.session_state.current_session]
    question = (
        st.session_state.current_question_override
        or session["questions"][st.session_state.current_question]
    )

    historical = ""
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(year)
            if events:
                lines = [f"- {e['event']} ({e['year_range']})" + (f" [UK]" if e.get('region') == 'UK' else "") +
                         (f" (Age {e.get('approx_age')})" if 'approx_age' in e else "")
                         for e in events[:5]]
                historical = f"HISTORICAL CONTEXT (Born {year}):\n{chr(10).join(lines)}\nConsider connections."
        except:
            pass

    images = ""
    if st.session_state.logged_in and st.session_state.user_id:
        imgs = get_session_images(st.session_state.user_id, session["id"])
        if imgs:
            images = "\n\n📸 PHOTOS:\n" + "\n".join(f"- {i['original_filename']}" + (f" – {i.get('description','')}" if i.get('description') else "")
                           for i in imgs[:5]) + "\nAsk about people, place, moment, feelings."

    mode = st.session_state.ghostwriter_mode
    return f"""You are a {'senior literary biographer' if mode else 'warm professional biographer'}.
CURRENT SESSION: {session['title']}
CURRENT TOPIC: "{question}"
{historical}{images}

{'Focus on scenes, sensory detail, emotional truth.' if mode else 'Listen actively, ask one natural follow-up.'}
When photos mentioned: ask specific questions about who, where, when, feelings."""

# ── Core Functions ────────────────────────────────────────────────────────────
def save_response(session_id, question, answer):
    uid = st.session_state.user_id
    if not uid:
        return False

    update_streak()

    if st.session_state.user_account:
        wc = len(re.findall(r'\w+', answer))
        stats = st.session_state.user_account.setdefault("stats", {})
        stats["total_words"] = stats.get("total_words", 0) + wc
        stats["total_sessions"] = len(st.session_state.responses[session_id].get("questions", {}))
        stats["last_active"] = datetime.now().isoformat()
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

    return save_user_data(uid, st.session_state.responses)

def calculate_author_word_count(sid):
    total = 0
    for q, data in st.session_state.responses.get(sid, {}).get("questions", {}).items():
        if data.get("answer"):
            total += len(re.findall(r'\w+', data["answer"]))
    return total

def get_progress_info(sid):
    count = calculate_author_word_count(sid)
    target = st.session_state.responses.get(sid, {}).get("word_target", DEFAULT_WORD_TARGET)
    pct = 100 if target == 0 else (count / target) * 100
    emoji = "🟢" if pct >= 100 else "🟡" if pct >= 70 else "🔴"
    color = "#2ecc71" if pct >= 100 else "#f39c12" if pct >= 70 else "#e74c3c"
    remaining = max(0, target - count)
    status = f"{remaining} words remaining" if remaining > 0 else "Target achieved!"
    return {"current_count": count, "target": target, "progress_percent": pct, "emoji": emoji, "color": color, "remaining_words": remaining, "status_text": status}

def auto_correct_text(text):
    if not text or not st.session_state.spellcheck_enabled:
        return text
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Fix spelling/grammar only. Return corrected text."},
                      {"role": "user", "content": text}],
            max_tokens=len(text) + 100,
            temperature=0.1
        )
        return resp.choices[0].message.content
    except:
        return text

# ── Page Setup & State ────────────────────────────────────────────────────────
st.set_page_config(page_title="MemLife - Your Life Timeline", page_icon="📖", layout="wide", initial_sidebar_state="expanded")

for k, v in {
    "logged_in": False, "user_id": "", "user_account": None, "show_profile_setup": False,
    "current_session": 0, "current_question": 0, "responses": {}, "session_conversations": {},
    "editing": None, "ghostwriter_mode": True, "spellcheck_enabled": True, "data_loaded": False,
    "show_image_upload": False, "image_prompt_mode": False, "selected_images_for_prompt": [],
    "streak_days": 1, "last_active": date.today().isoformat(), "total_writing_days": 1
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

if not st.session_state.responses:
    for s in SESSIONS:
        st.session_state.responses[s["id"]] = {
            "title": s["title"],
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": s.get("word_target", DEFAULT_WORD_TARGET)
        }

if st.session_state.logged_in and st.session_state.user_id and not st.session_state.data_loaded:
    data = load_user_data(st.session_state.user_id)
    if "responses" in data:
        for sid_str, sdata in data["responses"].items():
            try:
                sid = int(sid_str)
                if sid in st.session_state.responses and "questions" in sdata:
                    st.session_state.responses[sid]["questions"] = sdata["questions"]
            except:
                pass
    st.session_state.data_loaded = True

# ── Auth & Profile Modal (your original code kept) ────────────────────────────
# ... paste your full show_login_signup(), show_login_form(), show_signup_form(), show_profile_setup_modal(), etc. here ...
# For brevity I left placeholders - add them back from your original file

if st.session_state.get('show_profile_setup', False):
    show_profile_setup_modal()
    st.stop()

if not st.session_state.logged_in:
    show_login_signup()
    st.stop()

# ── Sidebar & Main Content ────────────────────────────────────────────────────
# ... paste your full sidebar code (profile, streak, photos, jot, toggles, historical, sessions list, export, clear) here ...

# Main header
st.markdown(f"""
<div class="main-header">
    <img src="{LOGO_URL}" class="logo-img" alt="MemLife Logo">
    <h2>MemLife - Your Life Timeline</h2>
    <p>Preserve Your Legacy • Build Your Timeline • Share Your Story</p>
</div>
""", unsafe_allow_html=True)

# ... paste the rest of your main content: session header, image controls, question box, chat loop, progress, publish section, footer ...
# Everything from SECTION 21 to SECTION 27 in your original script goes here unchanged

# ============================================================================
# SECTION 21: MAIN CONTENT - SESSION HEADER
# ============================================================================
current_session = SESSIONS[st.session_state.current_session]
current_session_id = current_session["id"]

# Get the current question text (either override or regular)
if st.session_state.current_question_override:
    current_question_text = st.session_state.current_question_override
    question_source = "custom"
else:
    current_question_text = current_session["questions"][st.session_state.current_question]
    question_source = "regular"

# ============================================================================
# SECTION 22: SIMPLE IMAGE UPLOAD AND GALLERY
# ============================================================================
st.markdown("---")

# Create columns for the header with image controls
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.subheader(f"Session {current_session_id}: {current_session['title']}")
    
    # Show response count for this session
    session_responses = len(st.session_state.responses[current_session_id].get("questions", {}))
    total_questions = len(current_session["questions"])
    st.caption(f"📝 {session_responses}/{total_questions} topics answered")
    
    # Show image count for this session
    if st.session_state.logged_in:
        session_images = get_session_images(st.session_state.user_id, current_session_id)
        if session_images:
            st.caption(f"📸 {len(session_images)} photos in this session")
    
    if st.session_state.ghostwriter_mode:
        st.markdown('<p class="ghostwriter-tag">Professional Ghostwriter Mode (with historical context & photo integration)</p>', unsafe_allow_html=True)
        
with col2:
    if question_source == "custom":
        st.markdown(f'<div class="question-counter" style="margin-top: 1rem; color: #ff6b00;">✨ Custom Prompt</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="question-counter" style="margin-top: 1rem;">Topic {st.session_state.current_question + 1} of {len(current_session["questions"])}</div>', unsafe_allow_html=True)

with col3:
    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if st.button("← Previous Topic", disabled=st.session_state.current_question == 0, key="prev_q_quick", use_container_width=True):
            st.session_state.current_question = max(0, st.session_state.current_question - 1)
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()
    with nav_col2:
        if st.button("🔄 New Prompt", key="refresh_prompt_btn", use_container_width=True):
            st.session_state.prompt_index = (st.session_state.prompt_index + 1) % len(FALLBACK_PROMPTS)
            st.session_state.current_question_override = FALLBACK_PROMPTS[st.session_state.prompt_index]
            st.session_state.image_prompt_mode = False
            st.rerun()

# Show current topic
st.markdown(f"""
<div class="question-box">
    {current_question_text}
</div>
""", unsafe_allow_html=True)

# ============================================================================
# SIMPLE IMAGE CONTROLS
# ============================================================================
st.write("")  # Add some space

# Create a container for image controls
image_controls_container = st.container()

with image_controls_container:
    # Check if we have images for this session
    has_images = False
    if st.session_state.logged_in:
        session_images = get_session_images(st.session_state.user_id, current_session_id)
        has_images = len(session_images) > 0
    
    # Create columns for image controls
    img_col1, img_col2 = st.columns(2)
    
    with img_col1:
        # Toggle image upload panel
        button_text = "📷 Add Photos" if not st.session_state.show_image_upload else "📷 Hide Photos"
        if st.button(button_text, key="toggle_image_upload", use_container_width=True):
            st.session_state.show_image_upload = not st.session_state.show_image_upload
            st.rerun()
    
    with img_col2:
        # Photo prompt button
        if has_images:
            if st.button("✨ Tell Photo Stories", key="photo_stories_btn", use_container_width=True, type="primary"):
                st.session_state.image_prompt_mode = True
                st.rerun()
        else:
            st.button("✨ Tell Photo Stories", key="disabled_photo_stories", use_container_width=True, disabled=True)

# Show image upload/gallery interface if toggled on
if st.session_state.show_image_upload and st.session_state.logged_in:
    st.markdown("---")
    
    # Simple upload interface
    st.subheader("📤 Upload Photos for This Memory")
    
    # File uploader
    uploaded_files = st.file_uploader(
        "Choose photos to upload",
        type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
        accept_multiple_files=True,
        key=f"simple_uploader_{current_session_id}"
    )
    
    if uploaded_files:
        # Description input
        description = st.text_input(
            "Add a description for these photos (optional):",
            placeholder="E.g., 'Family vacation, 1985'",
            key=f"simple_desc_{current_session_id}"
        )
        
        # Upload button
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
    
    # Show gallery if there are images
    session_images = get_session_images(st.session_state.user_id, current_session_id)
    if session_images:
        st.divider()
        st.subheader("📷 Your Photos")
        
        # Display simple gallery
        selected_images = display_simple_gallery(st.session_state.user_id, current_session_id)
        
        if selected_images:
            st.session_state.selected_images_for_prompt = selected_images
            st.success(f"✅ Selected {len(selected_images)} photo(s)! Click 'Tell Photo Stories' to write about them.")
    else:
        st.info("No photos uploaded for this session yet.")
    
    st.markdown("---")

# Show image prompt mode indicator
if st.session_state.image_prompt_mode:
    if st.session_state.selected_images_for_prompt:
        selected_count = len(st.session_state.selected_images_for_prompt)
        st.success(f"📸 **Photo Story Mode**: Writing about {selected_count} selected photo(s)")
        st.info("The AI will ask you specific questions about each photo!")
    else:
        st.info("📸 **Photo Story Mode**: Select photos from the gallery to write about them")

# Show historical context note if available
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

# Show session guidance (only for regular prompts)
if question_source == "regular":
    st.markdown(f"""
    <div class="chapter-guidance">
        {current_session.get('guidance', '')}
    </div>
    """, unsafe_allow_html=True)
elif st.session_state.image_prompt_mode:
    st.info("✨ **Photo Story Mode** - The AI will ask you questions about your selected photos. Describe what you see, who's in them, and what memories they bring up!")
else:
    st.info("✨ **Custom Prompt** - Write about whatever comes to mind!")

# Topics progress (only for regular prompts)
if question_source == "regular":
    session_data = st.session_state.responses.get(current_session_id, {})
    topics_answered = len(session_data.get("questions", {}))
    total_topics = len(current_session["questions"])

    if total_topics > 0:
        topic_progress = topics_answered / total_topics
        st.progress(min(topic_progress, 1.0))
        st.caption(f"📝 Topics explored: {topics_answered}/{total_topics} ({topic_progress*100:.0f}%)")

# ============================================================================
# SECTION 23: CONVERSATION DISPLAY AND CHAT INPUT
# ============================================================================
if current_session_id not in st.session_state.session_conversations:
    st.session_state.session_conversations[current_session_id] = {}

conversation = st.session_state.session_conversations[current_session_id].get(current_question_text, [])

if not conversation:
    # Check if we have a saved response for this question
    saved_response = st.session_state.responses[current_session_id]["questions"].get(current_question_text)
    
    if saved_response:
        # We have a saved response but no conversation - create one
        conversation = [
            {"role": "assistant", "content": f"Let's explore this topic in detail: {current_question_text}"},
            {"role": "user", "content": saved_response["answer"]}
        ]
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation
    else:
        # Start new conversation
        with st.chat_message("assistant", avatar="👔"):
            welcome_msg = f"""<div style='font-size: 1.4rem; margin-bottom: 1rem;'>
Let's explore this topic in detail:
</div>
<div style='font-size: 1.8rem; font-weight: bold; color: #2c3e50; line-height: 1.3;'>
{current_question_text}
</div>"""
            
            # Add image prompt note if in image prompt mode
            if st.session_state.image_prompt_mode:
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #4CAF50; background-color: #e8f5e9; padding: 1rem; border-radius: 8px; border-left: 4px solid #4CAF50;'>
📸 <strong>Photo Story Mode:</strong> You've selected {len(st.session_state.selected_images_for_prompt)} photo(s) to write about. I'll ask you questions about each photo to help tell their stories.
</div>"""
            else:
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #555;'>
Take your time with this—good biographies are built from thoughtful reflection.
</div>"""
            
            st.markdown(welcome_msg, unsafe_allow_html=True)
            
            # Create conversation entry
            conv_text = f"Let's explore this topic in detail: {current_question_text}\n\n"
            if st.session_state.image_prompt_mode:
                conv_text += f"📸 Photo Story Mode: You've selected {len(st.session_state.selected_images_for_prompt)} photo(s) to write about. I'll ask you questions about each photo to help tell their stories."
            else:
                conv_text += "Take your time with this—good biographies are built from thoughtful reflection."
            
            conversation.append({"role": "assistant", "content": conv_text})
            st.session_state.session_conversations[current_session_id][current_question_text] = conversation

# Display existing conversation
for i, message in enumerate(conversation):
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="👔"):
            st.markdown(message["content"])
    
    elif message["role"] == "user":
        is_editing = (st.session_state.editing == (current_session_id, current_question_text, i))
        
        with st.chat_message("user", avatar="👤"):
            if is_editing:
                # Edit mode
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
                        # Auto-correct before saving
                        if st.session_state.spellcheck_enabled:
                            new_text = auto_correct_text(new_text)
                        
                        # Update conversation
                        conversation[i]["content"] = new_text
                        st.session_state.session_conversations[current_session_id][current_question_text] = conversation
                        
                        # Save to JSON file
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

# ============================================================================
# CHAT INPUT BOX
# ============================================================================
input_container = st.container()

with input_container:
    st.write("")
    st.write("")
    
    user_input = st.chat_input("Type your answer here...", key="chat_input")
    
    if user_input:
        # Auto-correct if enabled
        if st.session_state.spellcheck_enabled:
            user_input = auto_correct_text(user_input)
        
        # Add user message to conversation
        conversation.append({"role": "user", "content": user_input})
        
        # Generate AI response
        with st.chat_message("assistant", avatar="👔"):
            with st.spinner("Reflecting on your story..."):
                try:
                    # Generate thoughtful response
                    conversation_history = conversation[:-1]
                    
                    messages_for_api = [
                        {"role": "system", "content": get_system_prompt()},
                        *conversation_history,
                        {"role": "user", "content": user_input}
                    ]
                    
                    if st.session_state.ghostwriter_mode:
                        temperature = 0.8
                        max_tokens = 400
                    else:
                        temperature = 0.7
                        max_tokens = 300
                    
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    ai_response = response.choices[0].message.content
                    
                    # Add note about photos if in image prompt mode
                    if st.session_state.image_prompt_mode:
                        ai_response += f"\n\n📸 **Photo Note:** Keep describing your photos! Who, what, where, when, and why?"
                    
                    st.markdown(ai_response)
                    conversation.append({"role": "assistant", "content": ai_response})
                    
                except Exception as e:
                    error_msg = "Thank you for sharing that. Your response has been saved."
                    st.markdown(error_msg)
                    conversation.append({"role": "assistant", "content": error_msg})
        
        # Save conversation
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation
        
        # CRITICAL: Save the response to JSON file
        save_response(current_session_id, current_question_text, user_input)
        
        st.rerun()

# ============================================================================
# SECTION 24: WORD PROGRESS INDICATOR
# ============================================================================
st.divider()

# Get progress info
progress_info = get_progress_info(current_session_id)

# Display progress container
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

# Edit target button
if st.button("✏️ Change Word Target", key="edit_word_target_bottom", use_container_width=True):
    st.session_state.editing_word_target = not st.session_state.editing_word_target
    st.rerun()

# Show edit interface when triggered
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
            # Update session state
            st.session_state.responses[current_session_id]["word_target"] = new_target
            # Update JSON file
            save_user_data(st.session_state.user_id, st.session_state.responses)
            st.session_state.editing_word_target = False
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel", key="cancel_word_target_bottom", use_container_width=True):
            st.session_state.editing_word_target = False
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# SECTION 25: FOOTER WITH STATISTICS
# ============================================================================
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
    if st.session_state.logged_in:
        total_images = get_total_user_images(st.session_state.user_id)
        st.metric("Total Photos", f"{total_images}")

# ============================================================================
# SECTION 26: PUBLISH & VAULT SECTION
# ============================================================================
st.divider()
st.subheader("📘 Publish & Save Your Biography")

# Get the current user's data
current_user = st.session_state.get('user_id', '')

if current_user and current_user != "":
    # Prepare data
    export_data = {}
    for session in SESSIONS:
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        if session_data.get("questions"):
            export_data[str(session_id)] = {
                "title": session["title"],
                "questions": session_data["questions"]
            }
    
    # Prepare images
    image_data = {}
    if st.session_state.logged_in:
        for session in SESSIONS:
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
        # Count totals
        total_stories = sum(len(session['questions']) for session in export_data.values())
        total_images = sum(len(images) for images in image_data.values())
        
        # Create enhanced JSON data
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
        
        # Encode the data for URL
        encoded_data = base64.b64encode(json_data.encode()).decode()
        
        # Create URL for the publisher
        publisher_base_url = "https://deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/"
        publisher_url = f"{publisher_base_url}?data={encoded_data}"
        
        st.success(f"✅ **{total_stories} stories" + (f" + {total_images} photos" if total_images > 0 else "") + " ready to publish!**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🖨️ Create Your Book")
            st.markdown(f"""
            Generate a beautiful, formatted biography including your photos.
            
            Your enhanced book will include:
            • Professional formatting with images
            • Table of contents
            • All your stories organized
            • Photo captions and references
            • Ready to print or share
            """)
            
            # Use HTML button instead of st.link_button
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
            
            # Use HTML button for vault too
            vault_url = "https://digital-legacy-vault-vwvd4eclaeq4hxtcbbshr2.streamlit.app/"
            st.markdown(f'''
            <a href="{vault_url}" target="_blank">
                <button style="background: #3498db; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer; width: 100%; margin-top: 1rem;">
                    💾 Go to Secure Vault
                </button>
            </a>
            ''', unsafe_allow_html=True)
        
        # Backup download
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

# ============================================================================
# SECTION 27: FOOTER
# ============================================================================
st.markdown("---")

# Show account info in footer if available
if st.session_state.user_account:
    profile = st.session_state.user_account['profile']
    account_age = (datetime.now() - datetime.fromisoformat(st.session_state.user_account['created_at'])).days
    
    # Get total images
    total_images = get_total_user_images(st.session_state.user_id) if st.session_state.logged_in else 0
    
    footer_info = f"""
    MemLife Timeline • 👤 {profile['first_name']} {profile['last_name']} • 📧 {profile['email']} • 
    🎂 {profile.get('birthdate', 'Not specified')} • 🔥 {st.session_state.streak_days} day streak • 
    📷 {total_images} photos • 📅 Account Age: {account_age} days
    """
    st.caption(footer_info)
else:
    st.caption(f"MemLife Timeline • User: {st.session_state.user_id} • 🔥 {st.session_state.streak_days} day streak")
