"""MongoDB shard manager, roles/permissions, settings, users."""
import asyncio, re, time
from motor.motor_asyncio import AsyncIOMotorClient
from . import config as C

ROLES = {
    "owner":    {"*"},
    "admin":    {"upload", "videos", "users", "payments", "stats", "broadcast", "settings", "shards"},
    "uploader": {"upload", "videos", "stats"},
    "support":  {"users", "payments", "stats"},
}
ALL_PERMS = ["upload", "videos", "users", "payments", "stats", "broadcast", "settings", "shards", "admins"]

def allowed(role, perm):
    p = ROLES.get(role, set())
    return perm is None or "*" in p or perm in p

class Shards:
    """Videos + views live on the *active* shard (a separate cluster). When it reaches SHARD_MAX_MB the
    manager switches to the next one automatically. Meta (users, payments, admins, routing index) stays on shard 0's cluster."""
    def __init__(s):
        s.clients = [AsyncIOMotorClient(u, serverSelectionTimeoutMS=8000) for u in C.MONGO_URIS]
        s.meta = s.clients[0][f"{C.DB_NAME}_meta"]
        s.active, s._checked, s.lock, s.on_switch = 0, 0.0, asyncio.Lock(), None

    def db(s, i): return s.clients[i][f"{C.DB_NAME}_s{i}"]

    async def init(s):
        d = await s.meta.settings.find_one({"_id": "shard"})
        if d: s.active = min(d["active"], len(s.clients) - 1)
        else: await s.meta.settings.insert_one({"_id": "shard", "active": 0})
        await s.meta.users.create_index("sub_until")
        await s.meta.payments.create_index("track_id")
        for i in range(len(s.clients)):
            await s.db(i).videos.create_index([("created", -1)])
            await s.db(i).views.create_index([("vid", 1), ("uid", 1), ("ts", -1)])

    async def usage_mb(s, i):
        st = await s.db(i).command("dbStats")
        return (st.get("storageSize", 0) + st.get("indexSize", 0)) / 1048576

    async def set_active(s, i):
        s.active = i
        await s.meta.settings.update_one({"_id": "shard"}, {"$set": {"active": i}}, upsert=True)

    async def pick(s):
        """Active shard, auto-switching to the next one when capacity is reached."""
        if time.time() - s._checked > 45:
            async with s.lock:
                s._checked = time.time()
                try:
                    while s.active < len(s.clients) - 1 and await s.usage_mb(s.active) >= C.SHARD_MAX_MB:
                        full = s.active
                        await s.set_active(s.active + 1)
                        if s.on_switch: asyncio.create_task(s.on_switch(full, s.active))
                except Exception:
                    pass
        return s.active

    async def status(s):
        out = []
        for i in range(len(s.clients)):
            try:
                mb = await s.usage_mb(i); n = await s.db(i).videos.count_documents({}); ok = True
            except Exception:
                mb, n, ok = 0, 0, False
            out.append({"index": i, "usage_mb": round(mb, 1), "limit_mb": C.SHARD_MAX_MB, "videos": n,
                        "active": i == s.active, "online": ok})
        return out

    # ---- videos ----
    async def add_video(s, doc):
        i = await s.pick(); doc["shard"] = i
        await s.db(i).videos.insert_one(doc)
        await s.meta.video_index.insert_one({"_id": doc["_id"], "shard": i})

    async def shard_of(s, vid):
        d = await s.meta.video_index.find_one({"_id": vid})
        return d["shard"] if d else None

    async def get_video(s, vid):
        i = await s.shard_of(vid)
        return await s.db(i).videos.find_one({"_id": vid}) if i is not None else None

    async def update_video(s, vid, upd):
        i = await s.shard_of(vid)
        if i is not None: await s.db(i).videos.update_one({"_id": vid}, upd)

    async def delete_video(s, vid):
        i = await s.shard_of(vid)
        if i is None: return
        await s.db(i).videos.delete_one({"_id": vid}); await s.db(i).views.delete_many({"vid": vid})
        await s.meta.video_index.delete_one({"_id": vid})

    async def list_videos(s, limit=24, before=None, q=None):
        flt = {}
        if before: flt["created"] = {"$lt": float(before)}
        if q: flt["title"] = {"$regex": re.escape(q), "$options": "i"}
        res = await asyncio.gather(*[s.db(i).videos.find(flt).sort("created", -1).limit(limit).to_list(limit)
                                     for i in range(len(s.clients))], return_exceptions=True)
        items = [v for r in res if isinstance(r, list) for v in r]
        return sorted(items, key=lambda v: -v["created"])[:limit]

    async def record_view(s, vid, uid):
        """Counts one view per user per video per 30 min. Returns True if counted."""
        i = await s.shard_of(vid)
        if i is None: return False
        now = time.time()
        if await s.db(i).views.find_one({"vid": vid, "uid": uid, "ts": {"$gt": now - 1800}}): return False
        await s.db(i).views.insert_one({"vid": vid, "uid": uid, "ts": now})
        await s.db(i).videos.update_one({"_id": vid}, {"$inc": {"views": 1}})
        return True

    async def totals(s):
        vids = views = 0
        for i in range(len(s.clients)):
            try:
                vids += await s.db(i).videos.count_documents({})
                a = await s.db(i).videos.aggregate([{"$group": {"_id": None, "v": {"$sum": "$views"}}}]).to_list(1)
                views += a[0]["v"] if a else 0
            except Exception: pass
        return vids, views

