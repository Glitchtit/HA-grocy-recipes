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
