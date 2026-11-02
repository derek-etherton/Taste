"""Settings from the environment, falling back to the repo's .env file (gitignored).

Field names map to upper-case variables: OLLAMA_URL, OLLAMA_MODEL, TASTE_DATA_DIR, ...
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # the repo root (this file is backend/taste/settings.py)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    data_dir: Path = Field(ROOT / "data", validation_alias="TASTE_DATA_DIR")

    # Which domains the API serves (a JSON list): books only for now. The film code and data
    # stay; add "film" to bring them back, with taste carried over between the two.
    domains: list[str] = Field(["book"], validation_alias="TASTE_DOMAINS")

    # Genomes (taste/model/genomes.py): the one each domain uses, and BookGenome release folders
    # to offer besides data/genomes/book/*, as a JSON list of paths.
    film_genome: str = Field("default", validation_alias="TASTE_FILM_GENOME")
    book_genome: str = Field("truegenome", validation_alias="TASTE_BOOK_GENOME")
    book_genome_paths: list[Path] = Field([], validation_alias="TASTE_BOOK_GENOME_PATHS")

    # Shelf scan reads spines with Claude when ANTHROPIC_API_KEY is set (else the local Ollama model).
    anthropic_api_key: str | None = Field(None, validation_alias="ANTHROPIC_API_KEY")
    shelf_model: str = Field("claude-sonnet-5-5", validation_alias="TASTE_SHELF_MODEL")
    shelf_effort: str = Field("medium", validation_alias="TASTE_SHELF_EFFORT")  # low/medium/high: depth vs cost
    shelf_scans_per_hour: int = Field(5, validation_alias="TASTE_SHELF_SCANS_PER_HOUR")  # per user: each costs money

    # Local LLM server (Describe Me, Shelf scan without an Anthropic key)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_vision_model: str = "qwen3-vl:8b-instruct"  # an instruct variant: "thinking" ones stall

    # API. The web app signs in with a cookie, so CORS lists its origins explicitly (never "*"):
    # a JSON list in the environment, e.g. '["https://taste.app"]'.
    cors_origins: list[str] = ["http://localhost:8081"]

    # "development" on your own machine only: allows TASTE_DEV_LOGIN and running without
    # TASTE_SECRET. Anything else is production, and the API refuses to start with those.
    env: Literal["development", "production"] = Field("production", validation_alias="TASTE_ENV")

    # Accounts (taste/api/auth.py). The database: Postgres, e.g. postgresql+psycopg://taste@localhost/taste
    database_url: str | None = Field(None, validation_alias="TASTE_DATABASE_URL")
    # Signs shelf-photo links. Unset: a random one per start (links break on restart; fine locally).
    secret: str | None = Field(None, validation_alias="TASTE_SECRET")
    # Who may sign in: the iOS bundle id (Apple) and the OAuth client ids (Google: web, iOS, Android).
    apple_client_ids: list[str] = Field([], validation_alias="TASTE_APPLE_CLIENT_IDS")
    google_client_ids: list[str] = Field([], validation_alias="TASTE_GOOGLE_CLIENT_IDS")
    # Sign in by typing an email, for local development (Apple and Google don't run on localhost).
    # Never in production: anyone could sign in as anyone.
    dev_login: bool = Field(False, validation_alias="TASTE_DEV_LOGIN")
    # The session cookie's Secure flag. Browsers treat http://localhost as secure, so it can stay on.
    cookie_secure: bool = Field(True, validation_alias="TASTE_COOKIE_SECURE")

    # Source datasets for scripts/prepare_data.py
    taste_film_url: str | None = None
    taste_book_url: str | None = None

    # scripts/openlibrary.py: a contact for the User-Agent, as Open Library asks of API users
    openlibrary_contact: str | None = Field(None, validation_alias="TASTE_OPENLIBRARY_CONTACT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
