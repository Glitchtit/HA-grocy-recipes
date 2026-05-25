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


def pantry_ids_from_stock(stock: list[dict[str, Any]]) -> set[int]:
    """Set of product_ids that are currently in stock.

    Reads HA-storage `GET /api/stock` summaries. That endpoint already returns
    only active products with total amount > 0, but we defensively exclude rows
    with a non-positive ``amount`` and rows without a numeric ``product_id``.
    """
    ids: set[int] = set()
    for row in stock or []:
        pid = row.get("product_id")
        if pid is None:
            continue
        amount = row.get("amount")
        if amount is not None and amount <= 0:
            continue
        ids.add(int(pid))
    return ids


def expiring_ids_from_entries(entries: list[dict[str, Any]]) -> set[int]:
    """Set of product_ids that have at least one lot expiring soon.

    Reads HA-storage `GET /api/stock/entries?expiring_within_days=N`.
    """
    ids: set[int] = set()
    for e in entries or []:
        pid = e.get("product_id")
        if pid is not None:
            ids.add(int(pid))
    return ids


def ingredient_product_ids(detail: dict[str, Any]) -> set[int]:
    """Non-null product_ids referenced by a recipe detail's ingredients."""
    ids: set[int] = set()
    for ing in detail.get("ingredients") or []:
        pid = ing.get("product_id")
        if pid is not None:
            ids.add(int(pid))
    return ids


def is_cookable(detail: dict[str, Any]) -> bool:
    """A recipe is cookable now when it has ingredients and none are 'red'.

    Statuses come from the HA-recipes backend's _get_recipe_detail, which scores
    each ingredient against live HA-storage stock: green=in stock, yellow=low/
    opened, red=insufficient.
    """
    ingredients = detail.get("ingredients") or []
    if not ingredients:
        return False
    return all((ing.get("status") or "red") != "red" for ing in ingredients)


def rank_cookable(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stable-sort cookable recipe details: all-green first, then those with
    any 'yellow' (low/opened) ingredient."""
    def _key(d: dict[str, Any]) -> int:
        has_yellow = any(
            (ing.get("status") or "") == "yellow"
            for ing in d.get("ingredients") or []
        )
        return 1 if has_yellow else 0
    return sorted(details, key=_key)


DEFAULT_EXPIRING_DAYS = 7


async def run_suggest(
    recipes_client: Any,
    storage_client: Any | None,
    *,
    expiring_only: bool = False,
    days: int | None = None,
) -> dict[str, Any]:
    """Suggest recipes cookable from current Storage stock.

    The pantry is read automatically: each recipe's detail is scored by the
    backend against live stock, and recipes with no 'red' ingredient are kept.
    With ``expiring_only`` we additionally require at least one ingredient whose
    product is expiring within ``days`` (default 7).

    `recipes_client` needs async `list_recipes()` and `recipe_detail(id)`.
    `storage_client` (optional) needs async `fetch_expiring_entries(days)`; only
    used when ``expiring_only`` is set.
    """
    listed = await recipes_client.list_recipes()
    cookable: list[dict[str, Any]] = []
    for r in listed:
        rid = r.get("id")
        if rid is None:
            continue
        try:
            detail = await recipes_client.recipe_detail(int(rid))
        except Exception:  # noqa: BLE001
            continue
        if is_cookable(detail):
            cookable.append(detail)

    expiring_set: set[int] = set()
    if expiring_only:
        window = days if days is not None else DEFAULT_EXPIRING_DAYS
        entries = []
        if storage_client is not None:
            entries = await storage_client.fetch_expiring_entries(window)
        expiring_set = expiring_ids_from_entries(entries)
        cookable = [
            d for d in cookable
            if ingredient_product_ids(d) & expiring_set
        ]

    ranked = rank_cookable(cookable)
    slimmed = [
        {
            "id": d.get("id"),
            "name": d.get("name"),
            "servings": d.get("servings"),
            "picture_filename": d.get("picture_filename"),
            "source_url": d.get("source_url"),
        }
        for d in ranked
    ]
    return {
        "count": len(slimmed),
        "expiring_only": bool(expiring_only),
        "recipes": slimmed,
    }
