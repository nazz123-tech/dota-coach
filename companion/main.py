"""Phase 1: receive Dota 2 GSI payloads and log the basics.

Run:  uv run uvicorn companion.main:app --host 127.0.0.1 --port 3000
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

load_dotenv()
GSI_TOKEN = os.getenv("GSI_TOKEN", "change-me")
SAVE_FIXTURES = os.getenv("SAVE_FIXTURES") == "1"
FIXTURES_DIR = Path("fixtures")

app = FastAPI(title="Dota Coach companion")


@app.post("/")
async def receive_gsi(request: Request) -> dict:
    payload = await request.json()

    # Dota sends the token from the cfg file; reject anything else.
    if payload.get("auth", {}).get("token") != GSI_TOKEN:
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

    # Record real payloads for tests (Phase 1, step 4).
    if SAVE_FIXTURES and game_map:
        FIXTURES_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        (FIXTURES_DIR / f"gsi_{stamp}.json").write_text(json.dumps(payload, indent=2))

    return {"ok": True}
