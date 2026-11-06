"""Turn raw OpenDota constants into our small cache format.

Pure functions (no network, no files) so they're easy to test with the samples
in fixtures/opendota/. The sync script downloads, these functions convert,
the DataStore saves and loads.
"""

from typing import Any

from pydantic import BaseModel


class HeroInfo(BaseModel):
    id: int
    name: str  # display name, e.g. "Doom"
    primary_attr: str  # "str", "agi", "int" or "all"
    attack_type: str  # "Melee" or "Ranged"
    roles: list[str] = []


class ItemInfo(BaseModel):
    id: int
    name: str  # display name, e.g. "Hand of Midas"
    cost: int = 0
    components: list[str] = []  # internal names, e.g. ["item_gloves"]
    quality: str = ""  # OpenDota's "qual": "consumable", "common", "epic", ...


def heroes_from_opendota(raw: dict[str, Any]) -> dict[str, HeroInfo]:
    """Heroes keyed by GSI's internal name (e.g. "npc_dota_hero_doom_bringer")."""
    return {
        hero["name"]: HeroInfo(
            id=hero["id"],
            name=hero["localized_name"],
            primary_attr=hero["primary_attr"],
            attack_type=hero["attack_type"],
            roles=hero.get("roles") or [],
        )
        for hero in raw.values()
    }


def items_from_opendota(raw: dict[str, Any]) -> dict[str, ItemInfo]:
    """Items keyed like GSI sends them: OpenDota "hand_of_midas" -> "item_hand_of_midas"."""
    items = {}
    for key, item in raw.items():
        if not item.get("dname"):
            continue  # internal/unused entries with no display name
        items[f"item_{key}"] = ItemInfo(
            id=item["id"],
            name=item["dname"],
            cost=item.get("cost") or 0,
            components=[f"item_{c}" for c in item.get("components") or []],
            quality=item.get("qual") or "",
        )
    return items


def latest_patch(raw: list[dict[str, Any]]) -> str:
    """Name of the newest patch, e.g. "7.41" (OpenDota lists them oldest first)."""
    return max(raw, key=lambda p: p["id"])["name"]


# --- per-hero stats (one request per hero per endpoint) ---


class ItemPick(BaseModel):
    item: str  # internal name, e.g. "item_blink"
    count: int  # how many of the sampled games bought it in this phase


class HeroBuild(BaseModel):
    """Most popular items per game phase, most popular first."""

    start_game: list[ItemPick] = []
    early_game: list[ItemPick] = []
    mid_game: list[ItemPick] = []
    late_game: list[ItemPick] = []


class Matchup(BaseModel):
    hero: str  # the other hero's internal name
    games: int
    wins: int  # wins for OUR hero in those games

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0


class Percentiles(BaseModel):
    """Benchmark values by percentile, e.g. {0.5: 530} = median player gets 530."""

    values: dict[float, float] = {}

    def at(self, percentile: float) -> float | None:
        """Value at the nearest percentile OpenDota provides (0.1 ... 0.99).
        None if OpenDota had no data for this stat."""
        if not self.values:
            return None
        nearest = min(self.values, key=lambda p: abs(p - percentile))
        return self.values[nearest]


class HeroBenchmarks(BaseModel):
    """Per-minute rates; multiply by game minutes for expected totals."""

    gold_per_min: Percentiles = Percentiles()
    xp_per_min: Percentiles = Percentiles()
    last_hits_per_min: Percentiles = Percentiles()
    denies_per_min: Percentiles = Percentiles()
    kills_per_min: Percentiles = Percentiles()
    deaths_per_min: Percentiles = Percentiles()
    hero_damage_per_min: Percentiles = Percentiles()


def build_from_opendota(
    raw: dict[str, dict[str, int]], item_ids: dict[int, str], top: int = 10
) -> HeroBuild:
    """OpenDota itemPopularity -> HeroBuild. `item_ids` maps item id -> internal name."""

    def phase(key: str) -> list[ItemPick]:
        picks = [
            ItemPick(item=item_ids[int(item_id)], count=count)
            for item_id, count in raw.get(key, {}).items()
            if int(item_id) in item_ids  # skip ids missing from the constants
        ]
        # Most popular first; ties sorted by name so the order is always the same.
        picks.sort(key=lambda p: (-p.count, p.item))
        return picks[:top]

    return HeroBuild(
        start_game=phase("start_game_items"),
        early_game=phase("early_game_items"),
        mid_game=phase("mid_game_items"),
        late_game=phase("late_game_items"),
    )


def matchups_from_opendota(raw: list[dict[str, int]], hero_ids: dict[int, str]) -> list[Matchup]:
    """OpenDota matchups -> list sorted by games played (most reliable first)."""
    matchups = [
        Matchup(hero=hero_ids[m["hero_id"]], games=m["games_played"], wins=m["wins"])
        for m in raw
        if m["hero_id"] in hero_ids
    ]
    matchups.sort(key=lambda m: (-m.games, m.hero))
    return matchups


def benchmarks_from_opendota(raw: dict[str, Any]) -> HeroBenchmarks:
    """OpenDota benchmarks -> HeroBenchmarks (only the stats we model)."""
    result = raw.get("result", {})
    stats = {
        name: Percentiles(values={p["percentile"]: p["value"] for p in result.get(name, [])})
        for name in HeroBenchmarks.model_fields
    }
    return HeroBenchmarks(**stats)
