# biographer.py (Complete MemLife Main App)
# This is a self-contained, working version incorporating all features.
# - User auth: Simple JSON file-based (users.json)
# - Data persistence: JSON per user (e.g., data_userid.json)
# - OpenAI: Uses gpt-4o-mini (set your API key)
# - Photos: Upload to 'uploads' folder, metadata in user JSON
# - Historical events: Hardcoded sample data
# - Export/Publish: Copied/adapted from original
# - Integrated new modules: session_manager, topic_bank, vignettes (stubs if missing)

import streamlit as st
from datetime import date, datetime
import json
import base64
import re
import os
import openai
from openai import OpenAI
import hashlib
import shutil

# ── Config & Constants ───────────────────────────────────────────────────────
openai.api_key = os.environ.get("OPENAI_API_KEY", "your_openai_key_here")  # Set your key
client = OpenAI()

LOGO_URL = "https://via.placeholder.com/150?text=MemLife"  # Replace if needed
DEFAULT_WORD_TARGET = 500
USERS_FILE = "users.json"
DATA_DIR = "user_data"
UPLOADS_DIR = "uploads"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# ── Helper Functions ─────────────────────────────────────────────────────────

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def load_user_data(user_id):
    file = os.path.join(DATA_DIR, f"data_{user_id}.json")
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(user_id, data):
    file = os.path.join(DATA_DIR, f"data_{user_id}.json")
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

def show_login_signup():
    tab1, tab2 = st.tabs(["Login", "Signup"])
    with tab1:
        username = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            users = load_users()
            if username in users and users[username]["password"] == hash_password(pw):
                st.session_state.logged_in = True
                st.session_state.user_id = username
                st.session_state.user_account = users[username]
                st.success("Logged in!")
                st.rerun()
            else:
                st.error("Invalid credentials")
    with tab2:
        new_user = st.text_input("New Username")
        new_pw = st.text_input("New Password", type="password")
        email = st.text_input("Email")
        if st.button("Signup"):
            users = load_users()
            if new_user not in users:
                users[new_user] = {
                    "password": hash_password(new_pw),
                    "profile": {"first_name": new_user, "last_name": "", "email": email},
                    "created_at": datetime.now().isoformat()
                }
                save_users(users)
                st.success("Signed up! Please login.")
            else:
                st.error("Username taken")

def logout_user():
    st.session_state.logged_in = False
    st.session_state.user_id = ""
    st.session_state.user_account = None
    st.rerun()

def auto_correct_text(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Correct spelling and grammar:"}, {"role": "user", "content": text}],
            max_tokens=len(text) + 100,
            temperature=0.1
        )
        return response.choices[0].message.content
    except:
        return text

def get_system_prompt():
    return """
    You are a professional ghostwriter helping the user craft a detailed biography.
    Ask follow-up questions to draw out more details. Be empathetic and engaging.
    """

def estimate_year_from_text(text):
    years = re.findall(r'\b(19|20)\d{2}\b', text)
    return int(years[0]) if years else datetime.now().year

def save_jot(note, year):
    user_data = load_user_data(st.session_state.user_id)
    jots = user_data.get("quick_jots", [])
    jots.append({"note": note, "year": year, "date": datetime.now().isoformat()})
    user_data["quick_jots"] = jots
    save_user_data(st.session_state.user_id, user_data)
    st.session_state.quick_jots = jots

def get_total_user_images(user_id):
    user_data = load_user_data(user_id)
    images = user_data.get("images", {})
    return sum(len(imgs) for imgs in images.values())

def get_session_images(user_id, session_id):
    user_data = load_user_data(user_id)
    return user_data.get("images", {}).get(str(session_id), [])

