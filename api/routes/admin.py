from datetime import date
from flask import Blueprint, jsonify, request
from api.extensions import db
from api.models import Season, Team, Player, Tournament, TournamentEntry
from api.decorators import require_admin
from sqlalchemy.exc import IntegrityError

admin = Blueprint("admin", __name__, url_prefix="/api/admin")
admin.before_request(require_admin)


# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------

@admin.route("/seasons", methods=["POST"])
def create_season():
    data = request.get_json()
    season = Season(
        name=data["name"],
        start_date=_parse_date(data.get("start_date")),
        end_date=_parse_date(data.get("end_date")),
        status=data.get("status", "draft"),
    )
    db.session.add(season)
    db.session.commit()
    return jsonify(season.to_dict()), 201


@admin.route("/seasons/<int:season_id>", methods=["PUT"])
def update_season(season_id):
    season = db.get_or_404(Season, season_id)
    data = request.get_json()
    if "name" in data:
        season.name = data["name"]
    if "start_date" in data:
        season.start_date = _parse_date(data["start_date"])
    if "end_date" in data:
        season.end_date = _parse_date(data["end_date"])
    if "status" in data:
        season.status = data["status"]
    if "sync_from" in data:
        season.sync_from = _parse_date(data["sync_from"])
    if "sync_to" in data:
        season.sync_to = _parse_date(data["sync_to"])
    db.session.commit()
    return jsonify(season.to_dict())


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

@admin.route("/players", methods=["POST"])
def create_player():
    data = request.get_json()
    player = Player(
        display_name=data["display_name"],
        startgg_id=data.get("startgg_id"),
        startgg_slug=data.get("startgg_slug"),
    )
    db.session.add(player)
    db.session.commit()
    return jsonify(player.to_dict()), 201


@admin.route("/players/<int:player_id>", methods=["PUT"])
def update_player(player_id):
    player = db.get_or_404(Player, player_id)
    data = request.get_json()
    if "display_name" in data:
        player.display_name = data["display_name"]
    if "startgg_id" in data:
        player.startgg_id = data["startgg_id"]
    if "startgg_slug" in data:
        player.startgg_slug = data["startgg_slug"]
    db.session.commit()
    return jsonify(player.to_dict())


@admin.route("/players/<int:player_id>", methods=["DELETE"])
def delete_player(player_id):
    player = db.get_or_404(Player, player_id)
    db.session.delete(player)
    db.session.commit()
    return jsonify({"deleted": player_id})


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@admin.route("/teams", methods=["POST"])
def create_team():
    data = request.get_json()
    team = Team(
        name=data["name"],
        season_id=data["season_id"],
        captain_id=data.get("captain_id"),
    )
    db.session.add(team)
    db.session.commit()
    return jsonify(team.to_dict(include_roster=True)), 201


@admin.route("/teams/<int:team_id>", methods=["PUT"])
def update_team(team_id):
    team = db.get_or_404(Team, team_id)
    data = request.get_json()
    if "name" in data:
        team.name = data["name"]
    if "captain_id" in data:
        team.captain_id = data["captain_id"]
    db.session.commit()
    return jsonify(team.to_dict(include_roster=True))


@admin.route("/teams/<int:team_id>", methods=["DELETE"])
def delete_team(team_id):
    team = db.get_or_404(Team, team_id)
    db.session.delete(team)
    db.session.commit()
    return jsonify({"deleted": team_id})


@admin.route("/teams/<int:team_id>/roster", methods=["POST"])
def add_to_roster(team_id):
    team = db.get_or_404(Team, team_id)
    data = request.get_json()
    player = db.get_or_404(Player, data["player_id"])
    # A player on two rosters in the same season would double-count points
    other = _team_in_season_with_player(team.season_id, player, exclude_team_id=team.id)
    if other:
        return jsonify({
            "error": f"{player.display_name} is already on '{other.name}' in this season"
        }), 409
    if player not in team.roster:
        team.roster.append(player)
        db.session.commit()
    return jsonify(team.to_dict(include_roster=True))


def _team_in_season_with_player(season_id, player, exclude_team_id=None):
    """Return the team in this season whose roster contains player, if any."""
    for t in Team.query.filter_by(season_id=season_id).all():
        if t.id == exclude_team_id:
            continue
        if player in t.roster:
            return t
    return None


@admin.route("/teams/<int:team_id>/roster/<int:player_id>", methods=["DELETE"])
def remove_from_roster(team_id, player_id):
    team = db.get_or_404(Team, team_id)
    player = db.get_or_404(Player, player_id)
    if player in team.roster:
        team.roster.remove(player)
        db.session.commit()
    return jsonify(team.to_dict(include_roster=True))


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------

@admin.route("/tournaments", methods=["POST"])
def create_tournament():
    data = request.get_json()
    tournament = Tournament(
        name=data["name"],
        season_id=data["season_id"],
        date=_parse_date(data.get("date")),
        startgg_id=data.get("startgg_id"),
        startgg_slug=data.get("startgg_slug"),
        total_entrants=data.get("total_entrants"),
    )
    db.session.add(tournament)
    db.session.commit()
    return jsonify(tournament.to_dict()), 201


