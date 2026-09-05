"""Tests for the page fetcher used by recipe scraping.

Cloudflare-fronted sites (k-ruoka.fi) answer plain ``requests`` with a 403
managed challenge. When a FlareSolverr instance is configured the fetcher
must fall back to it; otherwise it must raise an actionable error instead of
a bare HTTPError.
"""

from __future__ import annotations

import types

import pytest

import backend


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", headers: dict | None = None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise backend.requests.exceptions.HTTPError(f"{self.status_code} Client Error")

    def json(self):
        return self._json

    @property
    def ok(self):
        return self.status_code < 400


CF_HEADERS = {"server": "cloudflare", "cf-mitigated": "challenge"}


def _patch_requests(monkeypatch, get=None, post=None):
    fake = types.SimpleNamespace(
        get=get or (lambda *a, **k: pytest.fail("unexpected GET")),
        post=post or (lambda *a, **k: pytest.fail("unexpected POST")),
        exceptions=backend.requests.exceptions,
    )
    monkeypatch.setattr(backend, "requests", fake)


class TestFetchHtml:
    def test_plain_fetch_returns_html(self, monkeypatch):
        _patch_requests(monkeypatch, get=lambda *a, **k: _FakeResponse(200, "<html>ok</html>"))
        assert backend._fetch_html("https://example.com/r") == "<html>ok</html>"

    def test_cloudflare_block_falls_back_to_flaresolverr(self, monkeypatch):
        monkeypatch.setattr(backend, "FLARESOLVERR_URL", "http://fs:8191")
        calls = []

        def fake_post(url, json=None, timeout=None):
            calls.append((url, json))
            r = _FakeResponse(200)
            r._json = {"status": "ok", "solution": {"status": 200, "response": "<html>solved</html>"}}
            return r

        _patch_requests(
            monkeypatch,
            get=lambda *a, **k: _FakeResponse(403, "blocked", CF_HEADERS),
            post=fake_post,
        )
        assert backend._fetch_html("https://www.k-ruoka.fi/reseptit/x") == "<html>solved</html>"
        assert calls[0][0] == "http://fs:8191/v1"
        assert calls[0][1]["cmd"] == "request.get"
        assert calls[0][1]["url"] == "https://www.k-ruoka.fi/reseptit/x"

    def test_flaresolverr_url_with_v1_suffix_not_doubled(self, monkeypatch):
        monkeypatch.setattr(backend, "FLARESOLVERR_URL", "http://fs:8191/v1")
        seen = []

        def fake_post(url, json=None, timeout=None):
            seen.append(url)
            r = _FakeResponse(200)
            r._json = {"status": "ok", "solution": {"status": 200, "response": "x"}}
            return r

        _patch_requests(monkeypatch, get=lambda *a, **k: _FakeResponse(403, "", CF_HEADERS), post=fake_post)
        backend._fetch_html("https://www.k-ruoka.fi/reseptit/x")
        assert seen == ["http://fs:8191/v1"]

    def test_cloudflare_block_without_flaresolverr_raises_actionable_error(self, monkeypatch):
        monkeypatch.setattr(backend, "FLARESOLVERR_URL", "")
        _patch_requests(monkeypatch, get=lambda *a, **k: _FakeResponse(403, "", CF_HEADERS))
        with pytest.raises(RuntimeError, match="flaresolverr_url"):
            backend._fetch_html("https://www.k-ruoka.fi/reseptit/x")

    def test_non_cloudflare_403_is_not_routed_to_flaresolverr(self, monkeypatch):
        monkeypatch.setattr(backend, "FLARESOLVERR_URL", "http://fs:8191")
        _patch_requests(monkeypatch, get=lambda *a, **k: _FakeResponse(403, "", {"server": "nginx"}))
        with pytest.raises(backend.requests.exceptions.HTTPError):
            backend._fetch_html("https://example.com/private")

    def test_flaresolverr_failure_surfaces_as_error(self, monkeypatch):
        monkeypatch.setattr(backend, "FLARESOLVERR_URL", "http://fs:8191")

        def fake_post(url, json=None, timeout=None):
            r = _FakeResponse(200)
            r._json = {"status": "error", "message": "Challenge not solved"}
            return r

        _patch_requests(monkeypatch, get=lambda *a, **k: _FakeResponse(403, "", CF_HEADERS), post=fake_post)
        with pytest.raises(RuntimeError, match="FlareSolverr"):
            backend._fetch_html("https://www.k-ruoka.fi/reseptit/x")