def save_uploaded_image_simple(uploaded_file, user_id, session_id, description=""):
    try:
        user_uploads = os.path.join(UPLOADS_DIR, user_id)
        os.makedirs(user_uploads, exist_ok=True)
        file_path = os.path.join(user_uploads, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        user_data = load_user_data(user_id)
        images = user_data.get("images", {})
        if str(session_id) not in images:
            images[str(session_id)] = []
        images[str(session_id)].append({
            "original_filename": uploaded_file.name,
            "path": file_path,
            "description": description,
            "upload_date": datetime.now().isoformat()
        })
        user_data["images"] = images
        save_user_data(user_id, user_data)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def display_simple_gallery(user_id, session_id):
    images = get_session_images(user_id, session_id)
    selected = []
    cols = st.columns(3)
    for i, img in enumerate(images):
        with cols[i % 3]:
            st.image(img["path"], caption=img.get("description", img["original_filename"]))
            if st.checkbox("Select", key=f"sel_img_{session_id}_{i}"):
                selected.append(img)
    return selected

def load_historical_events():
    # Sample hardcoded data
    return [
        {"year_range": "1960-1970", "event": "Moon Landing", "region": "Global", "category": "Space"},
        {"year_range": "1980-1990", "event": "Fall of Berlin Wall", "region": "Global", "category": "Politics"},
        # Add more real events
    ]

def get_events_for_birth_year(birth_year):
    events = load_historical_events()
    return [e for e in events if int(e["year_range"].split("-")[0]) >= birth_year]

def get_streak_emoji(days):
    if days >= 30: return "🌟"
    if days >= 7: return "🏆"
    return "🔥"

def calculate_author_word_count(session_id):
    responses = st.session_state.responses.get(session_id, {}).get("questions", {})
    return sum(len(re.findall(r'\w+', ans.get("answer", ""))) for ans in responses.values())

def get_progress_info(session_id):
    responses = st.session_state.responses.get(session_id, {})
    count = calculate_author_word_count(session_id)
    target = responses.get("word_target", DEFAULT_WORD_TARGET)
    percent = (count / target * 100) if target > 0 else 0
    return {
        "current_count": count,
        "target": target,
        "progress_percent": percent,
        "color": "#4CAF50" if percent >= 100 else "#ff9800" if percent > 30 else "#f44336",
        "emoji": "🏆" if percent >= 100 else "🔥" if percent > 50 else "📝",
        "status_text": "Complete!" if percent >= 100 else "In Progress" if percent > 0 else "Start Now"
    }

# ── Modular Stubs (if separate files not present) ────────────────────────────
standard_sessions = [
    {"id": 1, "title": "Early Years", "questions": ["Where were you born?", "Earliest memories?"], "word_target": 500},
    {"id": 2, "title": "Education", "questions": ["Schools attended?", "Favorite subjects?"], "word_target": 600},
    # Add your full list
]

def get_sessions(user_id):
    user_data = load_user_data(user_id)
    user_sessions = user_data.get('sessions', [])
    sessions = standard_sessions.copy()
    for us in user_sessions:
        existing = next((s for s in sessions if s['id'] == us['id']), None)
        if existing:
            existing.update(us)
        else:
            sessions.append(us)
    sessions.sort(key=lambda x: x['id'])
    return sessions

def add_session(user_id, title):
    user_data = load_user_data(user_id)
    user_sessions = user_data.get('sessions', [])
    max_id = max([s['id'] for s in standard_sessions + user_sessions], default=0) + 1
    new_session = {"id": max_id, "title": title, "questions": [], "word_target": DEFAULT_WORD_TARGET}
    user_sessions.append(new_session)
    user_data['sessions'] = user_sessions
    save_user_data(user_id, user_data)

def add_topic_to_session(user_id, session_id, topic):
    user_data = load_user_data(user_id)
    user_sessions = user_data.get('sessions', [])
    session = next((s for s in user_sessions if s['id'] == session_id), None)
    if session:
        session['questions'].append(topic)
    else:
        # Copy standard if needed
        std = next((s for s in standard_sessions if s['id'] == session_id), None)
        if std:
            new_s = std.copy()
            new_s['questions'].append(topic)
            user_sessions.append(new_s)
    user_data['sessions'] = user_sessions
    save_user_data(user_id, user_data)

standard_topics = [
    "Childhood Memories", "School Days", "First Job", "Family Traditions", "Hobbies", 
    "Travels", "Career Milestones", "Relationships", "Challenges", "Aspirations"
]

def get_standard_vignette_topics():
    return ["Life Lesson", "Achievement", "Work Loss of Life", "Illness", "New Child", 
            "Marriage", "Travel", "Relationship", "Interests", "Education"]

def get_user_vignettes(user_id):
    user_data = load_user_data(user_id)
    return user_data.get('vignettes', [])

def add_vignette(user_id, topic, content):
    user_data = load_user_data(user_id)
    vignettes = user_data.get('vignettes', [])
    vignettes.append({
        "topic": topic,
        "content": content,
        "created_at": datetime.now().isoformat(),
        "published": True
    })
    user_data['vignettes'] = vignettes
    save_user_data(user_id, user_data)

def add_vignette_to_main_story(user_id, vignette_index, session_id, topic_override=None):
    user_data = load_user_data(user_id)
    vignette = user_data['vignettes'][vignette_index]
    topic = topic_override or f"Vignette: {vignette['topic']}"
    add_topic_to_session(user_id, session_id, topic)
    responses = user_data.get("responses", st.session_state.responses)
    if session_id not in responses:
        responses[session_id] = {"questions": {}}
    responses[session_id]["questions"][topic] = {"answer": vignette['content']}
    user_data["responses"] = responses
    save_user_data(user_id, user_data)
    st.session_state.responses = responses

# ── Page Setup ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Session State Init ───────────────────────────────────────────────────────
defaults = {
    "logged_in": False,
    "user_id": "",
    "user_account": None,
    "show_profile_setup": False,
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
    "show_jots": False,
    "historical_events_loaded": False,
    "show_image_upload": False,
    "image_prompt_mode": False,
    "selected_images_for_prompt": [],
    "streak_days": 1,
    "last_active": date.today().isoformat(),
    "total_writing_days": 1,
    "view_mode": "home",
    "current_session_id": None,
    "current_topic_index": 0,
}

for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.get('show_profile_setup', False):
    # Simple profile edit modal
    with st.expander("Edit Profile", expanded=True):
        profile = st.session_state.user_account['profile']
        first_name = st.text_input("First Name", profile.get('first_name', ''))
        last_name = st.text_input("Last Name", profile.get('last_name', ''))
        email = st.text_input("Email", profile.get('email', ''))
        birthdate = st.text_input("Birthdate (e.g., January 1, 1980)", profile.get('birthdate', ''))
        if st.button("Save Profile"):
            users = load_users()
            users[st.session_state.user_id]['profile'] = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'birthdate': birthdate
            }
            save_users(users)
            st.session_state.user_account = users[st.session_state.user_id]
            st.session_state.show_profile_setup = False
            st.rerun()

