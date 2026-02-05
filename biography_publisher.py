# biography_publisher.py - BEAUTIFUL BIOGRAPHY PUBLISHER WITH IMAGES 1
import streamlit as st
import json
import base64
from datetime import datetime
import os
import tempfile

# Page setup
st.set_page_config(page_title="Biography Publisher", layout="wide", page_icon="📖")

st.title("📖 Beautiful Biography Creator")
st.markdown("### 🎨 Create Your Illustrated Life Story")

def decode_stories_from_url():
    """Extract stories from URL parameter"""
    try:
        query_params = st.query_params
        encoded_data = query_params.get("data", [None])[0]
        
        if not encoded_data:
            return None
            
        # Decode the data
        json_data = base64.b64decode(encoded_data).decode()
        stories_data = json.loads(json_data)
        
        return stories_data
    except:
        return None

def create_beautiful_biography(stories_data, include_images=True):
    """Create a professionally formatted biography with optional images"""
    user_name = stories_data.get("user", "Unknown")
    user_profile = stories_data.get("user_profile", {})
    stories_dict = stories_data.get("stories", {})
    
    # Collect all stories with images
    all_stories = []
    all_images = []
    
    for session_id, session_data in sorted(stories_dict.items()):
        session_title = session_data.get("title", f"Chapter {session_id}")
        
        # Get session images
        session_images = session_data.get("images", [])
        
        for question, answer_data in session_data.get("questions", {}).items():
            answer = answer_data.get("answer", "")
            if answer.strip():  # Only include non-empty answers
                story_entry = {
                    "session_id": session_id,
                    "session": session_title,
                    "question": question,
                    "answer": answer,
                    "date": answer_data.get("timestamp", "")[:10],
                    "images": []
                }
                
                # Find images related to this session
                if session_images:
                    story_entry["images"] = session_images
                
                all_stories.append(story_entry)
        
        # Collect all images
        all_images.extend(session_images)
    
    if not all_stories:
        return "No stories found to publish.", [], user_name, 0, 0, 0, 0, {}
    
    # ========== CREATE BEAUTIFUL BIOGRAPHY ==========
    bio_text = "=" * 60 + "\n"
    bio_text += f"{'THE LIFE STORY OF':^60}\n"
    bio_text += f"{user_name.upper():^60}\n"
    bio_text += "=" * 60 + "\n\n"
    
    # Author Profile
    if user_profile:
        bio_text += "AUTHOR PROFILE\n"
        bio_text += "-" * 40 + "\n"
        if user_profile.get('first_name'):
            bio_text += f"Name: {user_profile.get('first_name', '')} {user_profile.get('last_name', '')}\n"
        if user_profile.get('birthdate'):
            bio_text += f"Born: {user_profile.get('birthdate')}\n"
        if user_profile.get('email'):
            bio_text += f"Contact: {user_profile.get('email')}\n"
        bio_text += "\n"
    
    # Table of Contents
    bio_text += "TABLE OF CONTENTS\n"
    bio_text += "-" * 40 + "\n"
    
    current_session = None
    chapter_num = 0
    for i, story in enumerate(all_stories):
        if story["session"] != current_session:
            chapter_num += 1
            image_count = len(story["images"])
            photo_note = f" 📸 {image_count} photo(s)" if image_count > 0 else ""
            bio_text += f"\nChapter {chapter_num}: {story['session']}{photo_note}\n"
            current_session = story["session"]
    
    if all_images and include_images:
        bio_text += f"\n📸 Photo Gallery: {len(all_images)} images included\n"
    
    bio_text += "\n" + "=" * 60 + "\n\n"
    
    # Introduction
    bio_text += "FOREWORD\n\n"
    bio_text += f"This biography captures the unique life journey of {user_name}, "
    bio_text += f"compiled from personal reflections and photographs shared on {datetime.now().strftime('%B %d, %Y')}. "
    bio_text += "Each chapter represents a different phase of life, preserved here for future generations.\n\n"
    
    if all_images:
        bio_text += f"The story is illustrated with {len(all_images)} personal photographs "
        bio_text += "that bring these memories to life.\n\n"
    
    bio_text += "=" * 60 + "\n\n"
    
    # Chapters with stories and images
    current_session = None
    chapter_num = 0
    story_num = 0
    
    for story in all_stories:
        if story["session"] != current_session:
            chapter_num += 1
            bio_text += "\n" + "-" * 60 + "\n"
            bio_text += f"CHAPTER {chapter_num}\n"
            bio_text += f"{story['session'].upper()}\n"
            bio_text += "-" * 60 + "\n\n"
            current_session = story["session"]
            
            # Add session images description
            if story["images"] and include_images:
                bio_text += f"📸 **CHAPTER IMAGES** ({len(story['images'])} photos)\n"
                for img in story["images"][:3]:  # List first 3 images
                    img_desc = img.get('description', img.get('original_filename', 'Photo'))
                    bio_text += f"  • {img_desc}\n"
                if len(story["images"]) > 3:
                    bio_text += f"  • ...and {len(story['images']) - 3} more photos\n"
                bio_text += "\n"
        
        story_num += 1
        bio_text += f"STORY {story_num}\n"
        bio_text += f"Topic: {story['question']}\n"
        
        if story['date']:
            bio_text += f"Date Recorded: {story['date']}\n"
        
        bio_text += "-" * 40 + "\n"
        
        # Format the answer with proper paragraphs
        answer = story['answer'].strip()
        paragraphs = answer.split('\n')
        
        for para in paragraphs:
            if para.strip():
                # Add proper indentation for paragraphs
                bio_text += f"  {para.strip()}\n\n"
        
        # Add image references for this story
        if story["images"] and include_images:
            relevant_images = []
            # Simple logic: if story mentions "photo", "picture", or "image", include image references
            if any(word in answer.lower() for word in ['photo', 'picture', 'image', 'photograph', 'snapshot']):
                relevant_images = story["images"][:2]  # Take first 2 images
            
            if relevant_images:
                bio_text += "📸 **Related Photos:**\n"
                for img in relevant_images:
                    img_desc = img.get('description', img.get('original_filename', 'Photo'))
                    upload_date = img.get('upload_date', '')[:10]
                    date_note = f" ({upload_date})" if upload_date else ""
                    bio_text += f"  • {img_desc}{date_note}\n"
                bio_text += "\n"
        
        bio_text += "\n"
    
    # Photo Gallery Section
    if all_images and include_images:
        bio_text += "=" * 60 + "\n\n"
        bio_text += "PHOTO GALLERY\n\n"
        bio_text += f"This biography includes {len(all_images)} personal photographs:\n\n"
        
        # Group images by session
        images_by_session = {}
        for story in all_stories:
            session = story["session"]
            if session not in images_by_session:
                images_by_session[session] = []
            images_by_session[session].extend(story["images"])
        
        # Remove duplicates
        for session in images_by_session:
            seen = set()
            unique_images = []
            for img in images_by_session[session]:
                img_id = img.get('id')
                if img_id not in seen:
                    seen.add(img_id)
                    unique_images.append(img)
            images_by_session[session] = unique_images
        
        for session, images in images_by_session.items():
            if images:
                bio_text += f"{session.upper()} ({len(images)} photos)\n"
                bio_text += "-" * 40 + "\n"
                
                for img in images[:10]:  # List first 10 per session
                    img_desc = img.get('description', img.get('original_filename', 'Photo'))
                    upload_date = img.get('upload_date', '')[:10]
                    date_note = f" - {upload_date}" if upload_date else ""
                    dimensions = img.get('dimensions', '')
                    dim_note = f" [{dimensions}]" if dimensions else ""
                    
                    bio_text += f"• {img_desc}{date_note}{dim_note}\n"
                
                if len(images) > 10:
                    bio_text += f"• ...and {len(images) - 10} more photos\n"
                
                bio_text += "\n"
    
    # Conclusion
    bio_text += "=" * 60 + "\n\n"
    bio_text += "EPILOGUE\n\n"
    bio_text += f"This collection contains {story_num} stories across {chapter_num} chapters, "
    bio_text += f"each one a piece of {user_name}'s unique mosaic of memories. "
    
    if all_images:
        bio_text += f"Enhanced with {len(all_images)} personal photographs, "
    
    bio_text += "these reflections will continue to resonate long into the future.\n\n"
    
    # Statistics
    bio_text += "-" * 60 + "\n"
    bio_text += "BIOGRAPHY STATISTICS\n"
    bio_text += f"• Total Stories: {story_num}\n"
    bio_text += f"• Chapters: {chapter_num}\n"
    
    # Calculate word count
    total_words = sum(len(story['answer'].split()) for story in all_stories)
    bio_text += f"• Total Words: {total_words:,}\n"
    
    # Image stats
    if all_images:
        bio_text += f"• Photographs: {len(all_images)}\n"
    
    # Find longest story
    if all_stories:
        longest = max(all_stories, key=lambda x: len(x['answer'].split()))
        bio_text += f"• Longest Story: \"{longest['question'][:50]}...\" ({len(longest['answer'].split())} words)\n"
    
    bio_text += f"• Compiled: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n"
    bio_text += "-" * 60 + "\n\n"
    
    # Final note
    bio_text += "This illustrated digital legacy was created with the DeepVault UK Legacy Builder, "
    bio_text += "preserving personal history and photographs for generations to come.\n\n"
    bio_text += "=" * 60
    
    return bio_text, all_stories, user_name, story_num, chapter_num, total_words, len(all_images), images_by_session

