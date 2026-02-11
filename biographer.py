# biographer.py – Novel Writing App (FIXED FORM VERSION)
import streamlit as st
import pandas as pd
import json
import os
import hashlib
from datetime import datetime
import time

# ============================================================================
# AUTO-CREATE TEMPLATE FILES ON STARTUP
# ============================================================================

def create_template_files():
    """Create template CSV files if they don't exist"""
    templates_dir = "novel_templates"
    os.makedirs(templates_dir, exist_ok=True)
    
    # Simple templates
    fantasy_data = {
        "chapter_id": [1, 2, 3],
        "title": ["The Beginning", "The Journey", "The Challenge"],
        "guidance": ["Start your story", "Move the plot forward", "Add conflict"],
        "word_target": [2000, 2500, 3000]
    }
    
    pd.DataFrame(fantasy_data).to_csv(f"{templates_dir}/fantasy_novel_template.csv", index=False)
    
    return True

create_template_files()

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="NovelCraft",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# DATA MANAGEMENT (SIMPLE VERSION)
# ============================================================================

class NovelData:
    def __init__(self, user_id="default"):
        self.user_id = user_id
        self.data_dir = "novel_data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.novel_file = f"{self.data_dir}/{user_id}_novel.json"
    
    def create_new_novel(self, title, genre):
        """Create a new novel"""
        novel_data = {
            "id": hashlib.md5(f"{title}{datetime.now()}".encode()).hexdigest()[:8],
            "title": title,
            "genre": genre,
            "created": datetime.now().isoformat(),
            "chapters": [],
            "characters": [],
            "stats": {"total_words": 0}
        }
        return self._save_novel(novel_data)
    
    def load_novel(self):
        """Load novel data"""
        if os.path.exists(self.novel_file):
            try:
                with open(self.novel_file, 'r') as f:
                    return json.load(f)
            except:
                return None
        return None
    
    def _save_novel(self, novel_data):
        """Save novel data"""
        with open(self.novel_file, 'w') as f:
            json.dump(novel_data, f, indent=2)
        return novel_data
    
    def add_chapter(self, title, guidance=""):
        """Add a new chapter - SIMPLE VERSION"""
        novel = self.load_novel()
        if novel:
            chapter_id = len(novel["chapters"]) + 1
            chapter_data = {
                "id": chapter_id,
                "title": title,
                "guidance": guidance,
                "content": "",
                "notes": "",
                "word_count": 0,
                "created": datetime.now().isoformat()
            }
            novel["chapters"].append(chapter_data)
            self._save_novel(novel)
            return chapter_id
        return None
    
    def update_chapter_content(self, chapter_index, content):
        """Update chapter content"""
        novel = self.load_novel()
        if novel and 0 <= chapter_index < len(novel["chapters"]):
            novel["chapters"][chapter_index]["content"] = content
            novel["chapters"][chapter_index]["word_count"] = len(content.split())
            novel["stats"]["total_words"] = sum(c.get("word_count", 0) for c in novel["chapters"])
            self._save_novel(novel)
            return True
        return False
    
    def add_character(self, name, role=""):
        """Add a new character - SIMPLE VERSION"""
        novel = self.load_novel()
        if novel:
            character_id = len(novel["characters"]) + 1
            character_data = {
                "id": character_id,
                "name": name,
                "role": role,
                "created": datetime.now().isoformat()
            }
            novel["characters"].append(character_data)
            self._save_novel(novel)
            return character_id
        return None

# ============================================================================
# MAIN APP WITH WORKING FORMS
# ============================================================================

