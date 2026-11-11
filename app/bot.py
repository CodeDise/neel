import asyncio, html, logging, secrets, time
from pathlib import Path
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, FSInputFile, InlineKeyboardButton, MenuButtonWebApp, Message, WebAppInfo)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from . import config as C
from .core import S, get_settings, has_perm, role_of, touch_user

log = logging.getLogger("bot")
bot = Bot(C.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
r = Router(); dp.include_router(r)
esc = html.escape
IMG = Path(__file__).parent / "static" / "img"
FILE_IDS, JOINED = {}, {}

class Up(StatesGroup):
    video = State(); thumb = State(); title = State()

class Perm(Filter):
    def __init__(s, p): s.p = p
    async def __call__(s, ev): return bool(ev.from_user) and await has_perm(ev.from_user.id, s.p)

# ---------- helpers ----------
async def is_joined(uid, force=False):
    if not C.UPDATE_CHANNEL: return True
    if await role_of(uid): return True
    c = JOINED.get(uid)
    if c and not force and time.time() - c < 90: return True
    try:
        m = await bot.get_chat_member(C.UPDATE_CHANNEL, uid)
        ok = m.status in ("member", "administrator", "creator") or (m.status == "restricted" and getattr(m, "is_member", False))
    except Exception as e:
        log.error("force-join check failed (is the bot admin in UPDATE_CHANNEL?): %s", e); ok = False
    if ok: JOINED[uid] = time.time()
    return ok

async def send_img(chat_id, name, caption, kb=None):
    fid = FILE_IDS.get(name)
    try:
        m = await bot.send_photo(chat_id, fid or FSInputFile(IMG / name), caption=caption, reply_markup=kb)
        if not fid: FILE_IDS[name] = m.photo[-1].file_id
    except Exception as e:
        log.warning("send_img: %s", e); await bot.send_message(chat_id, caption, reply_markup=kb)

def fmt_dur(s):
    s = int(s or 0); h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"

def webapp_kb(vid=None, plans=False):
    kb = InlineKeyboardBuilder()
    url = C.WEBAPP_URL + (f"/?v={vid}" if vid else "")
    kb.row(InlineKeyboardButton(text="▶️ Watch now" if vid else "🎬 Open app", web_app=WebAppInfo(url=url)))
    if plans or not vid:
        kb.row(InlineKeyboardButton(text="💎 Go premium", web_app=WebAppInfo(url=C.WEBAPP_URL + "/?tab=plans")))
    return kb.as_markup()

async def send_welcome(chat_id):
    s = await get_settings()
    await send_img(chat_id, "welcome.jpg", s["welcome_text"], webapp_kb())

async def send_join(chat_id, payload=""):
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Join channel", url=C.UPDATE_CHANNEL_URL)
    kb.button(text="✅ I've joined", callback_data=f"chk:{payload}"[:64]); kb.adjust(1)
    await send_img(chat_id, "welcome.jpg", f"<b>One step first</b>\nJoin our updates channel to unlock {esc(C.APP_NAME)}.", kb.as_markup())

async def send_video_card(chat_id, vid):
    v = await S.get_video(vid)
    if not v: return await send_welcome(chat_id)
    cap = f"🎬 <b>{esc(v['title'])}</b>\n⏱ {fmt_dur(v.get('duration'))}  •  {'💎 Premium' if v.get('premium', True) else '🔓 Free'}"
    try: await bot.send_photo(chat_id, v["thumb"], caption=cap, reply_markup=webapp_kb(vid), protect_content=True)
    except Exception: await bot.send_message(chat_id, cap, reply_markup=webapp_kb(vid))

async def entry(chat_id, payload=""):
    if payload.startswith("v_"): await send_video_card(chat_id, payload[2:])
    else: await send_welcome(chat_id)

# ---------- public handlers ----------
@r.message(CommandStart())
async def start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear(); await touch_user(m.from_user)
    payload = command.args or ""
    if not await is_joined(m.from_user.id, True): return await send_join(m.chat.id, payload)
    await entry(m.chat.id, payload)

@r.callback_query(F.data.startswith("chk:"))
async def chk(cb: CallbackQuery):
    if not await is_joined(cb.from_user.id, True):
        return await cb.answer("You haven't joined yet.", show_alert=True)
    await cb.answer("Welcome!")
    try: await cb.message.delete()
    except Exception: pass
    await entry(cb.from_user.id, cb.data[4:])

# ---------- admin entry (invisible to normal users) ----------
def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬆️ Upload video", callback_data="up")
    kb.row(InlineKeyboardButton(text="🛠 Admin panel", web_app=WebAppInfo(url=C.WEBAPP_URL + "/admin")))
    return kb.adjust(1).as_markup()

@r.message(Command("admin"), Perm(None))
async def admin_cmd(m: Message, state: FSMContext):
    await state.clear(); await m.answer("<b>Admin</b>", reply_markup=admin_kb())

# ---------- upload: video -> thumbnail -> title ----------
STEP = {"video": "<b>Step 1/3</b> — send the <b>video file</b>.", "thumb": "<b>Step 2/3</b> — send the <b>thumbnail</b> image.",
        "title": "<b>Step 3/3</b> — send the <b>title</b> as text."}

@r.callback_query(F.data == "up", Perm("upload"))
async def up_cb(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Up.video); await cb.answer(); await cb.message.answer(STEP["video"])

@r.message(Command("upload"), Perm("upload"))
async def up_cmd(m: Message, state: FSMContext):
    await state.set_state(Up.video); await m.answer(STEP["video"])

@r.message(Command("cancel"), Perm(None))
async def cancel_cmd(m: Message, state: FSMContext):
    await state.clear(); await m.answer("Cancelled.")

@r.message(Up.video, F.video | F.document, Perm("upload"))
async def got_video(m: Message, state: FSMContext):
    if m.video: f, kind = m.video, "video"
    elif m.document and (m.document.mime_type or "").startswith("video/"): f, kind = m.document, "document"
    else: return await m.answer("That isn't a video. " + STEP["video"])
    await state.update_data(file_id=f.file_id, size=f.file_size or 0, mime=f.mime_type or "video/mp4", kind=kind,
                            duration=getattr(f, "duration", 0) or 0, w=getattr(f, "width", 0), h=getattr(f, "height", 0),
                            premium=True)
    await state.set_state(Up.thumb); await m.answer("✅ Video received.\n" + STEP["thumb"])

@r.message(Up.video)
async def need_video(m: Message): await m.answer(STEP["video"])

@r.message(Up.thumb, F.photo | F.document, Perm("upload"))
async def got_thumb(m: Message, state: FSMContext):
    if m.photo: tid = m.photo[-1].file_id
    elif m.document and (m.document.mime_type or "").startswith("image/"): tid = m.document.file_id
    else: return await m.answer(STEP["thumb"])
    await state.update_data(thumb=tid); await state.set_state(Up.title); await m.answer("✅ Thumbnail saved.\n" + STEP["title"])

@r.message(Up.thumb)
async def need_thumb(m: Message): await m.answer(STEP["thumb"])

def preview_kb(premium):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Publish", callback_data="pub")
    kb.button(text="🔓 Make free" if premium else "💎 Make premium", callback_data="tgl")
    kb.button(text="❌ Cancel", callback_data="cx"); return kb.adjust(1).as_markup()

def preview_cap(d):
    return (f"🎬 <b>{esc(d['title'])}</b>\n⏱ {fmt_dur(d['duration'])}  •  {round(d['size'] / 1048576, 1)} MB\n"
            f"Access: {'💎 Premium' if d['premium'] else '🔓 Free'}")

@r.message(Up.title, F.text, Perm("upload"))
async def got_title(m: Message, state: FSMContext):
    await state.update_data(title=m.text.strip()[:120]); d = await state.get_data()
    try: await m.answer_photo(d["thumb"], caption=preview_cap(d), reply_markup=preview_kb(d["premium"]))
    except Exception: await m.answer(preview_cap(d), reply_markup=preview_kb(d["premium"]))

@r.message(Up.title)
async def need_title(m: Message): await m.answer(STEP["title"])

async def _edit(cb, text, kb=None):
    try:
        if cb.message.photo: await cb.message.edit_caption(caption=text, reply_markup=kb)
        else: await cb.message.edit_text(text, reply_markup=kb)
    except Exception: pass

@r.callback_query(F.data == "tgl", Up.title, Perm("upload"))
async def tgl(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data(); await state.update_data(premium=not d["premium"]); d["premium"] = not d["premium"]
    await cb.answer(); await _edit(cb, preview_cap(d), preview_kb(d["premium"]))

@r.callback_query(F.data == "cx", Perm("upload"))
async def cx(cb: CallbackQuery, state: FSMContext):
    await state.clear(); await cb.answer("Cancelled"); await _edit(cb, "❌ Cancelled.")

@r.callback_query(F.data == "pub", Up.title, Perm("upload"))
async def publish(cb: CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if not d.get("title"): return await cb.answer("Title missing", show_alert=True)
    await cb.answer("Publishing…"); await state.clear()
    vid = secrets.token_urlsafe(6).replace("-", "a").replace("_", "b")
    cap = f"🎬 {esc(d['title'])}\n#{vid}"
    try:
        if d["kind"] == "video": cm = await bot.send_video(C.STORAGE_CHANNEL_ID, d["file_id"], caption=cap, protect_content=True); f = cm.video
        else: cm = await bot.send_document(C.STORAGE_CHANNEL_ID, d["file_id"], caption=cap, protect_content=True); f = cm.document
        try: await bot.send_photo(C.STORAGE_CHANNEL_ID, d["thumb"], caption=f"thumbnail #{vid}", reply_to_message_id=cm.message_id)
        except Exception: pass
    except Exception as e:
        log.exception("channel upload failed"); return await _edit(cb, f"⚠️ Couldn't save to the storage channel: {esc(str(e))}\nIs the bot an admin there?")
    await S.add_video({"_id": vid, "title": d["title"], "file_id": f.file_id, "size": f.file_size or d["size"], "mime": d["mime"],
                       "duration": d["duration"], "w": d["w"], "h": d["h"], "thumb": d["thumb"], "msg_id": cm.message_id,
                       "premium": d["premium"], "views": 0, "created": time.time(), "by": cb.from_user.id})
    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="▶️ Open in app", url=C.video_link(vid)))
    kb.button(text="⬆️ Upload another", callback_data="up"); kb.adjust(1)
    await _edit(cb, f"✅ <b>Published</b> — live in the app now.\n\n🔗 Share link:\n<code>{C.video_link(vid)}</code>", kb.as_markup())
    v = await S.get_video(vid)
    if (await get_settings())["notify"]: asyncio.create_task(broadcast(video=v, report_to=cb.from_user.id))

# ---------- push notifications / broadcast ----------
async def broadcast(video=None, text=None, report_to=None):
    sent = failed = 0
    kb = None
    if video:
        b = InlineKeyboardBuilder(); b.row(InlineKeyboardButton(text="▶️ Watch now", url=C.video_link(video["_id"]))); kb = b.as_markup()
        text = f"🆕 <b>New video</b>\n{esc(video['title'])}\n⏱ {fmt_dur(video.get('duration'))}  •  {'💎 Premium' if video.get('premium', True) else '🔓 Free'}"
    async for u in S.meta.users.find({"notify": True, "blocked": {"$ne": True}, "banned": {"$ne": True}}, {"_id": 1}):
        for _ in range(2):
            try:
                if video: await bot.send_photo(u["_id"], video["thumb"], caption=text, reply_markup=kb, protect_content=True)
                else: await bot.send_message(u["_id"], text)
                sent += 1; break
            except TelegramRetryAfter as e: await asyncio.sleep(e.retry_after + 1)
            except TelegramForbiddenError:
                await S.meta.users.update_one({"_id": u["_id"]}, {"$set": {"blocked": True}}); failed += 1; break
            except Exception: failed += 1; break
        await asyncio.sleep(0.05)
    if report_to:
        try: await bot.send_message(report_to, f"📣 Notification sent to {sent} users ({failed} failed).")
        except Exception: pass

async def notify_owners(text):
    for uid in C.SUPER_ADMIN_IDS:
        try: await bot.send_message(uid, text)
        except Exception: pass

async def on_shard_switch(full, new):
    await notify_owners(f"🗄 Shard {full} reached its limit. New videos now go to shard {new}.")

# ---------- fallback: anything else looks like a normal user chat ----------
@r.message(F.chat.type == "private")
async def fallback(m: Message):
    await touch_user(m.from_user)
    if not await is_joined(m.from_user.id): return await send_join(m.chat.id)
    await send_welcome(m.chat.id)

async def setup():
    S.on_switch = on_shard_switch
    await bot.delete_webhook(drop_pending_updates=False)
    try: await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Open", web_app=WebAppInfo(url=C.WEBAPP_URL)))
    except Exception: pass
