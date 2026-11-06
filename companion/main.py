"""Phase 1: receive Dota 2 GSI payloads and log the basics.

Run:  uvicorn companion.main:app --host 127.0.0.1 --port 3000
"""

import json
import logging
import os
import secrets
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

from companion.gsi.recorder import fixture_name, save_reason

load_dotenv()
logger = logging.getLogger("uvicorn.error")  # shows up in uvicorn's console output

DEFAULT_TOKEN = "change-me"
GSI_TOKEN = os.getenv("GSI_TOKEN", DEFAULT_TOKEN)
SAVE_FIXTURES = os.getenv("SAVE_FIXTURES") == "1"
# Absolute path based on this file's location, so it works no matter which
# folder you start the server from.
FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

if GSI_TOKEN == DEFAULT_TOKEN:
    logger.warning("GSI_TOKEN is still '%s'. Set your own token in .env.", DEFAULT_TOKEN)

app = FastAPI(title="Dota Coach companion")

# Previous payload, used to detect what changed (for saving fixtures).
_last_payload: dict[str, Any] | None = None


def _token_ok(payload: dict[str, Any]) -> bool:
    token = payload.get("auth", {}).get("token")
    # compare_digest takes the same time whether the token is right or wrong,
    # so an attacker can't guess it character by character from response times.
    return isinstance(token, str) and secrets.compare_digest(token, GSI_TOKEN)


def _save_fixture(payload: dict[str, Any], reason: str) -> None:
    FIXTURES_DIR.mkdir(exist_ok=True)
    base = fixture_name(payload, reason)
    path = FIXTURES_DIR / f"{base}.json"
    n = 2
    while path.exists():  # never overwrite: lion_min2_levelup_2.json, _3, ...
        path = FIXTURES_DIR / f"{base}_{n}.json"
        n += 1
    path.write_text(json.dumps(payload, indent=2))
    logger.info("saved fixture %s", path.name)


@app.post("/")
async def receive_gsi(request: Request) -> dict[str, bool]:
    global _last_payload

    try:
        payload = await request.json()
    except ValueError:  # body isn't valid JSON
        raise HTTPException(status_code=400, detail="invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="expected a JSON object")

    if not _token_ok(payload):
        raise HTTPException(status_code=401, detail="bad token")

    game_map = payload.get("map", {})
    hero = payload.get("hero", {})
    player = payload.get("player", {})

    if game_map:
        print(
            f"[{game_map.get('clock_time', '?'):>5}s] "
            f"{hero.get('name', '?')} lvl {hero.get('level', '?')} "
            f"gold {player.get('gold', '?')} "
            f"K/D/A {player.get('kills', 0)}/{player.get('deaths', 0)}/{player.get('assists', 0)}"
        )

    # Record real payloads for tests (Phase 1, step 4) -- only on interesting events.
    # Small file writes a few times per minute; fine for now, move off the hot path later.
    if SAVE_FIXTURES:
        reason = save_reason(_last_payload, payload)
        if reason:
            _save_fixture(payload, reason)

    _last_payload = payload
    return {"ok": True}
