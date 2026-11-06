from companion.gsi.recorder import clean_for_fixture, fixture_name, save_reason


def make(clock=120, level=3, deaths=0, items=("item_tango",), hero="npc_dota_hero_lion"):
    """Build a minimal GSI-like payload for tests."""
    slots = {f"slot{i}": {"name": name} for i, name in enumerate(items)}
    slots[f"slot{len(items)}"] = {"name": "empty"}
    return {
        "map": {"clock_time": clock},
        "hero": {"name": hero, "level": level},
        "player": {"deaths": deaths},
        "items": slots,
    }


def test_first_payload_is_saved():
    assert save_reason(None, make()) == "start"


def test_same_state_is_not_saved():
    assert save_reason(make(clock=120), make(clock=121)) is None


def test_new_minute():
    assert save_reason(make(clock=119), make(clock=120)) == "newminute"


def test_pregame_clock_is_not_a_new_minute():
    # Clock is negative before the horn; don't save every pre-game second.
    assert save_reason(make(clock=-61), make(clock=-59)) is None


def test_level_up():
    assert save_reason(make(level=3), make(level=4)) == "levelup"


def test_death():
    assert save_reason(make(deaths=0), make(deaths=1)) == "death"


def test_item_change():
    before = make(items=("item_tango",))
    after = make(items=("item_tango", "item_boots"))
    assert save_reason(before, after) == "items"


def test_moving_an_item_between_slots_is_not_a_change():
    before = make(items=("item_tango", "item_boots"))
    after = make(items=("item_boots", "item_tango"))
    assert save_reason(before, after) is None


def test_payload_without_map_is_ignored():
    # Dota sends map-less payloads in the menu; nothing useful to record.
    assert save_reason(None, {"provider": {}}) is None


def test_fixture_name():
    assert fixture_name(make(clock=725), "levelup") == "lion_min12_levelup"


def test_fixture_name_pregame():
    assert fixture_name(make(clock=-30), "start") == "lion_min0_start"


def test_clean_for_fixture_removes_token():
    payload = {"auth": {"token": "secret"}, "map": {"clock_time": 1}}
    cleaned = clean_for_fixture(payload)
    assert "auth" not in cleaned
    assert cleaned["map"] == {"clock_time": 1}
    assert payload["auth"] == {"token": "secret"}  # original left untouched


def test_clean_for_fixture_blanks_personal_info():
    payload = {
        "player": {"steamid": "765611", "accountid": "123", "name": "Me", "gold": 600},
        "previously": {"player": {"name": "OldName", "gold": 500}},
    }
    cleaned = clean_for_fixture(payload)
    assert cleaned["player"] == {
        "steamid": "<redacted>",
        "accountid": "<redacted>",
        "name": "<redacted>",
        "gold": 600,
    }
    assert cleaned["previously"]["player"] == {"name": "<redacted>", "gold": 500}
    assert payload["player"]["name"] == "Me"  # original left untouched
