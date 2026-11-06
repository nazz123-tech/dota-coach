# Dota Coach

Live Dota 2 coaching: item, skill, farm-pattern and draft advice during a match,
delivered by voice, a web dashboard and an MCP server.

- Design: [ARCHITECTURE.md](ARCHITECTURE.md)
- Build plan: [LEARNING_ROADMAP.md](LEARNING_ROADMAP.md)
- AI assistant context: [CLAUDE.md](CLAUDE.md)

## Status
Phase 1 (GSI receiver, fixtures, models) done. Next: Phase 2 — OpenDota data cache.

## Quick start (companion)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # set GSI_TOKEN
uvicorn companion.main:app --host 127.0.0.1 --port 3000
pytest                          # run tests
```
Then copy `dota_config/gamestate_integration_coach.cfg` into
`steamapps/common/dota 2 beta/game/dota/cfg/gamestate_integration/`
(use the same token) and add `-gamestateintegration` to Dota 2's launch options.

Set `SAVE_FIXTURES=1` in `.env` to record real payloads into `fixtures/`.
Only interesting moments are saved (game start, new minute, level up, death,
item change), with names like `lion_min12_levelup.json`.

## Fair play
Only the local player's official GSI data and public aggregate stats are used.
No memory reading, no opponent lookups.
