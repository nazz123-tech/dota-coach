import json

import pytest
from fastapi.testclient import TestClient

from companion import main
from companion.main import GSI_TOKEN, app

client = TestClient(app)


def payload(**overrides):
    data = {
        "auth": {"token": GSI_TOKEN},
        "map": {"clock_time": 120},
        "hero": {"name": "npc_dota_hero_lion", "level": 3},
        "player": {"gold": 450, "kills": 1, "deaths": 0, "assists": 2},
    }
    data.update(overrides)
    return data


@pytest.fixture(autouse=True)
def reset_last_payload(monkeypatch):
    # The receiver remembers the previous tick; start each test fresh.
    monkeypatch.setattr(main, "_last_payload", None)
    monkeypatch.setattr(main, "_warned_bad_token", False)


def test_rejects_bad_token():
    r = client.post("/", json={"auth": {"token": "wrong"}})
    assert r.status_code == 401


def test_bad_token_warns_once_with_placeholder_hint(caplog):
    caplog.set_level("WARNING", logger="uvicorn.error")
    for _ in range(3):
        client.post("/", json={"auth": {"token": "GSI_TOKEN"}, "map": {"clock_time": 1}})
    warnings = [r.getMessage() for r in caplog.records if "Rejected payload" in r.getMessage()]
    assert len(warnings) == 1
    assert "placeholder 'GSI_TOKEN'" in warnings[0]


def test_rejects_non_string_token():
    r = client.post("/", json={"auth": {"token": 123}})
    assert r.status_code == 401


def test_accepts_valid_payload():
    r = client.post("/", json=payload())
    assert r.status_code == 200


def test_invalid_json_is_400():
    r = client.post("/", content=b"not json", headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_json_that_is_not_an_object_is_400():
    r = client.post("/", json=[1, 2, 3])
    assert r.status_code == 400


def test_saves_fixtures_only_on_events(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SAVE_FIXTURES", True)
    monkeypatch.setattr(main, "FIXTURES_DIR", tmp_path)

    client.post("/", json=payload())  # first tick -> saved ("start")
    client.post("/", json=payload(map={"clock_time": 121}))  # nothing changed -> skipped
    client.post("/", json=payload(map={"clock_time": 122}))  # nothing changed -> skipped
    client.post("/", json=payload(map={"clock_time": 180}))  # new minute -> saved

    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["lion_min2_start.json", "lion_min3_newminute.json"]
    saved = json.loads((tmp_path / "lion_min3_newminute.json").read_text())
    assert saved["map"]["clock_time"] == 180
    assert "auth" not in saved  # the token must never end up in a fixture


def test_same_name_does_not_overwrite(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "SAVE_FIXTURES", True)
    monkeypatch.setattr(main, "FIXTURES_DIR", tmp_path)

    client.post("/", json=payload())
    client.post("/", json=payload(hero={"name": "npc_dota_hero_lion", "level": 4}))
    client.post("/", json=payload(hero={"name": "npc_dota_hero_lion", "level": 5}))

    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["lion_min2_levelup.json", "lion_min2_levelup_2.json", "lion_min2_start.json"]
