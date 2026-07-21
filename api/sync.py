"""
Season sync logic.

For each rostered player with a start.gg slug or Parry.gg profile ID, fetches
their Melee singles results within the season's sync window, auto-creates
tournament records, and upserts TournamentEntry rows with SPR + points computed.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# League operates in the Pacific Northwest — sync windows are interpreted
# in local time so tournaments on the boundary dates aren't dropped.
_LEAGUE_TZ = ZoneInfo("America/Los_Angeles")

from api.extensions import db
from api.models import Player, Tournament, TournamentEntry
from api import parrygg, startgg
from sqlalchemy import func


def sync_season(season) -> dict:
    """
    Sync all rostered players with at least one configured tournament source.

    Tournaments are auto-created from player event data — no manual slug entry needed.
    Already-synced entries are updated in place (idempotent).

    Returns a summary: players_synced, tournaments_created, entries_upserted, errors.
    """
    if not season.sync_from or not season.sync_to:
        raise ValueError(
            "Season must have sync_from and sync_to dates set before syncing. "
            "Set them via PUT /api/admin/seasons/<id>."
        )

    after_ts, before_ts = _sync_window(season)

    players = _rostered_players(season)
    syncable = [p for p in players if has_sync_identity(p)]

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
            created, upserted, pending, source_errors, source_succeeded = _sync_player(
                player, season, after_ts, before_ts
            )
            db.session.commit()
            result["players_synced"] += int(source_succeeded)
            result["tournaments_created"] += created
            result["entries_upserted"] += upserted
            result["entries_pending"] += pending
            result["errors"].extend(source_errors)
        except Exception as exc:
            db.session.rollback()
            result["errors"].append({
                "player": player.display_name,
                "error": str(exc),
            })

    removed, stranded = _deduplicate_tournaments(season)
    result["tournaments_auto_removed"] = removed
    result["entries_stranded_by_dedup"] = stranded
    return result


def sync_player(player: Player, season) -> dict:
    """Force re-sync a single player for the season window."""
    if not season.sync_from or not season.sync_to:
        raise ValueError("Season sync_from and sync_to must be set.")
    if player.id not in {rostered.id for rostered in _rostered_players(season)}:
        raise ValueError("Player is not rostered in this season.")
    if not has_sync_identity(player):
        raise ValueError("Player must have a start.gg slug or Parry.gg profile ID before syncing.")

    after_ts, before_ts = _sync_window(season)

    created, upserted, pending, source_errors, source_succeeded = _sync_player(
        player, season, after_ts, before_ts
    )
    db.session.commit()
    auto_removed, stranded = _deduplicate_tournaments(season)
    return {
        # Keep the background-job result contract identical to a season sync
        # so the shared admin result view can render either operation safely.
        "players_synced": int(source_succeeded),
        "players_skipped": 0,
        "tournaments_created": created,
        "entries_upserted": upserted,
        "entries_pending": pending,
        "tournaments_auto_removed": auto_removed,
        "entries_stranded_by_dedup": stranded,
        "errors": source_errors,
    }


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


def has_sync_identity(player: Player) -> bool:
    return bool(
        (player.startgg_slug and player.startgg_slug.strip())
        or (player.parrygg_id and player.parrygg_id.strip())
    )


def _sync_player(
    player: Player,
    season,
    after_ts: int,
    before_ts: int,
) -> tuple[int, int, int, list[dict], bool]:
    """
    Fetch this player's configured sources independently and upsert entries.

    A temporary failure in one provider does not discard valid results from
    the other. Database failures still bubble up and roll back the player.
    """
    sources = []
    if player.startgg_slug and player.startgg_slug.strip():
        sources.append(("start.gg", startgg.get_player_events, player.startgg_slug))
    if player.parrygg_id and player.parrygg_id.strip():
        sources.append(("parry.gg", parrygg.get_player_events, player.parrygg_id))

    events = []
    source_errors = []
    source_succeeded = False
    for source_name, fetch, identifier in sources:
        try:
            fetched = fetch(identifier, after_ts, before_ts)
        except Exception as exc:
            source_errors.append({
                "player": player.display_name,
                "source": source_name,
                "error": str(exc),
            })
            continue
        source_succeeded = True
        for warning in getattr(fetched, "warnings", []):
            source_errors.append({
                "player": player.display_name,
                "source": source_name,
                "error": warning,
            })
        for event in fetched:
            normalized = dict(event)
            normalized.setdefault("source", "parrygg" if source_name == "parry.gg" else "startgg")
            events.append(normalized)

    tournaments_created = 0
    entries_upserted = 0
    pending_results = 0
    processed_results = {}

    for ev in events:
        try:
            with db.session.begin_nested():
                created, upserted, pending = _upsert_event(
                    ev, player, season, processed_results, source_errors
                )
        except Exception as exc:
            source_errors.append({
                "player": player.display_name,
                "source": _source_label(ev.get("source", "startgg")),
                "error": f"Skipped invalid tournament result: {exc}",
            })
            continue
        tournaments_created += created
        entries_upserted += upserted
        pending_results += pending

    return (
        tournaments_created,
        entries_upserted,
        pending_results,
        source_errors,
        source_succeeded,
    )


def _upsert_event(ev, player, season, processed_results, source_errors):
    if ev["placement"] is None or ev["seed"] is None:
        return 0, 0, 1

    tournament = _get_or_create_tournament(ev, season, player)
    if tournament is None:
        return 0, 0, 0

    created = int(getattr(tournament, "_created", False))
    entrant_conflict = getattr(tournament, "_entrant_conflict", None)
    if entrant_conflict is not None:
        delattr(tournament, "_entrant_conflict")
        kept_count, rejected_count = entrant_conflict
        source_errors.append({
            "player": player.display_name,
            "source": _source_label(ev.get("source", "startgg")),
            "error": (
                "Conflicting mirrored entrant count; kept start.gg count "
                f"{kept_count} instead of {rejected_count}."
            ),
        })
    result_key = tournament.id
    result_value = (ev["seed"], ev["placement"])
    prior = processed_results.get(result_key)
    if prior is not None:
        prior_source, prior_value = prior
        if prior_value != result_value:
            source_errors.append({
                "player": player.display_name,
                "source": _source_label(ev.get("source", "startgg")),
                "error": (
                    "Conflicting mirrored result; kept "
                    f"{_source_label(prior_source)} seed {prior_value[0]}, "
                    f"placement {prior_value[1]} instead of seed {result_value[0]}, "
                    f"placement {result_value[1]}."
                ),
            })
        return created, 0, 0

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
    tournament.synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
    processed_results[result_key] = (ev.get("source", "startgg"), result_value)
    return created, 1, 0


def _source_label(source: str) -> str:
    return "Parry.gg" if source == "parrygg" else "start.gg"


def _get_or_create_tournament(ev: dict, season, player: Player | None = None) -> Tournament | None:
    """
    Look up a tournament by its provider event ID; create it if new.
    Stamps _created=True on the object when newly created.
    """
    # Scoped to this season: the same start.gg event may legitimately exist
    # as a separate Tournament row in another (e.g. overlapping) season.
    local_date = datetime.fromtimestamp(
        ev["tournament_date"], tz=_LEAGUE_TZ
    ).date()

    source = ev.get("source", "startgg")
    event_column = (
        Tournament.parrygg_event_id if source == "parrygg" else Tournament.startgg_event_id
    )
    opposite_event_column = (
        Tournament.startgg_event_id if source == "parrygg" else Tournament.parrygg_event_id
    )
    tournament = Tournament.query.filter(
        event_column == ev["event_id"],
        Tournament.season_id == season.id,
    ).first()

    if tournament is None and player is not None:
        # A tournament may be mirrored between providers. Exact name/date
        # matching plus a shared player result provides cross-provider evidence
        # without collapsing unrelated same-provider brackets.
        tournament = Tournament.query.join(TournamentEntry).filter(
            Tournament.season_id == season.id,
            Tournament.date == local_date,
            func.lower(func.trim(Tournament.name)) == ev["tournament_name"].strip().casefold(),
            event_column.is_(None),
            opposite_event_column.is_not(None),
            TournamentEntry.player_id == player.id,
        ).first()

    if tournament:
        if tournament.removed:
            return None  # excluded from sync
        cross_source_match = (
            source == "parrygg" and tournament.startgg_event_id
        ) or (
            source == "startgg" and tournament.parrygg_event_id
        )
        _link_provider_identifiers(tournament, ev)
        # Repair dates previously derived from UTC and keep upstream changes in sync.
        tournament.date = local_date
        # total_entrants is SPR's validation/clamping boundary, so recompute
        # entries when it changes.
        incoming_entrants = ev["num_entrants"]
        if (
            cross_source_match
            and tournament.total_entrants
            and incoming_entrants
            and tournament.total_entrants != incoming_entrants
        ):
            if source == "startgg":
                tournament._entrant_conflict = (incoming_entrants, tournament.total_entrants)
            else:
                tournament._entrant_conflict = (tournament.total_entrants, incoming_entrants)
                incoming_entrants = tournament.total_entrants
        if incoming_entrants and tournament.total_entrants != incoming_entrants:
            tournament.total_entrants = incoming_entrants
            for entry in tournament.entries:
                entry.compute()
        tournament._created = False
        return tournament

    tournament = Tournament(
        name=ev["tournament_name"],
        date=local_date,
        season_id=season.id,
        total_entrants=ev["num_entrants"],
    )
    _link_provider_identifiers(tournament, ev)
    db.session.add(tournament)
    db.session.flush()  # get tournament.id before creating entries
    tournament._created = True
    return tournament


def _link_provider_identifiers(tournament: Tournament, ev: dict) -> None:
    if ev.get("source", "startgg") == "parrygg":
        tournament.parrygg_id = ev["tournament_id"]
        tournament.parrygg_slug = ev.get("tournament_slug")
        tournament.parrygg_event_id = ev["event_id"]
    else:
        tournament.startgg_id = ev["tournament_id"]
        tournament.startgg_slug = ev.get("tournament_slug")
        tournament.startgg_event_id = ev["event_id"]


def _deduplicate_tournaments(season) -> tuple[int, list[dict]]:
    """
    For each provider tournament ID that appears in more than one active row in
    this season, keep the one with the most entrants and soft-remove the rest.

    Returns (tournaments_removed, stranded_entries) where stranded_entries
    lists players whose entry lived only on a removed duplicate bracket (so
    their points dropped from standings — an admin should review these).
    """
    active = Tournament.query.filter_by(season_id=season.id, removed=False).all()

    groups: dict[tuple[str, str], list] = {}
    for t in active:
        if t.startgg_id:
            groups.setdefault(("startgg", t.startgg_id), []).append(t)
        if t.parrygg_id:
            groups.setdefault(("parrygg", t.parrygg_id), []).append(t)

    by_id = {t.id: t for t in active}
    neighbors = {t.id: set() for t in active}
    for group in groups.values():
        if len(group) <= 1:
            continue
        first_id = group[0].id
        for member in group[1:]:
            neighbors[first_id].add(member.id)
            neighbors[member.id].add(first_id)

    count = 0
    stranded = []
    visited = set()
    for root in active:
        if root.id in visited:
            continue
        component_ids = []
        stack = [root.id]
        while stack:
            current_id = stack.pop()
            if current_id in visited:
                continue
            visited.add(current_id)
            component_ids.append(current_id)
            stack.extend(neighbors[current_id] - visited)
        if len(component_ids) <= 1:
            continue
        component = [by_id[tournament_id] for tournament_id in component_ids]
        component.sort(key=lambda t: (-(t.total_entrants or 0), t.id))
        kept = component[0]
        kept_player_ids = {e.player_id for e in kept.entries}
        for t in component[1:]:
            t.removed = True
            count += 1
            for e in t.entries:
                if e.player_id not in kept_player_ids:
                    stranded.append({
                        "player": e.player.display_name if e.player else e.player_id,
                        "removed_tournament": t.name,
                        "kept_tournament": kept.name,
                        "points_dropped": e.points,
                    })

    if count:
        db.session.commit()

    return count, stranded


def _sync_window(season) -> tuple[int, int]:
    """
    Convert the season's sync_from/sync_to dates into an inclusive Unix
    timestamp window [start of sync_from, end of sync_to] in league-local
    time, so tournaments held on either boundary date are included.
    """
    after_ts = _start_of_day(season.sync_from)
    # End of sync_to = start of the following day (exclusive bound, but the
    # provider comparisons use `>`, so subtract 1s).
    before_ts = _start_of_day(season.sync_to + timedelta(days=1)) - 1
    return after_ts, before_ts


def _start_of_day(d) -> int:
    """Unix timestamp for midnight at the start of date `d`, league-local time."""
    if isinstance(d, datetime):
        d = d.date()
    return int(datetime(d.year, d.month, d.day, tzinfo=_LEAGUE_TZ).timestamp())
