# biographer.py – Novel Writing App (REPLACES your old app)
import streamlit as st
import pandas as pd
import json
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta
import hashlib
import time

# ============================================================================
# AUTO-CREATE TEMPLATE FILES ON STARTUP
# ============================================================================

def create_template_files():
    """Create template CSV files if they don't exist"""
    templates_dir = "novel_templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    # Fantasy template
    fantasy_data = {
        "chapter_id": [1, 2, 3, 4, 5],
        "title": [
            "The Ordinary World",
            "The Call to Adventure", 
            "Meeting the Mentor",
            "Crossing the Threshold",
            "Tests, Allies, Enemies"
        ],
        "guidance": [
            "Introduce your protagonist in their normal life",
            "What disrupts their ordinary world?",
            "Who provides guidance or magical aid?",
            "The point of no return into the special world",
            "Early challenges and new relationships"
        ],
        "word_target": [2000, 2500, 2000, 2500, 3000]
    }
    
    # Mystery template  
    mystery_data = {
        "chapter_id": [1, 2, 3, 4, 5],
        "title": [
            "The Crime Scene",
            "The Detective Arrives",
            "First Clues",
            "Suspect Interviews", 
            "The Investigation Deepens"
        ],
        "guidance": [
            "Introduce the crime or mystery",
            "Introduce your sleuth",
            "Plant clues and red herrings",
            "Interview key characters",
            "Raise stakes and deepen mystery"
        ],
        "word_target": [2000, 2500, 3000, 2800, 3200]
    }
    
    # Romance template
    romance_data = {
        "chapter_id": [1, 2, 3, 4, 5],
        "title": [
            "The Meet-Cute",
            "First Impressions", 
            "Growing Connection",
            "First Date/Kiss",
            "The Conflict"
        ],
        "guidance": [
            "How do your protagonists meet?",
            "Initial attraction and/or conflict",
            "Shared experiences that bring them closer",
            "First romantic milestone",
            "What stands in their way?"
        ],
        "word_target": [2000, 2500, 3000, 2800, 3200]
    }
    
    # Save all templates
    pd.DataFrame(fantasy_data).to_csv(f"{templates_dir}/fantasy_novel_template.csv", index=False)
    pd.DataFrame(mystery_data).to_csv(f"{templates_dir}/mystery_novel_template.csv", index=False) 
    pd.DataFrame(romance_data).to_csv(f"{templates_dir}/romance_novel_template.csv", index=False)
    
    return True

