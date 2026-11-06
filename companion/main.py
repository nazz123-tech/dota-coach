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
from pydantic import ValidationError

from companion.gsi.models import GameState
from companion.gsi.recorder import clean_for_fixture, fixture_name, save_reason

logger = logging.getLogger("uvicorn.error")  # shows up in uvicorn's console output

# Paths based on this file's location, so they work no matter which folder you
# start the server from.
PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_DIR / ".env"
FIXTURES_DIR = PROJECT_DIR / "fixtures"

load_dotenv(ENV_FILE)

DEFAULT_TOKEN = "change-me"
GSI_TOKEN = os.getenv("GSI_TOKEN", DEFAULT_TOKEN).strip()
# Accept "1", "true", "yes" (any case, extra spaces ignored).
SAVE_FIXTURES = os.getenv("SAVE_FIXTURES", "").strip().lower() in {"1", "true", "yes"}

# Startup report: makes setup problems visible right away.
if ENV_FILE.exists():
    logger.info(".env loaded from %s", ENV_FILE)
elif (PROJECT_DIR / ".env.txt").exists():
    logger.warning("Found .env.txt but not .env -- rename it: mv .env.txt .env")
else:
    logger.warning("No .env file in %s -- copy .env.example to .env", PROJECT_DIR)
if GSI_TOKEN == DEFAULT_TOKEN:
    logger.warning("GSI_TOKEN is still '%s'. Set your own token in .env.", DEFAULT_TOKEN)
if SAVE_FIXTURES:
    logger.info("Fixture saving: ON -> %s", FIXTURES_DIR)
else:
    logger.info("Fixture saving: OFF (set SAVE_FIXTURES=1 in .env to turn on)")

# Set after the first rejected payload, so the hint below prints once, not 10x/second.
_warned_bad_token = False

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
    path.write_text(json.dumps(clean_for_fixture(payload), indent=2))
    logger.info("saved fixture %s", path.name)


@app.post("/")
async def receive_gsi(request: Request) -> dict[str, bool]:
    global _last_payload, _warned_bad_token

    try:
        payload = await request.json()
    except ValueError:  # body isn't valid JSON
        raise HTTPException(status_code=400, detail="invalid JSON")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="expected a JSON object")

    if not _token_ok(payload):
        if not _warned_bad_token:
            _warned_bad_token = True
            sent = payload.get("auth", {}).get("token")
            hint = (
                " Dota sent the placeholder 'GSI_TOKEN' -- put your real token in the .cfg"
                " inside the Dota folder, then restart Dota."
                if sent == "GSI_TOKEN"
                else ""
            )
            logger.warning(
                "Rejected payload: token in the Dota .cfg doesn't match GSI_TOKEN in .env.%s",
                hint,
            )
        raise HTTPException(status_code=401, detail="bad token")

    # Turn the raw dict into typed data (see companion/gsi/models.py).
    try:
        state = GameState.model_validate(payload)
    except ValidationError as err:
        logger.warning("Payload didn't match the GSI models: %s", err)
        raise HTTPException(status_code=400, detail="unexpected payload shape")

    if state.map is not None and state.hero_picked:
        p, h = state.player, state.hero
        items = ", ".join(name.removeprefix("item_") for name in state.inventory) or "-"
        print(
            f"[{state.map.clock_time:>5}s] {h.name} lvl {h.level} "
            f"gold {p.gold} K/D/A {p.kills}/{p.deaths}/{p.assists} | {items}"
        )

    # Record real payloads for tests (Phase 1, step 4) -- only on interesting events.
    # Small file writes a few times per minute; fine for now, move off the hot path later.
    if SAVE_FIXTURES:
        reason = save_reason(_last_payload, payload)
        if reason:
            _save_fixture(payload, reason)

    _last_payload = payload
    return {"ok": True}
