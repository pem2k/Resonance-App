from flask import Blueprint, jsonify
from api.extensions import db
from api.models import Season, Player
from api import sync as sync_service
from api.decorators import require_admin

sync_bp = Blueprint("sync", __name__, url_prefix="/api/admin/sync")
sync_bp.before_request(require_admin)


@sync_bp.route("/season/<int:season_id>", methods=["POST"])
def sync_season(season_id):
    """
    Sync all rostered players in a season who have a startgg_slug.
    Tournaments are discovered automatically from player event history.
    Requires season.sync_from and season.sync_to to be set.
    """
    season = db.get_or_404(Season, season_id)
    result = sync_service.sync_season(season)
    return jsonify(result)


@sync_bp.route("/season/<int:season_id>/player/<int:player_id>", methods=["POST"])
def sync_player(season_id, player_id):
    """Force re-sync a single player within the season window."""
    season = db.get_or_404(Season, season_id)
    player = db.get_or_404(Player, player_id)
    result = sync_service.sync_player(player, season)
    return jsonify(result)


@sync_bp.route("/season/<int:season_id>/status", methods=["GET"])
def sync_status(season_id):
    """
    Show sync window and per-player sync coverage (how many entries each has).
    """
    season = db.get_or_404(Season, season_id)

    players = []
    for team in season.teams:
        for player in team.roster:
            entry_count = sum(
                1 for e in player.entries
                if e.tournament and e.tournament.season_id == season_id
            )
            players.append({
                "id": player.id,
                "display_name": player.display_name,
                "startgg_slug": player.startgg_slug,
                "has_slug": player.startgg_slug is not None,
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
                "synced_at": t.synced_at.isoformat() if t.synced_at else None,
            }
            for t in sorted(season.tournaments, key=lambda t: t.date or "")
        ],
    })
