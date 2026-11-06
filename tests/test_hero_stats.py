"""Per-hero stats: item popularity (builds), matchups and benchmarks.

Uses real OpenDota responses for Doom saved in fixtures/opendota/, and the
committed cache in data/ to turn OpenDota's numeric IDs into internal names.
"""

import json
from pathlib import Path

import pytest

from companion.data.store import DataStore
from companion.data.transform import (
    benchmarks_from_opendota,
    build_from_opendota,
    matchups_from_opendota,
)

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "fixtures" / "opendota"
DOOM = "npc_dota_hero_doom_bringer"


def sample(name: str):
    return json.loads((SAMPLES / name).read_text())


@pytest.fixture(scope="module")
def constants() -> DataStore:
    return DataStore.load(ROOT / "data")


@pytest.fixture(scope="module")
def item_ids(constants) -> dict[int, str]:
    return {item.id: name for name, item in constants.items.items()}


@pytest.fixture(scope="module")
def hero_ids(constants) -> dict[int, str]:
    return {hero.id: name for name, hero in constants.heroes.items()}


# --- builds (item popularity) ---


def test_build_most_popular_first(item_ids):
    build = build_from_opendota(sample("doom_item_popularity.json"), item_ids)
    assert [p.item for p in build.start_game[:2]] == ["item_gauntlets", "item_branches"]
    assert build.start_game[0].count == 203
    assert build.mid_game[0].item == "item_blink"
    assert build.late_game[0].item == "item_shivas_guard"


def test_build_ties_are_sorted_by_name(item_ids):
    # Chainmail and Boots both have 99 games; order must not depend on luck.
    build = build_from_opendota(sample("doom_item_popularity.json"), item_ids)
    assert [p.item for p in build.early_game[:2]] == ["item_boots", "item_chainmail"]


def test_build_keeps_top_n(item_ids):
    build = build_from_opendota(sample("doom_item_popularity.json"), item_ids, top=3)
    assert len(build.late_game) == 3


def test_build_skips_unknown_item_ids():
    raw = {"start_game_items": {"44": 10, "99999": 50}}
    build = build_from_opendota(raw, {44: "item_tango"})
    assert [p.item for p in build.start_game] == ["item_tango"]
    assert build.late_game == []


# --- matchups ---


def test_matchups_most_games_first(hero_ids):
    matchups = matchups_from_opendota(sample("doom_matchups.json"), hero_ids)
    assert matchups[0].hero == "npc_dota_hero_rubick"
    assert matchups[0].games == 274
    assert matchups[0].wins == 142
    assert matchups[0].win_rate == pytest.approx(142 / 274)


def test_matchups_skip_unknown_heroes():
    raw = [
        {"hero_id": 1, "games_played": 5, "wins": 2},
        {"hero_id": 999, "games_played": 9, "wins": 1},
    ]
    matchups = matchups_from_opendota(raw, {1: "npc_dota_hero_antimage"})
    assert [m.hero for m in matchups] == ["npc_dota_hero_antimage"]


# --- benchmarks ---


def test_benchmarks_median():
    bench = benchmarks_from_opendota(sample("doom_benchmarks.json"))
    assert bench.gold_per_min.at(0.5) == 530
    assert bench.last_hits_per_min.at(0.5) == pytest.approx(4.861, abs=0.001)


def test_benchmark_uses_nearest_percentile():
    bench = benchmarks_from_opendota(sample("doom_benchmarks.json"))
    assert bench.gold_per_min.at(0.52) == bench.gold_per_min.at(0.5)
    assert bench.gold_per_min.at(0.9) > bench.gold_per_min.at(0.5)


def test_benchmark_without_data_is_none():
    bench = benchmarks_from_opendota({"result": {}})
    assert bench.gold_per_min.at(0.5) is None
