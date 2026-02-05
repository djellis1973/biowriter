# vignettes.py

from datetime import datetime

def get_standard_vignette_topics():
    return [
        "Life Lesson",
        "Achievement",
        "Work Loss of Life",
        "Illness",
        "New Child",
        "Marriage",
        "Travel",
        "Relationship",
        "Interests",
        "Education",
    ]

def get_user_vignettes(user_id):
    user_data = load_user_data(user_id)
    return user_data.get('vignettes', [])

def add_vignette(user_id, topic, content):
    user_data = load_user_data(user_id)
    vignettes = user_data.get('vignettes', [])
    new_vignette = {
        "topic": topic,
        "content": content,
        "created_at": datetime.now().isoformat(),
        "published": True,
    }
    vignettes.append(new_vignette)
    user_data['vignettes'] = vignettes
    save_user_data(user_id, user_data)

def add_vignette_to_main_story(user_id, vignette_index, session_id, topic_override=None):
    user_data = load_user_data(user_id)
    vignette = user_data['vignettes'][vignette_index]
    topic = topic_override or f"Vignette: {vignette['topic']}"
    add_topic_to_session(user_id, session_id, topic)
    responses = user_data.get("responses", {})
    if session_id not in responses:
        responses[session_id] = {
            "title": "",  # Will be set later
            "questions": {},
            "summary": "",
            "completed": False,
            "word_target": 500,
        }
    responses[session_id]["questions"][topic] = {"answer": vignette['content']}
    user_data["responses"] = responses
    save_user_data(user_id, user_data)
