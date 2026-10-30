"""The HTTP API.

    uvicorn taste.api.app:app --reload        # from backend/; docs at http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from taste.api.engine import Engine
from taste.api.routes import router
from taste.settings import get_settings


def create_app(engine: Engine | None = None) -> FastAPI:
    """The app; tests pass an engine with a temporary store and stand-in LLMs."""
    app = FastAPI(title="Taste", version="0.2.0",
                  description="Person-centred film and book recommendations, Describe Me and Shelf scan.")
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins,
                       allow_methods=["*"], allow_headers=["*"])
    app.state.engine = engine or Engine()
    app.include_router(router)
    return app


def __getattr__(name: str):
    # `app` is built on first access, so importing this module (e.g. in tests) loads nothing.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
