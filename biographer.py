# novel_app.py - Standalone Novel Writing Application
import streamlit as st
import pandas as pd
import json
import os
import plotly.graph_objects as go
from datetime import datetime, timedelta
import hashlib
import time

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
            "locations": [],
            "plot_points": [],
            "settings": {
                "auto_save": True,
                "focus_mode": False,
                "daily_word_goal": 1000,
                "theme": "light"
            },
            "stats": {
                "total_words": 0,
                "writing_streak": 0,
                "last_write_date": None,
                "chapters_completed": 0,
                "writing_sessions": 0
            }
        }
        self.save_novel(novel_data)
        return novel_data
    
    def load_novel(self):
        if os.path.exists(self.novel_file):
            with open(self.novel_file, 'r') as f:
                return json.load(f)
        return None
    
    def save_novel(self, novel_data):
        novel_data["modified"] = datetime.now().isoformat()
        with open(self.novel_file, 'w') as f:
            json.dump(novel_data, f, indent=2)
        return True
    
    def add_chapter(self, chapter_data):
        novel = self.load_novel()
        if novel:
            # Generate chapter ID
            chapter_id = len(novel["chapters"]) + 1
            chapter_data["id"] = chapter_id
            chapter_data["created"] = datetime.now().isoformat()
            chapter_data["modified"] = datetime.now().isoformat()
            chapter_data["word_count"] = len(chapter_data.get("content", "").split())
            
            novel["chapters"].append(chapter_data)
            
            # Update stats
            novel["stats"]["total_words"] = sum(c.get("word_count", 0) for c in novel["chapters"])
            novel["stats"]["chapters_completed"] = len([c for c in novel["chapters"] if c.get("completed", False)])
            
            self.save_novel(novel)
            return chapter_id
        return None
    
    def update_chapter(self, chapter_id, updates):
        novel = self.load_novel()
        if novel and 0 <= chapter_id - 1 < len(novel["chapters"]):
            novel["chapters"][chapter_id - 1].update(updates)
            novel["chapters"][chapter_id - 1]["modified"] = datetime.now().isoformat()
            novel["chapters"][chapter_id - 1]["word_count"] = len(updates.get("content", "").split())
            
            # Update stats
            novel["stats"]["total_words"] = sum(c.get("word_count", 0) for c in novel["chapters"])
            self.save_novel(novel)
            return True
        return False
    
    def add_character(self, character_data):
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
        self.create_default_templates()
    
    def create_default_templates(self):
        templates = {
            "fantasy": {
                "name": "Fantasy Epic",
                "chapters": [
                    {"title": "The Ordinary World", "guidance": "Introduce your protagonist in their normal life before the adventure begins.", "word_target": 2500},
                    {"title": "The Call to Adventure", "guidance": "The moment everything changes. What disrupts the ordinary world?", "word_target": 3000},
                    {"title": "Refusal of the Call", "guidance": "Why does your protagonist hesitate or resist the journey?", "word_target": 2000},
                    {"title": "Meeting the Mentor", "guidance": "Who provides guidance, training, or magical aid?", "word_target": 2500},
                    {"title": "Crossing the Threshold", "guidance": "The point of no return. Entering the special world.", "word_target": 3000}
                ]
            },
            "mystery": {
                "name": "Mystery/Thriller",
                "chapters": [
                    {"title": "The Crime Scene", "guidance": "Introduce the crime or mystery. Show, don't tell.", "word_target": 2000},
                    {"title": "The Detective Arrives", "guidance": "Introduce your sleuth. Show their unique approach.", "word_target": 2500},
                    {"title": "First Clues", "guidance": "Plant clues and red herrings. Introduce suspects.", "word_target": 3000},
                    {"title": "The Investigation Deepens", "guidance": "Raise stakes. Personal connection to detective?", "word_target": 3000},
                    {"title": "The Twist", "guidance": "Unexpected revelation that changes everything.", "word_target": 2500}
                ]
            },
            "romance": {
                "name": "Contemporary Romance",
                "chapters": [
                    {"title": "The Meet-Cute", "guidance": "How do your protagonists first encounter each other?", "word_target": 2000},
                    {"title": "First Impressions", "guidance": "Initial attraction and/or conflict. Chemistry!", "word_target": 2500},
                    {"title": "Growing Connection", "guidance": "Shared experiences that bring them closer.", "word_target": 3000},
                    {"title": "The Conflict", "guidance": "What stands in their way? Internal or external?", "word_target": 3000},
                    {"title": "The Resolution", "guidance": "How do they overcome obstacles?", "word_target": 2500}
                ]
            }
        }
        
        for genre, template in templates.items():
            df = pd.DataFrame(template["chapters"])
            df["chapter_id"] = range(1, len(df) + 1)
            df.to_csv(f"{self.templates_dir}/{genre}_novel_template.csv", index=False)
    
    def load_template(self, genre):
        file_path = f"{self.templates_dir}/{genre}_novel_template.csv"
        if os.path.exists(file_path):
            return pd.read_csv(file_path)
        return None
    
    def get_available_templates(self):
        templates = []
        for file in os.listdir(self.templates_dir):
            if file.endswith("_template.csv"):
                genre = file.replace("_novel_template.csv", "")
                templates.append(genre)
        return templates

