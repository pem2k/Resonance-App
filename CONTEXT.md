# RESONANCE — Dev Context for Resuming

## What This Is
A WWA (Pacific Northwest) Smash Bros. Melee crew league web dashboard. 8 teams of 5 players (captain + 4 draftees) earn points over a 6-week season by attending tournaments and performing relative to their seed. Points seed a finale crew battle.

**Head TO:** Rome0 (rome0. on Discord)
**Season 1 captains:** Graves, Stiv, Chango, Melo, SpiritGun, Jontae, Shanks, Browndogsarecool42

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Flask + SQLAlchemy + SQLite, Python 3.12 |
| Frontend | React 18 + Vite, CSS Modules |
| Data sources | start.gg GraphQL API and Parry.gg JSON-over-HTTP API (player-centric sync) |

**Backend entry point:** `run.py` → `api/` (Flask factory pattern)
**Frontend:** `client/` (Vite dev server on :5173, proxies `/api` to :5000)

---

## Running the App

```bash
# Backend (from project root)
venv/bin/python run.py
# or: source venv/bin/activate && python run.py

# Frontend (from client/)
npm run dev
```

Flask binds `0.0.0.0:5000`. Vite binds `0.0.0.0:5173` with proxy to `127.0.0.1:5000`.

---

## Environment (.env in project root)

```
SECRET_KEY=<generated hex>
APP_ENV=development
CORS_ORIGINS=http://localhost:5173
DATABASE_URL=sqlite:///resonance.db
STARTGG_API_KEY=<start.gg bearer token>
PARRYGG_API_KEY=<parry.gg API key>
```

The `.env` is gitignored. You need to recreate it on a new machine. Get a start.gg API key at start.gg → Admin → Developer and a Parry.gg API key from the Developer section of your Parry.gg profile.

---

## Creating an Admin User

The DB has no default admin. After first run (which creates the DB via `db.create_all()`):

```python
# from project root
venv/bin/python - <<'EOF'
from api import create_app
from api.extensions import db
from api.models import AdminUser
app = create_app()
with app.app_context():
    u = AdminUser(username='admin')
    u.set_password('yourpassword')
    db.session.add(u)
    db.session.commit()
    print('done')
EOF
```

---

## Points System (SPR = Seed Performance Rating)

SPR counts the difference between the double-elimination finish tier projected
by a player's seed and their actual finish tier. The ordered tiers are 1st,
2nd, 3rd, 4th, 5th–6th, 7th–8th, 9th–12th, 13th–16th, and so on. For example,
a 10th seed is projected to finish 9th; placing 4th passes through 7th, 5th,
and 4th for SPR +3. Tournament entrant count validates and clamps anomalous
seed or placement values.

| SPR | Points |
|---|---|
| ≤ −1 | 1 |
| 0 | 2 |
| +1 | 3 |
| +2 | 5 |
| +3 | 10 |
| +4 | 15 |
| +5 | 20 |
| +6 | 25 (continues +5/step) |

**Captains are coaches — their entries are synced but contribute 0 points to team totals and are excluded from the player leaderboard.**

---

## Data Model (SQLite via SQLAlchemy)

```
Season       id, name, start_date, end_date, status, sync_from, sync_to
Player       id, display_name, startgg_slug, parrygg_id  (global — reused across seasons)
Team         id, name, season_id, captain_id → Player
team_roster  team_id, player_id  (join table)
Tournament   id, name, date, season_id, startgg_id, startgg_slug,
             startgg_event_id, parrygg_id, parrygg_slug, parrygg_event_id,
             total_entrants, synced_at
TournamentEntry  id, player_id, tournament_id, seed, placement, spr, points
AdminUser    id, username, password_hash
```

`db.create_all()` is used for fresh databases. Existing databases can add the nullable Parry.gg columns safely with `flask --app api migrate-parrygg`; no database reset is required.

---

## File Structure

