import base64, hashlib, hmac, json, time, urllib.parse
from . import config as C

def verify_init_data(init_data: str):
    """Validate Telegram WebApp initData. Returns user dict or None."""
    try:
        pairs = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        h = pairs.pop("hash", None)
        if not h: return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", C.BOT_TOKEN.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(hmac.new(secret, check.encode(), hashlib.sha256).hexdigest(), h): return None
        if time.time() - int(pairs.get("auth_date", 0)) > 86400: return None
        return json.loads(pairs["user"])
    except Exception:
        return None

def sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    return f"{raw}.{hmac.new(C.SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32]}"

def unsign(tok: str):
    try:
        raw, sig = tok.rsplit(".", 1)
        if not hmac.compare_digest(hmac.new(C.SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()[:32], sig): return None
        return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:
        return None
