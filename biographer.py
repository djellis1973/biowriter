# ============================================================================
# SECTION 1: IMPORTS AND INITIAL SETUP
# ============================================================================
import streamlit as st
import json
from datetime import datetime, date, timedelta
from openai import OpenAI
import os
import sqlite3
import re  # For word counting
import hashlib  # For creating user file names
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import string
import base64  # For encoding export data
import pandas as pd  # ADDED: For CSV handling of historical events
import shutil  # ADDED: For image management
import uuid  # ADDED: For image management
from PIL import Image  # ADDED: For image management
import io  # ADDED: For image management

# Initialize OpenAI client
client = OpenAI(api_key=st.secrets.get("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY")))

# ============================================================================
# SECTION 2: EMAIL CONFIGURATION
# ============================================================================
EMAIL_CONFIG = {
    "smtp_server": st.secrets.get("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(st.secrets.get("SMTP_PORT", 587)),
    "sender_email": st.secrets.get("SENDER_EMAIL", ""),
    "sender_password": st.secrets.get("SENDER_PASSWORD", ""),
    "use_tls": True
}

# ============================================================================
# SECTION 3: SIMPLIFIED IMAGE MANAGER
# ============================================================================
def get_user_image_folder(user_id):
    """Get or create user's image folder"""
    folder_path = f"user_images/{user_id}"
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def get_session_image_folder(user_id, session_id):
    """Get or create session-specific image folder"""
    folder_path = f"user_images/{user_id}/session_{session_id}"
    os.makedirs(folder_path, exist_ok=True)
    return folder_path

def save_image_metadata(user_id, session_id, image_info):
    """Save image metadata to JSON file"""
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    
    try:
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        if str(session_id) not in metadata:
            metadata[str(session_id)] = []
        
        metadata[str(session_id)].append(image_info)
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error saving image metadata: {e}")
        return False

def get_session_images(user_id, session_id):
    """Get all images for a specific session"""
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            session_key = str(session_id)
            if session_key in metadata:
                return metadata[session_key]
        except:
            pass
    
    return []

def save_uploaded_image_simple(uploaded_file, user_id, session_id, description=""):
    """Simple image upload function"""
    try:
        # Generate unique filename
        unique_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_filename = uploaded_file.name
        file_ext = original_filename.split('.')[-1].lower()
        safe_filename = f"{timestamp}_{unique_id}.{file_ext}"
        
        # Get session folder
        session_folder = get_session_image_folder(user_id, session_id)
        
        # Save the file
        file_path = os.path.join(session_folder, safe_filename)
        
        # Read and save
        image_bytes = uploaded_file.read()
        with open(file_path, 'wb') as f:
            f.write(image_bytes)
        
        # Create thumbnail if it's an image
        try:
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']:
                img = Image.open(io.BytesIO(image_bytes))
                img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                thumb_path = os.path.join(session_folder, f"thumb_{safe_filename}")
                img.save(thumb_path, quality=85)
                thumbnail_path = thumb_path
            else:
                thumbnail_path = file_path
        except:
            thumbnail_path = file_path
        
        # Create image info
        image_info = {
            "id": unique_id,
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "description": description,
            "upload_date": datetime.now().isoformat(),
            "session_id": session_id,
            "file_size_kb": len(image_bytes) / 1024,
            "paths": {
                "original": file_path,
                "thumbnail": thumbnail_path
            }
        }
        
        # Save metadata
        save_image_metadata(user_id, session_id, image_info)
        
        return {
            "success": True,
            "image_info": image_info,
            "message": f"Image '{original_filename}' uploaded successfully!"
        }
        
    except Exception as e:
        return {"success": False, "error": f"Error processing image: {str(e)}"}

def delete_image_simple(user_id, session_id, image_id):
    """Delete an image"""
    try:
        metadata_file = f"user_images/{user_id}/image_metadata.json"
        
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            session_key = str(session_id)
            if session_key in metadata:
                for i, img in enumerate(metadata[session_key]):
                    if img["id"] == image_id:
                        # Delete files
                        if os.path.exists(img["paths"]["original"]):
                            os.remove(img["paths"]["original"])
                        if os.path.exists(img["paths"]["thumbnail"]):
                            os.remove(img["paths"]["thumbnail"])
                        
                        # Remove from metadata
                        metadata[session_key].pop(i)
                        
                        # Save updated metadata
                        with open(metadata_file, 'w') as f:
                            json.dump(metadata, f, indent=2)
                        
                        return {"success": True, "message": "Image deleted successfully"}
        
        return {"success": False, "error": "Image not found"}
    except Exception as e:
        return {"success": False, "error": f"Error deleting image: {str(e)}"}

def get_image_data_url(image_path):
    """Convert image to data URL"""
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
            extension = image_path.split('.')[-1].lower()
            mime_type = f"image/{'jpeg' if extension in ['jpg', 'jpeg'] else extension}"
            return f"data:{mime_type};base64,{encoded}"
    except:
        return None

def display_simple_gallery(user_id, session_id):
    """Display simple image gallery"""
    images = get_session_images(user_id, session_id)
    
    if not images:
        return []
    
    st.subheader(f"📸 Your Photos ({len(images)})")
    
    selected_images = []
    
    for idx, img_info in enumerate(images):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Display thumbnail if exists
            if os.path.exists(img_info["paths"]["thumbnail"]):
                data_url = get_image_data_url(img_info["paths"]["thumbnail"])
                if data_url:
                    st.markdown(f'<img src="{data_url}" style="width:100%; max-height:200px; object-fit:cover; border-radius:8px;">', unsafe_allow_html=True)
            
            st.caption(f"{img_info['original_filename']}")
            if img_info.get('description'):
                st.caption(f"📝 {img_info['description']}")
        
        with col2:
            # Select button
            if st.button("✨ Use", key=f"select_{img_info['id']}", help="Use this photo to create prompts"):
                selected_images.append(img_info)
            
            # Delete button
            if st.button("🗑️", key=f"delete_{img_info['id']}", help="Delete this photo"):
                result = delete_image_simple(user_id, session_id, img_info["id"])
                if result["success"]:
                    st.success("Photo deleted")
                    st.rerun()
                else:
                    st.error(result["error"])
    
    return selected_images

def get_images_for_prompt_simple(user_id, session_id):
    """Simple prompt generation from images"""
    images = get_session_images(user_id, session_id)
    
    if not images:
        return ""
    
    prompt_text = "\n\n📸 **PHOTOS UPLOADED FOR THIS MEMORY:**\n"
    
    for img in images[:5]:  # Limit to 5 images
        prompt_text += f"- Photo: {img['original_filename']}"
        if img.get('description'):
            prompt_text += f" - {img['description']}"
        prompt_text += "\n"
    
    prompt_text += """
**Use these photos to ask specific questions about:
1. Who is in the photo?
2. Where was it taken?
3. When was it taken?
4. What's happening in the photo?
5. What emotions does it bring up?
6. What happened before/after this moment?**
"""
    
    return prompt_text

def get_total_user_images(user_id):
    """Get total number of images"""
    metadata_file = f"user_images/{user_id}/image_metadata.json"
    
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            total = 0
            for session_id, images in metadata.items():
                total += len(images)
            return total
        except:
            pass
    
    return 0
# ============================================================================
# SECTION 4: CSS STYLING AND VISUAL DESIGN
# ============================================================================
LOGO_URL = "https://menuhunterai.com/wp-content/uploads/2026/01/logo.png"

st.markdown(f"""
<style>
    /* All existing CSS stays the same */
    .main-header {{
        text-align: center;
        padding-top: 0.5rem;
        margin-top: -1rem;
        margin-bottom: 0.5rem;
    }}
    
    .logo-img {{
        width: 100px;
        height: 100px;
        border-radius: 50%;
        object-fit: cover;
        margin: 0 auto 0.25rem auto;
        display: block;
    }}
    
    .chapter-guidance {{
        background-color: #e8f4f8;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #3498db;
        margin-bottom: 1rem;
        font-size: 0.95rem;
        line-height: 1.5;
    }}
    
    .question-box {{
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #4a5568;
        margin-bottom: 0.5rem;
        font-size: 1.3rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        line-height: 1.4;
    }}
    
    .question-counter {{
        font-size: 1.1rem;
        font-weight: bold;
        color: #2c3e50;
    }}
    
    .stChatMessage {{
        margin-bottom: 0.5rem !important;
    }}
    
    .user-message-container {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        width: 100%;
    }}
    
    .message-text {{
        flex: 1;
        min-width: 0;
    }}
    
    [data-testid="stAppViewContainer"] {{
        padding-top: 0.5rem !important;
    }}
    
    .ghostwriter-tag {{
        font-size: 0.8rem;
        color: #666;
        font-style: italic;
        margin-top: 0.5rem;
    }}
    
    .edit-target-box {{
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border: 1px solid #dee2e6;
    }}
    
    .warning-box {{
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 6px;
        padding: 1rem;
        margin: 0.5rem 0;
    }}
    
    .progress-container {{
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        margin: 1rem 0;
    }}
    
    .progress-header {{
        font-size: 1.2rem;
        font-weight: bold;
        margin-bottom: 1rem;
        color: #2c3e50;
    }}
    
    .progress-status {{
        font-size: 1.1rem;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }}
    
    .progress-bar-container {{
        height: 10px;
        background-color: #e0e0e0;
        border-radius: 5px;
        overflow: hidden;
        margin: 1rem 0;
    }}
    
    .progress-bar-fill {{
        height: 100%;
        border-radius: 5px;
        transition: width 0.3s ease;
    }}
    
    .jot-box {{
        background-color: #fff8e1;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ffb300;
        margin-bottom: 1rem;
        font-size: 0.9rem;
    }}
    
    .streak-flame {{
        font-size: 1.5rem;
        animation: pulse 2s infinite;
    }}
    
    @keyframes pulse {{
        0% {{ opacity: 0.8; }}
        50% {{ opacity: 1; }}
        100% {{ opacity: 0.8; }}
    }}
    
    .refresh-prompt-btn {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        cursor: pointer;
        transition: transform 0.2s;
    }}
    
    .refresh-prompt-btn:hover {{
        transform: scale(1.05);
    }}
    
    /* Login/Signup Styles */
    .auth-container {{
        max-width: 500px;
        margin: 3rem auto;
        padding: 2.5rem;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }}
    
    .auth-title {{
        text-align: center;
        color: #2c3e50;
        margin-bottom: 0.5rem;
        font-size: 2rem;
        font-weight: 300;
    }}
    
    .auth-subtitle {{
        text-align: center;
        color: #7f8c8d;
        margin-bottom: 2rem;
        font-size: 1rem;
    }}
    
    .auth-tabs {{
        display: flex;
        margin-bottom: 2rem;
        border-bottom: 2px solid #f1f2f6;
    }}
    
    .auth-tab {{
        flex: 1;
        padding: 1rem;
        text-align: center;
        cursor: pointer;
        font-weight: 500;
        color: #7f8c8d;
        transition: all 0.3s;
        border-bottom: 3px solid transparent;
    }}
    
    .auth-tab:hover {{
        background-color: #f8f9fa;
    }}
    
    .auth-tab.active {{
        color: #3498db;
        border-bottom-color: #3498db;
    }}
    
    .auth-form {{
        margin-top: 1.5rem;
    }}
    
    .auth-input-group {{
        margin-bottom: 1.5rem;
    }}
    
    .auth-label {{
        display: block;
        margin-bottom: 0.5rem;
        color: #2c3e50;
        font-weight: 500;
    }}
    
    .auth-input {{
        width: 100%;
        padding: 0.75rem;
        border: 2px solid #e0e0e0;
        border-radius: 8px;
        font-size: 1rem;
        transition: border-color 0.3s;
    }}
    
    .auth-input:focus {{
        border-color: #3498db;
        outline: none;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
    }}
    
    .auth-button {{
        width: 100%;
        padding: 0.875rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
        transition: transform 0.3s, box-shadow 0.3s;
        margin-top: 0.5rem;
    }}
    
    .auth-button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }}
    
    .auth-divider {{
        display: flex;
        align-items: center;
        margin: 2rem 0;
        color: #7f8c8d;
    }}
    
    .auth-divider::before,
    .auth-divider::after {{
        content: "";
        flex: 1;
        border-bottom: 1px solid #e0e0e0;
    }}
    
    .auth-divider-text {{
        padding: 0 1rem;
        font-size: 0.9rem;
    }}
    
    .forgot-password {{
        text-align: center;
        margin-top: 1rem;
    }}
    
    .forgot-password a {{
        color: #3498db;
        text-decoration: none;
        font-size: 0.9rem;
    }}
    
    .forgot-password a:hover {{
        text-decoration: underline;
    }}
    
    /* Profile Setup Styles */
    .profile-setup-modal {{
        background: white;
        border-radius: 15px;
        padding: 2rem;
        margin: 2rem auto;
        max-width: 600px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }}
    
    /* HTML Link Button */
    .html-link-btn {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        font-weight: 600;
        cursor: pointer;
        width: 100%;
        margin-top: 1rem;
        text-align: center;
        text-decoration: none;
        display: inline-block;
    }}
    
    .html-link-btn:hover {{
        opacity: 0.9;
    }}
    
    /* Image Gallery Styles - SIMPLIFIED */
    .photo-prompt-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        cursor: pointer;
        transition: transform 0.2s;
    }}
    
    .photo-prompt-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }}
    
    .simple-image-btn {{
        background: #4CAF50;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        cursor: pointer;
        margin: 0.25rem;
        width: 100%;
    }}
    
    .simple-image-btn:hover {{
        background: #45a049;
    }}
</style>
""", unsafe_allow_html=True)

# ============================================================================
# SECTION 5: SESSIONS DATA STRUCTURE
# ============================================================================
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

# ============================================================================
# SECTION 6: FALLBACK PROMPTS FOR "NO BLANK PAGES" FEATURE
# ============================================================================
FALLBACK_PROMPTS = [
    "Describe a smell or sound that brings back a strong memory.",
    "What's a small moment that had a big impact?",
    "Tell me about a place that felt like home.",
    "Who believed in you when you didn't believe in yourself?",
    "What's something you learned the hard way?",
    "Describe a meal that holds special meaning.",
    "What was a turning point in how you see yourself?",
    "Tell me about a gift that meant more than its cost.",
    "What's a risk that paid off (or didn't)?",
    "Describe a time you felt truly proud."
]

# ============================================================================
# SECTION 7: HISTORICAL EVENTS CSV SYSTEM (SIMPLIFIED)
# ============================================================================
def create_default_events_csv():
    """Create a default historical events CSV file if it doesn't exist"""
    default_events = [
        ["1920s","Women get the vote in UK","Political","UK","Women over 21 get the right to vote in 1928"],
        ["1920s","BBC founded","Media","UK","British Broadcasting Corporation founded in 1922"],
        ["1930s","Great Depression","Economic","Global","Worldwide economic depression"],
        ["1930s","George VI coronation","Royal","UK","Coronation in 1937"],
        ["1940s","World War II","Military","Global","1939-1945 global conflict"],
        ["1940s","NHS founded","Healthcare","UK","National Health Service established in 1948"],
        ["1950s","Coronation of Elizabeth II","Royal","UK","Queen Elizabeth II crowned in 1953"],
        ["1950s","Suez Crisis","Political","UK/Global","1956 Suez Crisis"],
        ["1960s","Man on the moon","Science","Global","Apollo 11 moon landing in 1969"],
        ["1960s","Beatles become famous","Culture","UK","Beatles rise to fame in early 1960s"],
        ["1970s","UK joins EEC","Political","UK","UK joins European Economic Community in 1973"],
        ["1970s","Oil crisis","Economic","Global","1973 oil crisis causes shortages"],
        ["1980s","Falklands War","Military","UK","1982 war between UK and Argentina"],
        ["1980s","Live Aid concert","Culture","Global","1985 charity concert"],
        ["1990s","World Wide Web invented","Technology","Global","Tim Berners-Lee invents WWW in 1989"],
        ["2000s","Financial crisis","Economic","Global","2007-2008 global financial crisis"],
        ["2000s","London bombings","Political","UK","7 July 2005 London bombings"],
        ["2010s","London Olympics","Sports","UK","2012 Summer Olympics in London"],
        ["2010s","Brexit referendum","Political","UK","2016 referendum to leave EU"],
        ["2020s","COVID-19 pandemic","Health","Global","Global pandemic begins 2020"],
        ["2020s","Queen Elizabeth II dies","Royal","UK","Queen dies in 2022, King Charles III ascends"]
    ]
    
    try:
        with open("historical_events.csv", "w", encoding="utf-8") as f:
            f.write("year_range,event,category,region,description\n")
            for event in default_events:
                f.write(",".join([f'"{item}"' for item in event]) + "\n")
        return True
    except Exception as e:
        print(f"Error creating default CSV: {e}")
        return False

def load_historical_events():
    """Load historical events from CSV file"""
    try:
        csv_file = "historical_events.csv"
        
        if not os.path.exists(csv_file):
            create_default_events_csv()
        
        df = pd.read_csv(csv_file)
        
        events_by_decade = {}
        for _, row in df.iterrows():
            decade = str(row['year_range']).strip()
            event = str(row['event']).strip()
            category = str(row.get('category', 'General')).strip()
            region = str(row.get('region', 'Global')).strip()
            description = str(row.get('description', '')).strip()
            
            if decade not in events_by_decade:
                events_by_decade[decade] = []
            
            events_by_decade[decade].append({
                'event': event,
                'category': category,
                'region': region,
                'description': description,
                'year_range': decade
            })
        
        return events_by_decade
        
    except Exception as e:
        print(f"Error loading historical events: {e}")
        return {}

def get_events_for_birth_year(birth_year):
    """Get historical events relevant to a person based on their birth year"""
    try:
        events_by_decade = load_historical_events()
        relevant_events = []
        current_year = datetime.now().year
        start_decade_year = (birth_year // 10) * 10
        
        for decade_year in range(start_decade_year, current_year + 10, 10):
            decade_key = f"{decade_year}s"
            
            if decade_key in events_by_decade:
                for event in events_by_decade[decade_key]:
                    event_year = int(decade_key.replace('s', '')) + 5
                    age_at_event = event_year - birth_year
                    
                    if age_at_event >= 0:
                        event_with_age = event.copy()
                        event_with_age['approx_age'] = age_at_event
                        relevant_events.append(event_with_age)
        
        relevant_events.sort(key=lambda x: x['year_range'])
        return relevant_events[:20]
        
    except Exception as e:
        print(f"Error getting events for birth year {birth_year}: {e}")
        return []

# ============================================================================
# SECTION 8: AUTHENTICATION & ACCOUNT MANAGEMENT FUNCTIONS
# ============================================================================
def generate_password(length=12):
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def hash_password(password):
    """Hash password for storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash, password):
    """Verify password against stored hash"""
    return stored_hash == hash_password(password)

def create_user_account(user_data, password=None):
    """Create a new user account"""
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
        
        return {
            "success": True,
            "user_id": user_id,
            "password": password,
            "user_record": user_record
        }
        
    except Exception as e:
        print(f"Error creating user account: {e}")
        return {"success": False, "error": str(e)}

def save_account_data(user_record):
    """Save account data to JSON file"""
    try:
        filename = f"accounts/{user_record['user_id']}_account.json"
        os.makedirs("accounts", exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(user_record, f, indent=2)
        
        update_accounts_index(user_record)
        return True
    except Exception as e:
        print(f"Error saving account data: {e}")
        return False

def update_accounts_index(user_record):
    """Update main accounts index file"""
    try:
        index_file = "accounts/accounts_index.json"
        os.makedirs("accounts", exist_ok=True)
        
        if os.path.exists(index_file):
            with open(index_file, 'r') as f:
                index = json.load(f)
        else:
            index = {}
        
        index[user_record['user_id']] = {
            "email": user_record['email'],
            "first_name": user_record['profile']['first_name'],
            "last_name": user_record['profile']['last_name'],
            "created_at": user_record['created_at'],
            "account_type": user_record['account_type']
        }
        
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        return True
    except Exception as e:
        print(f"Error updating accounts index: {e}")
        return False

def get_account_data(user_id=None, email=None):
    """Get account data for a user"""
    try:
        if user_id:
            filename = f"accounts/{user_id}_account.json"
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
        elif email:
            email = email.lower().strip()
            index_file = "accounts/accounts_index.json"
            if os.path.exists(index_file):
                with open(index_file, 'r') as f:
                    index = json.load(f)
                
                for uid, user_data in index.items():
                    if user_data.get("email", "").lower() == email:
                        filename = f"accounts/{uid}_account.json"
                        if os.path.exists(filename):
                            with open(filename, 'r') as f:
                                return json.load(f)
    except Exception as e:
        print(f"Error loading account data: {e}")
    return None

def authenticate_user(email, password):
    """Authenticate user with email and password"""
    try:
        account_data = get_account_data(email=email)
        if account_data:
            if verify_password(account_data['password_hash'], password):
                account_data['last_login'] = datetime.now().isoformat()
                save_account_data(account_data)
                return {
                    "success": True,
                    "user_id": account_data['user_id'],
                    "user_record": account_data
                }
        return {"success": False, "error": "Invalid email or password"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_welcome_email(user_data, credentials):
    """Send welcome email with account details"""
    try:
        if not EMAIL_CONFIG['sender_email'] or not EMAIL_CONFIG['sender_password']:
            print("Email not configured - skipping email send")
            return False
        
        msg = MIMEMultipart()
        msg['From'] = EMAIL_CONFIG['sender_email']
        msg['To'] = user_data['email']
        msg['Subject'] = "Welcome to MemLife - Your Account Details"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Welcome to MemLife, {user_data['first_name']}!</h2>
                
                <p>Thank you for creating your account. We're excited to help you build your life timeline.</p>
                
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
    """Log out the current user"""
    keys_to_clear = [
        'user_id', 'user_account', 'logged_in', 'show_profile_setup',
        'current_session', 'current_question', 'responses', 
        'session_conversations', 'data_loaded', 'show_image_upload',
        'selected_images_for_prompt', 'image_prompt_mode'
    ]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.query_params.clear()
    st.rerun()

# ============================================================================
# SECTION 9: JSON-BASED STORAGE FUNCTIONS
# ============================================================================
def get_user_filename(user_id):
    """Create a safe filename for user data"""
    filename_hash = hashlib.md5(user_id.encode()).hexdigest()[:8]
    return f"user_data_{filename_hash}.json"

def load_user_data(user_id):
    """Load user data from JSON file"""
    filename = get_user_filename(user_id)
    
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                if "responses" in data:
                    return data
        return {"responses": {}, "last_loaded": datetime.now().isoformat()}
    except Exception as e:
        print(f"Error loading user data for {user_id}: {e}")
        return {"responses": {}, "last_loaded": datetime.now().isoformat()}

def save_user_data(user_id, responses_data):
    """Save user data to JSON file"""
    filename = get_user_filename(user_id)
    
    try:
        data_to_save = {
            "user_id": user_id,
            "responses": responses_data,
            "last_saved": datetime.now().isoformat()
        }
        
        with open(filename, 'w') as f:
            json.dump(data_to_save, f, indent=2)
        
        print(f"DEBUG: Saved data for {user_id} to {filename}")
        return True
    except Exception as e:
        print(f"Error saving user data for {user_id}: {e}")
        return False

# ============================================================================
# SECTION 10: NEW FUNCTIONS FOR ADDED FEATURES
# ============================================================================
def update_streak():
    """Update user's writing streak"""
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
    """Get flame emoji based on streak length"""
    if streak_days >= 30:
        return "🔥🔥🔥"
    elif streak_days >= 7:
        return "🔥🔥"
    elif streak_days >= 3:
        return "🔥"
    else:
        return "✨"

def estimate_year_from_text(text):
    """Simple year extraction from text"""
    try:
        years = re.findall(r'\b(19\d{2}|20\d{2})\b', text)
        if years:
            return int(years[0])
    except:
        pass
    return None

def save_jot(text, estimated_year=None):
    """Save a quick jot to session state"""
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

# ============================================================================
# SECTION 11: AUTHENTICATION COMPONENTS
# ============================================================================
def show_login_signup():
    """Show login/signup interface"""
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
    """Display login form"""
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
    """Display signup form"""
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
    """Show profile setup modal for new users"""
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
                
                birthdate = f"{birth_month} {birth_day}, {birth_year}"
                account_for_value = "self" if account_for == "For me" else "other"
                
                if st.session_state.user_account:
                    st.session_state.user_account['profile']['gender'] = gender
                    st.session_state.user_account['profile']['birthdate'] = birthdate
                    st.session_state.user_account['profile']['timeline_start'] = birthdate
                    st.session_state.user_account['account_type'] = account_for_value
                    
                    save_account_data(st.session_state.user_account)
                    st.success("Profile updated successfully!")
            
            st.session_state.show_profile_setup = False
            st.markdown('</div>', unsafe_allow_html=True)
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# SECTION 12: SESSION STATE INITIALIZATION
# ============================================================================

# Set page config first
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize ALL session state variables
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = ""
if "user_account" not in st.session_state:
    st.session_state.user_account = None
if "show_profile_setup" not in st.session_state:
    st.session_state.show_profile_setup = False
if "current_session" not in st.session_state:
    st.session_state.current_session = 0
if "current_question" not in st.session_state:
    st.session_state.current_question = 0
if "responses" not in st.session_state:
    st.session_state.responses = {}
if "session_conversations" not in st.session_state:
    st.session_state.session_conversations = {}
if "editing" not in st.session_state:
    st.session_state.editing = None
if "edit_text" not in st.session_state:
    st.session_state.edit_text = ""
if "ghostwriter_mode" not in st.session_state:
    st.session_state.ghostwriter_mode = True
if "spellcheck_enabled" not in st.session_state:
    st.session_state.spellcheck_enabled = True
if "editing_word_target" not in st.session_state:
    st.session_state.editing_word_target = False
if "confirming_clear" not in st.session_state:
    st.session_state.confirming_clear = None
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "prompt_index" not in st.session_state:
    st.session_state.prompt_index = 0
if "current_question_override" not in st.session_state:
    st.session_state.current_question_override = None
if "quick_jots" not in st.session_state:
    st.session_state.quick_jots = []
if "current_jot" not in st.session_state:
    st.session_state.current_jot = ""
if "show_jots" not in st.session_state:
    st.session_state.show_jots = False
if "historical_events_loaded" not in st.session_state:
    st.session_state.historical_events_loaded = False

# NEW: Initialize image-related state variables
if "show_image_upload" not in st.session_state:
    st.session_state.show_image_upload = False
if "image_prompt_mode" not in st.session_state:
    st.session_state.image_prompt_mode = False
if "selected_images_for_prompt" not in st.session_state:
    st.session_state.selected_images_for_prompt = []
if "image_description" not in st.session_state:
    st.session_state.image_description = ""

# Initialize streak system
if "streak_days" not in st.session_state:
    st.session_state.streak_days = 1
if "last_active" not in st.session_state:
    st.session_state.last_active = date.today().isoformat()
if "total_writing_days" not in st.session_state:
    st.session_state.total_writing_days = 1

# Check for remembered login via query params
if not st.session_state.logged_in and 'user' in st.query_params:
    url_user = st.query_params['user']
    account_data = get_account_data(url_user)
    if account_data:
        st.session_state.user_id = url_user
        st.session_state.user_account = account_data
        st.session_state.logged_in = True
        st.session_state.data_loaded = False

# Initialize empty session structures
if not st.session_state.responses:
    for session in SESSIONS:
        session_id = session["id"]
        st.session_state.responses[session_id] = {
            "title": session["title"],
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": session.get("word_target", 500)
        }
        st.session_state.session_conversations[session_id] = {}

# Load user data if logged in and data hasn't been loaded yet
if st.session_state.logged_in and st.session_state.user_id and not st.session_state.data_loaded:
    print(f"DEBUG: Loading data for user {st.session_state.user_id}")
    
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
    print(f"DEBUG: Data loaded for {st.session_state.user_id}")

# ============================================================================
# SECTION 13: CORE APPLICATION FUNCTIONS
# ============================================================================
def save_response(session_id, question, answer):
    """Save response to both session state AND JSON file"""
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
        st.session_state.responses[session_id] = {
            "title": SESSIONS[session_id-1]["title"],
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": SESSIONS[session_id-1].get("word_target", 500)
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
    target = st.session_state.responses[session_id].get("word_target", 500)
    
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

# ============================================================================
# SECTION 14: AUTO-CORRECT FUNCTION
# ============================================================================
def auto_correct_text(text):
    """Auto-correct text using OpenAI"""
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

# ============================================================================
# SECTION 15: GHOSTWRITER PROMPT FUNCTION WITH SIMPLE IMAGE PROMPTS
# ============================================================================
def get_system_prompt():
    current_session = SESSIONS[st.session_state.current_session]
    
    # Use override prompt if set
    if st.session_state.current_question_override:
        current_question = st.session_state.current_question_override
    else:
        current_question = current_session["questions"][st.session_state.current_question]
    
    # Get historical context if user has birthdate
    historical_context = ""
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birthdate = st.session_state.user_account['profile']['birthdate']
            birth_year = int(birthdate.split(', ')[-1])
            
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
    
    # Get image context if user has uploaded images
    image_context = ""
    if st.session_state.logged_in and st.session_state.user_id:
        current_session_id = current_session["id"]
        images = get_session_images(st.session_state.user_id, current_session_id)
        
        if images:
            image_context = get_images_for_prompt_simple(st.session_state.user_id, current_session_id)
    
    # If in image prompt mode, create specific photo prompts
    image_prompt_section = ""
    if st.session_state.image_prompt_mode and st.session_state.selected_images_for_prompt:
        image_prompt_section = "\n\n📸 **PHOTO STORY MODE:**\n"
        image_prompt_section += "The user has selected specific photos to write about. "
        image_prompt_section += "Ask questions about these specific photos:\n\n"
        
        for idx, img in enumerate(st.session_state.selected_images_for_prompt[:3]):
            image_prompt_section += f"**Photo {idx+1}: {img['original_filename']}**\n"
            if img.get('description'):
                image_prompt_section += f"Description: {img['description']}\n"
            
            # Add specific prompt questions for each photo
            photo_prompts = [
                "Who is in this photo?",
                "Where and when was this taken?",
                "What was happening just before/after this moment?",
                "What emotions does this photo bring up?",
                "Why was this photo taken/saved?"
            ]
            
            # Pick 2-3 random prompt questions for each photo
            import random
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

# ============================================================================
# SECTION 16: MAIN APP FLOW CONTROL
# ============================================================================

# Show profile setup modal if needed
if st.session_state.get('show_profile_setup', False):
    show_profile_setup_modal()
    st.stop()

# Show login/signup if not logged in
if not st.session_state.logged_in:
    show_login_signup()
    st.stop()

# Load historical events once
if not st.session_state.historical_events_loaded:
    try:
        events = load_historical_events()
        if events:
            print(f"Loaded historical events for {len(events)} decades")
        st.session_state.historical_events_loaded = True
    except Exception as e:
        print(f"Error loading historical events: {e}")

# ============================================================================
# SECTION 17: MAIN APP HEADER
# ============================================================================
st.markdown(f"""
<div class="main-header">
    <img src="{LOGO_URL}" class="logo-img" alt="MemLife Logo">
    <h2 style="margin: 0; line-height: 1.2;">MemLife - Your Life Timeline</h2>
    <p style="font-size: 0.9rem; color: #666; margin: 0; line-height: 1.2;">Preserve Your Legacy • Build Your Timeline • Share Your Story</p>
</div>
""", unsafe_allow_html=True)

# ============================================================================
# SECTION 18: SIDEBAR - USER PROFILE AND SETTINGS
# ============================================================================
with st.sidebar:
    # User Profile Header with Account Info
    st.header("👤 Your Profile")
    
    # Show current user with account info
    if st.session_state.user_account:
        profile = st.session_state.user_account['profile']
        st.success(f"✓ **{profile['first_name']} {profile['last_name']}**")
        st.caption(f"📧 {profile['email']}")
        
        # Show birthdate and timeline info
        if profile.get('birthdate'):
            st.caption(f"🎂 Born: {profile['birthdate']}")
            
            # Show historical context note
            try:
                birth_year = int(profile['birthdate'].split(', ')[-1])
                events = get_events_for_birth_year(birth_year)
                if events:
                    uk_events = [e for e in events if e.get('region') == 'UK']
                    global_events = len(events) - len(uk_events)
                    st.caption(f"📚 {len(events)} historical events in your lifetime ({len(uk_events)} UK, {global_events} global)")
            except:
                pass
        else:
            st.caption("🎂 Birthdate: Not set")
        
        # Account type
        account_type = st.session_state.user_account['account_type']
        st.caption(f"👤 Account: {account_type.title()}")
        
        # Edit Profile Button
        if st.button("📝 Edit Profile", use_container_width=True):
            st.session_state.show_profile_setup = True
            st.rerun()
        
        # Logout Button
        if st.button("🚪 Log Out", use_container_width=True):
            logout_user()
    
    st.divider()
    
    # ============================================================================
    # STREAK SYSTEM DISPLAY
    # ============================================================================
    st.subheader("🔥 Writing Streak")
    
    streak_emoji = get_streak_emoji(st.session_state.streak_days)
    st.markdown(f"<div class='streak-flame'>{streak_emoji}</div>", unsafe_allow_html=True)
    st.markdown(f"**{st.session_state.streak_days} day streak**")
    st.caption(f"Total writing days: {st.session_state.total_writing_days}")
    
    # Show milestone badges
    if st.session_state.streak_days >= 7:
        st.success("🏆 Weekly Writer!")
    if st.session_state.streak_days >= 30:
        st.success("🌟 Monthly Master!")
    
    # Image Stats
    st.divider()
    st.subheader("🖼️ Photo Gallery")
    
    if st.session_state.logged_in:
        total_images = get_total_user_images(st.session_state.user_id)
        st.metric("Total Photos", total_images)
        
        # Quick image navigation
        if total_images > 0:
            if st.button("📸 View Photos", use_container_width=True):
                st.session_state.show_image_upload = True
                st.rerun()
        else:
            st.info("No photos yet")
    
    # Timeline Progress (if we have birthdate)
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            current_year = datetime.now().year
            age = current_year - birth_year
            
            if age > 0:
                total_possible_entries = age * 12
                actual_entries = sum(len(session.get("questions", {})) for session in st.session_state.responses.values())
                coverage = min(100, (actual_entries / total_possible_entries) * 500)
                
                st.divider()
                st.subheader("📅 Timeline Coverage")
                st.progress(coverage / 100)
                st.caption(f"{actual_entries} memories across {age} years")
        except:
            pass
    
    # Stats
    st.divider()
    st.subheader("📊 Your Progress")
    total_responses = sum(len(session.get("questions", {})) for session in st.session_state.responses.values())
    total_words = sum(calculate_author_word_count(s["id"]) for s in SESSIONS)
    
    st.metric("Total Responses", total_responses)
    st.metric("Total Words", total_words)
    
    # ============================================================================
    # JOT NOW FEATURE
    # ============================================================================
    st.divider()
    st.subheader("⚡ Quick Capture")
    
    with st.expander("💭 **Jot Now - Quick Memory**", expanded=False):
        quick_note = st.text_area(
            "Got a memory? Jot it down:",
            value="",
            height=120,
            placeholder="E.g., 'That summer at grandma's house in 1995...' or 'My first day at IBM in 2003'",
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
                st.session_state.prompt_index = (st.session_state.prompt_index + 1) % len(FALLBACK_PROMPTS)
                st.info("Ready to write about this!")
                st.rerun()
    
    # Show saved jots if any
    if st.session_state.get('quick_jots'):
        st.caption(f"📝 {len(st.session_state.quick_jots)} quick notes saved")
        if st.button("View Quick Notes", key="view_jots_btn"):
            st.session_state.show_jots = True
            st.rerun()
    
    # ============================================================================
    # INTERVIEW STYLE SETTINGS
    # ============================================================================
    st.divider()
    st.header("✍️ Interview Style")
    
    ghostwriter_mode = st.toggle(
        "Professional Ghostwriter Mode", 
        value=st.session_state.ghostwriter_mode,
        help="When enabled, the AI acts as a professional biographer using advanced interviewing techniques with historical context and photo integration.",
        key="ghostwriter_toggle"
    )
    
    if ghostwriter_mode != st.session_state.ghostwriter_mode:
        st.session_state.ghostwriter_mode = ghostwriter_mode
        st.rerun()
    
    spellcheck_enabled = st.toggle(
        "Auto Spelling Correction",
        value=st.session_state.spellcheck_enabled,
        help="Automatically correct spelling and grammar as you type",
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
    
    # ============================================================================
    # HISTORICAL EVENTS MANAGEMENT
    # ============================================================================
    st.divider()
    st.header("📜 Historical Context")
    
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            
            if events:
                st.success(f"✓ {len(events)} historical events loaded")
                st.caption(f"From {birth_year} to present")
                
                # Show sample events
                with st.expander("View Sample Events", expanded=False):
                    for i, event in enumerate(events[:5]):
                        region_emoji = "🇬🇧" if event.get('region') == 'UK' else "🌍"
                        st.markdown(f"**{region_emoji} {event['event']}**")
                        st.caption(f"{event['year_range']} • {event.get('category', 'General')}")
                        if i < 4:
                            st.divider()
                
                # Button to view all events
                if st.button("📋 View All Historical Events", key="view_all_events"):
                    st.session_state.show_event_manager = True
                    st.rerun()
            else:
                st.info("No historical events loaded")
        except:
            st.info("Add birthdate to see historical context")
    else:
        st.info("Add your birthdate to enable historical context")
    
    # ============================================================================
    # SESSION NAVIGATION
    # ============================================================================
    st.divider()
    st.header("📖 Sessions")
    
    for i, session in enumerate(SESSIONS):
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        
        # Calculate responses in this session
        responses_count = len(session_data.get("questions", {}))
        total_questions = len(session["questions"])
        
        # Determine session status
        if i == st.session_state.current_session:
            status = "▶️"
        elif responses_count == total_questions:
            status = "✅"
        elif responses_count > 0:
            status = "🟡"
        else:
            status = "●"
        
        button_text = f"{status} Session {session_id}: {session['title']} ({responses_count}/{total_questions})"
        
        if st.button(button_text, 
                    key=f"select_session_{i}",
                    use_container_width=True):
            st.session_state.current_session = i
            st.session_state.current_question = 0
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()
    
    # ============================================================================
    # TOPIC NAVIGATION
    # ============================================================================
    st.divider()
    st.subheader("Topic Navigation")
    
    current_session = SESSIONS[st.session_state.current_session]
    st.markdown(f'<div class="question-counter">Topic {st.session_state.current_question + 1} of {len(current_session["questions"])}</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous Topic", disabled=st.session_state.current_question == 0, key="prev_q_sidebar"):
            st.session_state.current_question = max(0, st.session_state.current_question - 1)
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()
    
    with col2:
        if st.button("Next Topic →", disabled=st.session_state.current_question >= len(current_session["questions"]) - 1, key="next_q_sidebar"):
            st.session_state.current_question = min(len(current_session["questions"]) - 1, st.session_state.current_question + 1)
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()
    
    st.divider()
    st.subheader("Session Navigation")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous Session", disabled=st.session_state.current_session == 0, key="prev_session_sidebar"):
            st.session_state.current_session = max(0, st.session_state.current_session - 1)
            st.session_state.current_question = 0
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()
    with col2:
        if st.button("Next Session →", disabled=st.session_state.current_session >= len(SESSIONS)-1, key="next_session_sidebar"):
            st.session_state.current_session = min(len(SESSIONS)-1, st.session_state.current_session + 1)
            st.session_state.current_question = 0
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()
    
    session_options = [f"Session {s['id']}: {s['title']}" for s in SESSIONS]
    selected_session = st.selectbox("Jump to session:", session_options, index=st.session_state.current_session, key="session_selectbox")
    if session_options.index(selected_session) != st.session_state.current_session:
        st.session_state.current_session = session_options.index(selected_session)
        st.session_state.current_question = 0
        st.session_state.editing = None
        st.session_state.current_question_override = None
        st.session_state.image_prompt_mode = False
        st.rerun()
    
    st.divider()
    
    # ============================================================================
    # SIMPLE EXPORT OPTIONS WITH IMAGES
    # ============================================================================
    st.subheader("📤 Export Options")
    
    total_answers = sum(len(session.get("questions", {})) for session in st.session_state.responses.values())
    total_images = get_total_user_images(st.session_state.user_id) if st.session_state.logged_in else 0
    
    st.caption(f"Total answers: {total_answers} • Total photos: {total_images}")
    
    if st.session_state.logged_in and st.session_state.user_id:
        # Prepare stories data
        export_data = {}
        for session in SESSIONS:
            session_id = session["id"]
            session_data = st.session_state.responses.get(session_id, {})
            if session_data.get("questions"):
                export_data[str(session_id)] = {
                    "title": session["title"],
                    "questions": session_data["questions"]
                }
        
        # Prepare images data
        image_data = {}
        for session in SESSIONS:
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
            # Create complete export data
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
            
            # Encode the data for URL
            encoded_data = base64.b64encode(json_data.encode()).decode()
            
            # Create URL with the data
            publisher_base_url = "https://deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/"
            publisher_url = f"{publisher_base_url}?data={encoded_data}"
            
            # Download buttons in columns
            col1, col2 = st.columns(2)
            
            with col1:
                # Stories-only JSON
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
                    key="download_stories_btn",
                    help="Download only the stories (text) as JSON"
                )
            
            with col2:
                # Complete data with images
                st.download_button(
                    label="📊 Complete Data",
                    data=json_data,
                    file_name=f"MemLife_Complete_{st.session_state.user_id}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="download_complete_btn",
                    help="Download stories + image metadata"
                )
            
            # Image export if there are images
            if total_images > 0:
                st.divider()
                st.write("**📸 Photo Export**")
                
                # Create simple image list
                all_images = []
                for session in SESSIONS:
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
            
            # Use HTML button instead of st.link_button
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
    
    # ============================================================================
    # DANGEROUS ACTIONS WITH CONFIRMATION
    # ============================================================================
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

# ============================================================================
# SECTION 19: HISTORICAL EVENTS VIEWER (IF REQUESTED)
# ============================================================================
if st.session_state.get('show_event_manager', False):
    st.markdown("---")
    st.subheader("📜 Historical Events in Your Lifetime")
    
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            
            if events:
                st.info(f"**Born {birth_year}** - {len(events)} historical events from your lifetime")
                
                # Filter options
                col1, col2, col3 = st.columns(3)
                with col1:
                    show_uk = st.checkbox("UK Events", value=True, key="filter_uk")
                with col2:
                    show_global = st.checkbox("Global Events", value=True, key="filter_global")
                with col3:
                    category_filter = st.selectbox("Category", ["All"] + list(set(e.get('category', 'General') for e in events)))
                
                # Filter events
                filtered_events = []
                for event in events:
                    if show_uk and event.get('region') == 'UK':
                        if category_filter == "All" or event.get('category', 'General') == category_filter:
                            filtered_events.append(event)
                    elif show_global and event.get('region') != 'UK':
                        if category_filter == "All" or event.get('category', 'General') == category_filter:
                            filtered_events.append(event)
                
                # Display events
                for i, event in enumerate(filtered_events):
                    region_emoji = "🇬🇧" if event.get('region') == 'UK' else "🌍"
                    with st.expander(f"{region_emoji} {event['event']} ({event['year_range']})", expanded=False):
                        st.markdown(f"**Category:** {event.get('category', 'General')}")
                        if 'approx_age' in event:
                            st.markdown(f"**Your age:** {event['approx_age']} years old")
                        if event.get('description'):
                            st.markdown(f"**Description:** {event['description']}")
                
                st.divider()
                st.caption("These events are automatically integrated into your interview prompts to provide historical context.")
            else:
                st.warning("No historical events found for your birth year.")
        except Exception as e:
            st.error(f"Error loading historical events: {e}")
    else:
        st.warning("Please add your birthdate to view historical events.")
    
    if st.button("Close Event Viewer", key="close_events_btn"):
        st.session_state.show_event_manager = False
        st.rerun()
    
    st.markdown("---")

# ============================================================================
# SECTION 20: QUICK NOTES VIEWER (IF REQUESTED)
# ============================================================================
if st.session_state.get('show_jots', False) and st.session_state.quick_jots:
    st.markdown("---")
    st.subheader("📝 Your Quick Notes")
    
    for i, jot in enumerate(st.session_state.quick_jots):
        with st.expander(f"Note {i+1} - {jot.get('year', 'No year')} - {jot['word_count']} words", expanded=False):
            st.markdown(f'<div class="jot-box">{jot["text"]}</div>', unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                if st.button(f"✏️ Use as Prompt", key=f"use_jot_{i}"):
                    st.session_state.current_question_override = jot["text"]
                    st.session_state.show_jots = False
                    st.rerun()
            with col2:
                if st.button(f"🗑️ Delete", key=f"delete_jot_{i}"):
                    st.session_state.quick_jots.pop(i)
                    st.rerun()
    
    if st.button("Close Quick Notes", key="close_jots_btn"):
        st.session_state.show_jots = False
        st.rerun()
    
    st.markdown("---")

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
