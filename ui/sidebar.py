# ui/sidebar.py
import streamlit as st
from datetime import date
import re

from config.constants import SESSIONS, DEFAULT_WORD_TARGET
# Assuming you still have these in biographer.py for now or move later:
# get_total_user_images, get_streak_emoji, calculate_author_word_count, logout_user
# If not, you'll get NameError → we can fix in next round

def render_sidebar():
    """Renders the complete sidebar content."""
    
    # ── Profile Header ───────────────────────────────────────────────────────
    st.header("👤 Your Profile")
    
    if st.session_state.user_account:
        profile = st.session_state.user_account['profile']
        st.success(f"✓ **{profile.get('first_name', '')} {profile.get('last_name', '')}**")
        st.caption(f"📧 {profile.get('email', '—')}")
        
        if profile.get('birthdate'):
            st.caption(f"🎂 Born: {profile['birthdate']}")
        
        # Quick historical events count (if function exists)
        try:
            from core.historical_events import get_events_for_birth_year
            birth_year = int(profile['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)
            if events:
                uk = sum(1 for e in events if e.get('region') == 'UK')
                st.caption(f"📚 {len(events)} historical events ({uk} UK)")
        except:
            pass
        
        st.caption(f"👤 Account: {st.session_state.user_account.get('account_type', '—').title()}")
    
    if st.button("📝 Edit Profile", use_container_width=True):
        st.session_state.show_profile_setup = True
        st.rerun()
    
    if st.button("🚪 Log Out", use_container_width=True):
        logout_user()   # ← assume this function still exists in main file for now
    
    st.divider()
    
    # ── Streak ────────────────────────────────────────────────────────────────
    st.subheader("🔥 Writing Streak")
    
    streak_emoji = get_streak_emoji(st.session_state.streak_days)  # ← assume function exists
    st.markdown(f"<div class='streak-flame'>{streak_emoji}</div>", unsafe_allow_html=True)
    st.markdown(f"**{st.session_state.streak_days} day streak**")
    st.caption(f"Total writing days: {st.session_state.get('total_writing_days', 0)}")
    
    if st.session_state.streak_days >= 7:
        st.success("🏆 Weekly Writer!")
    if st.session_state.streak_days >= 30:
        st.success("🌟 Monthly Master!")
    
    # ── Photos quick stat ─────────────────────────────────────────────────────
    st.divider()
    st.subheader("🖼️ Photo Gallery")
    
    if st.session_state.logged_in:
        total = get_total_user_images(st.session_state.user_id)  # ← assume exists
        st.metric("Total Photos", total)
        
        if total > 0 and st.button("📸 View Photos", use_container_width=True):
            st.session_state.show_image_upload = True
            st.rerun()
    else:
        st.info("No photos yet")
    
    # ── Quick Capture (Jot Now) ───────────────────────────────────────────────
    st.divider()
    st.subheader("⚡ Quick Capture")
    
    with st.expander("💭 Jot Now - Quick Memory", expanded=False):
        quick_note = st.text_area(
            "Got a memory? Jot it down:",
            value="",
            height=120,
            placeholder="E.g., 'That summer at grandma's house in 1995...'",
            label_visibility="collapsed",
            key="sidebar_jot_area"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save Jot", key="save_jot_sidebar", use_container_width=True):
                if quick_note.strip():
                    # minimal save logic — extend later if needed
                    if "quick_jots" not in st.session_state:
                        st.session_state.quick_jots = []
                    st.session_state.quick_jots.append({
                        "text": quick_note,
                        "year": None,  # can improve later
                        "date": date.today().isoformat()
                    })
                    st.success("Saved!")
                    st.rerun()
        
        with col2:
            if quick_note.strip() and st.button("📝 Use as Prompt", key="use_jot_sidebar", use_container_width=True):
                st.session_state.current_question_override = quick_note
                st.rerun()
    
    # ── Interview Style Toggles ───────────────────────────────────────────────
    st.divider()
    st.header("✍️ Interview Style")
    
    ghost = st.toggle(
        "Professional Ghostwriter Mode",
        value=st.session_state.get("ghostwriter_mode", True),
        key="ghostwriter_toggle_sidebar"
    )
    if ghost != st.session_state.get("ghostwriter_mode", True):
        st.session_state.ghostwriter_mode = ghost
        st.rerun()
    
    spell = st.toggle(
        "Auto Spelling Correction",
        value=st.session_state.get("spellcheck_enabled", True),
        key="spellcheck_toggle_sidebar"
    )
    if spell != st.session_state.get("spellcheck_enabled", True):
        st.session_state.spellcheck_enabled = spell
        st.rerun()
    
    # ── Historical Context quick info ─────────────────────────────────────────
    st.divider()
    st.header("📜 Historical Context")
    if st.session_state.user_account and st.session_state.user_account['profile'].get('birthdate'):
        try:
            birth_year = int(st.session_state.user_account['profile']['birthdate'].split(', ')[-1])
            events = get_events_for_birth_year(birth_year)  # ← assume function exists
            st.success(f"✓ {len(events)} events loaded")
        except:
            st.info("Birthdate set — context active")
    else:
        st.info("Add birthdate to enable")
    
    # ── Session Navigation ────────────────────────────────────────────────────
    st.divider()
    st.header("📖 Sessions")
    
    for i, session in enumerate(SESSIONS):
        sid = session["id"]
        data = st.session_state.responses.get(sid, {})
        answered = len(data.get("questions", {}))
        total_q = len(session["questions"])
        
        if i == st.session_state.current_session:
            status = "▶️"
        elif answered == total_q:
            status = "✅"
        elif answered > 0:
            status = "🟡"
        else:
            status = "●"
        
        label = f"{status} Session {sid}: {session['title']} ({answered}/{total_q})"
        
        if st.button(label, key=f"session_select_{i}", use_container_width=True):
            st.session_state.current_session = i
            st.session_state.current_question = 0
            st.session_state.editing = None
            st.session_state.current_question_override = None
            st.rerun()
    
    # ── Export / Clear (bottom dangerous actions) ─────────────────────────────
    st.divider()
    st.subheader("📤 Export Options")
    # ... your existing export buttons / logic here ...
    # (keep minimal or move to separate component later)
    
    st.subheader("⚠️ Clear Data")
    # ... your clear session / clear all with confirmation logic ...