@admin.route("/tournaments/<int:tournament_id>", methods=["PUT"])
def update_tournament(tournament_id):
    tournament = db.get_or_404(Tournament, tournament_id)
    data = request.get_json()
    if "name" in data:
        tournament.name = data["name"]
    if "date" in data:
        tournament.date = _parse_date(data["date"])
    if "startgg_id" in data:
        tournament.startgg_id = data["startgg_id"]
    if "startgg_slug" in data:
        tournament.startgg_slug = data["startgg_slug"]
    if "total_entrants" in data and data["total_entrants"] != tournament.total_entrants:
        tournament.total_entrants = data["total_entrants"]
        # SPR/points are derived from total_entrants — recompute all entries
        try:
            for entry in tournament.entries:
                entry.compute()
        except ValueError as exc:
            db.session.rollback()
            return jsonify({"error": str(exc)}), 400
    db.session.commit()
    return jsonify(tournament.to_dict())


@admin.route("/tournaments/<int:tournament_id>", methods=["DELETE"])
def delete_tournament(tournament_id):
    tournament = db.get_or_404(Tournament, tournament_id)
    tournament.removed = True
    db.session.commit()
    return jsonify({"removed": tournament_id})


@admin.route("/tournaments/<int:tournament_id>/restore", methods=["POST"])
def restore_tournament(tournament_id):
    tournament = db.get_or_404(Tournament, tournament_id)
    tournament.removed = False
    db.session.commit()
    return jsonify(tournament.to_dict())


@admin.route("/seasons/<int:season_id>/removed-tournaments", methods=["GET"])
def removed_tournaments(season_id):
    db.get_or_404(Season, season_id)
    tournaments = (
        Tournament.query
        .filter_by(season_id=season_id, removed=True)
        .order_by(Tournament.date.desc())
        .all()
    )
    return jsonify([{**t.to_dict(), "entry_count": len(t.entries)} for t in tournaments])


# ---------------------------------------------------------------------------
# Tournament Entries
# ---------------------------------------------------------------------------

@admin.route("/tournaments/<int:tournament_id>/entries", methods=["POST"])
def create_entry(tournament_id):
    db.get_or_404(Tournament, tournament_id)
    data = request.get_json()
    entry = TournamentEntry(
        player_id=data["player_id"],
        tournament_id=tournament_id,
        seed=data.get("seed"),
        placement=data.get("placement"),
    )
    db.session.add(entry)
    # Flush first so entry.tournament resolves — compute() needs total_entrants
    db.session.flush()
    try:
        entry.compute()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    db.session.commit()
    return jsonify(entry.to_dict()), 201


@admin.route("/entries/<int:entry_id>", methods=["PUT"])
def update_entry(entry_id):
    entry = db.get_or_404(TournamentEntry, entry_id)
    data = request.get_json()
    if "seed" in data:
        entry.seed = data["seed"]
    if "placement" in data:
        entry.placement = data["placement"]
    try:
        entry.compute()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    db.session.commit()
    return jsonify(entry.to_dict())


@admin.route("/entries/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id):
    entry = db.get_or_404(TournamentEntry, entry_id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({"deleted": entry_id})


# ---------------------------------------------------------------------------
# Season import
# ---------------------------------------------------------------------------

@admin.route("/seasons/<int:season_id>/import", methods=["POST"])
def import_season(season_id):
    season = db.get_or_404(Season, season_id)
    data = request.get_json()
    text = (data.get("text") or "").strip()
    overwrite_confirm = (data.get("overwrite_confirm") or "").strip()

    if season.status in ("active", "completed"):
        required = f"Confirm overwrite {season.name}"
        if overwrite_confirm != required:
            return jsonify({"error": "confirmation_required", "required": required}), 409

    if not text:
        return jsonify({"error": "No text provided"}), 400

    blocks = [b.strip() for b in text.split("---") if b.strip()]
    results = {"teams_imported": 0, "players_created": 0, "players_found": 0, "errors": []}

    for block in blocks:
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            results["errors"].append(f"Skipped block — too short: {repr(block[:40])}")
            continue

        team_name = lines[0]

        captain_parts = [p.strip() for p in lines[1].split(",", 1)]
        if len(captain_parts) != 2:
            results["errors"].append(f"Bad captain line in '{team_name}': {lines[1]}")
            continue

        captain_name, captain_slug = captain_parts

        players_data = []
        parse_error = False
        for line in lines[2:]:
            parts = [p.strip() for p in line.split(",", 1)]
            if len(parts) != 2:
                results["errors"].append(f"Bad player line in '{team_name}': {line}")
                parse_error = True
                break
            players_data.append((parts[0], parts[1]))

        if parse_error:
            continue

        captain = _find_or_create_player(captain_name, captain_slug, results)

        team = Team.query.filter_by(season_id=season_id, name=team_name).first()
        if team is None:
            team = Team(name=team_name, season_id=season_id)
            db.session.add(team)
            db.session.flush()

        team.roster.clear()
        team.captain_id = captain.id
        team.roster.append(captain)

        for pname, pslug in players_data:
            player = _find_or_create_player(pname, pslug, results)
            other = _team_in_season_with_player(season_id, player, exclude_team_id=team.id)
            if other:
                results["errors"].append(
                    f"'{player.display_name}' already on '{other.name}' — skipped for '{team_name}'"
                )
                continue
            if player not in team.roster:
                team.roster.append(player)

        results["teams_imported"] += 1

    db.session.commit()
    return jsonify(results), 200


def _find_or_create_player(name, slug, results):
    player = Player.query.filter_by(startgg_slug=slug).first() if slug else None
    if player is None:
        player = Player.query.filter_by(display_name=name).first()
    if player is None:
        player = Player(display_name=name, startgg_slug=slug or None)
        db.session.add(player)
        db.session.flush()
        results["players_created"] += 1
    else:
        results["players_found"] += 1
        if slug and player.startgg_slug != slug:
            player.startgg_slug = slug
    return player


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)
