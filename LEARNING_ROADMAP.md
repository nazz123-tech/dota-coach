# Dota Coach — Learning Roadmap

A step-by-step path from "Python & TS basics" to a working, shippable Dota 2 coaching app.
Each phase has: **what you learn**, **what you build**, and a **done when** check.
Don't skip ahead — every phase is testable in a real game before you move on.

Rough time: 8–12 weeks alongside studies (2–3 short sessions a week).

---

## Phase 0 — Setup (1–2 evenings)

**Learn**
- Git basics: branches, commits, `.gitignore`, pushing to GitHub
- Python virtual environments (`uv` or `python -m venv`)
- Reading JSON and using `curl` / Postman / Bruno to call an API

**Build**
- New repo `dota-coach` on GitHub (nazz123-tech)
- Folder layout from `ARCHITECTURE.md` (empty folders + README)
- Add `CLAUDE.md` to the root

**Done when**
- `git clone` + `uv sync` (or `pip install -r requirements.txt`) works on a fresh machine

---

## Phase 1 — Receive live game data with GSI (1 week)

**Learn**
- What a webhook is: the game *pushes* JSON to your server
- FastAPI basics: routes, request bodies, running with `uvicorn`
- Pydantic models for typed data
- Dota 2 Game State Integration (GSI): config file, data sections

**Build**
1. Add Dota launch option `-gamestateintegration` (Steam → Dota 2 → Properties).
2. Create `steamapps/common/dota 2 beta/game/dota/cfg/gamestate_integration/gamestate_integration_coach.cfg`
   pointing at `http://127.0.0.1:3000/` with an auth token.
3. FastAPI endpoint `POST /` that checks the token and logs the JSON.
4. Save a few real payloads to `fixtures/` — you'll test against these forever.
5. Pydantic models for the parts you need: `map`, `player`, `hero`, `abilities`, `items`.

**Done when**
- You play a bot match and see clock time, gold, level and items updating in your terminal.
- You have 5+ saved fixture files from different game moments.

---

## Phase 2 — Static data + OpenDota (1 week)

**Learn**
- Calling REST APIs with `httpx` (async)
- Rate limits and caching (why you never call an API on every tick)
- SQLite basics (or just JSON files to start)

**Build**
1. Script `scripts/sync_data.py` that downloads once per patch:
   - hero list, item list (OpenDota constants)
   - per hero: item popularity, matchups
   - benchmarks (GPM/XPM targets)
2. Store in `data/` (JSON) or SQLite.
3. A `DataStore` class: `get_build(hero)`, `get_matchups(hero)`, `get_benchmark(hero, minute)`.

**Done when**
- The app runs a whole game with **zero** OpenDota calls (all from cache).
- Re-running the sync script after a patch refreshes everything.

---

## Phase 3 — Rule engine: the real brain (1–2 weeks)

**Learn**
- Designing small pure functions: `state in → tips out`
- Unit testing with `pytest` using your fixtures
- Simple state diffing (what changed since the last tick?)

**Build**
Rules, each its own small function returning `Tip(priority, kind, text)`:
- Skill point available → which ability to skill (from build data)
- Enough gold for next core item → "buy X"
- Behind GPM benchmark at 10/20 min → farm pattern advice
- Roshan respawn window, day/night, rune timers
- Low health + no regen items → "buy salve / go back"

Plus a **TipManager**: priority queue, cooldown per tip type, no repeats.

**Done when**
- `pytest` passes for every rule using saved fixtures.
- In a bot game, tips print at sensible moments and don't spam.

---

## Phase 4 — Voice (1 week)

**Learn**
- Text-to-speech basics; playing audio from Python
- Running blocking work off the main loop (`asyncio` + threads/queues)

**Build**
1. Piper TTS (local, free) with one voice.
2. `scripts/prerender_voice.py`: render common lines once to `assets/voice/*.wav`.
3. `VoiceOutput`: plays pre-rendered clips instantly, Piper for dynamic text.
4. "Fight detection": hold tips while health is dropping fast or hero is dead.
5. Voice levels: `urgent` / `normal` / `chatty`.

**Done when**
- You play a real match with voice on and it feels helpful, not annoying.

---

## Phase 5 — MCP server (1 week)

**Learn**
- What MCP is: tools + resources an AI client can call
- The official MCP Python SDK (`mcp`, FastMCP style)
- stdio transport and connecting a server to Claude Desktop

**Build**
MCP tools that read from the same state + DataStore:
- `get_live_state()` — compact summary of your current game
- `get_item_build(hero)`, `get_skill_order(hero)`
- `get_matchup(hero, enemy_hero)`
- `check_farm_pace()`
- `get_my_hero_stats(hero)` (Phase 6)

**Done when**
- In Claude Desktop, mid-game, you ask "what should I build next?" and get an answer using your live state.

---

## Phase 6 — Draft helper (1 week)

**Learn**
- Simple scoring/ranking (weighted sums)
- Steam account IDs; OpenDota player endpoints for **your own** account

**Build**
1. Check what GSI gives a *player* during hero selection. If enemy picks aren't sent,
   the user taps visible picks in the UI (see ARCHITECTURE.md).
2. Score candidate heroes: counter score + synergy + **your own** win rate/games on that hero.
3. Return top 5 with one-line reasons.

**Rule:** only visible picks + the user's own account. Never look up other players.

**Done when**
- During a real draft, you get a top-5 list you'd actually consider.

---

## Phase 7 — Web dashboard (2 weeks)

**Learn**
- Next.js App Router, server vs client components
- WebSockets (live updates)
- Postgres basics (Neon/Supabase free tier) + an ORM (Drizzle or Prisma)
- Deploying to Vercel; a small backend on Cloudflare Workers or Render

**Build**
1. Companion pushes compact state to the cloud relay over WebSocket.
2. Next.js pages:
   - `/live` — current game, latest tips, next items
   - `/heroes` — meta for the 4–5 heroes you pick
   - `/history` — your recent matches
3. Store finished matches in Postgres.

**Done when**
- You open `/live` on your phone during a game and it updates in real time.

---

## Phase 8 — AI coaching with Claude (1 week)

**Learn**
- Claude API: messages, system prompts, prompt caching
- Token budgeting; event-based calling

**Build**
- Backend endpoint `/coach` that takes a compact state summary and returns 1–2 sentences.
- Called only on events (death, every 5 min, item completed) — ~10–20 calls/game.
- Post-game review from the match summary.
- Per-user daily cap.

**Done when**
- Cost per game is measured and logged (target: a few cents).

---

## Phase 9 — Ship to other players (2+ weeks)

**Learn**
- Packaging: PyInstaller, or a Tauri app wrapping the companion
- Steam OpenID login
- Payments via a merchant-of-record (Lemon Squeezy / Paddle)
- Privacy basics (what you store, a simple privacy page)

**Build**
1. Installer that auto-finds the Dota folder and writes the GSI config.
2. Steam login → links companion to the user's web account.
3. Free tier (rules + voice) vs paid tier (AI coaching, voice Q&A, reviews).
4. Before charging: register an enkeltpersonforetak, check Valve's terms and
   OpenDota's commercial plan.

**Done when**
- 5 friends install it without your help and use it for a week.

---

## Stretch ideas (v2)
- Push-to-talk questions with local Whisper speech-to-text
- Personal "mistakes" report across your last 20 games
- Patch-change alerts for your heroes

## Rules to remember throughout
- Fair play: own hero data + public stats only. Never read game memory, never scout opponents.
- Never call an API or the AI on every GSI tick.
- Keep the Claude API key on the server, never in the client app.
- Test with saved fixtures before testing in real games.
