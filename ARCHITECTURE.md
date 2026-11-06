# Dota Coach — Architecture

A Dota 2 coaching app: live item, skill, farm and draft advice during a match,
delivered by voice, a web dashboard, and an MCP server for AI clients.

## Goals
- Useful live tips with **near-zero running cost**
- Fair play: only the player's own game state + public statistics
- Personal use first, multi-user and monetizable later (freemium)

## Non-goals
- Reading game memory or anything outside official GSI
- Looking up opponents' accounts or history
- Training a custom ML model

---

## High-level diagram

```
┌──────────────────────── Player's PC ────────────────────────┐
│                                                             │
│  Dota 2 client                                              │
│     │ GSI: HTTP POST JSON (~10/s) to 127.0.0.1:3000         │
│     ▼                                                       │
│  Companion app (Python)                                     │
│   ├─ gsi/        receive + validate + parse state           │
│   ├─ state/      current GameState + diff vs previous       │
│   ├─ data/       cached heroes/items/builds/matchups        │
│   ├─ rules/      pure functions: state → Tips               │
│   ├─ tips/       TipManager: priority, cooldowns, dedupe    │
│   ├─ voice/      Piper TTS + pre-rendered clips             │
│   ├─ draft/      pick scoring                               │
│   ├─ mcp/        MCP server (stdio) ──► Claude Desktop      │
│   └─ relay/      WebSocket client ─────────────┐            │
│                                                │            │
└────────────────────────────────────────────────│────────────┘
                                                 ▼
┌──────────────────────── Cloud ──────────────────────────────┐
│  Relay / API  (Cloudflare Workers + Durable Objects,        │
│               or FastAPI on Render)                         │
│   ├─ per-user live session (WebSocket fan-out)              │
│   ├─ /coach  → Claude API (event-based, capped)             │
│   └─ auth (Steam OpenID), usage counters                    │
│                                                             │
│  Postgres (Neon/Supabase free)  — users, matches, usage     │
│                                                             │
│  Next.js on Vercel                                          │
│   ├─ /live     live game + tips                             │
│   ├─ /heroes   meta for chosen heroes                       │
│   ├─ /history  recent matches                               │
│   └─ /draft    draft helper UI                              │
└─────────────────────────────────────────────────────────────┘

External: OpenDota API (synced once per patch, cached)
```

---

## Components

### 1. GSI receiver (`companion/gsi`)
- FastAPI app on `127.0.0.1:3000`, single `POST /` route.
- Validates the `auth.token` from the GSI payload; rejects anything else.
- Parses into Pydantic models; unknown fields ignored.
  Models live in `companion/gsi/models.py` (`GameState`); every field has a
  default because Dota omits sections in the menu and during hero selection.
- Optional fixture recording (`SAVE_FIXTURES=1`) saves payloads only on events,
  with the `auth` token removed and Steam ID/account ID/name redacted.
- Dota config file: `cfg/gamestate_integration/gamestate_integration_coach.cfg`
  and launch option `-gamestateintegration`.
- Player GSI only contains the local player's hero. Full all-player data is
  spectator-only — design never depends on it.

### 2. State (`companion/state`)
- `GameState`: latest parsed snapshot.
- `StateDiff`: what changed (level up, item bought, died, minute crossed).
- Rules and AI triggers are driven by **events from diffs**, not by every tick.

### 3. Data store (`companion/data`, `scripts/sync_data.py`)
- Source: OpenDota (constants, hero item popularity, matchups, benchmarks).
- Synced once per patch into `data/*.json` by `python -m scripts.sync_data`
  (~7 min; `--constants-only` for just heroes/items/patch). Every file is keyed by
  GSI internal names (`npc_dota_hero_*`, `item_*`):
  - `heroes.json`, `items.json`: constants (display names, costs, components)
  - `builds.json`: top items per phase (start/early/mid/late) per hero
  - `matchups.json`: games and wins vs every other hero
  - `benchmarks.json`: per-minute rates (GPM, XPM, LH, ...) by percentile
  - `meta.json`: patch and sync time
  Committed to git so the gaming PC gets it with `git pull`.
- Sync is polite to the free tier (~60 req/min): one request at a time ~1.1 s
  apart, retries on 429/5xx with back-off, a failed hero keeps its old data.
- `companion/data/transform.py` (pure: raw OpenDota → cache format) and
  `companion/data/store.py` (`DataStore`: load/save + lookups).
- Runtime: zero network calls during a match.
- Interface: `get_build(hero)`, `get_matchups(hero)`,
  `get_benchmark(hero, minute, percentile=0.5)` (rate × minutes, approximate).
  `get_skill_order(hero)` is still open: OpenDota has no simple skill-build
  endpoint (see Open questions).

