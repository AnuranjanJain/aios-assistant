import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    AIOS_DESKTOP = os.getenv("AIOS_DESKTOP", "") == "1"
    AIOS_DATA_DIR = os.getenv("AIOS_DATA_DIR", "")
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///aios_assistant.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {
            "timeout": 30,
            "check_same_thread": False,
        }
    }
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    AI_PROVIDER = os.getenv("AI_PROVIDER", "rule_based")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    MEMORY_VECTOR_BACKEND = os.getenv("MEMORY_VECTOR_BACKEND", "auto")
    MEMORY_VECTOR_PATH = os.getenv("MEMORY_VECTOR_PATH", "instance/memory_vectors")
    USER_DISPLAY_NAME = os.getenv("USER_DISPLAY_NAME", "Anuranjan")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    GMAIL_MBOX_PATH = os.getenv("GMAIL_MBOX_PATH", "")
    GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials/google_client_secret.json")
    GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "credentials/gmail_token.json")
    GMAIL_OPPORTUNITY_QUERY = os.getenv("GMAIL_OPPORTUNITY_QUERY", "")
    GMAIL_HACKATHON_QUERY = os.getenv("GMAIL_HACKATHON_QUERY", "")
    JOB_PORTAL_IMPORT_DIR = os.getenv("JOB_PORTAL_IMPORT_DIR", "imports/job_portals")
    HACKATHON_IMPORT_DIR = os.getenv("HACKATHON_IMPORT_DIR", "imports/hackathons")
    HACKATHON_SCAN_INTERVAL_MINUTES = os.getenv("HACKATHON_SCAN_INTERVAL_MINUTES", "15")
    WATCH_IMPORT_DIR = os.getenv("WATCH_IMPORT_DIR", "imports/watch")
    LOCAL_API_TOKEN = os.getenv("LOCAL_API_TOKEN", "")
