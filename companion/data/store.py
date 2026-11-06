"""Read-only access to the cached OpenDota data in data/.

Loaded once at startup; lookups are plain dict reads, so they're instant and
make zero network calls during a match (hard rule 2).
Refresh the cache after a patch with:  python -m scripts.sync_data
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from companion.data.transform import HeroInfo, ItemInfo

HEROES_FILE = "heroes.json"
ITEMS_FILE = "items.json"
META_FILE = "meta.json"


class DataStore:
    def __init__(self, heroes: dict[str, HeroInfo], items: dict[str, ItemInfo], patch: str):
        self.heroes = heroes
        self.items = items
        self.patch = patch

    # --- loading and saving ---

    @classmethod
    def load(cls, data_dir: Path) -> "DataStore":
        """Load the cache from data_dir. Raises a clear error if it was never synced."""
        heroes_path = data_dir / HEROES_FILE
        if not heroes_path.exists():
            raise FileNotFoundError(
                f"No cached data in {data_dir}. Run: python -m scripts.sync_data"
            )
        heroes_raw = json.loads(heroes_path.read_text(encoding="utf-8"))
        items_raw = json.loads((data_dir / ITEMS_FILE).read_text(encoding="utf-8"))
        meta = json.loads((data_dir / META_FILE).read_text(encoding="utf-8"))
        return cls(
            heroes={k: HeroInfo.model_validate(v) for k, v in heroes_raw.items()},
            items={k: ItemInfo.model_validate(v) for k, v in items_raw.items()},
            patch=meta["patch"],
        )

    @staticmethod
    def save(
        data_dir: Path, heroes: dict[str, HeroInfo], items: dict[str, ItemInfo], patch: str
    ) -> None:
        """Write the cache. Keys are sorted so git diffs after a patch are readable."""
        data_dir.mkdir(parents=True, exist_ok=True)

        def write(name: str, data: object) -> None:
            text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
            (data_dir / name).write_text(text + "\n", encoding="utf-8")

        write(HEROES_FILE, {k: v.model_dump() for k, v in heroes.items()})
        write(ITEMS_FILE, {k: v.model_dump() for k, v in items.items()})
        write(
            META_FILE,
            {"patch": patch, "synced_at": datetime.now(UTC).isoformat(timespec="seconds")},
        )

    # --- lookups (use GSI internal names) ---

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
