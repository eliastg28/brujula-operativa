import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


MODE = _env("MODE", "demo").lower()  # demo | live
DB_PATH = Path(_env("DB_PATH", str(ROOT / "data" / "brujula.db")))
CONFIG_DIR = ROOT / "config"

MCP_PORT = int(_env("MCP_PORT", "8001"))
MCP_URL = _env("MCP_URL", f"http://127.0.0.1:{MCP_PORT}/mcp")

ANTHROPIC_MODEL = _env("ANTHROPIC_MODEL", "claude-opus-5-5")
AI_EFFORT = _env("AI_EFFORT", "low")
AI_MODE = _env("AI_MODE", "auto").lower()
AI_TIMEOUT = float(_env("AI_TIMEOUT", "60"))

JIRA_BASE_URL = _env("JIRA_BASE_URL").rstrip("/")
JIRA_EMAIL = _env("JIRA_EMAIL")
JIRA_API_TOKEN = _env("JIRA_API_TOKEN")
JIRA_PROJECT_KEY = _env("JIRA_PROJECT_KEY")  # en live, proyecto único para todos los squads

TEAMS_WEBHOOK_URL = _env("TEAMS_WEBHOOK_URL")

SMTP_HOST = _env("SMTP_HOST")
SMTP_PORT = int(_env("SMTP_PORT", "587"))
SMTP_USER = _env("SMTP_USER")
SMTP_PASSWORD = _env("SMTP_PASSWORD")
SMTP_FROM = _env("SMTP_FROM")

APP_PUBLIC_URL = _env("APP_PUBLIC_URL", "http://localhost:5173")


def ai_available() -> bool:
    if AI_MODE == "off":
        return False
    return bool(_env("ANTHROPIC_API_KEY") or _env("ANTHROPIC_AUTH_TOKEN"))


def jira_live() -> bool:
    return MODE == "live" and bool(JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN)


def teams_live() -> bool:
    return MODE == "live" and bool(TEAMS_WEBHOOK_URL)


def smtp_live() -> bool:
    return MODE == "live" and bool(SMTP_HOST and SMTP_FROM)
