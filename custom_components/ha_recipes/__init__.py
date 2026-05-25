"""HA-recipes custom integration.

Services-only integration (no entities). Discovers the HA-recipes add-on
via the Supervisor API and exposes search, scrape_url services (suggest added
in Task 5).
"""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .clients.recipes import RecipesClient
from .const import (
    ADDON_SLUG_RECIPES_PATTERN,
    CONF_ADDON_URL,
    DOMAIN,
    RECIPES_PORT,
    SERVICE_SCRAPE_URL,
    SERVICE_SEARCH,
)
from .discovery import discover_addon_url
from .helpers import filter_recipes_by_query, run_scrape

_LOGGER = logging.getLogger(__name__)

SEARCH_SCHEMA = vol.Schema({vol.Required("query"): str})
SCRAPE_SCHEMA = vol.Schema({vol.Required("url"): str})


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    addon_url = entry.data[CONF_ADDON_URL]

    recipes_url = (
        await discover_addon_url(
            slug_patterns=[ADDON_SLUG_RECIPES_PATTERN],
            port=RECIPES_PORT,
            health_path="/api/config",
        )
        or addon_url
    )

    recipes = RecipesClient(recipes_url) if recipes_url else None

    hass.data[DOMAIN][entry.entry_id] = {"recipes": recipes}

    async def _search_service(call: ServiceCall) -> dict:
        if recipes is None:
            raise HomeAssistantError(
                "HA-recipes add-on was not auto-discovered; cannot search recipes."
            )
        try:
            all_recipes = await recipes.list_recipes()
        except Exception as exc:  # noqa: BLE001
            raise HomeAssistantError(f"Failed to list recipes: {exc}") from exc
        matched = filter_recipes_by_query(all_recipes, call.data["query"])
        return {"count": len(matched), "recipes": matched}

    async def _scrape_service(call: ServiceCall) -> dict:
        if recipes is None:
            raise HomeAssistantError(
                "HA-recipes add-on was not auto-discovered; cannot scrape."
            )
        try:
            return await run_scrape(recipes, call.data["url"])
        except Exception as exc:  # noqa: BLE001
            raise HomeAssistantError(f"Scrape failed: {exc}") from exc

    if not hass.services.has_service(DOMAIN, SERVICE_SEARCH):
        hass.services.async_register(
            DOMAIN, SERVICE_SEARCH, _search_service,
            schema=SEARCH_SCHEMA, supports_response=SupportsResponse.ONLY,
        )
    if not hass.services.has_service(DOMAIN, SERVICE_SCRAPE_URL):
        hass.services.async_register(
            DOMAIN, SERVICE_SCRAPE_URL, _scrape_service,
            schema=SCRAPE_SCHEMA, supports_response=SupportsResponse.ONLY,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SEARCH)
        hass.services.async_remove(DOMAIN, SERVICE_SCRAPE_URL)
    return True
