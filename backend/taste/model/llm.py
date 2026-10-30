"""The local LLM server (Ollama), shared by Describe Me and Shelf scan."""

import json
import urllib.error
import urllib.request

from taste.settings import get_settings


class LLMError(Exception):
    """Something the user should see, e.g. Ollama not running or a model not pulled."""


def ollama_chat(messages: list[dict], model: str, format: dict | None = None,
                options: dict | None = None, timeout: float = 180, url: str | None = None) -> str:
    """One non-streaming chat turn; returns the reply text. Images go in a message's
    "images" list (base64). `format` is a JSON schema the reply must follow."""
    url = (url or get_settings().ollama_url).rstrip("/")
    # think=False: reasoning models (e.g. qwen3) answer directly instead of thinking first.
    body = {"model": model, "messages": messages, "stream": False, "think": False}
    if format:
        body["format"] = format
    if options:
        body["options"] = options
    request = urllib.request.Request(f"{url}/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())["message"]["content"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        if e.code == 404:
            raise LLMError(f"Ollama doesn't have {model}; run `ollama pull {model}`.") from None
        raise LLMError(f"Ollama returned an error ({e.code}): {detail}") from None
    except (urllib.error.URLError, TimeoutError, ConnectionError):
        raise LLMError(f"Couldn't reach Ollama at {url}; is it running?") from None