```
api/
  __init__.py          Flask factory, WAL mode setup, CLI commands
  extensions.py        db, limiter singletons
  decorators.py        require_admin() — used by admin + sync blueprints
  utils.py             calculate_spr(), spr_to_points()
  sync.py              sync_season(), sync_player() — per-player commit
  startgg.py           GraphQL client, two-phase query (events then entrants)
  parrygg.py           JSON-over-HTTP client (placements, events, tournaments)
  models/
    season.py
    player.py
    team.py
    tournament.py
    entry.py           TournamentEntry.compute() — calls calculate_spr + spr_to_points
    admin_user.py
  routes/
    public.py          /api/seasons, /api/seasons/:id/standings, /api/seasons/:id/players, etc.
    admin.py           /api/admin/* — CRUD, requires admin session
    sync.py            /api/admin/sync/* — run sync, per-player sync, status
    auth.py            /api/auth/login, logout, me — rate limited

client/src/
  App.jsx              Root — fetches seasons/standings/players, manages isAdmin
  index.css            CSS variables (Discord dark theme)
  components/
    Header.jsx / .module.css
    AdminLogin.jsx / .module.css
    Leaderboard.jsx / .module.css   (team standings + player leaderboard)
    TournamentAdmin.jsx             (admin-only: list/delete tournaments)
    AdminPanel.jsx / .module.css    (admin tab container, season picker)
    SeasonAdmin.jsx                 (create/edit seasons + sync window dates)
    PlayerAdmin.jsx                 (create teams, add/remove players, set captain, edit slugs)
    SyncAdmin.jsx                   (run sync, per-player re-sync, coverage view)
    AdminForm.module.css            (shared styles for all three admin forms)
    About.jsx
```

---

## Tournament Sync — How It Works

Player-centric sync: each player can have a `startgg_slug`, a `parrygg_id`, or both. Configured providers are queried independently so a temporary error from one provider does not discard valid results from the other.

**Two-phase query to avoid GraphQL complexity limits:**
1. `GET_USER_EVENTS_QUERY` — get list of events the user attended (Melee only, no entrant data). Also fetches `user.player.id`.
2. `GET_EVENT_ENTRANTS_QUERY` — for each event in the sync window, paginate through entrants (64/page) and find the matching one by player ID.

Filters applied in Python (not GQL): singles only (`type == 1`), date window.

Parry.gg uses its documented JSON-over-HTTP proxy. `GetUserPlacements` is paginated, then `GetEvent` filters to Melee singles and `GetTournament` supplies the tournament name, date, and public slug. Exact same-name/same-date copies from both providers are merged so they cannot award duplicate points.

Rate limiting: 0.6s sleep between every API call, exponential backoff (4s/8s/16s) on 429s.

SQLite WAL mode is enabled so status-poll reads don't block the long sync write. Each player is committed individually so a failure on one doesn't roll back others.

---

## Known Quirks / Past Bugs Fixed

- **start.gg filter fields that DON'T exist:** `type`, `afterDate`, `beforeDate` on `UserEventsPaginationFilter`; `isCurrentUser` and `playerIds` on `EventEntrantPageQueryFilter`. None of these work — filter in Python instead.
- **SQLite locked during sync:** Fixed with WAL mode (`PRAGMA journal_mode=WAL`), `busy_timeout=10000`, and per-player commits.
- **`display: flex` on `<td>`** breaks table column alignment — `.actions` td must use `text-align: right` only.
- **DB schema changes:** `db.create_all()` does not migrate existing tables. Use the explicit schema command documented above; do not delete a populated database.
- **Port 5000 conflict:** `fuser -k 5000/tcp` to kill stale Flask process.
- **Vite proxy:** must point to `127.0.0.1:5000` not `localhost:5000`.

---

## UI Notes

- Dark theme using Discord color palette (CSS variables in `index.css`)
- Admin tab in header only visible when logged in; logging out redirects to Leaderboard
- Tables are horizontally scrollable on mobile; some columns hidden at ≤560px breakpoint
- Captains shown in team roster UI but excluded from leaderboard query and point sums
- `points_per_event` field in player leaderboard is `total_points / events_attended`, rounded to 1 decimal (renamed from the misleading `avg_spr`)

---

## What's Not Built Yet

- Finale bracket seeding logic
- Public-facing About page content (placeholder exists)
- Discord link (placeholder URL in Header.jsx)
- Multi-season UI on the public leaderboard (currently auto-selects active/first season)
