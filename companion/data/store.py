"""Read-only access to the cached OpenDota data in data/.

Loaded once at startup; lookups are plain dict reads, so they're instant and
make zero network calls during a match (hard rule 2).
Refresh the cache after a patch with:  python -m scripts.sync_data
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from companion.data.transform import HeroBenchmarks, HeroBuild, HeroInfo, ItemInfo, Matchup

# One JSON file per kind of data, each keyed by internal name.
# TypeAdapter lets Pydantic read/write a whole {name: model} dict in one go.
FILES: dict[str, tuple[str, TypeAdapter[Any]]] = {
    "heroes": ("heroes.json", TypeAdapter(dict[str, HeroInfo])),
    "items": ("items.json", TypeAdapter(dict[str, ItemInfo])),
    "builds": ("builds.json", TypeAdapter(dict[str, HeroBuild])),
    "matchups": ("matchups.json", TypeAdapter(dict[str, list[Matchup]])),
    "benchmarks": ("benchmarks.json", TypeAdapter(dict[str, HeroBenchmarks])),
}
META_FILE = "meta.json"


class Benchmark(BaseModel):
    """What a player at `percentile` typically has by `minute` on this hero."""

    minute: int
    percentile: float
    gold: int
    xp: int
    last_hits: int
    denies: int


class DataStore:
    def __init__(
        self,
        heroes: dict[str, HeroInfo],
        items: dict[str, ItemInfo],
        patch: str,
        builds: dict[str, HeroBuild] | None = None,
        matchups: dict[str, list[Matchup]] | None = None,
        benchmarks: dict[str, HeroBenchmarks] | None = None,
    ):
        self.heroes = heroes
        self.items = items
        self.patch = patch
        self.builds = builds or {}
        self.matchups = matchups or {}
        self.benchmarks = benchmarks or {}

    # --- loading and saving ---

    @classmethod
    def load(cls, data_dir: Path) -> "DataStore":
        """Load the cache from data_dir. Raises a clear error if it was never synced.
        Per-hero stats files are optional (e.g. after a --constants-only sync)."""
        if not (data_dir / FILES["heroes"][0]).exists():
            raise FileNotFoundError(
                f"No cached data in {data_dir}. Run: python -m scripts.sync_data"
            )
        loaded: dict[str, Any] = {}
        for key, (filename, adapter) in FILES.items():
            path = data_dir / filename
            loaded[key] = adapter.validate_json(path.read_bytes()) if path.exists() else {}
        meta = json.loads((data_dir / META_FILE).read_text(encoding="utf-8"))
        return cls(patch=meta["patch"], **loaded)

    def save(self, data_dir: Path) -> None:
        """Write the cache. Keys are sorted so git diffs after a patch are readable."""
        data_dir.mkdir(parents=True, exist_ok=True)
        for key, (filename, adapter) in FILES.items():
            _write_json(data_dir / filename, adapter.dump_python(getattr(self, key), mode="json"))
        synced_at = datetime.now(UTC).isoformat(timespec="seconds")
        _write_json(data_dir / META_FILE, {"patch": self.patch, "synced_at": synced_at})

    # --- constants lookups (use GSI internal names) ---

    def hero(self, internal_name: str) -> HeroInfo | None:
        return self.heroes.get(internal_name)

    def item(self, internal_name: str) -> ItemInfo | None:
        return self.items.get(internal_name)

    def hero_name(self, internal_name: str) -> str:
        """Display name, e.g. "Doom". Falls back to the internal name if unknown
        (e.g. a brand-new hero before the next sync) instead of crashing."""
        hero = self.hero(internal_name)
        return hero.name if hero else internal_name

    def item_name(self, internal_name: str) -> str:
        item = self.item(internal_name)
        return item.name if item else internal_name

    def item_cost(self, internal_name: str) -> int | None:
        item = self.item(internal_name)
        return item.cost if item else None

    # --- per-hero stats ---

    def get_build(self, hero: str) -> HeroBuild | None:
        """Most popular items per game phase for this hero."""
        return self.builds.get(hero)

    def get_matchups(self, hero: str) -> list[Matchup]:
        """Results vs every other hero, most games first. Empty if unknown."""
        return self.matchups.get(hero, [])

    def get_benchmark(self, hero: str, minute: int, percentile: float = 0.5) -> Benchmark | None:
        """Expected totals at `minute` for a player at `percentile` (0.5 = median).

        OpenDota gives per-minute rates (e.g. 530 GPM); we multiply by minutes.
        It's an approximation: real farm is slower early and faster later.
        """
        bench = self.benchmarks.get(hero)
        if bench is None:
            return None
        rates = {
            "gold": bench.gold_per_min.at(percentile),
            "xp": bench.xp_per_min.at(percentile),
            "last_hits": bench.last_hits_per_min.at(percentile),
            "denies": bench.denies_per_min.at(percentile),
        }
        if any(rate is None for rate in rates.values()):
            return None
        totals = {name: round(rate * minute) for name, rate in rates.items() if rate is not None}
        return Benchmark(minute=minute, percentile=percentile, **totals)


def _write_json(path: Path, data: Any) -> None:
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