if not st.session_state.logged_in:
    show_login_signup()
    st.stop()

if not st.session_state.data_loaded and st.session_state.user_id:
    user_data = load_user_data(st.session_state.user_id)
    st.session_state.responses = user_data.get("responses", {})
    st.session_state.quick_jots = user_data.get("quick_jots", [])
    sessions = get_sessions(st.session_state.user_id)
    for s in sessions:
        sid = s["id"]
        if sid not in st.session_state.responses:
            st.session_state.responses[sid] = {
                "title": s["title"],
                "questions": {},
                "summary": "",
                "completed": False,
                "word_target": s.get("word_target", DEFAULT_WORD_TARGET)
            }
        if sid not in st.session_state.session_conversations:
            st.session_state.session_conversations[sid] = {}
    st.session_state.data_loaded = True

# Load historical events
if not st.session_state.historical_events_loaded:
    try:
        events = load_historical_events()
        if events:
            st.session_state.historical_events = events
            st.session_state.historical_events_loaded = True
    except:
        pass

# ── Main Header ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="main-header">
<img src="{LOGO_URL}" alt="MemLife Logo" style="width:50px;">
<h2>MemLife - Your Life Timeline</h2>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # Profile
    st.header("👤 Your Profile")
    if st.session_state.user_account:
        profile = st.session_state.user_account['profile']
        st.success(f"✓ **{profile.get('first_name','')} {profile.get('last_name','')}**")
        st.caption(f"📧 {profile.get('email','')}")
        if profile.get('birthdate'):
            st.caption(f"🎂 {profile['birthdate']}")
    if st.button("📝 Edit Profile"):
        st.session_state.show_profile_setup = True
        st.rerun()
    if st.button("🚪 Log Out"):
        logout_user()
    st.divider()
    # Streak
    st.subheader("🔥 Writing Streak")
    emoji = get_streak_emoji(st.session_state.streak_days)
    st.markdown(f"<div style='font-size:2rem;'>{emoji}</div>", unsafe_allow_html=True)
    st.markdown(f"**{st.session_state.streak_days} days**")
    # Photos
    st.divider()
    st.subheader("🖼️ Photos")
    total_images = get_total_user_images(st.session_state.user_id)
    st.metric("Total", total_images)
    # Quick Capture
    st.divider()
    st.subheader("⚡ Quick Capture")
    quick_note = st.text_area("Jot a memory:", height=100)
    if st.button("Save Jot"):
        if quick_note.strip():
            year = estimate_year_from_text(quick_note)
            save_jot(quick_note, year)
            st.success("Saved!")
            st.rerun()
    # Modes
    st.divider()
    st.header("✍️ Style")
    st.toggle("Ghostwriter Mode", key="ghostwriter_mode")
    st.toggle("Spellcheck", key="spellcheck_enabled")
    # Historical
    st.divider()
    st.header("📜 History")
    if 'birthdate' in st.session_state.user_account['profile']:
        birth_year = int(st.session_state.user_account['profile']['birthdate'].split()[-1])
        events = get_events_for_birth_year(birth_year)
        st.success(f"✓ {len(events)} events loaded")
    # Navigation
    st.divider()
    if st.button("🏠 Home"):
        st.session_state.view_mode = "home"
        st.rerun()
    if st.button("📝 Vignettes"):
        st.session_state.view_mode = "vignettes"
        st.rerun()
    # Export
    st.divider()
    st.subheader("📤 Export")
    if st.session_state.user_id:
        export_data = st.session_state.responses
        image_data = load_user_data(st.session_state.user_id).get("images", {})
        complete_data = {
            "stories": export_data,
            "images": image_data,
            "export_date": datetime.now().isoformat()
        }
        json_data = json.dumps(complete_data, indent=2)
        st.download_button("Download Data", json_data, "memlife.json")
    # Clear Data
    st.divider()
    st.subheader("⚠️ Clear Data")
    if st.button("Clear All"):
        save_user_data(st.session_state.user_id, {})
        st.session_state.responses = {}
        st.rerun()

