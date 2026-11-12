import json
from pathlib import Path

import pytest

from companion.data.store import DataStore
from companion.data.transform import heroes_from_opendota, items_from_opendota, latest_patch
from companion.gsi.models import GameState

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "fixtures" / "opendota"


def sample(name: str):
    return json.loads((SAMPLES / name).read_text())


# --- transform: raw OpenDota JSON -> our compact cache format (pure functions) ---


def test_heroes_keyed_by_gsi_name():
    heroes = heroes_from_opendota(sample("heroes_sample.json"))
    doom = heroes["npc_dota_hero_doom_bringer"]
    assert doom.id == 69
    assert doom.name == "Doom"
    assert doom.primary_attr == "str"
    assert "npc_dota_hero_nevermore" in heroes


def test_items_get_gsi_prefix():
    items = items_from_opendota(sample("items_sample.json"))
    midas = items["item_hand_of_midas"]
    assert midas.name == "Hand of Midas"
    assert midas.cost == 2200
    # Components use the same prefixed names, so they can be looked up too.
    assert midas.components == ["item_gloves"]
    assert items["item_tango"].components == []


def test_items_without_display_name_are_skipped():
    # OpenDota has a few internal/unused entries without a display name.
    items = items_from_opendota(sample("items_sample.json"))
    assert all(item.name for item in items.values())
    assert "item_greater_mango" not in items


def test_latest_patch():
    assert latest_patch(sample("patch_sample.json")) == "7.41"


# --- DataStore: loads the cache from disk, no network ---


@pytest.fixture
def store(tmp_path) -> DataStore:
    DataStore(
        heroes=heroes_from_opendota(sample("heroes_sample.json")),
        items=items_from_opendota(sample("items_sample.json")),
        patch="7.41",
    ).save(tmp_path)
    return DataStore.load(tmp_path)


def test_store_round_trip(store):
    assert store.patch == "7.41"
    assert store.hero_name("npc_dota_hero_doom_bringer") == "Doom"
    assert store.item_name("item_hand_of_midas") == "Hand of Midas"
    assert store.item_cost("item_hand_of_midas") == 2200


def test_store_unknown_names(store):
    # Unknown names fall back to the internal name instead of crashing mid-game.
    assert store.hero_name("npc_dota_hero_new_guy") == "npc_dota_hero_new_guy"
    assert store.item_name("item_new_thing") == "item_new_thing"
    assert store.item_cost("item_new_thing") is None


def test_missing_cache_has_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="sync_data"):
        DataStore.load(tmp_path)


# --- The real committed cache in data/ must cover everything seen in real games ---


def test_real_cache_knows_every_hero_and_item_in_fixtures():
    store = DataStore.load(ROOT / "data")
    for path in sorted(ROOT.glob("fixtures/*.json")):
        state = GameState.model_validate(json.loads(path.read_text()))
        if state.hero_picked:
            assert store.hero(state.hero.name) is not None, f"{path.name}: {state.hero.name}"
        for name in state.inventory + state.backpack + state.stash:
            assert store.item(name) is not None, f"{path.name}: {name}"
