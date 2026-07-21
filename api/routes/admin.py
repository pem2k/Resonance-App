from datetime import date
import re
from urllib.parse import urlparse
from uuid import UUID
from flask import Blueprint, jsonify, request
from api.extensions import db
from api.models import Season, Team, Player, Tournament, TournamentEntry
from api.decorators import require_admin
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_

admin = Blueprint("admin", __name__, url_prefix="/api/admin")
admin.before_request(require_admin)

_SEASON_STATUSES = {"draft", "active", "completed"}


class AdminAPIError(Exception):
    def __init__(self, message, status=400, **details):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


@admin.errorhandler(AdminAPIError)
def handle_admin_api_error(error):
    db.session.rollback()
    return jsonify({"error": error.message, **error.details}), error.status


@admin.errorhandler(IntegrityError)
def handle_integrity_error(_error):
    db.session.rollback()
    return jsonify({"error": "The request conflicts with existing data."}), 409


def _json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AdminAPIError("Request body must be a JSON object.")
    return data


def _required_string(data, key, label=None):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AdminAPIError(f"{label or key.replace('_', ' ').title()} is required.")
    return value.strip()


def _optional_string(data, key):
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise AdminAPIError(f"{key.replace('_', ' ').title()} must be a string or null.")
    return value.strip() or None


def _parrygg_id(data, key="parrygg_id"):
    value = _optional_string(data, key)
    if value is None:
        return None

    candidate = value
    if "://" in value:
        parsed = urlparse(value)
        parts = [part for part in parsed.path.split("/") if part]
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"parry.gg", "www.parry.gg"}
            or len(parts) != 2
            or parts[0] != "profile"
        ):
            raise AdminAPIError("Parry.gg profile must be a profile URL or UUID.")
        candidate = parts[1]

    try:
        return str(UUID(candidate))
    except (ValueError, AttributeError) as exc:
        raise AdminAPIError("Parry.gg profile must be a profile URL or UUID.") from exc


def _required_id(data, key):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdminAPIError(f"{key.replace('_', ' ').title()} must be an integer.")
    return value


def _positive_integer(value, label, *, allow_none=True):
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AdminAPIError(f"{label} must be a positive integer.")
    return value


def _normalized_name_query(model, column, value):
    return model.query.filter(func.lower(func.trim(column)) == value.casefold())


def _validate_season_dates(season):
    if season.start_date and season.end_date and season.start_date > season.end_date:
        raise AdminAPIError("Start date must be on or before end date.")
    if season.sync_from and season.sync_to and season.sync_from > season.sync_to:
        raise AdminAPIError("Sync from must be on or before sync to.")


def _season_status(value):
    if not isinstance(value, str) or value not in _SEASON_STATUSES:
        raise AdminAPIError("Status must be draft, active, or completed.")
    return value


# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------

@admin.route("/seasons", methods=["POST"])
def create_season():
    data = _json_body()
    name = _required_string(data, "name")
    status = _season_status(data.get("status", "draft"))
    season = Season(
        name=name,
        start_date=_parse_date(data.get("start_date"), "start_date"),
        end_date=_parse_date(data.get("end_date"), "end_date"),
        sync_from=_parse_date(data.get("sync_from"), "sync_from"),
        sync_to=_parse_date(data.get("sync_to"), "sync_to"),
        status=status,
    )
    _validate_season_dates(season)
    db.session.add(season)
    db.session.commit()
    return jsonify(season.to_dict()), 201


@admin.route("/seasons/<int:season_id>", methods=["PUT"])
def update_season(season_id):
    season = db.get_or_404(Season, season_id)
    data = _json_body()
    if "name" in data:
        season.name = _required_string(data, "name")
    if "start_date" in data:
        season.start_date = _parse_date(data["start_date"], "start_date")
    if "end_date" in data:
        season.end_date = _parse_date(data["end_date"], "end_date")
    if "status" in data:
        season.status = _season_status(data["status"])
    if "sync_from" in data:
        season.sync_from = _parse_date(data["sync_from"], "sync_from")
    if "sync_to" in data:
        season.sync_to = _parse_date(data["sync_to"], "sync_to")
    _validate_season_dates(season)
    db.session.commit()
    return jsonify(season.to_dict())


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------

