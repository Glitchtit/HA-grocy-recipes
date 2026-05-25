"""Pure, HA-free helpers for the ha_recipes integration.

Kept import-light (stdlib only) so they unit-test without Home Assistant.
"""
from __future__ import annotations

from typing import Any


def filter_recipes_by_query(
    recipes: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    """Case-insensitive substring filter on recipe ``name``.

    A blank/whitespace query returns the list unchanged (acts as "list all").
    The HA-recipes backend has no search route, so search is done client-side
    over the recipe list payload, whose only text field is ``name``.
    """
    q = (query or "").strip().lower()
    if not q:
        return recipes
    return [r for r in recipes if q in (r.get("name") or "").lower()]


async def run_scrape(recipes_client: Any, url: str) -> dict[str, Any]:
    """Proxy a scrape request and return the parsed recipe + Storage matches.

    `recipes_client` must expose an async `scrape(url) -> dict`.
    """
    return await recipes_client.scrape(url)
