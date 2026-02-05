# config/constants.py
"""
Central place for app-wide constants, session definitions, URLs, defaults.
Import from here instead of hardcoding values in biographer.py.
"""

# Branding & external services
LOGO_URL = "https://menuhunterai.com/wp-content/uploads/2026/01/logo.png"

PUBLISHER_BASE_URL = "https://deeperbiographer-dny9n2j6sflcsppshrtrmu.streamlit.app/"
VAULT_URL = "https://digital-legacy-vault-vwvd4eclaeq4hxtcbbshr2.streamlit.app/"

# Default values
DEFAULT_WORD_TARGET = 500

# All session definitions moved here from main file
SESSIONS = [
    {
        "id": 1,
        "title": "Childhood",
        "guidance": (
            "Welcome to Session 1: Childhood—this is where we lay the foundation of your story. "
            "Professional biographies thrive on specific, sensory-rich memories. I'm looking for "
            "the kind of details that transport readers: not just what happened, but how it felt, "
            "smelled, sounded. The 'insignificant' moments often reveal the most. "
            "Take your time—we're mining for gold here."
        ),
        "questions": [
            "What is your earliest memory?",
            "Can you describe your family home growing up?",
            "Who were the most influential people in your early years?",
            "What was school like for you?",
            "Were there any favourite games or hobbies?",
            "Is there a moment from childhood that shaped who you are?",
            "If you could give your younger self some advice, what would it be?"
        ],
        "completed": False,
        "word_target": 800
    },
    {
        "id": 2,
        "title": "Family & Relationships",
        "guidance": (
            "Welcome to Session 2: Family & Relationships—this is where we explore the people who shaped you. "
            "Family stories are complex ecosystems. We're not seeking perfect narratives, but authentic ones. "
            "The richest material often lives in the tensions, the unsaid things, the small rituals. "
            "My job is to help you articulate what usually goes unspoken. Think in scenes rather than summaries."
        ),
        "questions": [
            "How would you describe your relationship with your parents?",
            "Are there any family traditions you remember fondly?",
            "What was your relationship like with siblings or close relatives?",
            "Can you share a story about a family celebration or challenge?",
            "How did your family shape your values?"
        ],
        "completed": False,
        "word_target": 700
    },
    {
        "id": 3,
        "title": "Education & Growing Up",
        "guidance": (
            "Welcome to Session 3: Education & Growing Up—this is where we explore how you learned to navigate the world. "
            "Education isn't just about schools—it's about how you learned to navigate the world. "
            "We're interested in the hidden curriculum: what you learned about yourself, about systems, "
            "about survival and growth. Think beyond grades to transformation."
        ),
        "questions": [
            "What were your favourite subjects at school?",
            "Did you have any memorable teachers or mentors?",
            "How did you feel about exams and studying?",
            "Were there any big turning points in your education?",
            "Did you pursue further education or training?",
            "What advice would you give about learning?"
        ],
        "completed": False,
        "word_target": 600
    },
    # ← Add more sessions here later if you have them
]

# You can add more constants later, for example:
# EMAIL_CONFIG_KEYS = ["smtp_server", "smtp_port", "sender_email", "sender_password", "use_tls"]
# IMAGE_FOLDER = "user_images"