@admin.route("/players", methods=["GET"])
def list_players():
    players = Player.query.order_by(func.lower(Player.display_name), Player.id).all()
    return jsonify([player.to_dict() for player in players])


@admin.route("/players", methods=["POST"])
def create_player():
    data = _json_body()
    display_name = _required_string(data, "display_name", "Display name")
    startgg_id = _optional_string(data, "startgg_id")
    startgg_slug = _optional_string(data, "startgg_slug")
    parrygg_id = _parrygg_id(data)
    existing = _player_identity_conflict(
        display_name=display_name,
        startgg_id=startgg_id,
        startgg_slug=startgg_slug,
        parrygg_id=parrygg_id,
        check_name=not startgg_id and not startgg_slug and not parrygg_id,
    )
    if existing:
        raise AdminAPIError(
            "A player with that identity already exists.",
            409,
            existing_player=existing.to_dict(),
        )
    player = Player(
        display_name=display_name,
        startgg_id=startgg_id,
        startgg_slug=startgg_slug,
        parrygg_id=parrygg_id,
    )
    db.session.add(player)
    db.session.commit()
    return jsonify(player.to_dict()), 201


@admin.route("/players/<int:player_id>", methods=["PUT"])
def update_player(player_id):
    player = db.get_or_404(Player, player_id)
    data = _json_body()
    display_name = player.display_name
    startgg_id = player.startgg_id
    startgg_slug = player.startgg_slug
    parrygg_id = player.parrygg_id
    if "display_name" in data:
        display_name = _required_string(data, "display_name", "Display name")
    if "startgg_id" in data:
        startgg_id = _optional_string(data, "startgg_id")
    if "startgg_slug" in data:
        startgg_slug = _optional_string(data, "startgg_slug")
    if "parrygg_id" in data:
        parrygg_id = _parrygg_id(data)
    id_changed = "startgg_id" in data and startgg_id != player.startgg_id
    old_slug = player.startgg_slug.casefold() if player.startgg_slug else None
    new_slug = startgg_slug.casefold() if startgg_slug else None
    slug_changed = "startgg_slug" in data and new_slug != old_slug
    parry_id_changed = "parrygg_id" in data and parrygg_id != player.parrygg_id
    existing = _player_identity_conflict(
        startgg_id=startgg_id if id_changed else None,
        startgg_slug=startgg_slug if slug_changed else None,
        parrygg_id=parrygg_id if parry_id_changed else None,
        exclude_player_id=player.id,
    )
    if existing:
        raise AdminAPIError(
            "A player with that tournament-platform identity already exists.",
            409,
            existing_player=existing.to_dict(),
        )
    player.display_name = display_name
    player.startgg_id = startgg_id
    player.startgg_slug = startgg_slug
    player.parrygg_id = parrygg_id
    db.session.commit()
    return jsonify(player.to_dict())


@admin.route("/players/<int:player_id>", methods=["DELETE"])
def delete_player(player_id):
    player = db.get_or_404(Player, player_id)
    roster_teams = list(player.teams)
    captain_teams = Team.query.filter_by(captain_id=player.id).all()
    if roster_teams or captain_teams or player.entries:
        raise AdminAPIError(
            "Player cannot be deleted while referenced by teams or tournament entries.",
            409,
            dependencies={
                "roster_teams": [team.name for team in roster_teams],
                "captain_teams": [team.name for team in captain_teams],
                "tournament_entries": len(player.entries),
            },
        )
    db.session.delete(player)
    db.session.commit()
    return jsonify({"deleted": player_id})


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

@admin.route("/teams", methods=["POST"])
def create_team():
    data = _json_body()
    name = _required_string(data, "name", "Team name")
    season_id = _required_id(data, "season_id")
    db.get_or_404(Season, season_id)
    _ensure_unique_team_name(season_id, name)
    captain_id = data.get("captain_id")
    if captain_id is not None:
        if isinstance(captain_id, bool) or not isinstance(captain_id, int):
            raise AdminAPIError("Captain id must be an integer or null.")
        db.get_or_404(Player, captain_id)
        raise AdminAPIError("Add the captain to the team roster before assigning them.")
    team = Team(
        name=name,
        season_id=season_id,
    )
    db.session.add(team)
    db.session.commit()
    return jsonify(team.to_dict(include_roster=True)), 201


