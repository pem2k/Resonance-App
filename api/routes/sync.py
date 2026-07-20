import threading
from datetime import date, datetime, timezone

from flask import Blueprint, jsonify, current_app
from api.extensions import db
from api.models import Season, Player
from api import sync as sync_service
from api.decorators import require_admin

sync_bp = Blueprint("sync", __name__, url_prefix="/api/admin/sync")
sync_bp.before_request(require_admin)

# In-memory job state, one slot per season. Sync runs in a background thread
# because a full-season sync takes minutes — far beyond Heroku's 30s request
# timeout. Requires a single web process (see Procfile: --workers 1).
_jobs: dict[int, dict] = {}
_jobs_lock = threading.Lock()


def _start_job(season_id: int, kind: str, target, *args) -> bool:
    """Start a background sync job for a season. Returns False if one is already running."""
    with _jobs_lock:
        job = _jobs.get(season_id)
        if job and job["running"]:
            return False
        _jobs[season_id] = {
            "running": True,
            "kind": kind,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "result": None,
            "error": None,
        }

    app = current_app._get_current_object()

    def run():
        with app.app_context():
            try:
                result = target(*args)
                _jobs[season_id].update(result=result)
            except Exception as exc:
                db.session.rollback()
                _jobs[season_id].update(error=str(exc))
            finally:
                db.session.remove()
                _jobs[season_id].update(
                    running=False,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )

    threading.Thread(target=run, daemon=True, name=f"sync-season-{season_id}").start()
    return True


def _job_payload(season_id: int) -> dict:
    job = _jobs.get(season_id)
    return job if job else {"running": False, "kind": None, "result": None, "error": None}


@sync_bp.route("/season/<int:season_id>", methods=["POST"])
def sync_season(season_id):
    """
    Start a background sync of all rostered players in a season who have a
    startgg_slug. Returns 202 immediately; poll GET /season/<id>/job for progress.
    """
    season = db.get_or_404(Season, season_id)
    if not season.sync_from or not season.sync_to:
        return jsonify({"error": "Season sync_from and sync_to must be set."}), 400

    def task(sid):
        s = db.session.get(Season, sid)
        return sync_service.sync_season(s)

    if not _start_job(season_id, "season", task, season_id):
        return jsonify({"error": "A sync is already running for this season."}), 409
    return jsonify({"started": True}), 202


@sync_bp.route("/season/<int:season_id>/player/<int:player_id>", methods=["POST"])
def sync_player(season_id, player_id):
    """Start a background re-sync of a single player within the season window."""
    season = db.get_or_404(Season, season_id)
    player = db.get_or_404(Player, player_id)
    if not season.sync_from or not season.sync_to:
        return jsonify({"error": "Season sync_from and sync_to must be set."}), 400
    rostered_ids = {
        rostered.id for team in season.teams for rostered in team.roster
    }
    if player.id not in rostered_ids:
        return jsonify({"error": "Player is not rostered in this season."}), 400
    if not player.startgg_slug or not player.startgg_slug.strip():
        return jsonify({"error": "Player must have a start.gg slug before syncing."}), 400

    def task(sid, pid):
        s = db.session.get(Season, sid)
        p = db.session.get(Player, pid)
        return sync_service.sync_player(p, s)

    if not _start_job(season_id, "player", task, season_id, player_id):
        return jsonify({"error": "A sync is already running for this season."}), 409
    return jsonify({"started": True}), 202


@sync_bp.route("/season/<int:season_id>/job", methods=["GET"])
def sync_job(season_id):
    """Poll the state of the season's background sync job."""
    db.get_or_404(Season, season_id)
    return jsonify(_job_payload(season_id))


@sync_bp.route("/season/<int:season_id>/status", methods=["GET"])
def sync_status(season_id):
    """
    Show sync window and per-player sync coverage (how many entries each has).
    """
    season = db.get_or_404(Season, season_id)

    players = []
    seen_player_ids = set()
    for team in season.teams:
        for player in team.roster:
            if player.id in seen_player_ids:
                continue
            seen_player_ids.add(player.id)
            entry_count = sum(
                1 for e in player.entries
                if (
                    e.tournament
                    and e.tournament.season_id == season_id
                    and not e.tournament.removed
                )
            )
            players.append({
                "id": player.id,
                "display_name": player.display_name,
                "startgg_slug": player.startgg_slug,
                "has_slug": bool(player.startgg_slug and player.startgg_slug.strip()),
                "entries_this_season": entry_count,
            })

    return jsonify({
        "sync_from": season.sync_from.isoformat() if season.sync_from else None,
        "sync_to": season.sync_to.isoformat() if season.sync_to else None,
        "players": players,
        "tournaments": [
            {
                "id": t.id,
                "name": t.name,
                "date": t.date.isoformat() if t.date else None,
                "total_entrants": t.total_entrants,
                "entry_count": len(t.entries),
                "synced_at": t.to_dict()["synced_at"],
            }
            for t in sorted(
                (t for t in season.tournaments if not t.removed),
                key=lambda t: t.date or date.min,
            )
        ],
    })
