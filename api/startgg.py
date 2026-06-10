"""
start.gg GraphQL client.

Requires STARTGG_API_KEY environment variable (Bearer token).
Get one at: https://start.gg/admin/profile/developer
"""

import os
import time
import requests

_API_URL = "https://api.start.gg/gql/alpha"
_EVENTS_PER_PAGE = 100
_ENTRANTS_PER_PAGE = 64

MELEE_GAME_ID = 1
EVENT_TYPE_SINGLES = 1


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _gql(query: str, variables: dict, _retry: int = 3) -> dict:
    token = os.getenv("STARTGG_API_KEY")
    if not token:
        raise RuntimeError("STARTGG_API_KEY environment variable is not set")

    for attempt in range(_retry):
        resp = requests.post(
            _API_URL,
            json={"query": query, "variables": variables},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

        if resp.status_code == 429:
            wait = 2 ** (attempt + 2)  # 4s, 8s, 16s
            time.sleep(wait)
            continue

        resp.raise_for_status()
        body = resp.json()
        if "errors" in body:
            raise RuntimeError(f"start.gg GraphQL error: {body['errors']}")

        time.sleep(0.8)  # max 80 req/60s → minimum 0.75s; 0.8s gives a small buffer
        return body["data"]

    raise RuntimeError("start.gg rate limit: too many retries")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

# Phase 1: get the user's player ID and list of events they attended (no entrant data)
_GET_USER_EVENTS_QUERY = """
query GetPlayerEvents($slug: String!, $page: Int!, $perPage: Int!, $videogameIds: [ID]) {
  user(slug: $slug) {
    player { id }
    events(query: {
      page: $page
      perPage: $perPage
      filter: { videogameId: $videogameIds }
    }) {
      pageInfo { totalPages }
      nodes {
        id
        name
        type
        numEntrants
        tournament {
          id
          name
          slug
          startAt
        }
      }
    }
  }
}
"""

# Phase 2: paginate entrants for a single event to find this user's seed/placement
_GET_EVENT_ENTRANTS_QUERY = """
query GetEventEntrants($eventId: ID!, $page: Int!, $perPage: Int!) {
  event(id: $eventId) {
    entrants(query: { page: $page, perPage: $perPage }) {
      pageInfo { totalPages }
      nodes {
        initialSeedNum
        seeds { seedNum }
        standing { placement }
        participants {
          player { id }
        }
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_entrant_for_player(event_id: str, player_id: str) -> dict:
    """
    Paginate through an event's entrants and return the one belonging to player_id.
    Returns an empty dict if not found.
    """
    page = 1
    total_pages = None

    while total_pages is None or page <= total_pages:
        data = _gql(_GET_EVENT_ENTRANTS_QUERY, {
            "eventId": event_id,
            "page": page,
            "perPage": _ENTRANTS_PER_PAGE,
        })

        entrants_page = (data.get("event") or {}).get("entrants") or {}
        if total_pages is None:
            total_pages = entrants_page.get("pageInfo", {}).get("totalPages", 1)

        for entrant in entrants_page.get("nodes") or []:
            for participant in entrant.get("participants") or []:
                if str((participant.get("player") or {}).get("id", "")) == player_id:
                    return entrant

        page += 1

    return {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_player_events(
    user_slug: str,
    after_timestamp: int | None = None,
    before_timestamp: int | None = None,
) -> list[dict]:
    """
    Fetch all Melee singles events a player entered within an optional date range.

    after_timestamp / before_timestamp are Unix timestamps (seconds).

    Each returned dict has:
      event_id       : str
      event_name     : str
      num_entrants   : int
      tournament_id  : str
      tournament_name: str
      tournament_slug: str
      tournament_date: int  (Unix timestamp)
      seed           : int | None
      placement      : int | None
    """
    # Phase 1: get the user's player ID + all their Melee events
    page = 1
    total_pages = None
    player_id = None
    candidate_events = []

    while total_pages is None or page <= total_pages:
        data = _gql(_GET_USER_EVENTS_QUERY, {
            "slug": user_slug,
            "page": page,
            "perPage": _EVENTS_PER_PAGE,
            "videogameIds": [MELEE_GAME_ID],
        })

        user = data.get("user")
        if not user:
            raise ValueError(f"Player not found on start.gg: {user_slug!r}")

        if player_id is None:
            player_id = str((user.get("player") or {}).get("id", ""))
            if not player_id:
                raise ValueError(f"No player record linked to start.gg user: {user_slug!r}")

        events_page = user["events"]
        if total_pages is None:
            total_pages = events_page["pageInfo"]["totalPages"]

        for node in events_page["nodes"]:
            # Singles only
            if node.get("type") != EVENT_TYPE_SINGLES:
                continue

            tournament_date = node["tournament"]["startAt"]

            # Date window filter
            if after_timestamp and tournament_date < after_timestamp:
                continue
            if before_timestamp and tournament_date > before_timestamp:
                continue

            candidate_events.append(node)

        page += 1

    # Phase 2: for each candidate event, find this user's entrant to get seed/placement
    results = []
    for node in candidate_events:
        event_id = str(node["id"])
        entrant = _find_entrant_for_player(event_id, player_id)

        # Prefer initialSeedNum (the event-wide initial seed). Falling back to
        # min(seedNum) is wrong for multi-phase events: later phases (e.g. a
        # top-24 bracket after pools) renumber seeds 1..k, so the min would
        # understate the player's true seed and deflate their SPR.
        seed = entrant.get("initialSeedNum")
        if seed is None:
            seeds = entrant.get("seeds") or []
            seed = min((s["seedNum"] for s in seeds), default=None)

        standing = entrant.get("standing") or {}
        placement = standing.get("placement")

        results.append({
            "event_id": event_id,
            "event_name": node["name"],
            "num_entrants": node["numEntrants"],
            "tournament_id": str(node["tournament"]["id"]),
            "tournament_name": node["tournament"]["name"],
            "tournament_slug": node["tournament"]["slug"],
            "tournament_date": node["tournament"]["startAt"],
            "seed": seed,
            "placement": placement,
        })

    return results
