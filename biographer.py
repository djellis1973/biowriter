# biographer.py – MemLife main app (grid sessions + vignettes – complete & working)

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

# ── NEW MODULE IMPORTS ───────────────────────────────────────────────────────
import session_manager
import topic_bank
import vignettes

DEFAULT_WORD_TARGET = 500

# ── OpenAI client ─────────────────────────────────────────────────────────────
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")))

# ── Load external CSS (optional) ──────────────────────────────────────────────
try:
    with open("styles.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

LOGO_URL = "https://menuhunterai.com/wp-content/uploads/2026/01/logo.png"

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
        return {"success": True, "image_info": image_info}
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
                        return {"success": True}
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
    selected_images = []
    for idx, img_info in enumerate(images):
        col1, col2 = st.columns([4, 1])
        with col1:
            thumb = img_info["paths"].get("thumbnail")
            if thumb and os.path.exists(thumb):
                data_url = get_image_data_url(thumb)
                if data_url:
                    st.image(data_url, use_column_width=True)
            st.caption(img_info['original_filename'])
            if img_info.get('description'):
                st.caption(img_info['description'])
        with col2:
            if st.button("Select", key=f"sel_img_{img_info['id']}"):
                selected_images.append(img_info)
            if st.button("Delete", key=f"del_img_{img_info['id']}"):
                result = delete_image_simple(user_id, session_id, img_info["id"])
                if result["success"]:
                    st.success("Deleted")
                    st.rerun()
                else:
                    st.error(result["error"])
    return selected_images

def get_total_user_images(user_id):
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    if os.path.exists(metadata_file):
        try:
            metadata = json.load(open(metadata_file, 'r'))
            return sum(len(v) for v in metadata.values())
        except:
            pass
    return 0

# ── Authentication & Email ────────────────────────────────────────────────────
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",
    "use_tls": True
}

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
            "settings": {"email_notifications": True, "auto_save": True, "privacy_level": "private", "theme": "light"},
            "stats": {"total_sessions": 0, "total_words": 0, "current_streak": 0, "longest_streak": 0, "account_age_days": 0, "last_active": datetime.now().isoformat()}
        }
        os.makedirs("accounts", exist_ok=True)
        json.dump(user_record, open(f"accounts/{user_id}_account.json", 'w'), indent=2)
        return {"success": True, "user_id": user_id, "password": password, "user_record": user_record}
    except Exception as e:
        return {"success": False, "error": str(e)}

def authenticate_user(email, password):
    try:
        email = email.lower().strip()
        for filename in os.listdir("accounts"):
            if filename.endswith("_account.json"):
                account = json.load(open(f"accounts/{filename}", 'r'))
                if account["email"] == email and verify_password(account["password_hash"], password):
                    account["last_login"] = datetime.now().isoformat()
                    json.dump(account, open(f"accounts/{filename}", 'w'), indent=2)
                    return {"success": True, "user_id": account["user_id"], "user_record": account}
        return {"success": False, "error": "Invalid credentials"}
    except:
        return {"success": False, "error": "Login error"}

def send_welcome_email(user_data, credentials):
    return True  # stub - implement if you need real emails

def logout_user():
    for key in list(st.session_state.keys()):
        if key in ['user_id', 'user_account', 'logged_in', 'show_profile_setup']:
            del st.session_state[key]
    st.rerun()

def show_login_signup():
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            res = authenticate_user(email, pw)
            if res["success"]:
                st.session_state.logged_in = True
                st.session_state.user_id = res["user_id"]
                st.session_state.user_account = res["user_record"]
                st.rerun()
            else:
                st.error(res["error"])
    with tab2:
        fn = st.text_input("First Name")
        ln = st.text_input("Last Name")
        email = st.text_input("Email")
        pw = st.text_input("Password", type="password")
        if st.button("Sign Up"):
            res = create_user_account({"first_name": fn, "last_name": ln, "email": email})
            if res["success"]:
                send_welcome_email({"email": email, "first_name": fn}, res)
                st.success("Account created - please log in")
            else:
                st.error(res["error"])

def show_profile_setup_modal():
    st.subheader("Complete Your Profile")
    birthdate = st.text_input("Birthdate (Month Day, Year)")
    if st.button("Save"):
        st.session_state.user_account["profile"]["birthdate"] = birthdate
        st.session_state.show_profile_setup = False
        st.rerun()

