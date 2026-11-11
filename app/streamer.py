"""Streams big videos from Telegram (MTProto, no 20MB Bot API limit) with HTTP Range support."""
import re
from fastapi import Response
from fastapi.responses import StreamingResponse
from pyrogram import Client
from . import config as C

client = Client("stream", api_id=C.API_ID, api_hash=C.API_HASH, bot_token=C.BOT_TOKEN, in_memory=True, no_updates=True)
CH = 1024 * 1024
MAX_PART = 12 * CH   # each response is capped -> browsers just ask for the next range

async def start(): await client.start()
async def stop():
    try: await client.stop()
    except Exception: pass

async def stream_response(request, v: dict):
    size = int(v["size"]); mime = v.get("mime") or "video/mp4"
    start, end, rng = 0, size - 1, request.headers.get("range")
    if rng:
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        if m:
            a, b = m.groups()
            if a == "" and b: start = max(0, size - int(b))
            else:
                start = int(a or 0)
                end = min(int(b), size - 1) if b else size - 1
    end = min(end, start + MAX_PART - 1)
    if start >= size or start > end:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})
    length = end - start + 1
    first = start // CH; skip = start - first * CH
    blocks = (skip + length + CH - 1) // CH

    async def gen():
        rem, sk = length, skip
        async for chunk in client.stream_media(v["file_id"], limit=blocks, offset=first):
            if sk: chunk, sk = chunk[sk:], 0
            if len(chunk) > rem: chunk = chunk[:rem]
            rem -= len(chunk)
            yield chunk
            if rem <= 0: break

    h = {"Accept-Ranges": "bytes", "Content-Length": str(length), "Cache-Control": "no-store",
         "Content-Range": f"bytes {start}-{end}/{size}", "Content-Disposition": "inline",
         "X-Content-Type-Options": "nosniff"}
    return StreamingResponse(gen(), status_code=206, headers=h, media_type=mime)
