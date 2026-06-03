import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///aios_assistant.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "5000"))
    AI_PROVIDER = os.getenv("AI_PROVIDER", "rule_based")
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
    GMAIL_MBOX_PATH = os.getenv("GMAIL_MBOX_PATH", "")
    GMAIL_CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials/google_client_secret.json")
    GMAIL_TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "credentials/gmail_token.json")
    JOB_PORTAL_IMPORT_DIR = os.getenv("JOB_PORTAL_IMPORT_DIR", "imports/job_portals")
    WATCH_IMPORT_DIR = os.getenv("WATCH_IMPORT_DIR", "imports/watch")