@admin.route("/teams/<int:team_id>", methods=["PUT"])
def update_team(team_id):
    team = db.get_or_404(Team, team_id)
    data = _json_body()
    if "name" in data:
        name = _required_string(data, "name", "Team name")
        _ensure_unique_team_name(team.season_id, name, exclude_team_id=team.id)
        team.name = name
    if "captain_id" in data:
        captain_id = data["captain_id"]
        if captain_id is not None:
            if isinstance(captain_id, bool) or not isinstance(captain_id, int):
                raise AdminAPIError("Captain id must be an integer or null.")
            db.get_or_404(Player, captain_id)
        if captain_id is not None and all(player.id != captain_id for player in team.roster):
            raise AdminAPIError("Captain must be on the team roster.")
        team.captain_id = captain_id
    db.session.commit()
    return jsonify(team.to_dict(include_roster=True))


@admin.route("/teams/<int:team_id>", methods=["DELETE"])
def delete_team(team_id):
    team = db.get_or_404(Team, team_id)
    team.captain_id = None
    team.roster.clear()
    db.session.flush()
    db.session.delete(team)
    db.session.commit()
    return jsonify({"deleted": team_id})


@admin.route("/teams/<int:team_id>/roster", methods=["POST"])
def add_to_roster(team_id):
    team = db.get_or_404(Team, team_id)
    data = _json_body()
    player = db.get_or_404(Player, _required_id(data, "player_id"))
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
        if player.id == team.captain_id:
            team.captain_id = None
        db.session.commit()
    return jsonify(team.to_dict(include_roster=True))


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------

@admin.route("/tournaments", methods=["POST"])
def create_tournament():
    data = _json_body()
    season_id = _required_id(data, "season_id")
    db.get_or_404(Season, season_id)
    tournament = Tournament(
        name=_required_string(data, "name", "Tournament name"),
        season_id=season_id,
        date=_parse_date(data.get("date"), "date"),
        startgg_id=_optional_string(data, "startgg_id"),
        startgg_slug=_optional_string(data, "startgg_slug"),
        total_entrants=_positive_integer(data.get("total_entrants"), "Total entrants"),
    )
    db.session.add(tournament)
    db.session.commit()
    return jsonify(tournament.to_dict()), 201