# ============================================================================
# UI COMPONENTS
# ============================================================================

def render_novel_header(novel_data):
    if not novel_data:
        return
    
    progress = (novel_data["stats"]["total_words"] / novel_data["target_word_count"]) * 100
    progress = min(progress, 100)
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        st.markdown(f"""
        <div class="novel-header">
        <h1>📖 {novel_data['title']}</h1>
        <p>Genre: {novel_data['genre'].title()} | Created: {datetime.fromisoformat(novel_data['created']).strftime('%B %d, %Y')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("Total Words", f"{novel_data['stats']['total_words']:,}")
        st.caption(f"Target: {novel_data['target_word_count']:,}")
    
    with col3:
        st.metric("Progress", f"{progress:.1f}%")
        st.progress(progress / 100)

def render_chapter_navigation(novel_data, current_chapter):
    if not novel_data or not novel_data.get("chapters"):
        st.info("No chapters yet. Create your first chapter!")
        return
    
    st.subheader("📚 Chapters")
    
    for i, chapter in enumerate(novel_data["chapters"]):
        status = "▶️" if i == current_chapter else ("✓" if chapter.get("completed", False) else "○")
        word_count = chapter.get("word_count", 0)
        
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            st.write(f"**{status} Ch. {i+1}**")
        with col2:
            title = chapter.get("title", f"Chapter {i+1}")
            st.write(title)
        with col3:
            st.caption(f"{word_count:,}w")
        
        if st.button(f"Select Chapter {i+1}", key=f"select_ch_{i}", use_container_width=True):
            st.session_state.current_chapter = i
            st.rerun()
        
        st.divider()
    
    if st.button("➕ Add New Chapter", use_container_width=True):
        st.session_state.show_new_chapter_modal = True
        st.rerun()

def render_writing_interface(novel_data, chapter_index):
    if not novel_data or chapter_index >= len(novel_data["chapters"]):
        st.warning("Select or create a chapter to start writing")
        return
    
    chapter = novel_data["chapters"][chapter_index]
    
    # Chapter header
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"## 📝 Chapter {chapter_index + 1}: {chapter.get('title', 'Untitled')}")
    with col2:
        word_count = chapter.get("word_count", 0)
        st.metric("Words", word_count)
    with col3:
        completed = st.checkbox("Mark Complete", value=chapter.get("completed", False), 
                               key=f"complete_ch_{chapter_index}")
        if completed != chapter.get("completed", False):
            novel_data["chapters"][chapter_index]["completed"] = completed
            novel_data.save_novel(novel_data)
    
    # Chapter guidance
    if chapter.get("guidance"):
        st.info(f"**Chapter Guidance:** {chapter.get('guidance')}")
    
    # Writing area
    content = st.text_area(
        "Write your chapter here...",
        value=chapter.get("content", ""),
        height=400,
        key=f"chapter_content_{chapter_index}",
        placeholder="Begin your chapter...",
        label_visibility="collapsed"
    )
    
    # Save button
    if st.button("💾 Save Chapter", type="primary", use_container_width=True):
        if content != chapter.get("content", ""):
            novel_data.update_chapter(chapter_index + 1, {"content": content})
            st.success("Chapter saved!")
            time.sleep(0.5)
            st.rerun()
    
    # Chapter notes
    with st.expander("📋 Chapter Notes & Planning"):
        notes = st.text_area(
            "Notes for this chapter",
            value=chapter.get("notes", ""),
            height=150,
            key=f"chapter_notes_{chapter_index}",
            placeholder="Plot points, character developments, research notes..."
        )
        if notes != chapter.get("notes", ""):
            novel_data.update_chapter(chapter_index + 1, {"notes": notes})

def render_character_panel(novel_data):
    st.subheader("👥 Characters")
    
    if novel_data.get("characters"):
        for char in novel_data["characters"]:
            with st.expander(f"{char.get('name', 'Unnamed')} - {char.get('role', 'Character')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Age:** {char.get('age', 'Not specified')}")
                    st.write(f"**Occupation:** {char.get('occupation', 'Not specified')}")
                with col2:
                    st.write(f"**Personality:** {char.get('personality', 'Not specified')}")
                    st.write(f"**Motivation:** {char.get('motivation', 'Not specified')}")
                st.write(f"**Background:** {char.get('background', 'Not specified')}")
    
    if st.button("➕ Add Character", key="add_character"):
        st.session_state.show_character_modal = True
        st.rerun()

def render_plot_tracker(novel_data):
    st.subheader("📈 Plot Progress")
    
    if not novel_data.get("chapters"):
        st.info("Write some chapters to track your plot")
        return
    
    # Create a simple plot arc visualization
    chapters = novel_data["chapters"]
    tension_levels = []
    
    for i, chapter in enumerate(chapters):
        # Simulate tension level based on chapter position
        if i < len(chapters) * 0.25:
            tension = 30 + (i / len(chapters)) * 70  # Rising
        elif i < len(chapters) * 0.75:
            tension = 70 + ((i - len(chapters)*0.25) / (len(chapters)*0.5)) * 20  # Climax
        else:
            tension = 90 - ((i - len(chapters)*0.75) / (len(chapters)*0.25)) * 60  # Resolution
        
        tension_levels.append(tension)
    
    # Plot using Plotly
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=list(range(1, len(tension_levels) + 1)),
        y=tension_levels,
        mode='lines+markers',
        name='Story Tension',
        line=dict(color='#673ab7', width=3),
        marker=dict(size=8)
    ))
    
    # Add story beat annotations
    if len(chapters) >= 3:
        beats = [
            (1, "Inciting Incident"),
            (max(1, len(chapters)//4), "First Plot Point"),
            (len(chapters)//2, "Midpoint"),
            (max(len(chapters)//2 + 1, len(chapters)*3//4), "Climax"),
            (len(chapters), "Resolution")
        ]
        
        for x_pos, label in beats:
            if x_pos <= len(chapters):
                fig.add_annotation(
                    x=x_pos,
                    y=tension_levels[x_pos-1] if x_pos <= len(tension_levels) else 50,
                    text=label,
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=2,
                    arrowcolor="#ff9800"
                )
    
    fig.update_layout(
        title="Story Arc Visualization",
        xaxis_title="Chapter",
        yaxis_title="Tension Level",
        height=300,
        showlegend=False,
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Word count by chapter
    if chapters:
        word_counts = [c.get("word_count", 0) for c in chapters]
        
        fig2 = go.Figure(data=[go.Bar(
            x=list(range(1, len(word_counts) + 1)),
            y=word_counts,
            marker_color='#4caf50'
        )])
        
        fig2.update_layout(
            title="Word Count by Chapter",
            xaxis_title="Chapter",
            yaxis_title="Words",
            height=250,
            showlegend=False
        )
        
        st.plotly_chart(fig2, use_container_width=True)

def render_new_chapter_modal():
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    st.subheader("➕ Create New Chapter")
    
    with st.form("new_chapter_form"):
        title = st.text_input("Chapter Title", placeholder="e.g., 'The Journey Begins'")
        
        col1, col2 = st.columns(2)
        with col1:
            word_target = st.number_input("Word Target", min_value=500, max_value=10000, value=2500)
        with col2:
            template_loader = TemplateLoader()
            templates = template_loader.get_available_templates()
            use_template = st.selectbox("Use Template Guidance", ["None"] + templates)
        
        guidance = st.text_area("Chapter Guidance", 
                               placeholder="What should this chapter accomplish?",
                               height=100)
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Create Chapter", type="primary", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("Cancel", type="secondary", use_container_width=True)
        
        if cancel:
            st.session_state.show_new_chapter_modal = False
            st.rerun()
        
        if submit and title:
            novel_data = NovelData(st.session_state.user_id)
            novel = novel_data.load_novel()
            
            if novel:
                # If using template, get guidance from template
                if use_template != "None":
                    template_df = template_loader.load_template(use_template)
                    if template_df is not None and len(template_df) > len(novel["chapters"]):
                        template_row = template_df.iloc[len(novel["chapters"])]
                        if not guidance:
                            guidance = template_row.get("guidance", "")
                        if not title or title == "":
                            title = template_row.get("title", title)
                
                chapter_data = {
                    "title": title,
                    "guidance": guidance,
                    "word_target": word_target,
                    "content": "",
                    "notes": "",
                    "completed": False,
                    "tags": []
                }
                
                chapter_id = novel_data.add_chapter(chapter_data)
                if chapter_id:
                    st.session_state.current_chapter = chapter_id - 1
                    st.session_state.show_new_chapter_modal = False
                    st.success(f"Chapter '{title}' created!")
                    time.sleep(0.5)
                    st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def render_character_modal():
    st.markdown('<div class="modal-overlay">', unsafe_allow_html=True)
    
    st.subheader("👥 Add New Character")
    
    with st.form("new_character_form"):
        name = st.text_input("Character Name", placeholder="e.g., 'Eleanor Vance'")
        
        col1, col2 = st.columns(2)
        with col1:
            role = st.selectbox("Role", ["Protagonist", "Antagonist", "Supporting", "Love Interest", "Mentor", "Comic Relief"])
            age = st.text_input("Age", placeholder="e.g., '32' or 'Ancient'")
        with col2:
            occupation = st.text_input("Occupation", placeholder="e.g., 'Detective', 'Wizard'")
            appearance = st.text_input("Appearance", placeholder="e.g., 'Tall, dark hair, scar on cheek'")
        
        personality = st.text_area("Personality Traits", 
                                  placeholder="e.g., 'Brave but impulsive, loyal to friends, afraid of failure'",
                                  height=80)
        
        motivation = st.text_input("Primary Motivation", 
                                  placeholder="e.g., 'To find her missing brother'")
        
        background = st.text_area("Background Story", 
                                 placeholder="Brief history and key life events",
                                 height=100)
        
        col1, col2 = st.columns(2)
        with col1:
            submit = st.form_submit_button("Add Character", type="primary", use_container_width=True)
        with col2:
            cancel = st.form_submit_button("Cancel", type="secondary", use_container_width=True)
        
        if cancel:
            st.session_state.show_character_modal = False
            st.rerun()
        
        if submit and name:
            novel_data = NovelData(st.session_state.user_id)
            character_data = {
                "name": name,
                "role": role,
                "age": age,
                "occupation": occupation,
                "appearance": appearance,
                "personality": personality,
                "motivation": motivation,
                "background": background,
                "created": datetime.now().isoformat()
            }
            
            character_id = novel_data.add_character(character_data)
            if character_id:
                st.session_state.show_character_modal = False
                st.success(f"Character '{name}' added!")
                time.sleep(0.5)
                st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    # Initialize session state
    if "user_id" not in st.session_state:
        st.session_state.user_id = "demo_user"
    
    if "current_chapter" not in st.session_state:
        st.session_state.current_chapter = 0
    
    if "show_new_chapter_modal" not in st.session_state:
        st.session_state.show_new_chapter_modal = False
    
    if "show_character_modal" not in st.session_state:
        st.session_state.show_character_modal = False
    
    # Initialize data manager
    novel_data = NovelData(st.session_state.user_id)
    novel = novel_data.load_novel()
    
    # If no novel exists, show creation screen
    if not novel:
        st.title("📖 Welcome to NovelCraft")
        st.markdown("### Start Your Writing Journey")
        
        col1, col2 = st.columns(2)
        
        with col1:
            with st.form("new_novel_form"):
                title = st.text_input("Novel Title", placeholder="e.g., 'Whispers of the Lost City'")
                genre = st.selectbox("Genre", ["Fantasy", "Science Fiction", "Mystery", "Romance", 
                                              "Thriller", "Historical", "Literary", "Young Adult"])
                target_words = st.slider("Target Word Count", 20000, 200000, 80000, 5000)
                
                if st.form_submit_button("Create Novel", type="primary", use_container_width=True):
                    if title:
                        new_novel = novel_data.create_new_novel(title, genre, target_words)
                        st.success(f"Novel '{title}' created!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
        
        with col2:
            st.info("""
            **NovelCraft Features:**
            - 📝 Chapter-based writing
            - 👥 Character management
            - 📈 Plot tracking
            - 🎯 Word count goals
            - 💾 Auto-save functionality
            
            Start by giving your novel a title and choosing a genre!
            """)
        
        # Show sample templates
        st.divider()
        st.subheader("🎭 Start with a Template")
        
        template_loader = TemplateLoader()
        templates = template_loader.get_available_templates()
        
        cols = st.columns(len(templates))
        for idx, genre in enumerate(templates):
            with cols[idx]:
                if st.button(f"📚 {genre.title()} Template", use_container_width=True):
                    df = template_loader.load_template(genre)
                    if df is not None:
                        st.session_state.template_preview = df
                        st.rerun()
        
        if "template_preview" in st.session_state:
            st.subheader("Template Preview")
            st.dataframe(st.session_state.template_preview, use_container_width=True)
        
        st.stop()
    
    # Main app layout
    render_novel_header(novel)
    
    # Sidebar
    with st.sidebar:
        st.title("📖 NovelCraft")
        
        # Quick stats
        st.metric("Chapters", len(novel.get("chapters", [])))
        st.metric("Characters", len(novel.get("characters", [])))
        
        st.divider()
        
        # Navigation
        render_chapter_navigation(novel, st.session_state.current_chapter)
        
        st.divider()
        
        # Tools
        st.subheader("🛠️ Writing Tools")
        if st.button("📊 Writing Analytics", use_container_width=True):
            st.session_state.show_analytics = True
        
        if st.button("🎯 Set Daily Goal", use_container_width=True):
            st.session_state.show_goal_setter = True
        
        if st.button("📤 Export Manuscript", use_container_width=True):
            st.session_state.show_export = True
        
        st.divider()
        
        # Character panel
        render_character_panel(novel)
    
    # Main content area
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Writing interface
        render_writing_interface(novel_data, st.session_state.current_chapter)
        
        # Chapter notes expander
        if novel.get("chapters") and st.session_state.current_chapter < len(novel["chapters"]):
            chapter = novel["chapters"][st.session_state.current_chapter]
            if chapter.get("notes"):
                with st.expander("📝 View Chapter Notes"):
                    st.write(chapter.get("notes"))
    
    with col2:
        # Plot tracker
        render_plot_tracker(novel)
        
        # Quick stats
        st.subheader("⚡ Quick Stats")
        
        if novel.get("chapters"):
            current_chapter = novel["chapters"][st.session_state.current_chapter]
            word_count = current_chapter.get("word_count", 0)
            target = current_chapter.get("word_target", 2500)
            
            if target > 0:
                progress = min((word_count / target) * 100, 100)
                st.progress(progress / 100)
                st.caption(f"{word_count} / {target} words ({progress:.1f}%)")
            
            # Writing streak
            if novel["stats"].get("writing_streak", 0) > 0:
                st.metric("🔥 Writing Streak", f"{novel['stats']['writing_streak']} days")
        
        # Focus timer
        st.subheader("⏱️ Focus Timer")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("25m", use_container_width=True):
                st.session_state.focus_timer = 25 * 60
        with col2:
            if st.button("50m", use_container_width=True):
                st.session_state.focus_timer = 50 * 60
        with col3:
            if st.button("🍅", use_container_width=True, help="Pomodoro: 25 min work, 5 min break"):
                st.session_state.focus_timer = 25 * 60
        
        if "focus_timer" in st.session_state and st.session_state.focus_timer > 0:
            minutes = st.session_state.focus_timer // 60
            seconds = st.session_state.focus_timer % 60
            st.write(f"⏳ {minutes:02d}:{seconds:02d} remaining")
    
    # Modals
    if st.session_state.show_new_chapter_modal:
        render_new_chapter_modal()
        st.stop()
    
    if st.session_state.show_character_modal:
        render_character_modal()
        st.stop()

if __name__ == "__main__":
    main()

