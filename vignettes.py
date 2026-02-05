# vignettes.py
import streamlit as st
import json
from datetime import datetime
from typing import Dict, List, Optional
import os
import uuid

class VignetteManager:
    """Manages vignettes (short stories)"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.vignettes_file = f"user_vignettes/{user_id}_vignettes.json"
        self.published_file = f"published_vignettes/{user_id}_published.json"
        self._ensure_directories()
        self._load_vignettes()
        self._load_published()
        
        # Standard vignette themes
        self.standard_themes = [
            "Life Lesson",
            "Achievement",
            "Work Experience",
            "Loss of Life",
            "Illness",
            "New Child",
            "Marriage",
            "Travel",
            "Relationship",
            "Interests",
            "Education",
            "Childhood Memory",
            "Family Story",
            "Career Moment",
            "Personal Growth"
        ]
    
    def _ensure_directories(self):
        """Create necessary directories"""
        os.makedirs("user_vignettes", exist_ok=True)
        os.makedirs("published_vignettes", exist_ok=True)
    
    def _load_vignettes(self):
        """Load vignettes from file"""
        try:
            if os.path.exists(self.vignettes_file):
                with open(self.vignettes_file, 'r') as f:
                    self.vignettes = json.load(f)
            else:
                self.vignettes = []
        except Exception as e:
            print(f"Error loading vignettes: {e}")
            self.vignettes = []
    
    def _save_vignettes(self):
        """Save vignettes to file"""
        try:
            with open(self.vignettes_file, 'w') as f:
                json.dump(self.vignettes, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving vignettes: {e}")
            return False
    
    def _load_published(self):
        """Load published vignettes"""
        try:
            if os.path.exists(self.published_file):
                with open(self.published_file, 'r') as f:
                    self.published = json.load(f)
            else:
                self.published = []
        except Exception as e:
            print(f"Error loading published vignettes: {e}")
            self.published = []
    
    def _save_published(self):
        """Save published vignettes"""
        try:
            with open(self.published_file, 'w') as f:
                json.dump(self.published, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving published: {e}")
            return False
    
    def create_vignette(self, title: str, content: str, theme: str, 
                       tags: List[str] = None, is_draft: bool = False) -> Dict:
        """Create a new vignette"""
        if tags is None:
            tags = []
        
        vignette_id = str(uuid.uuid4())[:8]
        
        new_vignette = {
            "id": vignette_id,
            "title": title,
            "content": content,
            "theme": theme,
            "tags": tags,
            "word_count": len(content.split()),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "is_draft": is_draft,
            "is_published": False,
            "views": 0,
            "likes": 0
        }
        
        self.vignettes.append(new_vignette)
        self._save_vignettes()
        return new_vignette
    
    def publish_vignette(self, vignette_id: str) -> bool:
        """Publish a vignette"""
        for vignette in self.vignettes:
            if vignette["id"] == vignette_id:
                vignette["is_published"] = True
                vignette["is_draft"] = False
                vignette["published_at"] = datetime.now().isoformat()
                
                # Add to published list
                published_copy = vignette.copy()
                self.published.append(published_copy)
                
                self._save_vignettes()
                self._save_published()
                return True
        return False
    
    def get_vignette_by_id(self, vignette_id: str) -> Optional[Dict]:
        """Get a vignette by ID"""
        for vignette in self.vignettes:
            if vignette["id"] == vignette_id:
                return vignette
        return None
    
    def get_all_vignettes(self, include_drafts: bool = False) -> List[Dict]:
        """Get all vignettes"""
        if include_drafts:
            return self.vignettes
        return [v for v in self.vignettes if not v["is_draft"]]
    
    def get_published_vignettes(self) -> List[Dict]:
        """Get published vignettes"""
        return self.published
    
    def get_vignettes_by_theme(self, theme: str) -> List[Dict]:
        """Get vignettes by theme"""
        return [v for v in self.vignettes 
                if v["theme"].lower() == theme.lower() and not v["is_draft"]]
    
    def search_vignettes(self, query: str) -> List[Dict]:
        """Search vignettes by title or content"""
        results = []
        query_lower = query.lower()
        
        for vignette in self.vignettes:
            if (query_lower in vignette["title"].lower() or 
                query_lower in vignette["content"].lower() or
                any(query_lower in tag.lower() for tag in vignette.get("tags", []))):
                results.append(vignette)
        
        return results
    
    def display_vignette_creator(self, on_publish=None):
        """Display vignette creation interface"""
        st.subheader("✨ Write a Short Story")
        
        with st.form("create_vignette_form"):
            # Theme selection
            theme_options = self.standard_themes + ["Custom Theme"]
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
                                 height=300,
                                 placeholder="Write your short story here...\n\nTip: Focus on a single moment or experience. Be descriptive and emotional.")
            
            # Tags
            tags_input = st.text_input("Tags (comma-separated)",
                                     placeholder="e.g., family, travel, achievement")
            
            # Word count display
            if content:
                word_count = len(content.split())
                st.caption(f"📝 {word_count} words")
            
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
                tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
                vignette = self.create_vignette(title, content, theme, tags, is_draft=False)
                self.publish_vignette(vignette["id"])
                
                if on_publish:
                    on_publish(vignette)
                
                st.success("🎉 Published! Your story is now live.")
                st.balloons()
                return True
            
            elif draft_button and content.strip():
                title_to_use = title if title.strip() else f"Draft: {theme}"
                tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()]
                self.create_vignette(title_to_use, content, theme, tags, is_draft=True)
                st.success("💾 Saved as draft!")
                return True
            
            elif cancel_button:
                st.rerun()
            
            return False
    
    def display_vignette_gallery(self, filter_by: str = "all", on_select=None):
        """Display vignettes in a gallery"""
        
        # Filter options
        filter_options = {
            "all": "All Stories",
            "published": "Published",
            "drafts": "Drafts",
            "popular": "Most Popular"
        }
        
        # Filter vignettes
        if filter_by == "published":
            vignettes_to_show = [v for v in self.vignettes if v["is_published"]]
        elif filter_by == "drafts":
            vignettes_to_show = [v for v in self.vignettes if v["is_draft"]]
        elif filter_by == "popular":
            vignettes_to_show = sorted(self.vignettes, 
                                      key=lambda x: x.get("views", 0), 
                                      reverse=True)
        else:
            vignettes_to_show = self.vignettes
        
        if not vignettes_to_show:
            st.info(f"No {filter_options[filter_by].lower()} yet.")
            return
        
        # Display in grid
        cols = st.columns(2)
        
        for i, vignette in enumerate(vignettes_to_show[:6]):  # Show first 6
            col_idx = i % 2
            with cols[col_idx]:
                self._display_vignette_card(vignette, on_select)
    
    def _display_vignette_card(self, vignette: Dict, on_select=None):
        """Display a single vignette card"""
        with st.container():
            # Card container
            st.markdown(f"""
            <div style="
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 1rem;
                margin-bottom: 1rem;
                background-color: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            ">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <h4 style="margin: 0 0 0.5rem 0; color: #333;">{vignette['title']}</h4>
                    {self._get_status_badge(vignette)}
                </div>
            """, unsafe_allow_html=True)
            
            # Theme badge
            st.markdown(f"""
            <div style="
                background-color: #E8F5E9;
                color: #2E7D32;
                padding: 0.2rem 0.5rem;
                border-radius: 10px;
                font-size: 0.8rem;
                display: inline-block;
                margin-bottom: 0.5rem;
            ">
                {vignette['theme']}
            </div>
            """, unsafe_allow_html=True)
            
            # Preview (first 100 chars)
            preview = vignette['content'][:100] + "..." if len(vignette['content']) > 100 else vignette['content']
            st.write(preview)
            
            # Stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"📝 {vignette['word_count']} words")
            with col2:
                if vignette.get('views', 0) > 0:
                    st.caption(f"👁️ {vignette['views']}")
            with col3:
                if vignette.get('likes', 0) > 0:
                    st.caption(f"❤️ {vignette['likes']}")
            
            # Action buttons
            if on_select:
                if st.button("Read", key=f"read_{vignette['id']}", 
                           use_container_width=True):
                    on_select(vignette['id'])
            
            st.markdown("</div>", unsafe_allow_html=True)
    
    def _get_status_badge(self, vignette: Dict) -> str:
        """Get HTML badge for vignette status"""
        if vignette.get("is_published"):
            return """
            <span style="
                background-color: #4CAF50;
                color: white;
                padding: 0.2rem 0.5rem;
                border-radius: 12px;
                font-size: 0.7rem;
            ">
                Published
            </span>
            """
        elif vignette.get("is_draft"):
            return """
            <span style="
                background-color: #FF9800;
                color: white;
                padding: 0.2rem 0.5rem;
                border-radius: 12px;
                font-size: 0.7rem;
            ">
                Draft
            </span>
            """
        return ""
