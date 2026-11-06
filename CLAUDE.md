# CLAUDE.md — Dota Coach

Context for Claude Code working in this repo. Read `ARCHITECTURE.md` for the full design
and `LEARNING_ROADMAP.md` for the current phase.

## What this project is
A Dota 2 coaching app: live item, skill, farm-pattern and draft advice during a match.
Data comes from Dota 2 Game State Integration (GSI) and cached OpenDota stats.
Tips are delivered by voice (local TTS), a Next.js dashboard, and an MCP server.

## About the developer
- Student developer, Python and TypeScript at a basic level, learning as we build.
- Explain non-obvious code briefly in comments or in the reply. Prefer simple, readable
  solutions over clever ones. Don't introduce new frameworks without saying why.

## Hard rules (never break)
1. **Fair play.** Only use official GSI data for the local player and aggregate public
   stats. Never read game memory, hook the client, or look up opponents' accounts.
2. **No API calls on every GSI tick.** OpenDota data is synced per patch and cached;
   the AI is called only on events and only from the backend.
3. **Secrets stay server-side.** The Claude API key never appears in `companion/` or `web/`
   client code. Use env vars; never commit `.env`.
4. **Rules are pure functions.** `rules/` has no I/O; test them with `fixtures/`.
5. GSI receiver binds to `127.0.0.1` and checks the auth token.

## Stack
- **Companion (local):** Python 3.12 (venv + pip, pinned `requirements*.txt`), FastAPI + uvicorn, Pydantic, httpx, pytest,
  Piper TTS, official MCP Python SDK (stdio).
- **Cloud:** Cloudflare Workers + Durable Objects (TS) or FastAPI on Render — see
  open question in ARCHITECTURE.md. Postgres on Neon/Supabase.
- **Web:** Next.js (App Router), TypeScript, deployed on Vercel.
- **AI:** Claude API, cheapest model tier, prompt caching for static context.

## Commands
> Update this section as tooling is added.
```bash
# companion
python3 -m venv .venv                    # create env (once)
source .venv/bin/activate                # activate (every new terminal)
pip install -r requirements-dev.txt      # install deps (app + pytest, ruff)
uvicorn companion.main:app --host 127.0.0.1 --port 3000
pytest                                   # tests (use fixtures/)
python -m scripts.sync_data              # refresh OpenDota cache after a patch (~7 min)
python -m scripts.sync_data --constants-only  # just heroes/items/patch

# web
cd web && npm install && npm run dev
```

## Conventions
- Python: new packages go into `requirements.txt` (or `-dev`) with an exact `==` version.
- Python: type hints everywhere, Pydantic for external data, `ruff` for lint/format.
- TypeScript: strict mode, no `any` without a comment explaining why.
- One rule per function in `companion/rules/`, named `rule_<what>()`, each with tests.
- Tips: `Tip(kind, priority, text, voice_key)`; new tip kinds need a cooldown entry.
- Hero/item names from GSI use internal names (e.g. `npc_dota_hero_lion`,
  `item_blink`); map them via `data/` constants, never hardcode display names.
- Save new real GSI payloads to `fixtures/` with descriptive names
  (e.g. `lion_min12_skillpoint.json`) when adding rules.
- Small commits, conventional messages (`feat:`, `fix:`, `test:`, `docs:`).

## When working on a task
1. Check which phase in `LEARNING_ROADMAP.md` the task belongs to; don't build later
   phases early.
2. Write or update tests first for rules and parsers.
3. Keep the hot path (GSI → tips → voice) non-blocking.
4. If a change affects the architecture, update `ARCHITECTURE.md` in the same commit.
5. Never commit to `main`. Work on a feature branch (`feat/...`, `fix/...`), make small
   commits with clear messages, run `pytest` and `ruff`, then open a pull request.
   The PR describes the changes per commit, includes the test results, and lists any
   manual steps for the gaming PC (Windows, runs Dota) or the Mac (dev machine).
   The developer reviews and merges.

## Out of scope
- Custom ML models, memory reading, opponent scouting, overlays drawn into the game.
