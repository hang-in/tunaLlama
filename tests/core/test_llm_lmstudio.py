"""LMStudioClient 테스트. ``httpx.MockTransport`` 로 네트워크 차단."""

from __future__ import annotations

import json

import httpx
import pytest

from tunallama_core.errors import LLMError
from tunallama_core.llm.lmstudio import LMStudioClient


def _patch_post(monkeypatch, handler):
    """``httpx.post`` 호출을 MockTransport 로 라우팅."""
    transport = httpx.MockTransport(handler)

    def fake_post(url, *, headers=None, json=None, timeout=None):
        with httpx.Client(transport=transport, timeout=timeout) as c:
            return c.post(url, headers=headers, json=json)

    monkeypatch.setattr("tunallama_core.llm.lmstudio.httpx.post", fake_post)


def test_chat_success(monkeypatch):
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        captured["headers"] = dict(req.headers)
        captured["body"] = json.loads(req.content)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "hi back"}}],
                "usage": {"total_tokens": 42},
            },
        )

    _patch_post(monkeypatch, handler)
    c = LMStudioClient(
        host="http://localhost:1234/v1",
        model="m",
        api_key="lm-studio",
        temperature=0.5,
        timeout=10,
    )
    r = c.chat(system="sys", prompt="hi")

    assert r.text == "hi back"
    assert r.model == "m"
    assert r.tokens_estimated == 42
    assert captured["url"] == "http://localhost:1234/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer lm-studio"
    assert captured["body"]["temperature"] == 0.5
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["body"]["messages"][1]["content"] == "hi"


def test_trailing_slash_in_host(monkeypatch):
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    _patch_post(monkeypatch, handler)
    c = LMStudioClient(
        host="http://localhost:1234/v1/",
        model="m",
        api_key="x",
        temperature=0.3,
        timeout=10,
    )
    c.chat(system="s", prompt="p")
    assert seen["url"] == "http://localhost:1234/v1/chat/completions"


def test_http_error_wrapped(monkeypatch):
    def handler(req):
        return httpx.Response(500, json={"error": "boom"})

    _patch_post(monkeypatch, handler)
    c = LMStudioClient(host="http://x", model="m", api_key="k", temperature=0.3, timeout=10)
    with pytest.raises(LLMError, match="LM Studio"):
        c.chat(system="s", prompt="p")


def test_malformed_response_wrapped(monkeypatch):
    def handler(req):
        return httpx.Response(200, json={"unexpected": "shape"})

    _patch_post(monkeypatch, handler)
    c = LMStudioClient(host="http://x", model="m", api_key="k", temperature=0.3, timeout=10)
    with pytest.raises(LLMError, match="응답 형식"):
        c.chat(system="s", prompt="p")


def test_missing_usage_field_returns_none_tokens(monkeypatch):
    def handler(req):
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}]}
        )

    _patch_post(monkeypatch, handler)
    c = LMStudioClient(host="http://x", model="m", api_key="k", temperature=0.3, timeout=10)
    r = c.chat(system="s", prompt="p")
    assert r.tokens_estimated is None
