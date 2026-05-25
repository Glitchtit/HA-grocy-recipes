"""Handler-level tests for ha_recipes services using mocked clients."""
import asyncio
import importlib.util
import pathlib
import sys

import pytest

_HELPERS = (
    pathlib.Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ha_recipes"
    / "helpers.py"
)
_spec = importlib.util.spec_from_file_location("ha_recipes_helpers2", _HELPERS)
helpers = importlib.util.module_from_spec(_spec)
sys.modules["ha_recipes_helpers2"] = helpers
_spec.loader.exec_module(helpers)


class FakeRecipes:
    def __init__(self, scrape_result=None, list_result=None, details=None):
        self._scrape = scrape_result or {}
        self._list = list_result or []
        self._details = details or {}
        self.scrape_calls = []

    async def scrape(self, url):
        self.scrape_calls.append(url)
        return self._scrape

    async def list_recipes(self):
        return self._list

    async def recipe_detail(self, rid):
        return self._details[rid]


def test_run_scrape_passes_url_and_returns_payload():
    fake = FakeRecipes(scrape_result={
        "name": "Pannukakku", "servings": 6,
        "ingredients": [{"name": "muna"}], "instructions": ["sekoita"],
        "matches": [{"product_id": 5}],
    })
    out = asyncio.run(helpers.run_scrape(fake, "https://example.com/r"))
    assert fake.scrape_calls == ["https://example.com/r"]
    assert out["name"] == "Pannukakku"
    assert out["servings"] == 6
    assert out["matches"] == [{"product_id": 5}]


class FakeStorage:
    def __init__(self, stock=None, expiring=None):
        self._stock = stock or []
        self._expiring = expiring or []

    async def fetch_stock(self):
        return self._stock

    async def fetch_expiring_entries(self, days):
        self._days = days
        return self._expiring


def _details():
    return {
        1: {"id": 1, "name": "All green", "ingredients": [
            {"product_id": 10, "status": "green"}]},
        2: {"id": 2, "name": "Has red", "ingredients": [
            {"product_id": 10, "status": "green"}, {"product_id": 11, "status": "red"}]},
        3: {"id": 3, "name": "Yellow expiring", "ingredients": [
            {"product_id": 12, "status": "yellow"}]},
    }


def test_run_suggest_returns_only_cookable_ranked():
    fake = FakeRecipes(
        list_result=[{"id": 1}, {"id": 2}, {"id": 3}],
        details=_details(),
    )
    storage = FakeStorage(stock=[{"product_id": 10, "amount": 1}])
    out = asyncio.run(helpers.run_suggest(
        fake, storage, expiring_only=False, days=None))
    # recipe 2 dropped (red); 1 (all green) ranked before 3 (yellow)
    assert [r["id"] for r in out["recipes"]] == [1, 3]
    assert out["count"] == 2
    assert out["expiring_only"] is False


def test_run_suggest_expiring_only_filters_to_expiring_products():
    fake = FakeRecipes(
        list_result=[{"id": 1}, {"id": 3}],
        details=_details(),
    )
    # only product 12 is expiring -> recipe 3 qualifies, recipe 1 (prod 10) does not
    storage = FakeStorage(
        stock=[{"product_id": 10, "amount": 1}, {"product_id": 12, "amount": 1}],
        expiring=[{"product_id": 12, "best_before_date": "2026-05-26"}],
    )
    out = asyncio.run(helpers.run_suggest(
        fake, storage, expiring_only=True, days=3))
    assert [r["id"] for r in out["recipes"]] == [3]
    assert storage._days == 3
    assert out["expiring_only"] is True
