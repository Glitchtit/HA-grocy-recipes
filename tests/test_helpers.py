"""Pure-helper unit tests for the ha_recipes integration (no HA harness)."""
import importlib.util
import pathlib
import sys

# Load helpers.py directly so we don't need the homeassistant package installed.
_HELPERS = (
    pathlib.Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ha_recipes"
    / "helpers.py"
)
_spec = importlib.util.spec_from_file_location("ha_recipes_helpers", _HELPERS)
helpers = importlib.util.module_from_spec(_spec)
sys.modules["ha_recipes_helpers"] = helpers
_spec.loader.exec_module(helpers)


RECIPES = [
    {"id": 1, "name": "Lihapullat ja perunamuusi", "servings": 4},
    {"id": 2, "name": "Kasvissosekeitto", "servings": 2},
    {"id": 3, "name": "Pannukakku", "servings": 6},
]


def test_filter_recipes_by_query_substring_case_insensitive():
    out = helpers.filter_recipes_by_query(RECIPES, "PANNU")
    assert [r["id"] for r in out] == [3]


def test_filter_recipes_by_query_blank_returns_all():
    assert helpers.filter_recipes_by_query(RECIPES, "") == RECIPES
    assert helpers.filter_recipes_by_query(RECIPES, "   ") == RECIPES


def test_filter_recipes_by_query_no_match_returns_empty():
    assert helpers.filter_recipes_by_query(RECIPES, "sushi") == []


# --- suggest_from_stock helpers ---

EXPIRING_ENTRIES = [
    {"product_id": 10, "best_before_date": "2026-05-26", "amount": 1.0},
    {"product_id": 99, "best_before_date": "2026-05-27", "amount": 1.0},
]


def test_expiring_ids_from_entries():
    assert helpers.expiring_ids_from_entries(EXPIRING_ENTRIES) == {10, 99}


def test_ingredient_product_ids():
    detail = {"ingredients": [
        {"product_id": 10, "status": "green"},
        {"product_id": 11, "status": "yellow"},
        {"product_id": None, "status": "red"},
    ]}
    assert helpers.ingredient_product_ids(detail) == {10, 11}


def test_is_cookable_true_when_no_red():
    detail = {"ingredients": [
        {"status": "green"}, {"status": "yellow"},
    ]}
    assert helpers.is_cookable(detail) is True


def test_is_cookable_false_when_any_red():
    detail = {"ingredients": [
        {"status": "green"}, {"status": "red"},
    ]}
    assert helpers.is_cookable(detail) is False


def test_is_cookable_false_when_no_ingredients():
    assert helpers.is_cookable({"ingredients": []}) is False


def test_rank_cookable_all_green_before_has_yellow():
    a = {"id": 1, "name": "A", "ingredients": [{"status": "green"}]}
    b = {"id": 2, "name": "B", "ingredients": [{"status": "yellow"}, {"status": "green"}]}
    ranked = helpers.rank_cookable([b, a])
    assert [r["id"] for r in ranked] == [1, 2]  # all-green first