def main():
    # Initialize session state
    if "user_id" not in st.session_state:
        st.session_state.user_id = "user_001"
    
    if "current_chapter" not in st.session_state:
        st.session_state.current_chapter = 0
    
    if "show_add_chapter" not in st.session_state:
        st.session_state.show_add_chapter = False
    
    if "show_add_character" not in st.session_state:
        st.session_state.show_add_character = False
    
    # Initialize data manager
    data_manager = NovelData(st.session_state.user_id)
    novel = data_manager.load_novel()
    
    # ========== NOVEL CREATION SCREEN ==========
    if not novel:
        st.title("📖 Create Your Novel")
        
        with st.form("create_novel_form"):
            title = st.text_input("Novel Title", placeholder="My Awesome Novel")
            genre = st.selectbox("Genre", ["Fantasy", "Mystery", "Romance", "Sci-Fi", "General"])
            
            submitted = st.form_submit_button("Create Novel", type="primary")
            
            if submitted:
                if title:
                    data_manager.create_new_novel(title, genre)
                    st.success(f"Novel '{title}' created!")
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please enter a title")
        
        st.stop()
    
    # ========== MAIN APP SCREEN ==========
    
    # Header
    st.title(f"📖 {novel['title']}")
    st.caption(f"Genre: {novel['genre']} | Created: {datetime.fromisoformat(novel['created']).strftime('%b %d, %Y')}")
    
    # Sidebar
    with st.sidebar:
        st.header("📚 Chapters")
        
        # Chapter list
        if novel["chapters"]:
            for i, chapter in enumerate(novel["chapters"]):
                title = chapter.get("title", f"Chapter {i+1}")
                status = "▶️" if i == st.session_state.current_chapter else "○"
                
                if st.button(f"{status} {title}", key=f"ch_btn_{i}", use_container_width=True):
                    st.session_state.current_chapter = i
                    st.rerun()
        else:
            st.info("No chapters yet")
        
        st.divider()
        
        # Add Chapter Button
        if st.button("➕ Add Chapter", key="add_chapter_btn", use_container_width=True, type="primary"):
            st.session_state.show_add_chapter = True
            st.rerun()
        
        st.divider()
        
        # Characters section
        st.header("👥 Characters")
        
        if novel["characters"]:
            for char in novel["characters"]:
                st.write(f"• {char.get('name', 'Unnamed')} ({char.get('role', 'Character')})")
        else:
            st.info("No characters yet")
        
        if st.button("➕ Add Character", key="add_char_btn", use_container_width=True):
            st.session_state.show_add_character = True
            st.rerun()
    
    # ========== ADD CHAPTER MODAL ==========
    if st.session_state.show_add_chapter:
        st.markdown("---")
        st.subheader("Add New Chapter")
        
        with st.form("add_chapter_form"):
            title = st.text_input("Chapter Title", key="new_chapter_title")
            guidance = st.text_area("Guidance/Notes", key="new_chapter_guidance", height=100)
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Add Chapter", type="primary", use_container_width=True)
            with col2:
                cancel = st.form_submit_button("Cancel", use_container_width=True)
            
            if submit:
                if title:
                    chapter_id = data_manager.add_chapter(title, guidance)
                    if chapter_id:
                        st.session_state.current_chapter = chapter_id - 1
                        st.session_state.show_add_chapter = False
                        st.success(f"Chapter '{title}' added!")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.error("Please enter a chapter title")
            
            if cancel:
                st.session_state.show_add_chapter = False
                st.rerun()
        
        st.stop()  # Stop rendering rest of app when modal is open
    
    # ========== ADD CHARACTER MODAL ==========
    if st.session_state.show_add_character:
        st.markdown("---")
        st.subheader("Add New Character")
        
        with st.form("add_character_form"):
            name = st.text_input("Character Name", key="new_char_name")
            role = st.selectbox("Role", ["", "Protagonist", "Antagonist", "Supporting", "Love Interest"], key="new_char_role")
            
            col1, col2 = st.columns(2)
            with col1:
                submit = st.form_submit_button("Add Character", type="primary", use_container_width=True)
            with col2:
                cancel = st.form_submit_button("Cancel", use_container_width=True)
            
            if submit:
                if name:
                    character_id = data_manager.add_character(name, role)
                    if character_id:
                        st.session_state.show_add_character = False
                        st.success(f"Character '{name}' added!")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.error("Please enter a character name")
            
            if cancel:
                st.session_state.show_add_character = False
                st.rerun()
        
        st.stop()  # Stop rendering rest of app when modal is open
    
    # ========== MAIN WRITING AREA ==========
    if novel["chapters"]:
        chapter_index = st.session_state.current_chapter
        if 0 <= chapter_index < len(novel["chapters"]):
            chapter = novel["chapters"][chapter_index]
            
            st.subheader(f"📝 {chapter.get('title', f'Chapter {chapter_index + 1}')}")
            
            # Word count
            word_count = chapter.get("word_count", 0)
            st.caption(f"Words: {word_count}")
            
            # Guidance
            if chapter.get("guidance"):
                st.info(f"**Guidance:** {chapter.get('guidance')}")
            
            # Writing area
            content = st.text_area(
                "Write your chapter here...",
                value=chapter.get("content", ""),
                height=400,
                key=f"editor_{chapter_index}",
                placeholder="Begin writing your chapter...",
                label_visibility="collapsed"
            )
            
            # Save button
            if st.button("💾 Save Chapter", type="primary"):
                if content != chapter.get("content", ""):
                    if data_manager.update_chapter_content(chapter_index, content):
                        st.success("Chapter saved!")
                        time.sleep(0.5)
                        st.rerun()
            
            # Notes section
            with st.expander("📝 Chapter Notes"):
                st.write("Add any notes or ideas for this chapter")
        else:
            st.info("Select a chapter from the sidebar")
    else:
        st.info("Click 'Add Chapter' in the sidebar to start writing!")

if __name__ == "__main__":
    main()
