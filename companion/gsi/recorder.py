"""Decide which GSI payloads are worth saving as test fixtures.

Dota sends ~10 payloads per second; saving all of them would create tens of
thousands of near-identical files per game. Instead we compare each payload with
the previous one and only save when something interesting happened.

These are pure functions (no file I/O) so they are easy to test.
"""

from typing import Any

Payload = dict[str, Any]


def _minute(payload: Payload) -> int:
    """Game minute; pre-game (negative clock) counts as minute 0."""
    clock = payload.get("map", {}).get("clock_time", 0)
    return max(clock, 0) // 60


def _item_names(payload: Payload) -> list[str]:
    """Sorted item names, ignoring empty slots and which slot an item is in."""
    items = payload.get("items", {})
    names = [slot.get("name") for slot in items.values() if isinstance(slot, dict)]
    return sorted(n for n in names if n and n != "empty")


def save_reason(previous: Payload | None, current: Payload) -> str | None:
    """Return why `current` should be saved, or None to skip it."""
    if "map" not in current:
        return None  # in the menu, no game running
    if previous is None or "map" not in previous:
        return "start"

    if current.get("hero", {}).get("level") != previous.get("hero", {}).get("level"):
        return "levelup"
    if current.get("player", {}).get("deaths") != previous.get("player", {}).get("deaths"):
        return "death"
    if _item_names(current) != _item_names(previous):
        return "items"
    if _minute(current) != _minute(previous):
        return "newminute"
    return None


def fixture_name(payload: Payload, reason: str) -> str:
    """Descriptive file name (without .json), e.g. 'lion_min12_levelup'."""
    hero = payload.get("hero", {}).get("name", "unknown")
    hero = hero.removeprefix("npc_dota_hero_")
    return f"{hero}_min{_minute(payload)}_{reason}"


# Personal fields we never want in a committed fixture. Rules don't need them.
PERSONAL_PLAYER_FIELDS = ("steamid", "accountid", "name")
REDACTED = "<redacted>"


def _redact_player(player: Any) -> Any:
    if not isinstance(player, dict):
        return player
    return {k: (REDACTED if k in PERSONAL_PLAYER_FIELDS else v) for k, v in player.items()}


def clean_for_fixture(payload: Payload) -> Payload:
    """Copy of the payload that is safe to save and commit (repo is public).

    - drops the `auth` block so the GSI token never ends up in a fixture file
    - replaces Steam ID, account ID and player name with "<redacted>",
      also inside Dota's `previously` / `added` change blocks
    """
    cleaned = {key: value for key, value in payload.items() if key != "auth"}
    if "player" in cleaned:
        cleaned["player"] = _redact_player(cleaned["player"])
    for block in ("previously", "added"):
        if isinstance(cleaned.get(block), dict) and "player" in cleaned[block]:
            cleaned[block] = {**cleaned[block], "player": _redact_player(cleaned[block]["player"])}
    return cleaned