# Create templates on startup
create_template_files()

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="NovelCraft - Your Novel Writing Studio",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load CSS
try:
    with open("styles.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except:
    st.markdown("""
    <style>
    .novel-header { background: linear-gradient(135deg, #1a237e 0%, #4a148c 100%); color: white; padding: 2rem; border-radius: 10px; margin-bottom: 2rem; }
    .chapter-card { background: #f5f5f5; border-left: 4px solid #673ab7; padding: 1rem; margin: 0.5rem 0; border-radius: 5px; }
    .writing-area { background: #fff; border: 2px solid #e0e0e0; border-radius: 10px; padding: 1.5rem; margin: 1rem 0; }
    </style>
    """, unsafe_allow_html=True)

# ============================================================================
# DATA MANAGEMENT
# ============================================================================

class NovelData:
    def __init__(self, user_id="default"):
        self.user_id = user_id
        self.data_dir = "novel_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.novel_file = f"{self.data_dir}/{user_id}_novel.json"
        
    def create_new_novel(self, title, genre, target_word_count=80000):
        novel_data = {
            "id": hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()[:8],
            "title": title,
            "genre": genre,
            "target_word_count": target_word_count,
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "chapters": [],
            "characters": [],
            "settings": {
                "auto_save": True,
                "daily_word_goal": 1000
            },
            "stats": {
                "total_words": 0,
                "writing_streak": 0,
                "chapters_completed": 0
            }
        }
        self.save_novel(novel_data)
        return novel_data
    
    def load_novel(self):
        """Load novel data from file"""
        if os.path.exists(self.novel_file):
            try:
                with open(self.novel_file, 'r') as f:
                    return json.load(f)
            except:
                return None
        return None
    
    def save_novel(self, novel_data):
        """Save novel data to file"""
        if novel_data:
            novel_data["modified"] = datetime.now().isoformat()
            with open(self.novel_file, 'w') as f:
                json.dump(novel_data, f, indent=2)
            return True
        return False
    
    def add_chapter(self, chapter_data):
        """Add a new chapter to the novel"""
        novel = self.load_novel()
        if novel:
            chapter_id = len(novel["chapters"]) + 1
            chapter_data["id"] = chapter_id
            chapter_data["created"] = datetime.now().isoformat()
            chapter_data["word_count"] = len(str(chapter_data.get("content", "")).split())
            
            novel["chapters"].append(chapter_data)
            novel["stats"]["total_words"] = sum(c.get("word_count", 0) for c in novel["chapters"])
            
            self.save_novel(novel)
            return chapter_id
        return None
    
    def update_chapter(self, chapter_id, updates):
        """Update an existing chapter"""
        novel = self.load_novel()
        if novel and novel.get("chapters"):
            chapter_index = chapter_id - 1
            if 0 <= chapter_index < len(novel["chapters"]):
                novel["chapters"][chapter_index].update(updates)
                
                if "content" in updates:
                    content = updates["content"]
                    novel["chapters"][chapter_index]["word_count"] = len(str(content).split())
                
                novel["stats"]["total_words"] = sum(c.get("word_count", 0) for c in novel["chapters"])
                
                self.save_novel(novel)
                return True
        return False
    
    def add_character(self, character_data):
        """Add a new character to the novel"""
        novel = self.load_novel()
        if novel:
            character_id = len(novel["characters"]) + 1
            character_data["id"] = character_id
            novel["characters"].append(character_data)
            self.save_novel(novel)
            return character_id
        return None

# ============================================================================
# TEMPLATE LOADER
# ============================================================================

class TemplateLoader:
    def __init__(self):
        self.templates_dir = "novel_templates"
        os.makedirs(self.templates_dir, exist_ok=True)
    
    def load_template(self, genre):
        """Load template for specific genre"""
        file_path = f"{self.templates_dir}/{genre}_novel_template.csv"
        if os.path.exists(file_path):
            return pd.read_csv(file_path)
        return None
    
    def get_available_templates(self):
        """Get list of available template genres"""
        templates = []
        for file in os.listdir(self.templates_dir):
            if file.endswith("_novel_template.csv"):
                genre = file.replace("_novel_template.csv", "")
                templates.append(genre)
        return sorted(templates)

# ============================================================================
# SIMPLE UI COMPONENTS
# ============================================================================

def show_novel_creation(data_manager):
    """Show novel creation screen"""
    st.title("📖 Welcome to NovelCraft")
    st.markdown("### Start Your Writing Journey")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.form("new_novel_form"):
            title = st.text_input("Novel Title", placeholder="e.g., 'Whispers of the Lost City'")
            genre = st.selectbox("Genre", ["Fantasy", "Mystery", "Romance", "Science Fiction", "Thriller"])
            target_words = st.number_input("Target Word Count", min_value=10000, max_value=200000, value=80000, step=5000)
            
            if st.form_submit_button("Create Novel", type="primary", use_container_width=True):
                if title:
                    new_novel = data_manager.create_new_novel(title, genre, target_words)
                    st.success(f"Novel '{title}' created!")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
    
    with col2:
        st.info("""
        **NovelCraft Features:**
        - 📝 Chapter-based writing
        - 👥 Character management  
        - 📈 Progress tracking
        - 🎯 Word count goals
        - 💾 Auto-save functionality
        
        Start by giving your novel a title!
        """)
    
    return False

def show_main_app(data_manager):
    """Show main writing interface"""
    novel = data_manager.load_novel()
    if not novel:
        return False
    
    # Header
    progress = 0
    if novel.get("target_word_count", 0) > 0:
        progress = (novel["stats"]["total_words"] / novel["target_word_count"]) * 100
    progress = min(progress, 100)
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"## 📖 {novel['title']}")
        st.caption(f"Genre: {novel['genre']} | {novel['stats']['total_words']:,} words written")
    with col2:
        st.metric("Chapters", len(novel.get("chapters", [])))
    with col3:
        st.metric("Progress", f"{progress:.0f}%")
        st.progress(progress / 100)
    
    # Sidebar
    with st.sidebar:
        st.title("📚 Chapters")
        
        # Chapter list
        if novel.get("chapters"):
            for i, chapter in enumerate(novel["chapters"]):
                status = "▶️" if i == st.session_state.current_chapter else "○"
                if st.button(f"{status} {chapter.get('title', f'Chapter {i+1}')}", 
                           key=f"ch_{i}", use_container_width=True):
                    st.session_state.current_chapter = i
                    st.rerun()
        
        st.divider()
        
        # Add chapter button
        if st.button("➕ Add Chapter", use_container_width=True, type="primary"):
            show_add_chapter_modal(data_manager)
        
        st.divider()
        
        # Characters
        st.subheader("👥 Characters")
        if novel.get("characters"):
            for char in novel["characters"]:
                st.write(f"• {char.get('name', 'Unnamed')}")
        if st.button("Add Character", key="add_char_btn"):
            show_add_character_modal(data_manager)
    
    # Main writing area
    if novel.get("chapters"):
        show_chapter_writing(data_manager, st.session_state.current_chapter)
    else:
        st.info("Click 'Add Chapter' to start writing!")
    
    return True