### 4. Rule engine (`companion/rules`)
- Each rule: `def rule(state, diff, data) -> list[Tip]` — pure, no I/O.
- `Tip(kind, priority, text, voice_key | None)`.
- Examples: skill point, next item affordable, farm pace vs benchmark,
  Roshan/rune timers, low HP without regen.
- Tested with `pytest` against `fixtures/*.json` (real saved payloads).

### 5. Tip manager (`companion/tips`)
- Priority queue; one tip delivered at a time.
- Cooldown per `kind`; no duplicate text within a window.
- "Combat hold": suppresses non-urgent tips while HP drops fast or hero is dead.
- Verbosity levels: `urgent` / `normal` / `chatty`.

### 6. Voice (`companion/voice`)
- Piper TTS, local and free.
- Common lines pre-rendered to `assets/voice/*.wav` → instant playback.
- Dynamic text synthesized on a worker thread; never blocks GSI handling.
- v2: push-to-talk + local Whisper speech-to-text.

### 7. Draft helper (`companion/draft`)
- Inputs: visible picks (from GSI if available to players; otherwise user taps
  picks in the UI) + the user's own hero stats from their own account.
- Score = counter score + synergy + personal win rate/experience (weighted).
- Output: top 5 heroes with one-line reasons.
- Never queries other players' accounts.

### 8. MCP server (`companion/mcp`)
- Official MCP Python SDK, stdio transport, runs inside the companion process
  (or as a sibling process reading shared state).
- Tools: `get_live_state`, `get_item_build`, `get_skill_order`, `get_matchup`,
  `check_farm_pace`, `get_my_hero_stats`, `suggest_picks`.
- Personal use via Claude Desktop → no API cost.

### 9. Relay + API (`cloud/`)
- Companion → cloud over WebSocket with a user token.
- Sends **compact state summaries** (a few hundred bytes), throttled (~1/s).
- Fans out to the user's open web pages.
- `/coach`: builds a compact prompt, calls Claude (cheapest model, prompt
  caching for static context), enforces per-user daily cap.
- Claude API key lives only here.

### 10. Web app (`web/`)
- Next.js (App Router, TypeScript) on Vercel.
- Pages: `/live`, `/heroes`, `/history`, `/draft`, `/settings`, `/pricing` (later).
- Reads Postgres for history/meta; WebSocket for live.

---

## Data flow: one tick
1. Dota POSTs GSI JSON → receiver validates token → `GameState`.
2. `StateDiff` computed → events emitted.
3. Rules run on events → Tips → TipManager.
4. TipManager picks one → Voice speaks it; also pushed to relay.
5. On selected events (death, 5-min mark, item done), backend may call Claude
   for a richer tip (paid tier).

## Cost model
| Piece | Cost |
|---|---|
| GSI, rules, voice (Piper), draft | $0 (runs locally) |
| OpenDota | free tier; cached per patch; paid plan if commercial |
| Vercel / Cloudflare / Neon | free tiers to start |
| Claude API | ~10–20 small calls/game, paid tier only, capped |
| Personal AI use | Claude Desktop via MCP, no API cost |

## Security & fair play
- GSI receiver binds to `127.0.0.1` only; token-checked.
- No memory reading, injection, or client modification.
- No opponent lookups; only the user's own account + aggregate public stats.
- API keys never shipped in the client.
- Store minimal user data: Steam ID, settings, own match summaries.

## Monetization (later)
- Free: rules, voice, draft helper, dashboard.
- Paid: AI coaching, voice Q&A, post-game reviews.
- Payments via merchant of record (Lemon Squeezy/Paddle).
- Prerequisites: enkeltpersonforetak, Valve terms check, OpenDota commercial plan.

## Repo layout
```
dota-coach/
├─ CLAUDE.md
├─ ARCHITECTURE.md
├─ LEARNING_ROADMAP.md
├─ companion/            # Python
│  ├─ gsi/ state/ data/ rules/ tips/ voice/ draft/ mcp/ relay/
│  └─ main.py
├─ dota_config/         # GSI .cfg to copy into the Dota folder
├─ requirements.txt     # pinned Python deps (+ requirements-dev.txt)
├─ scripts/              # sync_data.py, prerender_voice.py
├─ data/                 # cached OpenDota data (gitignored or versioned per patch)
├─ fixtures/             # saved GSI payloads for tests
├─ assets/voice/         # pre-rendered clips
├─ tests/
├─ cloud/                # relay + API (Workers TS or FastAPI)
└─ web/                  # Next.js app
```

## Open questions
- Skill-order source for `get_skill_order`: OpenDota has no aggregate endpoint;
  options are parsed public matches or a hand-written order per hero.
- Does player-side GSI include enemy picks during hero selection? (Verify in Phase 6.)
- Cloudflare Durable Objects (TS) vs FastAPI on Render (Python) for the relay.
- Packaging: PyInstaller vs Tauri wrapper.