@admin.route("/tournaments/<int:tournament_id>", methods=["PUT"])
def update_tournament(tournament_id):
    tournament = db.get_or_404(Tournament, tournament_id)
    data = _json_body()
    if "name" in data:
        tournament.name = _required_string(data, "name", "Tournament name")
    if "date" in data:
        tournament.date = _parse_date(data["date"], "date")
    if "startgg_id" in data:
        tournament.startgg_id = _optional_string(data, "startgg_id")
    if "startgg_slug" in data:
        tournament.startgg_slug = _optional_string(data, "startgg_slug")
    if "total_entrants" in data:
        total_entrants = _positive_integer(
            data["total_entrants"], "Total entrants", allow_none=False
        )
        if total_entrants != tournament.total_entrants:
            tournament.total_entrants = total_entrants
            # total_entrants is SPR's validation/clamping boundary. Recompute
            # so anomalous seeds or placements stay current when it changes.
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
    identity_filters = []
    if tournament.startgg_id:
        identity_filters.append(Tournament.startgg_id == tournament.startgg_id)
    if tournament.parrygg_id:
        identity_filters.append(Tournament.parrygg_id == tournament.parrygg_id)
    if identity_filters:
        active_duplicate = Tournament.query.filter(
            Tournament.season_id == tournament.season_id,
            or_(*identity_filters),
            Tournament.removed.is_(False),
            Tournament.id != tournament.id,
        ).first()
        if active_duplicate:
            raise AdminAPIError(
                f"Cannot restore while '{active_duplicate.name}' is active for the same tournament-platform identity.",
                409,
            )
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
    tournament = db.get_or_404(Tournament, tournament_id)
    if tournament.removed:
        raise AdminAPIError("Cannot add entries to a removed tournament.", 409)
    data = _json_body()
    player = db.get_or_404(Player, _required_id(data, "player_id"))
    if not _player_is_rostered(player, tournament.season):
        raise AdminAPIError("Player is not rostered in this tournament's season.")
    duplicate = TournamentEntry.query.filter_by(
        player_id=player.id, tournament_id=tournament_id
    ).first()
    if duplicate:
        raise AdminAPIError("Player already has an entry for this tournament.", 409)
    entry = TournamentEntry(
        player_id=player.id,
        tournament_id=tournament_id,
        seed=_positive_integer(data.get("seed"), "Seed"),
        placement=_positive_integer(data.get("placement"), "Placement"),
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
    data = _json_body()
    if "seed" in data:
        entry.seed = _positive_integer(data["seed"], "Seed", allow_none=False)
    if "placement" in data:
        entry.placement = _positive_integer(data["placement"], "Placement", allow_none=False)
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
    data = _json_body()
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        raise AdminAPIError("No text provided.")
    text = text.strip()
    overwrite_confirm = data.get("overwrite_confirm") or ""
    if not isinstance(overwrite_confirm, str):
        raise AdminAPIError("Overwrite confirmation must be a string.")
    overwrite_confirm = overwrite_confirm.strip()

    if season.status in ("active", "completed"):
        required = f"Confirm import {season.name}"
        if overwrite_confirm != required:
            return jsonify({"error": "confirmation_required", "required": required}), 409

    plans, errors = _parse_import(text)
    if errors:
        return jsonify({"error": "Import validation failed.", "errors": errors}), 400

    owners = {}
    for plan in plans:
        people = ([plan["captain"]] if plan["captain"] else []) + plan["players"]
        seen_on_team = set()
        for person in people:
            key = _import_identity_key(*person)
            if key in seen_on_team:
                errors.append(f"'{person[0]}' appears more than once on '{plan['name']}'.")
                continue
            seen_on_team.add(key)
            prior_team = owners.get(key)
            if prior_team and prior_team != plan["name"]:
                errors.append(
                    f"'{person[0]}' is assigned to multiple imported teams: "
                    f"'{prior_team}' and '{plan['name']}'."
                )
            owners[key] = plan["name"]
    if errors:
        return jsonify({
            "error": "A player cannot be assigned to multiple imported teams.",
            "errors": errors,
        }), 409

    results = {"teams_imported": len(plans), "players_created": 0, "players_found": 0, "errors": []}

    # Resolve every target team first, then clear every target roster before
    # assigning players. This makes swaps independent of block order.
    for plan in plans:
        team = _normalized_name_query(Team, Team.name, plan["name"]).filter_by(
            season_id=season_id
        ).first()
        if team is None:
            team = Team(name=plan["name"], season_id=season_id)
            db.session.add(team)
        plan["team"] = team
    db.session.flush()

    for plan in plans:
        plan["team"].captain_id = None
        plan["team"].roster.clear()
    db.session.flush()

    for plan in plans:
        team = plan["team"]
        people = ([plan["captain"]] if plan["captain"] else []) + plan["players"]
        resolved = []
        for name, slug in people:
            player = _find_or_create_import_player(name, slug, results)
            other = _team_in_season_with_player(season_id, player, exclude_team_id=team.id)
            if other:
                raise AdminAPIError(
                    f"'{player.display_name}' is already on '{other.name}' in this season.",
                    409,
                )
            resolved.append(player)
            if player not in team.roster:
                team.roster.append(player)
        team.captain_id = resolved[0].id if plan["captain"] else None

    db.session.commit()
    return jsonify(results), 200


def _parse_import(text):
    blocks = [
        block.strip()
        for block in re.split(r"(?m)^\s*---\s*$", text)
        if block.strip()
    ]
    plans = []
    errors = []
    team_names = set()
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            errors.append(f"Skipped block — too short: {repr(block[:40])}")
            continue
        team_name = lines[0].strip()
        if not team_name:
            errors.append("Team name is required.")
            continue
        normalized_team = team_name.casefold()
        if normalized_team in team_names:
            errors.append(f"Duplicate team block: '{team_name}'.")
            continue
        team_names.add(normalized_team)

        captain = None
        if lines[1].casefold() != "no captain":
            captain = _parse_import_person(lines[1])
            if captain is None:
                errors.append(f"Bad captain line in '{team_name}': {lines[1]}")

        players = []
        for line in lines[2:]:
            player = _parse_import_person(line)
            if player is None:
                errors.append(f"Bad player line in '{team_name}': {line}")
            else:
                players.append(player)
        plans.append({"name": team_name, "captain": captain, "players": players})
    return plans, errors


def _parse_import_person(line):
    parts = [part.strip() for part in line.split(",", 1)]
    if len(parts) != 2 or not parts[0]:
        return None
    return parts[0], parts[1] or None


def _import_identity_key(name, slug):
    return ("slug", slug.casefold()) if slug else ("name", name.casefold())


def _find_or_create_import_player(name, slug, results):
    player = None
    if slug:
        slug_matches = Player.query.filter(
            func.lower(func.trim(Player.startgg_slug)) == slug.casefold()
        ).all()
        if len(slug_matches) > 1:
            raise AdminAPIError(
                f"start.gg slug '{slug}' matches multiple existing players; resolve that conflict first.",
                409,
            )
        player = slug_matches[0] if slug_matches else None

    name_matches = _normalized_name_query(Player, Player.display_name, name).all()
    if player is not None and name_matches and player not in name_matches:
        raise AdminAPIError(
            f"'{name}' and start.gg slug '{slug}' identify different existing players.",
            409,
        )
    if player is None and len(name_matches) == 1:
        candidate = name_matches[0]
        if candidate.startgg_slug and slug and candidate.startgg_slug.casefold() != slug.casefold():
            raise AdminAPIError(
                f"'{name}' already exists with a different start.gg slug.", 409
            )
        player = candidate
    elif player is None and len(name_matches) > 1:
        raise AdminAPIError(f"Player name '{name}' is ambiguous; use a unique start.gg slug.", 409)

    if player is None:
        player = Player(display_name=name, startgg_slug=slug)
        db.session.add(player)
        db.session.flush()
        results["players_created"] += 1
    else:
        results["players_found"] += 1
        if slug and not player.startgg_slug:
            player.startgg_slug = slug
    return player


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value, field_name="date"):
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise AdminAPIError(f"{field_name.replace('_', ' ').title()} must be an ISO date.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AdminAPIError(
            f"{field_name.replace('_', ' ').title()} must be an ISO date (YYYY-MM-DD)."
        ) from exc


