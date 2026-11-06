"""Download OpenDota constants once per patch and save them to data/.

Run from the project folder:  python -m scripts.sync_data

This is the ONLY place that talks to OpenDota. The companion reads data/ at
startup and never calls the API during a match (hard rule 2).
"""

import asyncio
from pathlib import Path

import httpx

from companion.data.store import DataStore
from companion.data.transform import heroes_from_opendota, items_from_opendota, latest_patch

API = "https://api.opendota.com/api"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


async def fetch_json(client: httpx.AsyncClient, path: str):
    response = await client.get(f"{API}{path}")
    response.raise_for_status()  # stop on 4xx/5xx instead of saving an error page
    return response.json()


async def main() -> None:
    async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "dota-coach-sync"}) as client:
        # Three independent requests, so run them at the same time.
        heroes_raw, items_raw, patch_raw = await asyncio.gather(
            fetch_json(client, "/constants/heroes"),
            fetch_json(client, "/constants/items"),
            fetch_json(client, "/constants/patch"),
        )

    heroes = heroes_from_opendota(heroes_raw)
    items = items_from_opendota(items_raw)
    patch = latest_patch(patch_raw)
    DataStore.save(DATA_DIR, heroes=heroes, items=items, patch=patch)
    print(f"Saved {len(heroes)} heroes and {len(items)} items for patch {patch} to {DATA_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
