# session_manager.py

# Note: This assumes load_user_data and save_user_data are defined in the main script and can be imported or are global.
# For modularity, we can pass them if needed, but for simplicity, assume they are available.

standard_sessions = [
    # Replace with the original SESSIONS list. Since not provided in the query, here's an example structure.
    # In practice, copy the SESSIONS definition from your original code here.
    {"id": 1, "title": "Early Years", "questions": ["Where were you born?", "What are your earliest memories?"], "word_target": 500, "guidance": "Reflect on your childhood."},
    {"id": 2, "title": "Education", "questions": ["What schools did you attend?", "Favorite subjects?"], "word_target": 600},
    # Add all original sessions here...
]

def get_sessions(user_id):
    user_data = load_user_data(user_id)
    user_sessions = user_data.get('sessions', [])
    sessions = []
    for s in standard_sessions:
        user_s = next((us for us in user_sessions if us['id'] == s['id']), None)
        if user_s:
            sessions.append(user_s)
        else:
            sessions.append(s.copy())  # Copy to avoid modifying standard
    for us in user_sessions:
        if us['id'] not in [s['id'] for s in standard_sessions]:
            sessions.append(us)
    sessions.sort(key=lambda s: s['id'])
    return sessions

def add_session(user_id, title):
    user_data = load_user_data(user_id)
    user_sessions = user_data.get('sessions', [])
    max_id = max([s['id'] for s in user_sessions] + [len(standard_sessions)])
    new_id = max_id + 1
    new_session = {"id": new_id, "title": title, "questions": [], "word_target": 500, "guidance": ""}
    user_sessions.append(new_session)
    user_data['sessions'] = user_sessions
    save_user_data(user_id, user_data)

def add_topic_to_session(user_id, session_id, topic):
    user_data = load_user_data(user_id)
    user_sessions = user_data.get('sessions', [])
    for s in user_sessions:
        if s['id'] == session_id:
            s['questions'].append(topic)
            break
    else:
        # If not in user_sessions, it might be standard; add to user_sessions
        standard_s = next((ss for ss in standard_sessions if ss['id'] == session_id), None)
        if standard_s:
            new_s = standard_s.copy()
            new_s['questions'] = new_s['questions'] + [topic]
            user_sessions.append(new_s)
    user_data['sessions'] = user_sessions
    save_user_data(user_id, user_data)
