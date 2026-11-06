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
