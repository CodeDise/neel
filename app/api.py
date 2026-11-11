import asyncio, io, json, math, re, secrets, time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from PIL import Image
from . import config as C, oxapay
from .bot import bot, broadcast, is_joined
from .core import ALL_PERMS, ROLES, S, allowed, get_settings, role_of, save_settings, sub_state, touch_user
from .security import sign, unsign, verify_init_data
from .streamer import stream_response

router = APIRouter()
THUMBS = Path(__file__).parent.parent / "data" / "thumbs"
SESS: dict = {}   # uid -> {nonce: last_ping}   (max 2 concurrent players per user)
LIVE: dict = {}   # vid -> {uid: last_ping}
ID_RE = re.compile(r"[A-Za-z0-9]{4,16}")

class Safe(dict):
    def __missing__(s, k): return "{" + k + "}"

# ---------- auth ----------
async def auth(request: Request):
    u = verify_init_data(request.headers.get("x-init-data", ""))
    if not u: raise HTTPException(401)
    doc = await touch_user(u)
    if doc.get("banned"): raise HTTPException(403, "banned")
    return doc

def need(perm):
    async def dep(u=Depends(auth)):
        role = await role_of(u["_id"])
        if not role or not allowed(role, perm): raise HTTPException(404)   # admins stay invisible
        return {"u": u, "role": role}
    return dep

def vpub(v, locked):
    return {"id": v["_id"], "title": v["title"], "duration": v.get("duration", 0), "views": v.get("views", 0),
            "premium": v.get("premium", True), "created": v["created"], "locked": locked, "thumb": f"/thumb/{v['_id']}"}

# ---------- user API ----------
@router.get("/api/me")
async def me(fresh: int = 0, u=Depends(auth)):
    s = await get_settings(); role = await role_of(u["_id"])
    return {"user": {"id": u["_id"], "name": u.get("name", ""), "username": u.get("username", "")},
            "sub": sub_state(u), "vip": bool(role),
            "joined": await is_joined(u["_id"], bool(fresh)),
            "channel": {"url": C.UPDATE_CHANNEL_URL, "on": bool(C.UPDATE_CHANNEL)},
            "plans": s["plans"], "app_name": C.APP_NAME,
            "wm_opacity": s["wm_opacity"], "bot": C.BOT_USERNAME}

@router.get("/api/videos")
async def videos(before: float = None, q: str = None, u=Depends(auth)):
    role = await role_of(u["_id"]); access = sub_state(u)["active"] or bool(role)
    items = await S.list_videos(24, before, q)
    return {"items": [vpub(v, v.get("premium", True) and not access) for v in items],
            "next": items[-1]["created"] if len(items) == 24 else None}

@router.get("/api/video/{vid}")
async def video(vid: str, u=Depends(auth)):
    v = await S.get_video(vid)
    if not v: raise HTTPException(404)
    access = sub_state(u)["active"] or bool(await role_of(u["_id"]))
    return {**vpub(v, v.get("premium", True) and not access), "link": C.video_link(vid), "live": len(_live(vid))}

def _live(vid):
    now = time.time(); d = LIVE.setdefault(vid, {})
    for k in [k for k, t in d.items() if now - t > 35]: d.pop(k, None)
    return d

@router.post("/api/video/{vid}/play")
async def play(vid: str, u=Depends(auth)):
    role = await role_of(u["_id"])
    if not role and not await is_joined(u["_id"]): raise HTTPException(403, "join")
    v = await S.get_video(vid)
    if not v: raise HTTPException(404)
    if v.get("premium", True) and not role and not sub_state(u)["active"]: raise HTTPException(402, "premium")
    now, nonce = time.time(), secrets.token_hex(6)
    ss = SESS.setdefault(u["_id"], {})
    for k in [k for k, t in ss.items() if now - t > 300]: ss.pop(k, None)
    while len(ss) >= 2: ss.pop(min(ss, key=ss.get))          # oldest session gets kicked
    ss[nonce] = now
    tok = sign({"v": vid, "u": u["_id"], "n": nonce, "e": int(now + 10800)})
    counted = await S.record_view(vid, u["_id"])
    st = await get_settings()
    wm = st["wm_template"].format_map(Safe(name=u.get("name", ""), id=u["_id"], username=("@" + u["username"]) if u.get("username") else ""))
    _live(vid)[u["_id"]] = now
    return {"url": f"/stream/{tok}", "token": tok, "wm": wm, "opacity": st["wm_opacity"],
            "views": v.get("views", 0) + (1 if counted else 0), "live": len(_live(vid))}

@router.post("/api/video/{vid}/ping")
async def ping(vid: str, body: dict, u=Depends(auth)):
    p = unsign(body.get("t", ""))
    if not p or p["u"] != u["_id"] or p["v"] != vid or p["n"] not in SESS.get(u["_id"], {}): raise HTTPException(403, "session")
    now = time.time(); SESS[u["_id"]][p["n"]] = now; _live(vid)[u["_id"]] = now
    v = await S.get_video(vid)
    return {"views": v.get("views", 0) if v else 0, "live": len(_live(vid))}

