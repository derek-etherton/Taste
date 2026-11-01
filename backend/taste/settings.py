"""Settings from the environment, falling back to the repo's .env file (gitignored).

Field names map to upper-case variables: OLLAMA_URL, OLLAMA_MODEL, TASTE_DATA_DIR, ...
"""

from functools import lru_cache
from pathlib import Path

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

    # Local LLM server (Describe Me, Shelf scan)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"
    ollama_vision_model: str = "qwen3-vl:8b-instruct"  # an instruct variant: "thinking" ones stall

    # API
    cors_origins: list[str] = ["*"]  # JSON list in the environment, e.g. '["https://app.example.com"]'

    # Source datasets for scripts/prepare_data.py
    taste_film_url: str | None = None
    taste_book_url: str | None = None

    # scripts/openlibrary.py: a contact for the User-Agent, as Open Library asks of API users
    openlibrary_contact: str | None = Field(None, validation_alias="TASTE_OPENLIBRARY_CONTACT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
