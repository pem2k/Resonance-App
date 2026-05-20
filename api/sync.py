"""
Season sync logic.

For each rostered player with a startgg_slug, fetches their Melee singles
results within the season's sync window, auto-creates tournament records,
and upserts TournamentEntry rows with SPR + points computed.
"""

from datetime import datetime, timezone

from api.extensions import db
from api.models import Player, Tournament, TournamentEntry
from api import startgg


def sync_season(season) -> dict:
    """
    Sync all rostered players in a season who have a startgg_slug.

    Tournaments are auto-created from player event data — no manual slug entry needed.
    Already-synced entries are updated in place (idempotent).

    Returns a summary: players_synced, tournaments_created, entries_upserted, errors.
    """
    if not season.sync_from or not season.sync_to:
        raise ValueError(
            "Season must have sync_from and sync_to dates set before syncing. "
            "Set them via PUT /api/admin/seasons/<id>."
        )

    after_ts = _to_timestamp(season.sync_from)
    before_ts = _to_timestamp(season.sync_to)

    players = _rostered_players(season)
    syncable = [p for p in players if p.startgg_slug]

    result = {
        "players_synced": 0,
        "players_skipped": len(players) - len(syncable),
        "tournaments_created": 0,
        "entries_upserted": 0,
        "entries_pending": 0,
        "errors": [],
    }

    for player in syncable:
        try:
            created, upserted, pending = _sync_player(player, season, after_ts, before_ts)
            db.session.commit()
            result["players_synced"] += 1
            result["tournaments_created"] += created
            result["entries_upserted"] += upserted
            result["entries_pending"] += pending
        except Exception as exc:
            db.session.rollback()
            result["errors"].append({
                "player": player.display_name,
                "error": str(exc),
            })

    result["tournaments_auto_removed"] = _deduplicate_tournaments(season)
    return result


def sync_player(player: Player, season) -> dict:
    """Force re-sync a single player for the season window."""
    if not season.sync_from or not season.sync_to:
        raise ValueError("Season sync_from and sync_to must be set.")

    after_ts = _to_timestamp(season.sync_from)
    before_ts = _to_timestamp(season.sync_to)

    created, upserted, pending = _sync_player(player, season, after_ts, before_ts)
    db.session.commit()
    auto_removed = _deduplicate_tournaments(season)
    return {"tournaments_created": created, "entries_upserted": upserted, "entries_pending": pending, "tournaments_auto_removed": auto_removed}


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _rostered_players(season) -> list[Player]:
    seen = set()
    players = []
    for team in season.teams:
        for player in team.roster:
            if player.id not in seen:
                seen.add(player.id)
                players.append(player)
    return players


def _sync_player(
    player: Player,
    season,
    after_ts: int,
    before_ts: int,
) -> tuple[int, int]:
    """
    Fetch this player's events from start.gg and upsert entries.
    Returns (tournaments_created, entries_upserted).
    """
    events = startgg.get_player_events(player.startgg_slug, after_ts, before_ts)

    tournaments_created = 0
    entries_upserted = 0
    pending_results = 0

    for ev in events:
        if ev["placement"] is None or ev["seed"] is None:
            # Results not finalised yet — skip
            pending_results += 1
            continue

        tournament = _get_or_create_tournament(ev, season)
        if tournament is None:
            continue

        if getattr(tournament, "_created", False):
            tournaments_created += 1

        entry = TournamentEntry.query.filter_by(
            player_id=player.id,
            tournament_id=tournament.id,
        ).first()

        if entry is None:
            entry = TournamentEntry(player_id=player.id, tournament_id=tournament.id)
            db.session.add(entry)

        entry.seed = ev["seed"]
        entry.placement = ev["placement"]
        db.session.flush()
        entry.compute()
        entries_upserted += 1

    return tournaments_created, entries_upserted, pending_results


def _get_or_create_tournament(ev: dict, season) -> Tournament | None:
    """
    Look up a tournament by its start.gg event ID; create it if new.
    Stamps _created=True on the object when newly created.
    """
    tournament = Tournament.query.filter_by(
        startgg_event_id=ev["event_id"]
    ).first()

    if tournament:
        if tournament.removed:
            return None  # excluded from sync
        # Keep total_entrants up to date
        tournament.total_entrants = ev["num_entrants"]
        tournament._created = False
        return tournament

    t_date = datetime.fromtimestamp(ev["tournament_date"], tz=timezone.utc).date()

    tournament = Tournament(
        name=ev["tournament_name"],
        date=t_date,
        season_id=season.id,
        startgg_id=ev["tournament_id"],
        startgg_slug=ev["tournament_slug"],
        startgg_event_id=ev["event_id"],
        total_entrants=ev["num_entrants"],
    )
    db.session.add(tournament)
    db.session.flush()  # get tournament.id before creating entries
    tournament._created = True
    return tournament


def _deduplicate_tournaments(season) -> int:
    """
    For each startgg_id that appears in more than one active tournament in this
    season, keep the one with the most entrants and soft-remove the rest.
    Returns the number of tournaments auto-removed.
    """
    active = Tournament.query.filter_by(season_id=season.id, removed=False).all()

    groups: dict[str, list] = {}
    for t in active:
        if t.startgg_id:
            groups.setdefault(t.startgg_id, []).append(t)

    count = 0
    for group in groups.values():
        if len(group) <= 1:
            continue
        group.sort(key=lambda t: t.total_entrants or 0, reverse=True)
        for t in group[1:]:
            t.removed = True
            count += 1

    if count:
        db.session.commit()

    return count


def _to_timestamp(d) -> int:
    """Convert a date or datetime to a Unix timestamp (seconds)."""
    if hasattr(d, "date"):
        # it's a datetime
        return int(d.replace(tzinfo=timezone.utc).timestamp())
    # it's a date
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