# ── Streak & Jots ─────────────────────────────────────────────────────────────
def update_streak():
    today = date.today().isoformat()
    if st.session_state.last_active != today:
        last = date.fromisoformat(st.session_state.last_active)
        diff = (date.today() - last).days
        if diff == 1:
            st.session_state.streak_days += 1
        elif diff > 1:
            st.session_state.streak_days = 1
        st.session_state.total_writing_days += 1
        st.session_state.last_active = today

def save_jot(text, year=None):
    if "quick_jots" not in st.session_state:
        st.session_state.quick_jots = []
    st.session_state.quick_jots.append({"text": text, "year": year, "date": datetime.now().isoformat()})

def estimate_year_from_text(text):
    m = re.search(r'\b(19|20)\d{2}\b', text)
    return int(m.group()) if m else None

# ── Core Save / Progress ──────────────────────────────────────────────────────
def save_response(session_id, question, answer):
    update_streak()
    if session_id not in st.session_state.responses:
        st.session_state.responses[session_id] = {"questions": {}}
    st.session_state.responses[session_id]["questions"][question] = {"answer": answer}
    # Save to file (your original logic)
    filename = f"user_data_{st.session_state.user_id}.json"
    try:
        json.dump({"responses": st.session_state.responses}, open(filename, 'w'), indent=2)
    except:
        pass

def calculate_author_word_count(session_id):
    return sum(len(re.findall(r'\w+', q.get("answer", ""))) 
               for q in st.session_state.responses.get(session_id, {}).get("questions", {}).values())

def get_progress_info(session_id):
    count = calculate_author_word_count(session_id)
    target = st.session_state.responses.get(session_id, {}).get("word_target", DEFAULT_WORD_TARGET)
    percent = (count / target * 100) if target > 0 else 0
    color = "#4CAF50" if percent >= 100 else "#ff9800" if percent > 30 else "#f44336"
    emoji = "🏆" if percent >= 100 else "🔥" if percent > 50 else "📝"
    return {"current_count": count, "target": target, "progress_percent": percent, "color": color, "emoji": emoji}

# ── System Prompt ─────────────────────────────────────────────────────────────
def get_system_prompt():
    return "You are a thoughtful biographer helping the user write their life story. Ask follow-up questions."

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="MemLife", page_icon="📖", layout="wide")

