"""Describe Me: the brief sent to the LLM, and handling of its reply (no network calls)."""

import pytest

from conftest import find
from taste.model import UserModel
from taste.model.describe import DescribeError, describe, taste_brief
from taste.model.llm import ollama_chat


@pytest.fixture(scope="module")
def ratings(cats):
    return ({find(cats["film"], t): 1 for t in ["Children of Men", "Blade Runner"]}
            | {find(cats["film"], "The Hangover"): -1, find(cats["book"], "1984"): 1})


@pytest.fixture(scope="module")
def brief(cats, traits, ratings):
    models = {d: UserModel(c, ratings, prior=traits.prior(d, ratings)) for d, c in cats.items()}
    return taste_brief(models, traits, ratings)


def test_brief_lists_ratings_and_traits(brief):
    assert "Liked films: " in brief and "Children of Men" in brief
    assert "Disliked films: The Hangover" in brief
    assert "Liked books: 1984" in brief
    assert "Taste that carries across films and books:" in brief
    assert "Drawn to:" in brief and "Steers away from:" in brief


def test_describe_sends_brief_and_returns_text(brief):
    sent = []
    chat = lambda messages: sent.append(messages) or "You like bleak futures."
    assert describe(brief, chat) == "You like bleak futures."
    assert [m["role"] for m in sent[0]] == ["system", "user"]
    assert sent[0][1]["content"] == brief


def test_inline_reasoning_is_stripped(brief):
    assert describe(brief, lambda m: "<think>hmm, dystopias</think>\nYou like bleak futures.") == \
        "You like bleak futures."
    with pytest.raises(DescribeError, match="no text"):
        describe(brief, lambda m: "<think>only thoughts</think>")


def test_unreachable_server_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens on the discard port
    with pytest.raises(DescribeError, match="Couldn't reach Ollama"):
        ollama_chat([{"role": "user", "content": "hi"}], "any-model")


def test_dashes_become_commas(brief):
    reply = "Beware punchlines—your soul won't survive. Next – a rogue AI."
    assert describe(brief, lambda m: reply) == "Beware punchlines, your soul won't survive. Next, a rogue AI."