def create_html_biography(stories_data, include_images=True):
    """Create an HTML version of the biography with embedded images"""
    bio_text, all_stories, author_name, story_num, chapter_num, total_words, image_count, images_by_session = create_beautiful_biography(stories_data, include_images)
    
    # Start HTML document
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{author_name}'s Biography</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:wght@400;600;700&family=Open+Sans:wght@300;400;600&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Crimson Text', serif;
            line-height: 1.8;
            color: #333;
            background: #fefefe;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
            border-left: 1px solid #e0e0e0;
            border-right: 1px solid #e0e0e0;
            box-shadow: 0 0 30px rgba(0,0,0,0.1);
        }}
        
        .container {{
            padding: 20px;
        }}
        
        .header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 3px double #2c5282;
            margin-bottom: 40px;
        }}
        
        h1 {{
            font-size: 2.8em;
            color: #2c5282;
            margin-bottom: 10px;
            letter-spacing: 1px;
        }}
        
        .subtitle {{
            font-family: 'Open Sans', sans-serif;
            font-size: 1.2em;
            color: #666;
            font-weight: 300;
            margin-bottom: 30px;
        }}
        
        .chapter {{
            margin: 50px 0;
            padding: 30px;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }}
        
        .chapter-title {{
            color: #2c5282;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 10px;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        
        .story {{
            margin: 25px 0;
            padding: 20px;
            background: #f8f9fa;
            border-left: 4px solid #4299e1;
            border-radius: 4px;
        }}
        
        .question {{
            font-weight: 700;
            color: #2d3748;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        
        .answer {{
            font-size: 1.1em;
            line-height: 1.7;
            white-space: pre-line;
        }}
        
        .image-gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .image-card {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 3px 10px rgba(0,0,0,0.1);
            transition: transform 0.3s ease;
        }}
        
        .image-card:hover {{
            transform: translateY(-5px);
        }}
        
        .image-placeholder {{
            height: 200px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.2em;
        }}
        
        .image-info {{
            padding: 15px;
        }}
        
        .image-title {{
            font-weight: 600;
            margin-bottom: 5px;
            color: #2d3748;
        }}
        
        .image-desc {{
            color: #718096;
            font-size: 0.9em;
            margin-bottom: 10px;
        }}
        
        .stats {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin: 40px 0;
            text-align: center;
        }}
        
        .stat-item {{
            display: inline-block;
            margin: 0 20px;
        }}
        
        .stat-number {{
            font-size: 2.5em;
            font-weight: 700;
            display: block;
        }}
        
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #e2e8f0;
            color: #718096;
            font-size: 0.9em;
        }}
        
        @media (max-width: 768px) {{
            body {{
                padding: 20px 10px;
            }}
            
            h1 {{
                font-size: 2em;
            }}
            
            .image-gallery {{
                grid-template-columns: 1fr;
            }}
            
            .stat-item {{
                display: block;
                margin: 15px 0;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{author_name}'s Life Story</h1>
            <div class="subtitle">
                A personal biography • {datetime.now().strftime('%B %d, %Y')}
            </div>
        </div>
        
        <div class="stats">
            <div class="stat-item">
                <span class="stat-number">{story_num}</span>
                <span class="stat-label">Stories</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">{chapter_num}</span>
                <span class="stat-label">Chapters</span>
            </div>
            <div class="stat-item">
                <span class="stat-number">{total_words:,}</span>
                <span class="stat-label">Words</span>
            </div>
"""
    
    # Add image stat if available
    if image_count > 0:
        html += f"""
            <div class="stat-item">
                <span class="stat-number">{image_count}</span>
                <span class="stat-label">Photos</span>
            </div>
"""
    
    html += """
        </div>
        
        <div class="content">
            <h2 style="color: #2c5282; margin: 40px 0 20px 0;">Table of Contents</h2>
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px;">
"""
    
    # Generate TOC
    current_session = None
    chapter_num = 0
    for story in all_stories:
        if story["session"] != current_session:
            chapter_num += 1
            image_count = len(story["images"])
            photo_note = f" <span style='color: #667eea;'>({image_count} photos)</span>" if image_count > 0 else ""
            html += f"<p style='margin: 10px 0;'><strong>Chapter {chapter_num}:</strong> {story['session']}{photo_note}</p>"
            current_session = story["session"]
    
    html += """
            </div>
    """
    
    # Add chapters
    current_session = None
    chapter_num = 0
    
    for story in all_stories:
        if story["session"] != current_session:
            chapter_num += 1
            current_session = story["session"]
            
            html += f"""
            <div class="chapter">
                <h2 class="chapter-title">Chapter {chapter_num}: {story['session']}</h2>
            """
            
            # Add images for this chapter
            if story["images"] and include_images:
                html += f"""
                <div style="margin: 20px 0; padding: 15px; background: #e6fffa; border-radius: 6px;">
                    <h3 style="color: #234e52; margin-bottom: 10px;">📸 Chapter Images</h3>
                    <p>This chapter includes {len(story['images'])} personal photographs.</p>
                </div>
                """
        
        # Add story
        html += f"""
        <div class="story">
            <div class="question">✏️ {story['question']}</div>
            <div class="answer">{story['answer']}</div>
        """
        
        # Add date if available
        if story['date']:
            html += f"""<div style="margin-top: 15px; font-size: 0.9em; color: #718096;">
                Recorded: {story['date']}
            </div>"""
        
        html += "</div>"  # Close story div
        
        # If this is the last story of the chapter
        next_idx = all_stories.index(story) + 1
        if next_idx >= len(all_stories) or all_stories[next_idx]["session"] != current_session:
            html += "</div>"  # Close chapter div
    
    # Add image gallery section if there are images
    if image_count > 0 and include_images and images_by_session:
        html += """
        <div class="chapter">
            <h2 class="chapter-title">Photo Gallery</h2>
            <div class="image-gallery">
        """
        
        # Add image cards (placeholders with info since we can't embed actual images)
        for session, images in images_by_session.items():
            for img in images[:12]:  # Limit to 12 images in HTML
                img_desc = img.get('description', img.get('original_filename', 'Photo'))
                upload_date = img.get('upload_date', '')[:10]
                
                html += f"""
                <div class="image-card">
                    <div class="image-placeholder">
                        📸 {session}<br>Photo
                    </div>
                    <div class="image-info">
                        <div class="image-title">{img_desc[:50]}{'...' if len(img_desc) > 50 else ''}</div>
                        <div class="image-desc">{session} • {upload_date}</div>
                        <div style="font-size: 0.8em; color: #a0aec0;">
                            Image included in full package
                        </div>
                    </div>
                </div>
                """
        
        html += """
            </div>
            <p style="text-align: center; margin-top: 20px; color: #718096;">
                <em>{image_count} personal photographs accompany this biography in the complete package.</em>
            </p>
        </div>
        """
    
    # Close HTML
    html += f"""
        </div>
        
        <div class="footer">
            <p>Created with the DeepVault UK Legacy Builder</p>
            <p>{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            <p style="margin-top: 20px; font-size: 0.8em;">
                This biography contains {story_num} stories, {chapter_num} chapters, 
                and {total_words:,} words{', illustrated with personal photographs' if image_count > 0 else ''}.
            </p>
        </div>
    </div>
</body>
</html>
"""
    
    return html

def create_image_zip(stories_data):
    """Create instructions for downloading images separately"""
    # This function would create a zip file of images
    # For now, return instructions
    all_images = []
    for session_id, session_data in stories_data.get("stories", {}).items():
        all_images.extend(session_data.get("images", []))
    
    if not all_images:
        return None
    
    # Create a text file with image information
    image_info = "IMAGE CATALOG FOR BIOGRAPHY\n"
    image_info += "=" * 50 + "\n\n"
    image_info += f"Total Images: {len(all_images)}\n"
    image_info += f"Biography Owner: {stories_data.get('user', 'Unknown')}\n"
    image_info += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    image_info += "IMAGE LIST:\n"
    image_info += "-" * 40 + "\n\n"
    
    for i, img in enumerate(all_images, 1):
        image_info += f"IMAGE {i}:\n"
        image_info += f"  Filename: {img.get('original_filename', 'Unknown')}\n"
        if img.get('description'):
            image_info += f"  Description: {img.get('description')}\n"
        if img.get('upload_date'):
            image_info += f"  Uploaded: {img.get('upload_date')[:10]}\n"
        if img.get('dimensions'):
            image_info += f"  Dimensions: {img.get('dimensions')}\n"
        if img.get('path'):
            image_info += f"  File Path: {img.get('path')}\n"
        image_info += "\n"
    
    return image_info

# ============================================================================
# MAIN APP INTERFACE
# ============================================================================

# Try to get data from URL first
stories_data = decode_stories_from_url()

if stories_data:
    # Auto-process data from URL
    user_name = stories_data.get("user", "Unknown")
    user_profile = stories_data.get("user_profile", {})
    
    # Count stories and images
    story_count = 0
    image_count = 0
    
    for session_id, session_data in stories_data.get("stories", {}).items():
        story_count += len(session_data.get("questions", {}))
        image_count += len(session_data.get("images", []))
    
    if story_count > 0:
        # Display welcome message with profile
        col_welcome1, col_welcome2 = st.columns([3, 1])
        
        with col_welcome1:
            st.success(f"✅ Welcome back, **{user_name}**!")
            if user_profile.get('birthdate'):
                st.caption(f"🎂 Born: {user_profile.get('birthdate')}")
        
        with col_welcome2:
            st.metric("Stories", story_count)
            if image_count > 0:
                st.metric("Photos", image_count)
        
        # Show formatting options
        st.markdown("### 🎯 Formatting Options")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            include_toc = st.checkbox("Table of Contents", value=True)
        with col2:
            include_stats = st.checkbox("Statistics Page", value=True)
        with col3:
            include_date = st.checkbox("Story Dates", value=True)
        with col4:
            include_images = st.checkbox("Include Photos", value=True, disabled=image_count==0)
            if image_count == 0:
                st.caption("No photos found")
        
        # Display image preview if available
        if image_count > 0:
            with st.expander(f"📸 Preview {image_count} Photos", expanded=False):
                # Show first few images
                first_images = []
                for session_id, session_data in stories_data.get("stories", {}).items():
                    first_images.extend(session_data.get("images", [])[:2])
                
                if first_images:
                    cols = st.columns(min(3, len(first_images)))
                    for idx, img in enumerate(first_images[:3]):
                        with cols[idx]:
                            st.markdown(f"**{img.get('original_filename', 'Photo')}**")
                            if img.get('description'):
                                st.caption(img.get('description')[:50] + "..." if len(img.get('description')) > 50 else img.get('description'))
                            st.caption(f"Session: {session_data.get('title', 'Unknown')}")
        
        # Generate biography button
        if st.button("✨ Create Beautiful Biography", type="primary", use_container_width=True):
            with st.spinner("Crafting your beautiful biography..."):
                biography, all_stories, author_name, story_num, chapter_num, total_words, img_count, images_by_session = create_beautiful_biography(
                    stories_data, 
                    include_images=include_images
                )
            
            # Show preview
            st.subheader("📖 Your Biography Preview")
            
            # Display in columns for better layout
            col_preview1, col_preview2 = st.columns([2, 1])
            
            with col_preview1:
                # Show first 1000 characters as preview
                preview_text = biography[:1000] + "..." if len(biography) > 1000 else biography
                st.text_area("Preview:", preview_text, height=300)
            
            with col_preview2:
                st.metric("Total Stories", story_num)
                st.metric("Chapters", chapter_num)
                st.metric("Total Words", f"{total_words:,}")
                if img_count > 0:
                    st.metric("Photos Included", img_count)
                st.metric("Biography Size", f"{len(biography):,} chars")
            
            # Download options
            st.subheader("📥 Download Your Biography")
            
            col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
            
            with col_dl1:
                # Plain text version
                safe_name = author_name.replace(" ", "_")
                st.download_button(
                    label="📄 Text Version",
                    data=biography,
                    file_name=f"{safe_name}_Biography.txt",
                    mime="text/plain",
                    type="primary",
                    use_container_width=True,
                    help="Standard text format with photo references"
                )
            
            with col_dl2:
                # HTML version with images
                html_biography = create_html_biography(stories_data, include_images=include_images)
                st.download_button(
                    label="🌐 HTML Version",
                    data=html_biography,
                    file_name=f"{safe_name}_Biography.html",
                    mime="text/html",
                    use_container_width=True,
                    help="Beautiful web format with image placeholders"
                )
            
            with col_dl3:
                # Markdown version
                md_biography = biography.replace("=" * 60, "#" * 60)
                md_biography = md_biography.replace("-" * 60, "---")
                st.download_button(
                    label="📝 Markdown",
                    data=md_biography,
                    file_name=f"{safe_name}_Biography.md",
                    mime="text/markdown",
                    use_container_width=True,
                    help="Markdown format for easy conversion"
                )
            
            with col_dl4:
                # Image catalog
                if img_count > 0:
                    image_catalog = create_image_zip(stories_data)
                    if image_catalog:
                        st.download_button(
                            label="🖼️ Image Catalog",
                            data=image_catalog,
                            file_name=f"{safe_name}_Image_Catalog.txt",
                            mime="text/plain",
                            use_container_width=True,
                            help="List of all photos with descriptions"
                        )
                else:
                    st.button("🖼️ No Photos", disabled=True, use_container_width=True)
            
            # Story preview
            with st.expander("📋 Preview Your Stories & Photos", expanded=True):
                for session_id, session_data in stories_data.get("stories", {}).items():
                    session_title = session_data.get('title', f'Chapter {session_id}')
                    session_images = session_data.get('images', [])
                    
                    st.markdown(f"### {session_title}")
                    if session_images:
                        st.caption(f"📸 {len(session_images)} photo(s) in this chapter")
                    
                    for question, answer_data in session_data.get("questions", {}).items():
                        answer = answer_data.get("answer", "")
                        if answer.strip():
                            word_count = len(answer.split())
                            st.markdown(f"**{question}**")
                            st.write(f"{answer[:200]}..." if len(answer) > 200 else answer)
                            st.caption(f"{word_count} words")
                            st.divider()
            
            st.balloons()
            st.success(f"✨ Biography created! **{story_num} stories** across **{chapter_num} chapters** ({total_words:,} words)")
            
            # Shareable link
            st.markdown("---")
            st.markdown("### 🔗 Share Your Achievement")
            share_text = f"I've created my illustrated life story with {story_num} stories"
            if img_count > 0:
                share_text += f" and {img_count} photos"
            share_text += "! #LifeStory #Biography #FamilyHistory"
            st.code(share_text, language="markdown")
            
    else:
        st.warning(f"Found your profile (**{user_name}**) but no stories yet.")
        st.info("Go back to the main app and save some stories first!")
        
else:
    # Manual upload option
    st.info("📋 **How to create your biography:**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### 🚀 **Automatic Method**
        1. Go to your main interview app
        2. Answer questions and upload photos
        3. Click the **publisher link** at the bottom
        4. Your illustrated biography creates itself!
        """)
    
    with col2:
        st.markdown("""
        ### 📤 **Manual Upload**
        1. In main app, use **Export Current Progress**
        2. Download the JSON file (includes photos)
        3. Upload it here:
        """)
        
        uploaded_file = st.file_uploader("Upload stories JSON", type=['json'])
        if uploaded_file:
            try:
                uploaded_data = json.load(uploaded_file)
                user_name = uploaded_data.get('user', 'Unknown')
                
                # Count images
                image_count = 0
                for session_id, session_data in uploaded_data.get("stories", {}).items():
                    image_count += len(session_data.get("images", []))
                
                st.success(f"✅ Loaded stories for **{user_name}**")
                if image_count > 0:
                    st.info(f"📸 Found {image_count} photos")
                
                if st.button("Create Biography from File", type="primary"):
                    biography, all_stories, author_name, story_num, chapter_num, total_words, img_count, _ = create_beautiful_biography(uploaded_data, include_images=True)
                    
                    safe_name = author_name.replace(" ", "_")
                    
                    # Offer multiple download options
                    col_dl1, col_dl2 = st.columns(2)
                    with col_dl1:
                        st.download_button(
                            label="📥 Download Text Version",
                            data=biography,
                            file_name=f"{safe_name}_Biography.txt",
                            mime="text/plain"
                        )
                    with col_dl2:
                        html_version = create_html_biography(uploaded_data, include_images=True)
                        st.download_button(
                            label="🌐 Download HTML Version",
                            data=html_version,
                            file_name=f"{safe_name}_Biography.html",
                            mime="text/html"
                        )
            except Exception as e:
                st.error(f"❌ Error processing file: {e}")

# ============================================================================
# FOOTER
# ============================================================================
st.markdown("---")
st.caption("✨ **Professional formatting** • **Photo integration** • Multiple formats • Your illustrated life story, beautifully preserved")