@router.get("/stream/{tok}")
async def stream(tok: str, request: Request):
    p = unsign(tok)
    if not p or p["e"] < time.time() or p["n"] not in SESS.get(p["u"], {}): raise HTTPException(403)
    v = await S.get_video(p["v"])
    if not v: raise HTTPException(404)
    return await stream_response(request, v)

@router.get("/thumb/{vid}")
async def thumb(vid: str):
    if not ID_RE.fullmatch(vid): raise HTTPException(404)
    p = THUMBS / f"{vid}.jpg"
    if not p.exists():
        v = await S.get_video(vid)
        if not v: raise HTTPException(404)
        f = await bot.get_file(v["thumb"]); buf = io.BytesIO(); await bot.download_file(f.file_path, buf)
        try:
            im = Image.open(buf).convert("RGB"); im.thumbnail((720, 720)); im.save(p, "JPEG", quality=82)
        except Exception: p.write_bytes(buf.getvalue())
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

# ---------- payments ----------
@router.post("/api/pay")
async def pay(body: dict, u=Depends(auth)):
    st = await get_settings()
    plan = next((p for p in st["plans"] if p["id"] == body.get("plan")), None)
    if not plan: raise HTTPException(404)
    if not C.OXAPAY_KEY: raise HTTPException(503, "payments off")
    order = f"{u['_id']}-{plan['id']}-{secrets.token_hex(4)}"
    try: inv = await oxapay.create_invoice(plan["price"], order, f"{C.APP_NAME} {plan['name']}")
    except Exception as e: raise HTTPException(502, str(e))
    await S.meta.payments.insert_one({"_id": order, "track_id": str(inv["track_id"]), "uid": u["_id"], "plan": plan["id"],
        "plan_name": plan["name"], "days": plan["days"], "amount": plan["price"], "status": "pending", "created": time.time()})
    return {"url": inv["payment_url"]}

@router.post("/webhook/oxapay")
async def webhook(request: Request):
    raw = await request.body()
    if not oxapay.valid(raw, request.headers.get("hmac", "")): raise HTTPException(401)
    d = json.loads(raw)
    if str(d.get("status", "")).lower() == "paid":
        p = await S.meta.payments.find_one({"track_id": str(d.get("track_id"))})
        if p and p["status"] != "paid":
            if float(d.get("amount") or 0) + 0.01 < p["amount"]:
                await S.meta.payments.update_one({"_id": p["_id"]}, {"$set": {"status": "underpaid"}})
            else:
                await S.meta.payments.update_one({"_id": p["_id"]}, {"$set": {"status": "paid", "paid_at": time.time()}})
                await grant(p["uid"], p["days"], f"✅ Payment received — <b>{p['plan_name']}</b> is active. Enjoy!")
    return PlainTextResponse("OK")

async def grant(uid, days, msg=None):
    u = await S.meta.users.find_one({"_id": uid}) or {}
    base = max(time.time(), u.get("sub_until", 0))
    await S.meta.users.update_one({"_id": uid}, {"$set": {"sub_until": base + days * 86400}}, upsert=True)
    if msg:
        try: await bot.send_message(uid, msg)
        except Exception: pass

# ---------- admin API (404 for everyone who isn't an admin) ----------
@router.get("/api/admin/me")
async def a_me(a=Depends(need(None))):
    return {"role": a["role"], "perms": [p for p in ALL_PERMS if allowed(a["role"], p)], "name": a["u"].get("name", "")}

@router.get("/api/admin/stats")
async def a_stats(a=Depends(need("stats"))):
    now = time.time(); vids, views = await S.totals()
    rev = lambda m: S.meta.payments.aggregate([{"$match": {"status": "paid", **m}}, {"$group": {"_id": None, "s": {"$sum": "$amount"}}}]).to_list(1)
    t, m = await rev({}), await rev({"paid_at": {"$gt": now - 30 * 86400}})
    return {"users": await S.meta.users.count_documents({}), "subs": await S.meta.users.count_documents({"sub_until": {"$gt": now}}),
            "videos": vids, "views": views, "revenue": t[0]["s"] if t else 0, "revenue30": m[0]["s"] if m else 0,
            "live": sum(len(_live(v)) for v in list(LIVE)), "shards": await S.status()}

@router.get("/api/admin/videos")
async def a_videos(q: str = None, before: float = None, a=Depends(need("videos"))):
    items = await S.list_videos(30, before, q)
    return {"items": [{**vpub(v, False), "size": v.get("size", 0), "live": len(_live(v["_id"])), "shard": v.get("shard", 0)} for v in items],
            "next": items[-1]["created"] if len(items) == 30 else None}