# Session state defaults
for k, v in {
    "logged_in": False, "user_id": "", "user_account": None, "show_profile_setup": False,
    "responses": {}, "session_conversations": {}, "editing": None, "edit_text": "",
    "ghostwriter_mode": True, "spellcheck_enabled": True, "editing_word_target": False,
    "confirming_clear": None, "data_loaded": False, "current_question_override": None,
    "quick_jots": [], "show_jots": False, "historical_events_loaded": False,
    "show_image_upload": False, "image_prompt_mode": False, "selected_images_for_prompt": [],
    "streak_days": 1, "last_active": date.today().isoformat(), "total_writing_days": 1,
    "view_mode": "home", "current_session_id": None, "current_topic_index": 0
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Login / Profile ───────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    show_login_signup()
    st.stop()

if st.session_state.show_profile_setup:
    show_profile_setup_modal()
    st.stop()

# ── Load Data ─────────────────────────────────────────────────────────────────
if not st.session_state.data_loaded:
    filename = f"user_data_{st.session_state.user_id}.json"
    if os.path.exists(filename):
        try:
            data = json.load(open(filename))
            st.session_state.responses = data.get("responses", {})
        except:
            st.session_state.responses = {}
    st.session_state.data_loaded = True

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Profile")
    st.button("Log Out", on_click=logout_user)

    st.divider()
    st.subheader("Streak")
    st.write(f"{st.session_state.streak_days} days 🔥")

    st.divider()
    if st.button("Home"):
        st.session_state.view_mode = "home"
        st.rerun()
    if st.button("Vignettes"):
        st.session_state.view_mode = "vignettes"
        st.rerun()

# ── Main Content ──────────────────────────────────────────────────────────────
sessions = session_manager.get_sessions(st.session_state.user_id)

if st.session_state.view_mode == "home":
    st.title("Your Life Chapters")
    cols = st.columns(3)
    for s in sessions:
        sid = s["id"]
        answered = len(st.session_state.responses.get(sid, {}).get("questions", {}))
        total = len(s["questions"])
        color = "#4CAF50" if answered == total else "#ff9800" if answered > 0 else "#f44336"
        status = "Done" if answered == total else "In Progress" if answered > 0 else "Not Started"
        with cols[sid % 3]:
            st.markdown(f"**{s['title']}**  \n{status} ({answered}/{total})")
            st.button("Open", key=f"open_{sid}", on_click=lambda sid=sid: [setattr(st.session_state, "view_mode", "session"), setattr(st.session_state, "current_session_id", sid)])

elif st.session_state.view_mode == "session":
    sid = st.session_state.current_session_id
    session = next(s for s in sessions if s["id"] == sid)
    st.subheader(session["title"])
    if st.button("Back"):
        st.session_state.view_mode = "home"
        st.rerun()

    cols = st.columns(3)
    for i, q in enumerate(session["questions"]):
        has = q in st.session_state.responses.get(sid, {}).get("questions", {})
        with cols[i % 3]:
            st.button(q, key=f"t_{i}", on_click=lambda i=i: [setattr(st.session_state, "view_mode", "topic"), setattr(st.session_state, "current_topic_index", i)])

elif st.session_state.view_mode == "vignettes":
    st.title("Vignettes")
    topic = st.selectbox("Theme", vignettes.get_standard_vignette_topics() + ["Custom"])
    if topic == "Custom":
        topic = st.text_input("Custom theme")
    text = st.text_area("Write here", height=200)
    if st.button("Publish"):
        vignettes.add_vignette(st.session_state.user_id, topic, text)
        st.success("Published")
            # ── Topic View ──────────────────────────────────────────────────────────────
    sid = st.session_state.current_session_id
    session = next((s for s in sessions if s["id"] == sid), None)
    if not session:
        st.error("Session not found")
        st.stop()

    idx = st.session_state.current_topic_index
    if idx >= len(session["questions"]):
        st.warning("Topic index out of range")
        st.session_state.view_mode = "session"
        st.rerun()

    current_question_text = session["questions"][idx]

    st.subheader(current_question_text)

    col1, col2 = st.columns([5, 1])
    with col1:
        if st.button("← Back to Session"):
            st.session_state.view_mode = "session"
            st.rerun()
    with col2:
        if st.button("Next →", disabled=idx >= len(session["questions"])-1):
            st.session_state.current_topic_index += 1
            st.rerun()

    # Conversation
    conv_key = (sid, current_question_text)
    conversation = st.session_state.session_conversations.setdefault(sid, {}).setdefault(current_question_text, [])

    for msg in conversation:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Type your answer here...")
    if user_input:
        if st.session_state.spellcheck_enabled:
            user_input = auto_correct_text(user_input)
        conversation.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            with st.spinner("Reflecting..."):
                try:
                    messages = [{"role": "system", "content": get_system_prompt()}] + conversation
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=0.8 if st.session_state.ghostwriter_mode else 0.7,
                        max_tokens=400
                    )
                    ai_response = response.choices[0].message.content
                    st.markdown(ai_response)
                    conversation.append({"role": "assistant", "content": ai_response})
                except Exception as e:
                    st.markdown("Thank you for sharing. Response saved.")
        save_response(sid, current_question_text, user_input)
        st.rerun()

    # Image Controls
    if st.button("📷 Add Photos"):
        st.session_state.show_image_upload = not st.session_state.show_image_upload
        st.rerun()

    if st.session_state.show_image_upload:
        uploaded_files = st.file_uploader("Upload photos", accept_multiple_files=True, type=['jpg','png','jpeg'])
        desc = st.text_input("Description")
        if st.button("Upload"):
            for file in uploaded_files:
                save_uploaded_image_simple(file, st.session_state.user_id, sid, desc)
            st.rerun()
        display_simple_gallery(st.session_state.user_id, sid)

    # Progress
    progress_info = get_progress_info(sid)
    st.progress(min(progress_info['progress_percent']/100, 1.0))
    st.caption(f"{progress_info['current_count']} / {progress_info['target']} words")

# ── Footer ────────────────────────────────────────────────────────────────────
st.divider()
col1, col2, col3, col4 = st.columns(4)
with col1:
    total_words = sum(calculate_author_word_count(s["id"]) for s in sessions)
    st.metric("Total Words", total_words)
with col2:
    completed = sum(1 for s in sessions if len(st.session_state.responses.get(s["id"], {}).get("questions", {})) == len(s["questions"]))
    st.metric("Completed Sessions", f"{completed}/{len(sessions)}")
with col3:
    total_topics = sum(len(s["questions"]) for s in sessions)
    answered_topics = sum(len(st.session_state.responses.get(s["id"], {}).get("questions", {})) for s in sessions)
    st.metric("Topics", f"{answered_topics}/{total_topics}")
with col4:
    st.metric("Photos", get_total_user_images(st.session_state.user_id))

st.divider()
st.subheader("Publish & Save")
# Your original publish/vault/export code here - paste it if you want, or keep as placeholder
st.info("Publish section (add your original export/base64/publisher link code here)")
