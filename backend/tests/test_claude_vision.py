"""Shelf scan's Claude reader, with a stand-in client: the request it sends, and how the reply
becomes spines with locations (no network)."""

import base64
import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from taste.model.claude_vision import MAX_SIDE, claude_vision, spines
from taste.model.llm import LLMError
from taste.model.shelf import Where


def photo(width=4000, height=3000) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="JPEG")
    return out.getvalue()


class FakeClaude:
    """Records the request; answers with `reply` (a dict, sent as the JSON text block)."""

    def __init__(self, reply: dict, stop_reason: str = "end_turn"):
        self.sent = None
        self.reply, self.stop_reason = reply, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.sent = kwargs
        return SimpleNamespace(stop_reason=self.stop_reason, content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=json.dumps(self.reply)),
        ])


def test_one_request_per_photo():
    fake = FakeClaude({"shelves": 2, "books": [
        {"title": "Dune", "author": "Frank Herbert", "shelf": 1, "x": 500},
        {"title": "Emma", "author": None, "shelf": 2, "x": 2400},
    ]})
    steps = []
    out = claude_vision(photo(), progress=lambda d, t: steps.append((d, t)), claude=fake)
    assert [(s.title, s.author) for s in out] == [("Dune", "Frank Herbert"), ("Emma", None)]
    assert out[0].where == Where(0, 2, 500 / MAX_SIDE) and out[1].where == Where(1, 2, 2400 / MAX_SIDE)
    assert steps == [(0, 1), (1, 1)]

    sent = fake.sent
    assert sent["model"] == "claude-sonnet-5-5" and sent["output_config"]["effort"] == "medium"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in sent["betas"]
    image = sent["messages"][0]["content"][0]["source"]
    assert max(Image.open(io.BytesIO(base64.b64decode(image["data"]))).size) == MAX_SIDE  # downscaled to the limit


def test_reply_cleanup():
    reply = {"shelves": 1, "books": [
        {"title": "  ", "author": None, "shelf": 1, "x": 10},  # unreadable
        {"title": "Stephen King", "author": "Stephen King", "shelf": 1, "x": 20},  # an author read as a title
        {"title": "It", "author": "Stephen King", "shelf": 3, "x": 9999},  # a shelf it didn't count; off the edge
    ]}
    out = spines(reply, width=1000)
    assert [(s.title, s.where) for s in out] == [("It", Where(2, 3, 1.0))]


@pytest.mark.parametrize("stop, message", [("refusal", "declined"), ("max_tokens", "fewer shelves")])
def test_failures_are_explained(stop, message):
    with pytest.raises(LLMError, match=message):
        claude_vision(photo(800, 600), claude=FakeClaude({"shelves": 0, "books": []}, stop_reason=stop))