def _ensure_unique_team_name(season_id, name, exclude_team_id=None):
    query = _normalized_name_query(Team, Team.name, name).filter_by(season_id=season_id)
    if exclude_team_id is not None:
        query = query.filter(Team.id != exclude_team_id)
    if query.first():
        raise AdminAPIError("A team with that name already exists in this season.", 409)


def _player_identity_conflict(
    *,
    display_name=None,
    startgg_id=None,
    startgg_slug=None,
    parrygg_id=None,
    exclude_player_id=None,
    check_name=False,
):
    queries = []
    if startgg_id:
        queries.append(Player.query.filter(Player.startgg_id == startgg_id))
    if startgg_slug:
        queries.append(Player.query.filter(
            func.lower(func.trim(Player.startgg_slug)) == startgg_slug.casefold()
        ))
    if parrygg_id:
        queries.append(Player.query.filter(
            func.lower(func.trim(Player.parrygg_id)) == parrygg_id.casefold()
        ))
    if check_name and display_name:
        queries.append(_normalized_name_query(Player, Player.display_name, display_name))
    for query in queries:
        if exclude_player_id is not None:
            query = query.filter(Player.id != exclude_player_id)
        existing = query.first()
        if existing:
            return existing
    return None


def _player_is_rostered(player, season):
    return any(player in team.roster for team in season.teams)
