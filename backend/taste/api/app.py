"""The HTTP API.

    uvicorn taste.api.app:app --reload        # from backend/; docs at http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taste.api import auth
from taste.api.engine import Engine
from taste.api.routes import router
from taste.settings import Settings, get_settings



def check_settings(s: Settings) -> None:
    """Refuse to start with development settings unless TASTE_ENV=development says this is one:
    the dev sign-in lets anyone sign in as anyone, and without TASTE_SECRET photo links break on
    every restart (and differ between processes)."""
    if s.env == "development":
        return
    if s.dev_login:
        raise RuntimeError("TASTE_DEV_LOGIN is on outside development (TASTE_ENV): refusing to start, "
                           "as anyone could sign in as anyone.")
    if not s.secret:
        raise RuntimeError("Set TASTE_SECRET (a long random value), or TASTE_ENV=development on your own machine.")


def create_app(engine: Engine | None = None, auth_per_minute: int = 30) -> FastAPI:
    """The app; tests pass an engine with a temporary store and stand-in LLMs.
    `auth_per_minute`: sign-in requests allowed per client IP per minute."""
    check_settings(get_settings())
    app = FastAPI(title="Taste", version="0.2.0",
                  description="Person-centred book recommendations and Shelf scan.")
    # Credentials: the web app's session is a cookie, so origins must be listed, never "*".
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    app.state.engine = engine or Engine()
    app.state.auth_limit = auth.RateLimit(auth_per_minute)
    app.include_router(auth.router)
    app.include_router(router)
    return app


def __getattr__(name: str):
    # `app` is built on first access, so importing this module (e.g. in tests) loads nothing.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