@router.patch("/api/admin/video/{vid}")
async def a_vpatch(vid: str, body: dict, a=Depends(need("videos"))):
    s = {}
    if "title" in body: s["title"] = str(body["title"]).strip()[:120]
    if "premium" in body: s["premium"] = bool(body["premium"])
    if s: await S.update_video(vid, {"$set": s})
    return {"ok": True}

@router.delete("/api/admin/video/{vid}")
async def a_vdel(vid: str, a=Depends(need("videos"))):
    v = await S.get_video(vid)
    if v:
        try: await bot.delete_message(C.STORAGE_CHANNEL_ID, v["msg_id"])
        except Exception: pass
        await S.delete_video(vid); (THUMBS / f"{vid}.jpg").unlink(missing_ok=True)
    return {"ok": True}

@router.get("/api/admin/users")
async def a_users(q: str = "", a=Depends(need("users"))):
    flt = {}
    if q:
        flt = {"_id": int(q)} if q.lstrip("-").isdigit() else {"$or": [{"username": {"$regex": re.escape(q.lstrip("@")), "$options": "i"}}, {"name": {"$regex": re.escape(q), "$options": "i"}}]}
    us = await S.meta.users.find(flt).sort("last_seen", -1).limit(50).to_list(50)
    return {"items": [{"id": u["_id"], "name": u.get("name", ""), "username": u.get("username", ""), "sub_until": u.get("sub_until", 0),
                       "banned": bool(u.get("banned")), "blocked": bool(u.get("blocked")), "last_seen": u.get("last_seen", 0)} for u in us]}

@router.post("/api/admin/user/{uid}")
async def a_user(uid: int, body: dict, a=Depends(need("users"))):
    if "days" in body:
        d = int(body["days"])
        if d > 0: await grant(uid, d, f"🎁 You received <b>{d} days</b> of premium.")
        else: await S.meta.users.update_one({"_id": uid}, {"$set": {"sub_until": 0}})
    if "banned" in body: await S.meta.users.update_one({"_id": uid}, {"$set": {"banned": bool(body["banned"])}})
    return {"ok": True}

@router.get("/api/admin/payments")
async def a_pay(a=Depends(need("payments"))):
    ps = await S.meta.payments.find().sort("created", -1).limit(60).to_list(60)
    return {"items": [{"id": p["_id"], "uid": p["uid"], "plan": p.get("plan_name", ""), "amount": p["amount"], "status": p["status"], "created": p["created"]} for p in ps]}

@router.get("/api/admin/admins")
async def a_admins(a=Depends(need("admins"))):
    rows = [{"id": i, "role": "owner", "fixed": True} for i in C.SUPER_ADMIN_IDS]
    rows += [{"id": d["_id"], "role": d["role"]} async for d in S.meta.admins.find()]
    return {"items": rows, "roles": [r for r in ROLES if r != "owner"]}

@router.post("/api/admin/admins")
async def a_admin_add(body: dict, a=Depends(need("admins"))):
    if body.get("role") not in ROLES or body["role"] == "owner": raise HTTPException(400)
    await S.meta.admins.update_one({"_id": int(body["id"])}, {"$set": {"role": body["role"], "added": time.time()}}, upsert=True)
    return {"ok": True}

@router.delete("/api/admin/admins/{uid}")
async def a_admin_del(uid: int, a=Depends(need("admins"))):
    await S.meta.admins.delete_one({"_id": uid}); return {"ok": True}

@router.get("/api/admin/shards")
async def a_shards(a=Depends(need("shards"))): return {"items": await S.status()}

@router.post("/api/admin/shards/active")
async def a_shard_set(body: dict, a=Depends(need("shards"))):
    i = int(body["index"])
    if not 0 <= i < len(S.clients): raise HTTPException(400)
    await S.set_active(i); return {"ok": True}

@router.get("/api/admin/settings")
async def a_set(a=Depends(need("settings"))): return await get_settings(True)

@router.post("/api/admin/settings")
async def a_set_save(body: dict, a=Depends(need("settings"))):
    p = {}
    if "plans" in body:
        p["plans"] = [{"id": re.sub(r"\W", "", str(x["id"]))[:12], "name": str(x["name"])[:30], "days": int(x["days"]), "price": float(x["price"])} for x in body["plans"] if x.get("id")]
    if "wm_template" in body: p["wm_template"] = str(body["wm_template"])[:80]
    if "wm_opacity" in body: p["wm_opacity"] = min(0.6, max(0.05, float(body["wm_opacity"])))
    if "notify" in body: p["notify"] = bool(body["notify"])
    if "welcome_text" in body: p["welcome_text"] = str(body["welcome_text"])[:900]
    if p: await save_settings(p)
    return {"ok": True}

@router.post("/api/admin/broadcast")
async def a_bc(body: dict, a=Depends(need("broadcast"))):
    t = str(body.get("text", "")).strip()
    if not t: raise HTTPException(400)
    asyncio.create_task(broadcast(text=t, report_to=a["u"]["_id"])); return {"ok": True}