def show_chapter_writing(data_manager, chapter_index):
    """Show writing interface for a chapter"""
    novel = data_manager.load_novel()
    if not novel or chapter_index >= len(novel.get("chapters", [])):
        return
    
    chapter = novel["chapters"][chapter_index]
    
    st.markdown(f"### 📝 {chapter.get('title', f'Chapter {chapter_index + 1}')}")
    
    if chapter.get("guidance"):
        st.info(chapter.get("guidance"))
    
    # Word count
    word_count = chapter.get("word_count", 0)
    st.caption(f"Words: {word_count}")
    
    # Writing area
    content = st.text_area(
        "Write your chapter here...",
        value=chapter.get("content", ""),
        height=400,
        key=f"chapter_content_{chapter_index}",
        placeholder="Begin writing...",
        label_visibility="collapsed"
    )
    
    # Save button
    if st.button("💾 Save Chapter", type="primary"):
        if content != chapter.get("content", ""):
            data_manager.update_chapter(chapter_index + 1, {"content": content})
            st.success("Saved!")
            time.sleep(0.5)
            st.rerun()
    
    # Notes
    with st.expander("📋 Chapter Notes"):
        notes = st.text_area(
            "Notes",
            value=chapter.get("notes", ""),
            height=100,
            key=f"chapter_notes_{chapter_index}"
        )
        if notes != chapter.get("notes", ""):
            data_manager.update_chapter(chapter_index + 1, {"notes": notes})

def show_add_chapter_modal(data_manager):
    """Show modal for adding a new chapter"""
    novel = data_manager.load_novel()
    
    with st.form("add_chapter_form"):
        st.subheader("Add New Chapter")
        
        title = st.text_input("Chapter Title", placeholder="e.g., 'The Journey Begins'")
        guidance = st.text_area("Guidance", placeholder="What should this chapter accomplish?", height=100)
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Add Chapter", type="primary")
        with col2:
            cancel = st.form_submit_button("Cancel")
        
        if submit and title:
            chapter_data = {
                "title": title,
                "guidance": guidance,
                "content": "",
                "notes": "",
                "word_target": 2500
            }
            
            chapter_id = data_manager.add_chapter(chapter_data)
            if chapter_id:
                st.session_state.current_chapter = chapter_id - 1
                st.success(f"Chapter '{title}' added!")
                time.sleep(0.5)
                st.rerun()

def show_add_character_modal(data_manager):
    """Show modal for adding a new character"""
    with st.form("add_character_form"):
        st.subheader("Add Character")
        
        name = st.text_input("Name")
        role = st.selectbox("Role", ["Protagonist", "Antagonist", "Supporting"])
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Add", type="primary")
        with col2:
            cancel = st.form_submit_button("Cancel")
        
        if submit and name:
            character_data = {
                "name": name,
                "role": role
            }
            
            data_manager.add_character(character_data)
            st.success(f"Character '{name}' added!")
            time.sleep(0.5)
            st.rerun()

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # Initialize session state
    if "user_id" not in st.session_state:
        st.session_state.user_id = "user_001"
    
    if "current_chapter" not in st.session_state:
        st.session_state.current_chapter = 0
    
    # Initialize data manager
    data_manager = NovelData(st.session_state.user_id)
    novel = data_manager.load_novel()
    
    # Show appropriate screen
    if not novel:
        show_novel_creation(data_manager)
    else:
        show_main_app(data_manager)

if __name__ == "__main__":
    main()
