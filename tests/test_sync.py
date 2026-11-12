"""Sync script tests, fully offline.

httpx.MockTransport is a fake server: every request goes to our `handler`
function instead of the internet. A fake `sleep` records waits instead of
actually waiting, so tests run instantly.
"""

import json
from pathlib import Path

import httpx
import pytest

from companion.data.store import DataStore
from companion.data.transform import HeroBuild
from scripts.sync_data import MAX_RETRIES, OpenDota, sync_hero_stats

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "fixtures" / "opendota"
DOOM = "npc_dota_hero_doom_bringer"
SF = "npc_dota_hero_nevermore"

# Run the `async def` tests below with anyio's pytest plugin (installed with FastAPI).
pytestmark = pytest.mark.anyio


def sample(name: str):
    return json.loads((SAMPLES / name).read_text())


def make_api(handler, sleeps: list[float]) -> OpenDota:
    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://test")
    return OpenDota(client, delay=1.0, sleep=fake_sleep)


def small_store() -> DataStore:
    """Real constants, but only two heroes, to keep tests short."""
    real = DataStore.load(ROOT / "data")
    return DataStore(
        heroes={k: real.heroes[k] for k in (DOOM, SF)}, items=real.items, patch=real.patch
    )


async def test_requests_are_paced():
    sleeps: list[float] = []
    api = make_api(lambda request: httpx.Response(200, json={}), sleeps)
    for _ in range(3):
        await api.get("/x")
    assert sleeps == [1.0, 1.0]  # no wait before the first request


async def test_retries_after_429_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if len(calls) == 1:
            return httpx.Response(429)  # "too many requests"
        return httpx.Response(200, json={"ok": True})

    sleeps: list[float] = []
    assert await make_api(handler, sleeps).get("/x") == {"ok": True}
    assert len(calls) == 2
    assert max(sleeps) > 1.0  # backed off longer than the normal pace


async def test_gives_up_after_max_retries():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(httpx.HTTPStatusError):
        await make_api(handler, []).get("/x")
    assert len(calls) == MAX_RETRIES


async def test_404_is_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(404)

    with pytest.raises(httpx.HTTPStatusError):
        await make_api(handler, []).get("/x")
    assert len(calls) == 1


async def test_sync_hero_stats_fills_store_and_keeps_old_data_on_failure():
    # Doom (id 69) answers with real samples; Shadow Fiend (id 11) always fails.
    responses = {
        "/heroes/69/itemPopularity": sample("doom_item_popularity.json"),
        "/heroes/69/matchups": sample("doom_matchups.json"),
        "/benchmarks": sample("doom_benchmarks.json"),
    }

    def handler(request):
        if request.url.path == "/benchmarks" and request.url.params["hero_id"] != "69":
            return httpx.Response(500)
        if request.url.path in responses:
            return httpx.Response(200, json=responses[request.url.path])
        return httpx.Response(500)

    store = small_store()
    old_sf_build = HeroBuild()
    store.builds[SF] = old_sf_build  # pretend SF was synced successfully last time

    failed = await sync_hero_stats(make_api(handler, []), store)

    assert failed == [SF]
    assert store.get_build(DOOM).mid_game[0].item == "item_blink"
    # The small store only knows Doom and SF, so only the matchup vs SF is kept.
    assert [m.hero for m in store.get_matchups(DOOM)] == [SF]
    assert store.get_benchmark(DOOM, minute=10).gold == 5300
    assert store.get_build(SF) is old_sf_build  # old data kept, not wiped
