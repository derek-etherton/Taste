"""Settings from the project's .env file (gitignored): source URLs and Ollama settings."""

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env(path: Path = ENV_FILE) -> None:
    """Minimal .env reader: KEY=value lines; real environment variables win."""
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())
