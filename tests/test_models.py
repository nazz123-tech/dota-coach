import json
from pathlib import Path

import pytest

from companion.gsi.models import GameState

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str) -> GameState:
    return GameState.model_validate(json.loads((FIXTURES / name).read_text()))


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("*.json")), ids=lambda p: p.name)
def test_every_fixture_parses(path):
    # Real payloads from Dota must always parse, whatever moment they're from.
    GameState.model_validate(json.loads(path.read_text()))


def test_in_game_basics():
    state = load("nevermore_min1_levelup.json")
    assert state.map is not None
    assert state.map.clock_time == 60
    assert state.map.game_state == "DOTA_GAMERULES_STATE_GAME_IN_PROGRESS"
    assert state.hero.name == "npc_dota_hero_nevermore"
    assert state.hero.level == 2
    assert state.hero.health == 209
    assert state.player.gold == 213
    assert state.player.last_hits == 2


def test_abilities_in_order():
    state = load("nevermore_min1_levelup.json")
    names = [a.name for a in state.ability_list]
    assert names == [
        "nevermore_shadowraze1",
        "nevermore_shadowraze2",
        "nevermore_shadowraze3",
        "nevermore_frenzy",
        "nevermore_dark_lord",
        "nevermore_requiem",
    ]
    assert state.ability_list[5].ultimate is True
    assert state.ability_list[0].level == 1


def test_inventory_skips_empty_slots():
    state = load("nevermore_min1_levelup.json")
    assert state.inventory == ["item_orb_of_frost", "item_blight_stone"]
    assert state.backpack == []
    assert state.stash == []
    assert state.items["teleport0"].name == "item_tpscroll"
    assert state.items["teleport0"].charges == 1


def test_hero_selection_has_no_hero_yet():
    state = load("unknown_min0_start.json")
    assert state.map is not None
    assert state.map.game_state == "DOTA_GAMERULES_STATE_HERO_SELECTION"
    assert state.hero_picked is False
    assert state.hero.name is None
    assert state.ability_list == []
    assert state.inventory == []


def test_menu_payload_without_map():
    # In the main menu Dota sends only provider/auth; nothing else.
    state = GameState.model_validate({"provider": {"name": "Dota 2"}})
    assert state.map is None
    assert state.hero_picked is False
    assert state.inventory == []


def test_personal_info_is_not_modelled():
    # We parse only what rules need; Steam info is ignored on purpose.
    state = load("nevermore_min1_levelup.json")
    assert not hasattr(state.player, "steamid")