# ── Main Content ─────────────────────────────────────────────────────────────
sessions = get_sessions(st.session_state.user_id)

if st.session_state.view_mode == "home":
    st.subheader("Sessions")
    cols = st.columns(3)
    for i, session in enumerate(sessions):
        sid = session["id"]
        questions = session["questions"]
        responses = st.session_state.responses.get(sid, {}).get("questions", {})
        answered = len(responses)
        total = len(questions)
        if answered == total and total > 0:
            color = "green"
        elif answered > 0:
            color = "orange"
        else:
            color = "red"
        with cols[i % 3]:
            st.button(session["title"], key=f"sess_{sid}", on_click=lambda sid=sid: (setattr(st.session_state, 'view_mode', 'session'), setattr(st.session_state, 'current_session_id', sid)))
            st.caption(f"{answered}/{total} - color: {color}")

    st.subheader("Add Session")
    new_title = st.text_input("Title")
    if st.button("Add"):
        add_session(st.session_state.user_id, new_title)
        st.rerun()

elif st.session_state.view_mode == "session":
    sid = st.session_state.current_session_id
    session = next(s for s in sessions if s["id"] == sid)
    st.subheader(session["title"])
    st.button("Back to Home", on_click=lambda: setattr(st.session_state, 'view_mode', 'home'))
    cols = st.columns(3)
    for i, q in enumerate(session["questions"]):
        has_ans = q in st.session_state.responses.get(sid, {}).get("questions", {})
        color = "green" if has_ans else "red"
        with cols[i % 3]:
            st.button(q, key=f"topic_{sid}_{i}", on_click=lambda i=i: setattr(st.session_state, 'current_topic_index', i), args=(setattr(st.session_state, 'view_mode', 'topic'),))
            st.caption(color)
    st.subheader("Add Topic")
    new_topic = st.text_input("New Topic")
    if st.button("Add Topic"):
        add_topic_to_session(st.session_state.user_id, sid, new_topic)
        st.rerun()
    bank_topic = st.selectbox("From Bank", standard_topics)
    if st.button("Add from Bank"):
        add_topic_to_session(st.session_state.user_id, sid, bank_topic)
        st.rerun()

