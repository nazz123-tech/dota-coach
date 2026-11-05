from fastapi.testclient import TestClient

from companion.main import GSI_TOKEN, app

client = TestClient(app)


def test_rejects_bad_token():
    r = client.post("/", json={"auth": {"token": "wrong"}})
    assert r.status_code == 401


def test_accepts_valid_payload():
    payload = {
        "auth": {"token": GSI_TOKEN},
        "map": {"clock_time": 120},
        "hero": {"name": "npc_dota_hero_lion", "level": 3},
        "player": {"gold": 450, "kills": 1, "deaths": 0, "assists": 2},
    }
    r = client.post("/", json=payload)
    assert r.status_code == 200
