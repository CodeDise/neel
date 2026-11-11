import asyncio, logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from . import bot as B, streamer
from .api import router
from .core import S

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).parent / "static"
(Path(__file__).parent.parent / "data" / "thumbs").mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app):
    await S.init(); await B.setup(); await streamer.start()
    task = asyncio.create_task(B.dp.start_polling(B.bot, handle_signals=False))
    yield
    task.cancel(); await streamer.stop(); await B.bot.session.close()

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
NOCACHE = {"Cache-Control": "no-store"}

@app.get("/")
async def index(): return FileResponse(STATIC / "index.html", headers=NOCACHE)

@app.get("/admin")
async def admin(): return FileResponse(STATIC / "admin.html", headers=NOCACHE)

@app.get("/health")
async def health(): return {"ok": True}
