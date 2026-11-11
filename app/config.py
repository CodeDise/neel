import os
from dotenv import load_dotenv
load_dotenv()

def _ids(v): return [int(x) for x in v.replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()]

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.getenv("BOT_USERNAME", "").lstrip("@")
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")
MINIAPP_SHORT = os.getenv("MINIAPP_SHORT", "").strip()
WEBAPP_URL = os.environ["WEBAPP_URL"].rstrip("/")
STORAGE_CHANNEL_ID = int(os.environ["STORAGE_CHANNEL_ID"])
_uc = os.getenv("UPDATE_CHANNEL", "").strip()
UPDATE_CHANNEL = int(_uc) if _uc.lstrip("-").isdigit() else _uc
UPDATE_CHANNEL_URL = os.getenv("UPDATE_CHANNEL_URL") or (f"https://t.me/{_uc.lstrip('@')}" if _uc.startswith("@") else "")
SUPER_ADMIN_IDS = _ids(os.getenv("SUPER_ADMIN_IDS", ""))
MONGO_URIS = [u.strip() for u in os.environ["MONGO_URIS"].split(";") if u.strip()]
DB_NAME = os.getenv("DB_NAME", "neel")
SHARD_MAX_MB = int(os.getenv("SHARD_MAX_MB", "450"))
OXAPAY_KEY = os.getenv("OXAPAY_KEY", "")
APP_NAME = os.getenv("APP_NAME", "Neel")
SECRET = os.getenv("SECRET") or BOT_TOKEN

def video_link(vid: str) -> str:
    """Share link: opens the Mini App directly on the video."""
    if MINIAPP_SHORT:
        return f"https://t.me/{BOT_USERNAME}/{MINIAPP_SHORT}?startapp=v_{vid}"
    return f"https://t.me/{BOT_USERNAME}?start=v_{vid}"
