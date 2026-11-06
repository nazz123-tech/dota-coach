"""Download OpenDota data once per patch and save it to data/.

Run from the project folder:
    python -m scripts.sync_data                   # everything (~7 minutes)
    python -m scripts.sync_data --constants-only  # just heroes/items/patch (seconds)

This is the ONLY place that talks to OpenDota. The companion reads data/ at
startup and never calls the API during a match (hard rule 2).

OpenDota's free tier allows about 60 requests per minute, so requests are sent
one at a time with a short pause between them, and retried with a longer pause
when the server says "too many requests" (HTTP 429) or has a hiccup (5xx).
"""

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from companion.data.store import DataStore
from companion.data.transform import (
    benchmarks_from_opendota,
    build_from_opendota,
    heroes_from_opendota,
    items_from_opendota,
    latest_patch,
    matchups_from_opendota,
)

API = "https://api.opendota.com/api"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REQUEST_DELAY = 1.1  # seconds between requests (~55/min, under the 60/min limit)
MAX_RETRIES = 3  # attempts per request before giving up
SAVE_EVERY = 20  # save progress every N heroes, so Ctrl+C doesn't lose everything


class OpenDota:
    """Polite OpenDota client: paces requests and retries temporary errors.

    `sleep` is a parameter so tests can pass a fake one and run instantly.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        delay: float = REQUEST_DELAY,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self.client = client
        self.delay = delay
        self.sleep = sleep
        self._first_request = True

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        for attempt in range(1, MAX_RETRIES + 1):
            if not self._first_request:
                await self.sleep(self.delay)
            self._first_request = False

            response = await self.client.get(path, params=params)
            temporary = response.status_code == 429 or response.status_code >= 500
            if temporary and attempt < MAX_RETRIES:
                await self.sleep(self.delay * 10 * attempt)  # back off: 11s, then 22s
                continue
            response.raise_for_status()  # 404 etc. (or last failed retry) -> error
            return response.json()
        raise AssertionError("unreachable")  # the loop always returns or raises


async def sync_constants(api: OpenDota) -> DataStore:
    """Fresh heroes, items and patch name (no per-hero stats yet)."""
    heroes = heroes_from_opendota(await api.get("/constants/heroes"))
    items = items_from_opendota(await api.get("/constants/items"))
    patch = latest_patch(await api.get("/constants/patch"))
    return DataStore(heroes=heroes, items=items, patch=patch)


async def sync_hero_stats(
    api: OpenDota, store: DataStore, save_to: Path | None = None
) -> list[str]:
    """Fill builds, matchups and benchmarks for every hero in `store`.

    If a hero fails after retries, its previous data (if any) is kept.
    Returns the internal names of heroes that failed.
    """
    item_ids = {item.id: name for name, item in store.items.items()}
    hero_ids = {hero.id: name for name, hero in store.heroes.items()}
    heroes = sorted(store.heroes.items(), key=lambda pair: pair[1].id)
    failed = []

    for number, (name, hero) in enumerate(heroes, start=1):
        try:
            popularity = await api.get(f"/heroes/{hero.id}/itemPopularity")
            matchups = await api.get(f"/heroes/{hero.id}/matchups")
            benchmarks = await api.get("/benchmarks", params={"hero_id": hero.id})
        except httpx.HTTPError as err:
            failed.append(name)
            print(f"[{number:>3}/{len(heroes)}] {hero.name}: FAILED ({err}), keeping old data")
            continue

        store.builds[name] = build_from_opendota(popularity, item_ids)
        store.matchups[name] = matchups_from_opendota(matchups, hero_ids)
        store.benchmarks[name] = benchmarks_from_opendota(benchmarks)
        print(f"[{number:>3}/{len(heroes)}] {hero.name}")

        if save_to is not None and number % SAVE_EVERY == 0:
            store.save(save_to)
    return failed


async def main(constants_only: bool) -> int:
    headers = {"User-Agent": "dota-coach-sync"}
    async with httpx.AsyncClient(base_url=API, timeout=30, headers=headers) as client:
        api = OpenDota(client)
        store = await sync_constants(api)
        print(
            f"Constants: {len(store.heroes)} heroes, {len(store.items)} items, patch {store.patch}"
        )

        # Start from the existing per-hero stats, so failures keep old data.
        if (DATA_DIR / "heroes.json").exists():
            old = DataStore.load(DATA_DIR)
            store.builds, store.matchups, store.benchmarks = (
                old.builds,
                old.matchups,
                old.benchmarks,
            )

        failed: list[str] = []
        if not constants_only:
            minutes = len(store.heroes) * 3 * REQUEST_DELAY / 60
            print(f"Per-hero stats: {len(store.heroes) * 3} requests, about {minutes:.0f} minutes")
            failed = await sync_hero_stats(api, store, save_to=DATA_DIR)

    store.save(DATA_DIR)
    print(f"Saved to {DATA_DIR}")
    if failed:
        print(f"{len(failed)} heroes failed (old data kept): {', '.join(failed)}")
        print("Run the sync again later to retry them.")
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync OpenDota data into data/.")
    parser.add_argument(
        "--constants-only",
        action="store_true",
        help="only refresh heroes, items and patch (skip per-hero stats)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.constants_only)))
