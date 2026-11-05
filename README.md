# Dota Coach

Live Dota 2 coaching: item, skill, farm-pattern and draft advice during a match,
delivered by voice, a web dashboard and an MCP server.

- Design: [ARCHITECTURE.md](ARCHITECTURE.md)
- Build plan: [LEARNING_ROADMAP.md](LEARNING_ROADMAP.md)
- AI assistant context: [CLAUDE.md](CLAUDE.md)

## Status
Phase 1 — receiving live game data with Game State Integration.

## Quick start (companion)
```bash
uv sync
cp .env.example .env            # set GSI_TOKEN
uv run uvicorn companion.main:app --host 127.0.0.1 --port 3000
```
Then copy `dota_config/gamestate_integration_coach.cfg` into
`steamapps/common/dota 2 beta/game/dota/cfg/gamestate_integration/`
(use the same token) and add `-gamestateintegration` to Dota 2's launch options.

Set `SAVE_FIXTURES=1` in `.env` to record real payloads into `fixtures/`.

## Fair play
Only the local player's official GSI data and public aggregate stats are used.
No memory reading, no opponent lookups.
