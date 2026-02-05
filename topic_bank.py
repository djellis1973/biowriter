# topic_bank.py
import streamlit as st
import json
from datetime import datetime
from typing import Dict, List, Optional
import os

class TopicBank:
    """Manages a bank of topics for sessions"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.standard_topics_file = "data/standard_topics.json"
        self.user_topics_file = f"user_topics/{user_id}_topics.json"
        self._ensure_directories()
        self._load_topics()
    
    def _ensure_directories(self):
        """Create necessary directories"""
        os.makedirs("user_topics", exist_ok=True)
        os.makedirs("data", exist_ok=True)
    
    def _load_topics(self):
        """Load topics from files"""
        # Load standard topics
        try:
            if os.path.exists(self.standard_topics_file):
                with open(self.standard_topics_file, 'r') as f:
                    self.standard_topics = json.load(f)
            else:
                # Create default standard topics
                self.standard_topics = self._create_default_topics()
                with open(self.standard_topics_file, 'w') as f:
                    json.dump(self.standard_topics, f, indent=2)
        except Exception as e:
            print(f"Error loading standard topics: {e}")
            self.standard_topics = self._create_default_topics()
        
        # Load user topics
        try:
            if os.path.exists(self.user_topics_file):
                with open(self.user_topics_file, 'r') as f:
                    self.user_topics = json.load(f)
            else:
                self.user_topics = []
        except Exception as e:
            print(f"Error loading user topics: {e}")
            self.user_topics = []
    
    def _create_default_topics(self) -> Dict:
        """Create default standard topics"""
        return {
            "categories": {
                "childhood": [
                    "Earliest memory",
                    "Family home",
                    "First friends",
                    "School days",
                    "Favorite toys/games",
                    "Childhood fears",
                    "Holiday traditions"
                ],
                "family": [
                    "Parents' influence",
                    "Sibling relationships",
                    "Family values",
                    "Family traditions",
                    "Ancestry/heritage"
                ],
                "education": [
                    "Favorite teachers",
                    "School achievements",
                    "Learning challenges",
                    "Extracurricular activities",
                    "College/university experiences"
                ],
                "career": [
                    "First job",
                    "Career mentors",
                    "Major projects",
                    "Work challenges",
                    "Professional growth"
                ],
                "relationships": [
                    "Important friendships",
                    "Romantic relationships",
                    "Mentors",
                    "Community involvement"
                ],
                "life_events": [
                    "Travel experiences",
                    "Major decisions",
                    "Turning points",
                    "Achievements",
                    "Challenges overcome"
                ],
                "personal_growth": [
                    "Life lessons",
                    "Values and beliefs",
                    "Personal philosophy",
                    "Future aspirations"
                ]
            }
        }
    
    def _save_user_topics(self):
        """Save user topics to file"""
        try:
            with open(self.user_topics_file, 'w') as f:
                json.dump(self.user_topics, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving user topics: {e}")
            return False
    
    def get_all_categories(self) -> List[str]:
        """Get all topic categories"""
        categories = list(self.standard_topics["categories"].keys())
        # Add user-defined categories
        user_categories = set(topic.get("category") for topic in self.user_topics 
                            if topic.get("category"))
        return categories + list(user_categories)
    
    def get_topics_by_category(self, category: str) -> List[str]:
        """Get topics for a specific category"""
        topics = []
        
        # Get standard topics
        if category in self.standard_topics["categories"]:
            topics.extend(self.standard_topics["categories"][category])
        
        # Get user topics for this category
        user_topics = [t["text"] for t in self.user_topics 
                      if t.get("category") == category]
        topics.extend(user_topics)
        
        return topics
    
    def add_user_topic(self, text: str, category: str = "custom", 
                      tags: List[str] = None) -> bool:
        """Add a user-defined topic"""
        if tags is None:
            tags = []
        
        new_topic = {
            "id": len(self.user_topics) + 1,
            "text": text,
            "category": category,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "used_count": 0
        }
        
        self.user_topics.append(new_topic)
        return self._save_user_topics()
    
    def increment_topic_use(self, topic_text: str):
        """Increment usage count for a topic"""
        for topic in self.user_topics:
            if topic["text"] == topic_text:
                topic["used_count"] = topic.get("used_count", 0) + 1
                break
        self._save_user_topics()
    
    def search_topics(self, query: str) -> List[Dict]:
        """Search topics by text or tags"""
        results = []
        query_lower = query.lower()
        
        # Search in standard topics
        for category, topics in self.standard_topics["categories"].items():
            for topic in topics:
                if query_lower in topic.lower():
                    results.append({
                        "text": topic,
                        "category": category,
                        "type": "standard",
                        "score": topic.lower().count(query_lower)
                    })
        
        # Search in user topics
        for topic in self.user_topics:
            if (query_lower in topic["text"].lower() or 
                any(query_lower in tag.lower() for tag in topic.get("tags", []))):
                results.append({
                    "text": topic["text"],
                    "category": topic.get("category", "custom"),
                    "type": "user",
                    "used_count": topic.get("used_count", 0)
                })
        
        # Sort by relevance/usage
        results.sort(key=lambda x: (
            -x.get("score", 0) if "score" in x else -x.get("used_count", 0)
        ))
        return results[:20]  # Limit results
    
    def get_popular_topics(self, limit: int = 10) -> List[Dict]:
        """Get most frequently used topics"""
        user_topics_sorted = sorted(
            self.user_topics,
            key=lambda x: x.get("used_count", 0),
            reverse=True
        )
        return user_topics_sorted[:limit]
    
    def display_topic_browser(self, on_topic_select=None):
        """Display topic browser interface"""
        
        # Search bar
        search_query = st.text_input("🔍 Search topics...", 
                                   placeholder="Type to search topics")
        
        if search_query:
            search_results = self.search_topics(search_query)
            if search_results:
                st.subheader(f"Search Results ({len(search_results)})")
                for result in search_results:
                    self._display_topic_item(result, on_topic_select)
            else:
                st.info("No topics found. Try a different search term.")
        else:
            # Show categories
            st.subheader("Browse by Category")
            
            categories = self.get_all_categories()
            tabs = st.tabs(categories[:6])  # Show first 6 categories in tabs
            
            for i, category in enumerate(categories[:6]):
                with tabs[i]:
                    topics = self.get_topics_by_category(category)
                    if topics:
                        for topic in topics:
                            self._display_topic_item({
                                "text": topic,
                                "category": category,
                                "type": "standard"
                            }, on_topic_select)
                    else:
                        st.info(f"No topics in {category} category yet.")
            
            # Show popular topics
            st.divider()
            st.subheader("✨ Popular Topics")
            
            popular_topics = self.get_popular_topics(5)
            if popular_topics:
                for topic in popular_topics:
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.write(f"**{topic['text']}**")
                        st.caption(f"Category: {topic.get('category', 'custom')}")
                    with col2:
                        st.metric("Used", topic.get("used_count", 0))
                    
                    if on_topic_select:
                        if st.button("Use Topic", key=f"use_pop_{topic['id']}", 
                                   size="small"):
                            on_topic_select(topic["text"])
                            self.increment_topic_use(topic["text"])
                    
                    st.divider()
            else:
                st.info("No popular topics yet. Start adding topics!")
    
    def _display_topic_item(self, topic_data: Dict, on_topic_select=None):
        """Display a single topic item"""
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.write(topic_data["text"])
            st.caption(f"Category: {topic_data.get('category', 'N/A')}")
        
        with col2:
            if topic_data.get("type") == "user":
                st.caption("✨ Custom")
            else:
                st.caption("📚 Standard")
        
        with col3:
            if on_topic_select:
                if st.button("Select", key=f"select_{hash(topic_data['text'])}"):
                    on_topic_select(topic_data["text"])
                    if topic_data.get("type") == "user":
                        self.increment_topic_use(topic_data["text"])
    
    def display_topic_creator(self):
        """Display interface for creating custom topics"""
        with st.expander("➕ Add Custom Topic", expanded=False):
            with st.form("create_topic_form"):
                topic_text = st.text_area("Topic Prompt",
                                        placeholder="e.g., 'Tell me about your favorite childhood holiday memory'",
                                        height=100)
                
                # Category selection
                existing_categories = self.get_all_categories()
                category_options = existing_categories + ["custom", "new_category"]
                
                category = st.selectbox("Category", category_options)
                
                if category == "new_category":
                    new_category = st.text_input("New Category Name")
                    category = new_category if new_category.strip() else "custom"
                
                # Tags input
                tags_input = st.text_input("Tags (comma-separated)",
                                         placeholder="e.g., childhood, holiday, family")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Add Topic", type="primary", 
                                           use_container_width=True):
                        if topic_text.strip():
                            tags = [tag.strip() for tag in tags_input.split(',') 
                                   if tag.strip()]
                            success = self.add_user_topic(topic_text, category, tags)
                            if success:
                                st.success(f"Topic added to '{category}' category!")
                                st.rerun()
                            else:
                                st.error("Failed to add topic")
                        else:
                            st.error("Please enter a topic prompt")
                
                with col2:
                    if st.form_submit_button("Cancel", type="secondary", 
                                           use_container_width=True):
                        st.rerun()