elif st.session_state.view_mode == "topic":
    sid = st.session_state.current_session_id
    session = next(s for s in sessions if s["id"] == sid)
    questions = session["questions"]
    idx = st.session_state.current_topic_index
    current_question_text = questions[idx]
    st.subheader(current_question_text)
    st.button("Back to Session", on_click=lambda: setattr(st.session_state, 'view_mode', 'session'))
    # Images
    if st.button("Show Image Upload"):
        st.session_state.show_image_upload = not st.session_state.show_image_upload
    if st.session_state.show_image_upload:
        uploaded_files = st.file_uploader("Upload Photos", accept_multiple_files=True, type=['jpg', 'png'])
        desc = st.text_input("Description")
        if st.button("Upload"):
            for file in uploaded_files:
                save_uploaded_image_simple(file, st.session_state.user_id, sid, desc)
            st.rerun()
        selected = display_simple_gallery(st.session_state.user_id, sid)
        st.session_state.selected_images_for_prompt = selected
    # Conversation
    if sid not in st.session_state.session_conversations:
        st.session_state.session_conversations[sid] = {}
    conversation = st.session_state.session_conversations[sid].get(current_question_text, [])
    for message in conversation:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    user_input = st.chat_input("Your response...")
    if user_input:
        if st.session_state.spellcheck_enabled:
            user_input = auto_correct_text(user_input)
        conversation.append({"role": "user", "content": user_input})
        messages = [{"role": "system", "content": get_system_prompt()}] + conversation
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8 if st.session_state.ghostwriter_mode else 0.7,
            max_tokens=400
        )
        ai_response = response.choices[0].message.content
        conversation.append({"role": "assistant", "content": ai_response})
        st.session_state.session_conversations[sid][current_question_text] = conversation
        st.session_state.responses[sid]["questions"][current_question_text] = {"answer": user_input}
        save_user_data(st.session_state.user_id, {"responses": st.session_state.responses})
        st.rerun()
    # Progress
    progress = get_progress_info(sid)
    st.progress(min(progress["progress_percent"]/100, 1.0))
    st.caption(f"{progress['current_count']} / {progress['target']} words")

elif st.session_state.view_mode == "vignettes":
    st.subheader("Vignettes")
    st.button("Back to Home", on_click=lambda: setattr(st.session_state, 'view_mode', 'home'))
    topic = st.selectbox("Topic", get_standard_vignette_topics() + ["Custom"])
    if topic == "Custom":
        topic = st.text_input("Custom Topic")
    content = st.text_area("Write Vignette")
    if st.button("Publish"):
        add_vignette(st.session_state.user_id, topic, content)
        st.rerun()
    vignettes = get_user_vignettes(st.session_state.user_id)
    for i, v in enumerate(vignettes):
        with st.expander(v["topic"]):
            st.markdown(v["content"])
            sel_session = st.selectbox("Add to Session", [s["title"] for s in sessions], key=f"sel_v_{i}")
            custom_topic = st.text_input("Custom Topic Name", key=f"ct_v_{i}")
            if st.button("Add to Story", key=f"add_v_{i}"):
                sel_id = next(s["id"] for s in sessions if s["title"] == sel_session)
                add_vignette_to_main_story(st.session_state.user_id, i, sel_id, custom_topic)
                st.rerun()

# ── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.caption("MemLife © 2026")
