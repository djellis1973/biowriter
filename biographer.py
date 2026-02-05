ax_tokens=len(text) + 100,
            temperature=0.1
        )
        return response.choices[0].message.content
    except:
        return text

# ── Page Setup & Main Flow ────────────────────────────────────────────────────
st.set_page_config(
    page_title="MemLife - Your Life Timeline",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state initialization
for key, value in {
    "logged_in": False,
    "user_id": "",
    "user_account": None,
    "show_profile_setup": False,
    "current_session": 0,
    "current_question": 0,
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
    "current_jot": "",
    "show_jots": False,
    "historical_events_loaded": False,
    "show_image_upload": False,
    "image_prompt_mode": False,
    "selected_images_for_prompt": [],
    "image_description": "",
    "streak_days": 1,
    "last_active": date.today().isoformat(),
    "total_writing_days": 1
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

if not st.session_state.responses:
    for session in SESSIONS:
        session_id = session["id"]
        st.session_state.responses[session_id] = {
            "title": session["title"],
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": session.get("word_target", DEFAULT_WORD_TARGET)
        }
        st.session_state.session_conversations[session_id] = {}

if st.session_state.logged_in and st.session_state.user_id and not st.session_state.data_loaded:
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

# ── Main App Flow ─────────────────────────────────────────────────────────────
if st.session_state.get('show_profile_setup', False):
    show_profile_setup_modal()
    st.stop()

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

# Main header
st.markdown(f"""
<div class="main-header">
<img src="{LOGO_URL}" class="logo-img" alt="MemLife Logo">
<h2 style="margin: 0; line-height: 1.2;">MemLife - Your Life Timeline</h2>
<p style="font-size: 0.9rem; color: #666; margin: 0; line-height: 1.2;">Preserve Your Legacy • Build Your Timeline • Share Your Story</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Profile
    st.header("👤 Your Profile")
    if st.session_state.user_account:
        profile = st.session_state.user_account['profile']
        st.success(f"✓ **{profile['first_name']} {profile['last_name']}**")
        st.caption(f"📧 {profile['email']}")
        if profile.get('birthdate'):
            st.caption(f"🎂 Born: {profile['birthdate']}")
        try:
            birth_year = int(profile['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            if events:
                uk_events = [e for e in events if e.get('region') == 'UK']
                global_events = len(events) - len(uk_events)
                st.caption(f"📚 {len(events)} historical events ({len(uk_events)} UK, {global_events} global)")
        except:
            pass
        else:
            st.caption("🎂 Birthdate: Not set")
        account_type = st.session_state.user_account['account_type']
        st.caption(f"👤 Account: {account_type.title()}")
    if st.button("📝 Edit Profile", use_container_width=True):
        st.session_state.show_profile_setup = True
        st.rerun()
    if st.button("🚪 Log Out", use_container_width=True):
        logout_user()
    st.divider()
    # Streak
    st.subheader("🔥 Writing Streak")
    streak_emoji = get_streak_emoji(st.session_state.streak_days)
    st.markdown(f"<div class='streak-flame'>{streak_emoji}</div>", unsafe_allow_html=True)
    st.markdown(f"**{st.session_state.streak_days} day streak**")
    st.caption(f"Total writing days: {st.session_state.total_writing_days}")
    if st.session_state.streak_days >= 7:
        st.success("🏆 Weekly Writer!")
    if st.session_state.streak_days >= 30:
        st.success("🌟 Monthly Master!")
    # Photo Gallery
    st.divider()
    st.subheader("🖼️ Photo Gallery")
    if st.session_state.logged_in:
        total_images = get_total_user_images(st.session_state.user_id)
        st.metric("Total Photos", total_images)
        if total_images > 0:
            if st.button("📸 View Photos", use_container_width=True):
                st.session_state.show_image_upload = True
                st.rerun()
        else:
            st.info("No photos yet")
    # Quick Capture
    st.divider()
    st.subheader("⚡ Quick Capture")
    with st.expander("💭 **Jot Now - Quick Memory**", expanded=False):
        quick_note = st.text_area(
            "Got a memory? Jot it down:",
            value="",
            height=120,
            placeholder="E.g., 'That summer at grandma's house in 1995...'",
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
                st.info("Ready to write about this!")
                st.rerun()
        if st.session_state.get('quick_jots'):
            st.caption(f"📝 {len(st.session_state.quick_jots)} quick notes saved")
            if st.button("View Quick Notes", key="view_jots_btn"):
                st.session_state.show_jots = True
                st.rerun()
    # Interview Style
    st.divider()
    st.header("✍️ Interview Style")
    ghostwriter_mode = st.toggle(
        "Professional Ghostwriter Mode",
        value=st.session_state.ghostwriter_mode,
        key="ghostwriter_toggle"
    )
    if ghostwriter_mode != st.session_state.ghostwriter_mode:
        st.session_state.ghostwriter_mode = ghostwriter_mode
        st.rerun()
    spellcheck_enabled = st.toggle(
        "Auto Spelling Correction",
        value=st.session_state.spellcheck_enabled,
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
    # Historical Context
    st.divider()
    st.header("📜 Historical Context")
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            if events:
                st.success(f"✓ {len(events)} historical events loaded")
                st.caption(f"From {birth_year} to present")
                with st.expander("View Sample Events", expanded=False):
                    for i, event in enumerate(events[:5]):
                        region_emoji = "🇬🇧" if event.get('region') == 'UK' else "🌍"
                        st.markdown(f"**{region_emoji} {event['event']}**")
                        st.caption(f"{event['year_range']} • {event.get('category', 'General')}")
                        if i < 4:
                            st.divider()
                if st.button("📋 View All Historical Events", key="view_all_events"):
                    st.session_state.show_event_manager = True
                    st.rerun()
            else:
                st.info("No historical events loaded")
        except:
            st.info("Add birthdate to see historical context")
    else:
        st.info("Add your birthdate to enable historical context")
    # Session Navigation
    st.divider()
    st.header("📖 Sessions")
    for i, session in enumerate(SESSIONS):
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        responses_count = len(session_data.get("questions", {}))
        total_questions = len(session["questions"])
        if i == st.session_state.current_session:
            status = "▶️"
        elif responses_count == total_questions:
            status = "✅"
        elif responses_count > 0:
            status = "🟡"
        else:
            status = "●"
        button_text = f"{status} Session {session_id}: {session['title']} ({responses_count}/{total_questions})"
        if st.button(button_text, key=f"select_session_{i}", use_container_width=True):
            st.session_state.current_session = i
            st.session_state.current_question = 0
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()
    # Topic Navigation
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
    # Export Options
    st.subheader("📤 Export Options")
    total_answers = sum(len(session.get("questions", {})) for session in st.session_state.responses.values())
    total_images = get_total_user_images(st.session_state.user_id) if st.session_state.logged_in else 0
    st.caption(f"Total answers: {total_answers} • Total photos: {total_images}")
    if st.session_state.logged_in and st.session_state.user_id:
        export_data = {}
        for session in SESSIONS:
            session_id = session["id"]
            session_data = st.session_state.responses.get(session_id, {})
            if session_data.get("questions"):
                export_data[str(session_id)] = {
                    "title": session["title"],
                    "questions": session_data["questions"]
                }
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
            encoded_data = base64.b64encode(json_data.encode()).decode()
            publisher_url = f"{LOGO_URL.replace('logo.png', '')}deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/?data={encoded_data}"
            col1, col2 = st.columns(2)
            with col1:
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
                    key="download_stories_btn"
                )
            with col2:
                st.download_button(
                    label="📊 Complete Data",
                    data=json_data,
                    file_name=f"MemLife_Complete_{st.session_state.user_id}.json",
                    mime="application/json",
                    use_container_width=True,
                    key="download_complete_btn"
                )
            if total_images > 0:
                st.divider()
                st.write("**📸 Photo Export**")
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
    # Clear Data
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

# ── Main Content ──────────────────────────────────────────────────────────────
current_session = SESSIONS[st.session_state.current_session]
current_session_id = current_session["id"]
if st.session_state.current_question_override:
    current_question_text = st.session_state.current_question_override
    question_source = "custom"
else:
    current_question_text = current_session["questions"][st.session_state.current_question]
    question_source = "regular"

st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    st.subheader(f"Session {current_session_id}: {current_session['title']}")
    session_responses = len(st.session_state.responses.get(current_session_id, {}).get("questions", {}))
    total_questions = len(current_session["questions"])
    st.caption(f"📝 {session_responses}/{total_questions} topics answered")
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
        if st.button("Next Topic →", disabled=st.session_state.current_question >= len(current_session["questions"]) - 1, key="next_q_quick", use_container_width=True):
            st.session_state.current_question = min(len(current_session["questions"]) - 1, st.session_state.current_question + 1)
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.session_state.image_prompt_mode = False
            st.rerun()

st.markdown(f"""
<div class="question-box">
{current_question_text}
</div>
""", unsafe_allow_html=True)

# ── Image Controls ────────────────────────────────────────────────────────────
st.write("")
image_controls_container = st.container()
with image_controls_container:
    has_images = False
    if st.session_state.logged_in:
        session_images = get_session_images(st.session_state.user_id, current_session_id)
        has_images = len(session_images) > 0
    img_col1, img_col2 = st.columns(2)
    with img_col1:
        button_text = "📷 Add Photos" if not st.session_state.show_image_upload else "📷 Hide Photos"
        if st.button(button_text, key="toggle_image_upload", use_container_width=True):
            st.session_state.show_image_upload = not st.session_state.show_image_upload
            st.rerun()
    with img_col2:
        if has_images:
            if st.button("✨ Tell Photo Stories", key="photo_stories_btn", use_container_width=True, type="primary"):
                st.session_state.image_prompt_mode = True
                st.rerun()
        else:
            st.button("✨ Tell Photo Stories", key="disabled_photo_stories", use_container_width=True, disabled=True)
    if st.session_state.show_image_upload and st.session_state.logged_in:
        st.markdown("---")
        st.subheader("📤 Upload Photos for This Memory")
        uploaded_files = st.file_uploader(
            "Choose photos to upload",
            type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
            accept_multiple_files=True,
            key=f"simple_uploader_{current_session_id}"
        )
        if uploaded_files:
            description = st.text_input(
                "Add a description for these photos (optional):",
                placeholder="E.g., 'Family vacation, 1985'",
                key=f"simple_desc_{current_session_id}"
            )
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
        session_images = get_session_images(st.session_state.user_id, current_session_id)
        if session_images:
            st.divider()
            st.subheader("📷 Your Photos")
            selected_images = display_simple_gallery(st.session_state.user_id, current_session_id)
            if selected_images:
                st.session_state.selected_images_for_prompt = selected_images
                st.success(f"✅ Selected {len(selected_images)} photo(s)! Click 'Tell Photo Stories' to write about them.")
            else:
                st.info("No photos uploaded for this session yet.")
    st.markdown("---")
    if st.session_state.image_prompt_mode:
        if st.session_state.selected_images_for_prompt:
            selected_count = len(st.session_state.selected_images_for_prompt)
            st.success(f"📸 **Photo Story Mode**: Writing about {selected_count} selected photo(s)")
            st.info("The AI will ask you specific questions about each photo!")
        else:
            st.info("📸 **Photo Story Mode**: Select photos from the gallery to write about them")
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
    if question_source == "regular":
        session_data = st.session_state.responses.get(current_session_id, {})
        topics_answered = len(session_data.get("questions", {}))
        total_topics = len(current_session["questions"])
        if total_topics > 0:
            topic_progress = topics_answered / total_topics
            st.progress(min(topic_progress, 1.0))
            st.caption(f"📝 Topics explored: {topics_answered}/{total_topics} ({topic_progress*100:.0f}%)")

# ── Conversation & Chat ───────────────────────────────────────────────────────
if current_session_id not in st.session_state.session_conversations:
    st.session_state.session_conversations[current_session_id] = {}

conversation = st.session_state.session_conversations[current_session_id].get(current_question_text, [])

if not conversation:
    saved_response = st.session_state.responses[current_session_id]["questions"].get(current_question_text)
    if saved_response:
        conversation = [
            {"role": "assistant", "content": f"Let's explore this topic in detail: {current_question_text}"},
            {"role": "user", "content": saved_response["answer"]}
        ]
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation
    else:
        with st.chat_message("assistant", avatar="👔"):
            welcome_msg = f"""<div style='font-size: 1.4rem; margin-bottom: 1rem;'>
            Let's explore this topic in detail:
            </div>
            <div style='font-size: 1.8rem; font-weight: bold; color: #2c3e50; line-height: 1.3;'>
            {current_question_text}
            </div>"""
            if st.session_state.image_prompt_mode:
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #4CAF50; background-color: #e8f5e9; padding: 1rem; border-radius: 8px; border-left: 4px solid #4CAF50;'>
                📸 <strong>Photo Story Mode:</strong> You've selected {len(st.session_state.selected_images_for_prompt)} photo(s) to write about. I'll ask you questions about each photo to help tell their stories.
                </div>"""
            else:
                welcome_msg += f"""<div style='font-size: 1.1rem; margin-top: 1.5rem; color: #555;'>
                Take your time with this—good biographies are built from thoughtful reflection.
                </div>"""
            st.markdown(welcome_msg, unsafe_allow_html=True)
        conv_text = f"Let's explore this topic in detail: {current_question_text}\n\n"
        if st.session_state.image_prompt_mode:
            conv_text += f"📸 Photo Story Mode: You've selected {len(st.session_state.selected_images_for_prompt)} photo(s) to write about. I'll ask you questions about each photo to help tell their stories."
        else:
            conv_text += "Take your time with this—good biographies are built from thoughtful reflection."
        conversation.append({"role": "assistant", "content": conv_text})
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation

for i, message in enumerate(conversation):
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="👔"):
            st.markdown(message["content"])
    elif message["role"] == "user":
        is_editing = (st.session_state.editing == (current_session_id, current_question_text, i))
        with st.chat_message("user", avatar="👤"):
            if is_editing:
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
                            if st.session_state.spellcheck_enabled:
                                new_text = auto_correct_text(new_text)
                            conversation[i]["content"] = new_text
                            st.session_state.session_conversations[current_session_id][current_question_text] = conversation
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

input_container = st.container()
with input_container:
    st.write("")
    st.write("")
    user_input = st.chat_input("Type your answer here...", key="chat_input")
    if user_input:
        if st.session_state.spellcheck_enabled:
            user_input = auto_correct_text(user_input)
        conversation.append({"role": "user", "content": user_input})
        with st.chat_message("assistant", avatar="👔"):
            with st.spinner("Reflecting on your story..."):
                try:
                    conversation_history = conversation[:-1]
                    messages_for_api = [
                        {"role": "system", "content": get_system_prompt()},
                        *conversation_history,
                        {"role": "user", "content": user_input}
                    ]
                    temperature = 0.8 if st.session_state.ghostwriter_mode else 0.7
                    max_tokens = 400 if st.session_state.ghostwriter_mode else 300
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    ai_response = response.choices[0].message.content
                    if st.session_state.image_prompt_mode:
                        ai_response += f"\n\n📸 **Photo Note:** Keep describing your photos! Who, what, where, when, and why?"
                    st.markdown(ai_response)
                    conversation.append({"role": "assistant", "content": ai_response})
                except Exception as e:
                    error_msg = "Thank you for sharing that. Your response has been saved."
                    st.markdown(error_msg)
                    conversation.append({"role": "assistant", "content": error_msg})
        st.session_state.session_conversations[current_session_id][current_question_text] = conversation
        save_response(current_session_id, current_question_text, user_input)
        st.rerun()

# ── Word Progress ─────────────────────────────────────────────────────────────
st.divider()
progress_info = get_progress_info(current_session_id)
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

if st.button("✏️ Change Word Target", key="edit_word_target_bottom", use_container_width=True):
    st.session_state.editing_word_target = not st.session_state.editing_word_target
    st.rerun()

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
            st.session_state.responses[current_session_id]["word_target"] = new_target
            save_user_data(st.session_state.user_id, st.session_state.responses)
            st.session_state.editing_word_target = False
            st.rerun()
    with col_cancel:
        if st.button("❌ Cancel", key="cancel_word_target_bottom", use_container_width=True):
            st.session_state.editing_word_target = False
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
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

# ── Publish & Vault ───────────────────────────────────────────────────────────
st.divider()
st.subheader("📘 Publish & Save Your Biography")
current_user = st.session_state.get('user_id', '')
if current_user and current_user != "":
    export_data = {}
    for session in SESSIONS:
        session_id = session["id"]
        session_data = st.session_state.responses.get(session_id, {})
        if session_data.get("questions"):
            export_data[str(session_id)] = {
                "title": session["title"],
                "questions": session_data["questions"]
            }
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
        total_stories = sum(len(session['questions']) for session in export_data.values())
        total_images = sum(len(images) for images in image_data.values())
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
        encoded_data = base64.b64encode(json_data.encode()).decode()
        publisher_url = f"https://deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/?data={encoded_data}"
        st.success(f"✅ **{total_stories} stories**" + (f" + {total_images} photos" if total_images > 0 else "") + " ready to publish!")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🖨️ Create Your Book")
            st.markdown("""
            Generate a beautiful, formatted biography including your photos.
            Your enhanced book will include:
            • Professional formatting with images
            • Table of contents
            • All your stories organized
            • Photo captions and references
            • Ready to print or share
            """)
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
            vault_url = "https://digital-legacy-vault-vwvd4eclaeq4hxtcbbshr2.streamlit.app/"
            st.markdown(f'''
            <a href="{vault_url}" target="_blank">
            <button style="background: #3498db; color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600; cursor: pointer; width: 100%; margin-top: 1rem;">
            💾 Go to Secure Vault
            </button>
            </a>
            ''', unsafe_allow_html=True)
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

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
if st.session_state.user_account:
    profile = st.session_state.user_account['profile']
    account_age = (datetime.now() - datetime.fromisoformat(st.session_state.user_account['created_at'])).days
    total_images = get_total_user_images(st.session_state.user_id) if st.session_state.logged_in else 0
    footer_info = f"""
MemLife Timeline • 👤 {profile['first_name']} {profile['last_name']} • 📧 {profile['email']} •
🎂 {profile.get('birthdate', 'Not specified')} • 🔥 {st.session_state.streak_days} day streak •
📷 {total_images} photos • 📅 Account Age: {account_age} days
"""
    st.caption(footer_info)
else:
    st.caption(f"MemLife Timeline • User: {st.session_state.user_id} • 🔥 {st.session_state.streak_days} day streak")
