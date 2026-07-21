"""Read-only Parry.gg results client using the official JSON-over-HTTP API."""

from datetime import datetime, timezone
import os
import time

import requests


_API_BASE = "https://grpcweb.parry.gg/parrygg.services"
_PAGE_SIZE = 100
_MELEE_SLUG = "super-smash-bros-melee"


def _call(service: str, method: str, payload: dict, _retry: int = 3) -> dict:
    """Call one unary Parry.gg RPC through its documented JSON proxy."""
    api_key = os.getenv("PARRYGG_API_KEY")
    if not api_key:
        raise RuntimeError("PARRYGG_API_KEY environment variable is not set")

    url = f"{_API_BASE}.{service}/{method}"
    for attempt in range(_retry):
        response = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": api_key,
            },
            timeout=30,
        )
        if response.status_code == 429:
            time.sleep(2 ** (attempt + 1))
            continue
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise RuntimeError("Parry.gg returned an invalid JSON response")
        return body

    raise RuntimeError("Parry.gg rate limit: too many retries")


def get_player_events(
    user_id: str,
    after_timestamp: int | None = None,
    before_timestamp: int | None = None,
) -> list[dict]:
    """Return normalized completed Melee singles results for one Parry user."""
    placement_results = _get_all_placements(user_id)
    tournament_cache: dict[str, dict] = {}
    events = []

    for result in placement_results:
        event_id = result.get("eventId")
        placement = result.get("placement") or {}
        if not event_id or not placement.get("placement") or not placement.get("seed"):
            continue

        event = _call("EventService", "GetEvent", {"id": event_id}).get("event") or {}
        if not _is_melee_singles(event):
            continue

        tournament_id = event.get("tournamentId")
        if not tournament_id:
            continue
        if tournament_id not in tournament_cache:
            tournament_cache[tournament_id] = (
                _call("TournamentService", "GetTournament", {"id": tournament_id})
                .get("tournament")
                or {}
            )
        tournament = tournament_cache[tournament_id]

        timestamp = _timestamp(tournament.get("startDate") or event.get("startDate"))
        if timestamp is None:
            continue
        if after_timestamp is not None and timestamp < after_timestamp:
            continue
        if before_timestamp is not None and timestamp > before_timestamp:
            continue

        events.append({
            "source": "parrygg",
            "event_id": str(event_id),
            "event_name": event.get("name") or "Melee Singles",
            "num_entrants": event.get("entrantCount"),
            "tournament_id": str(tournament_id),
            "tournament_name": tournament.get("name") or event.get("name") or "Parry.gg event",
            "tournament_slug": _preferred_slug(tournament.get("slugs") or []),
            "tournament_date": timestamp,
            "seed": placement["seed"],
            "placement": placement["placement"],
        })

    return events


def _get_all_placements(user_id: str) -> list[dict]:
    results = []
    cursor = None

    while True:
        pagination = {"pageSize": _PAGE_SIZE}
        if cursor is not None:
            pagination["cursor"] = cursor
        body = _call(
            "UserService",
            "GetUserPlacements",
            {"id": user_id, "paginationRequest": pagination},
        )
        results.extend(body.get("results") or [])
        page = body.get("paginationResponse") or {}
        if not page.get("hasMore"):
            return results
        next_cursor = page.get("nextCursor")
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("Parry.gg pagination did not provide a new cursor")
        cursor = next_cursor


def _is_melee_singles(event: dict) -> bool:
    game_slug = ((event.get("game") or {}).get("slug") or "").casefold()
    return game_slug == _MELEE_SLUG and event.get("entrantSize") == 1


def _timestamp(value) -> int | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def _preferred_slug(slugs: list[dict]) -> str | None:
    def slug_type(item):
        return item.get("type")

    for preferred in ("SLUG_TYPE_PRIMARY", 1, "SLUG_TYPE_CUSTOM", 3):
        for item in slugs:
            if slug_type(item) == preferred and item.get("slug"):
                return item["slug"]
    return next((item["slug"] for item in slugs if item.get("slug")), None)

