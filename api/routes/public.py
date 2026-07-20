from flask import Blueprint, jsonify
from api.extensions import db
from api.models import Season, Team, Player, Tournament, TournamentEntry

public = Blueprint("public", __name__, url_prefix="/api")


def _scoring_player_ids(team):
    if team.captain_id is None:
        return [p.id for p in team.roster]
    return [p.id for p in team.roster if p.id != team.captain_id]


# --- Seasons ---

@public.route("/seasons", methods=["GET"])
def list_seasons():
    seasons = Season.query.order_by(Season.id.desc()).all()
    return jsonify([s.to_dict() for s in seasons])


@public.route("/seasons/<int:season_id>", methods=["GET"])
def get_season(season_id):
    season = db.get_or_404(Season, season_id)
    return jsonify(season.to_dict())


# --- Standings (teams ranked by total points in a season) ---

@public.route("/seasons/<int:season_id>/standings", methods=["GET"])
def season_standings(season_id):
    db.get_or_404(Season, season_id)

    teams = Team.query.filter_by(season_id=season_id).all()
    results = []
    for team in teams:
        # No captain assigned means every roster player's points count.
        player_ids = _scoring_player_ids(team)
        total = 0
        if player_ids:
            total = (
                db.session.query(db.func.sum(TournamentEntry.points))
                .join(Tournament, TournamentEntry.tournament_id == Tournament.id)
                .filter(
                    TournamentEntry.player_id.in_(player_ids),
                    Tournament.season_id == season_id,
                    Tournament.removed == False,
                )
                .scalar() or 0
            )
        results.append({**team.to_dict(include_roster=True), "total_points": total})

    results.sort(key=lambda t: t["total_points"], reverse=True)
    return jsonify(results)


# --- Player leaderboard for a season ---

@public.route("/seasons/<int:season_id>/players", methods=["GET"])
def season_players(season_id):
    season = db.get_or_404(Season, season_id)

    # Membership comes from current rosters, while totals come from active
    # tournament entries. This keeps the player and team tables consistent and
    # retains rostered players who have not attended an event yet.
    player_team = {}
    captain_ids = {team.captain_id for team in season.teams if team.captain_id}
    eligible_players = {}
    for team in season.teams:
        for player in team.roster:
            player_team[player.id] = {"id": team.id, "name": team.name}
            if player.id not in captain_ids:
                eligible_players[player.id] = player

    totals = {}
    if eligible_players:
        aggregate_rows = (
            db.session.query(
                TournamentEntry.player_id,
                db.func.sum(TournamentEntry.points).label("total_points"),
                db.func.count(TournamentEntry.id).label("events_attended"),
            )
            .join(Tournament, TournamentEntry.tournament_id == Tournament.id)
            .filter(
                TournamentEntry.player_id.in_(eligible_players),
                Tournament.season_id == season_id,
                Tournament.removed.is_(False),
            )
            .group_by(TournamentEntry.player_id)
            .all()
        )
        totals = {
            player_id: (total_points or 0, events_attended or 0)
            for player_id, total_points, events_attended in aggregate_rows
        }

    rows = []
    for player in eligible_players.values():
        total_points, events_attended = totals.get(player.id, (0, 0))
        rows.append({
            **player.to_dict(),
            "total_points": total_points,
            "events_attended": events_attended,
            "points_per_event": round(total_points / events_attended, 1) if events_attended else None,
            "team": player_team[player.id],
        })

    rows.sort(key=lambda row: (-row["total_points"], row["display_name"].casefold(), row["id"]))
    return jsonify(rows)


# --- Tournaments in a season ---

@public.route("/seasons/<int:season_id>/tournaments", methods=["GET"])
def season_tournaments(season_id):
    db.get_or_404(Season, season_id)
    tournaments = Tournament.query.filter_by(season_id=season_id, removed=False).order_by(Tournament.date).all()
    return jsonify([{**t.to_dict(), "entry_count": len(t.entries)} for t in tournaments])


# --- Team detail ---

@public.route("/teams/<int:team_id>", methods=["GET"])
def get_team(team_id):
    team = db.get_or_404(Team, team_id)
    # No captain assigned means every roster player's points count.
    player_ids = _scoring_player_ids(team)
    total = 0
    if player_ids:
        total = (
            db.session.query(db.func.sum(TournamentEntry.points))
            .join(Tournament, TournamentEntry.tournament_id == Tournament.id)
            .filter(
                TournamentEntry.player_id.in_(player_ids),
                Tournament.season_id == team.season_id,
                Tournament.removed == False,
            )
            .scalar() or 0
        )
    return jsonify({**team.to_dict(include_roster=True), "total_points": total})


# --- Player detail ---

@public.route("/players/<int:player_id>", methods=["GET"])
def get_player(player_id):
    player = db.get_or_404(Player, player_id)
    entries = (
        TournamentEntry.query
        .filter_by(player_id=player_id)
        .join(Tournament)
        .filter(Tournament.removed == False)
        .order_by(Tournament.date.desc())
        .all()
    )
    return jsonify({
        **player.to_dict(),
        "entries": [e.to_dict() for e in entries],
        "total_points": sum(e.points for e in entries),
    })


# --- Tournament detail ---

@public.route("/tournaments/<int:tournament_id>", methods=["GET"])
def get_tournament(tournament_id):
    tournament = db.get_or_404(Tournament, tournament_id)
    entries = (
        TournamentEntry.query
        .filter_by(tournament_id=tournament_id)
        .order_by(TournamentEntry.placement)
        .all()
    )
    return jsonify({**tournament.to_dict(), "entries": [e.to_dict() for e in entries]})