S = Shards()

# ---- roles ----
async def role_of(uid):
    if uid in C.SUPER_ADMIN_IDS: return "owner"
    d = await S.meta.admins.find_one({"_id": uid})
    return d["role"] if d else None

async def has_perm(uid, perm):
    r = await role_of(uid)
    return bool(r) and allowed(r, perm)

# ---- settings ----
DEFAULTS = {
    "plans": [{"id": "m1", "name": "1 Month", "days": 30, "price": 5},
              {"id": "m3", "name": "3 Months", "days": 90, "price": 12},
              {"id": "y1", "name": "1 Year", "days": 365, "price": 40}],
    "wm_template": "{name} • {id}", "wm_opacity": 0.22, "notify": True,
    "welcome_text": f"<b>Welcome to {C.APP_NAME}</b>\n18+ only. Exclusive videos, streamed privately inside Telegram.",
}
_cache = {"t": 0, "v": None}

async def get_settings(fresh=False):
    if not fresh and _cache["v"] and time.time() - _cache["t"] < 20: return _cache["v"]
    d = await S.meta.settings.find_one({"_id": "app"}) or {}
    v = {**DEFAULTS, **{k: x for k, x in d.items() if k != "_id"}}
    _cache.update(t=time.time(), v=v); return v

async def save_settings(patch: dict):
    await S.meta.settings.update_one({"_id": "app"}, {"$set": patch}, upsert=True)
    _cache["t"] = 0

# ---- users ----
async def touch_user(u):
    """u: telegram user (dict or aiogram User). Returns user document."""
    g = (lambda k: u.get(k)) if isinstance(u, dict) else (lambda k: getattr(u, k, None))
    uid = g("id"); name = (g("first_name") or "") + (" " + g("last_name") if g("last_name") else "")
    doc = await S.meta.users.find_one({"_id": uid})
    now = time.time()
    if not doc:
        doc = {"_id": uid, "name": name.strip(), "username": g("username") or "", "joined": now,
               "sub_until": 0, "notify": True, "last_seen": now}
        await S.meta.users.insert_one(doc)
    elif now - doc.get("last_seen", 0) > 300 or doc.get("name") != name.strip():
        doc.update(name=name.strip(), username=g("username") or "", last_seen=now, blocked=False)
        await S.meta.users.update_one({"_id": uid}, {"$set": {"name": doc["name"], "username": doc["username"], "last_seen": now, "blocked": False}})
    return doc

def sub_state(u):
    until, now = u.get("sub_until", 0), time.time()
    act = until > now
    return {"active": act, "until": until, "days_left": int((until - now) // 86400) + 1 if act else 0}
