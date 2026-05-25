"""Constants for the ha_recipes integration."""

DOMAIN = "ha_recipes"

# Config entry keys
CONF_ADDON_URL = "addon_url"

# Supervisor add-on slugs (used for hostname auto-discovery).
# Mirror the values HA-print uses: Recipes is matched by a substring of its
# slug/name, Storage by "ha.storage". HA-print discovers Recipes on 8100 and
# Storage on 8099 — reuse those ports here.
ADDON_SLUG_RECIPES_PATTERN = "recipes"
ADDON_SLUG_STORAGE_PATTERN = "ha.storage"

RECIPES_PORT = 8100
STORAGE_PORT = 8099

# Sensible default — Supervisor exposes add-ons by slug-as-hostname. The
# HA-recipes add-on slug is "recipes"; its sibling-accessible backend port is
# 8100 (the ingress port 8099 is nginx, the raw backend is on 8100).
DEFAULT_ADDON_URL = "http://core-recipes:8100"

# Service names
SERVICE_SEARCH = "search"
SERVICE_SCRAPE_URL = "scrape_url"
SERVICE_SUGGEST_FROM_STOCK = "suggest_from_stock"
