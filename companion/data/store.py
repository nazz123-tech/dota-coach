"""Read-only access to the cached OpenDota data in data/.

Loaded once at startup; lookups are plain dict reads, so they're instant and
make zero network calls during a match (hard rule 2).
Refresh the cache after a patch with:  python -m scripts.sync_data
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

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
        if not (data_dir / HEROES_FILE).exists():
            raise FileNotFoundError(
                f"No cached data in {data_dir}. Run: python -m scripts.sync_data"
            )
        return cls(
            heroes=_read_models(data_dir / HEROES_FILE, HeroInfo),
            items=_read_models(data_dir / ITEMS_FILE, ItemInfo),
            patch=_read_json(data_dir / META_FILE)["patch"],
        )

    def save(self, data_dir: Path) -> None:
        """Write the cache. Keys are sorted so git diffs after a patch are readable."""
        data_dir.mkdir(parents=True, exist_ok=True)
        _write_models(data_dir / HEROES_FILE, self.heroes)
        _write_models(data_dir / ITEMS_FILE, self.items)
        synced_at = datetime.now(UTC).isoformat(timespec="seconds")
        _write_json(data_dir / META_FILE, {"patch": self.patch, "synced_at": synced_at})

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


# --- small JSON helpers, shared by load() and save() ---


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Any) -> None:
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def _read_models[M: BaseModel](path: Path, model: type[M]) -> dict[str, M]:
    """Read a {key: {...}} JSON file into {key: model}."""
    return {key: model.model_validate(value) for key, value in _read_json(path).items()}


def _write_models(path: Path, models: dict[str, BaseModel]) -> None:
    _write_json(path, {key: value.model_dump() for key, value in models.items()})
