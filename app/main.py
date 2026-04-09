from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import create_pool
from app.web.routes import auth, pages


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await create_pool()
    app.state.templates = Jinja2Templates(directory="app/web/templates")
    yield
    await app.state.pool.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    https_only=settings.session_https_only,
    same_site="lax",
)
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")

app.include_router(auth.router)
app.include_router(pages.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
