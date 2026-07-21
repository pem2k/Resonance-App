from datetime import datetime, timezone
from unittest.mock import Mock, call, patch

import pytest

from api import parrygg


def test_call_requires_api_key(monkeypatch):
    monkeypatch.delenv("PARRYGG_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="PARRYGG_API_KEY"):
        parrygg._call("UserService", "GetUser", {"id": "player-id"})


def test_call_uses_json_proxy_and_keeps_key_server_side(monkeypatch):
    monkeypatch.setenv("PARRYGG_API_KEY", "secret-key")
    response = Mock()
    response.status_code = 200
    response.json.return_value = {"user": {"id": "player-id"}}
    response.raise_for_status.return_value = None

    with patch("api.parrygg.requests.post", return_value=response) as post:
        body = parrygg._call("UserService", "GetUser", {"id": "player-id"})

    assert body == {"user": {"id": "player-id"}}
    post.assert_called_once_with(
        "https://grpcweb.parry.gg/parrygg.services.UserService/GetUser",
        json={"id": "player-id"},
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": "secret-key",
        },
        timeout=30,
    )


def test_get_player_events_paginates_and_returns_only_melee_singles():
    first_page = {
        "results": [{
            "eventId": "melee-event",
            "placement": {"placement": 4, "seed": 10},
        }],
        "paginationResponse": {
            "hasMore": True,
            "nextCursor": {"lastId": "melee-event"},
        },
    }
    second_page = {
        "results": [{
            "eventId": "ultimate-event",
            "placement": {"placement": 2, "seed": 3},
        }],
        "paginationResponse": {"hasMore": False},
    }
    melee_event = {
        "event": {
            "id": "melee-event",
            "tournamentId": "weekly-id",
            "name": "Melee Singles",
            "startDate": "2026-07-10T20:00:00Z",
            "entrantSize": 1,
            "entrantCount": 30,
            "game": {"slug": "super-smash-bros-melee"},
        }
    }
    ultimate_event = {
        "event": {
            "id": "ultimate-event",
            "tournamentId": "weekly-id",
            "name": "Ultimate Singles",
            "startDate": "2026-07-10T20:00:00Z",
            "entrantSize": 1,
            "entrantCount": 40,
            "game": {"slug": "super-smash-bros-ultimate"},
        }
    }
    tournament = {
        "tournament": {
            "id": "weekly-id",
            "name": "PNW Weekly",
            "startDate": "2026-07-10T19:00:00Z",
            "slugs": [
                {"slug": "pnw-weekly-old", "type": "SLUG_TYPE_OUTDATED"},
                {"slug": "pnw-weekly", "type": "SLUG_TYPE_PRIMARY"},
            ],
        }
    }

    def fake_call(service, method, payload):
        if (service, method) == ("UserService", "GetUserPlacements"):
            return second_page if "cursor" in payload["paginationRequest"] else first_page
        if payload.get("id") == "melee-event":
            return melee_event
        if payload.get("id") == "ultimate-event":
            return ultimate_event
        if payload.get("id") == "weekly-id":
            return tournament
        raise AssertionError((service, method, payload))

    after = int(datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp())
    before = int(datetime(2026, 7, 31, 23, 59, tzinfo=timezone.utc).timestamp())
    with patch("api.parrygg._call", side_effect=fake_call) as api_call:
        events = parrygg.get_player_events("player-id", after, before)

    assert events == [{
        "source": "parrygg",
        "event_id": "melee-event",
        "event_name": "Melee Singles",
        "num_entrants": 30,
        "tournament_id": "weekly-id",
        "tournament_name": "PNW Weekly",
        "tournament_slug": "pnw-weekly",
        "tournament_date": int(
            datetime(2026, 7, 10, 19, tzinfo=timezone.utc).timestamp()
        ),
        "seed": 10,
        "placement": 4,
    }]
    assert api_call.call_args_list[:2] == [
        call(
            "UserService",
            "GetUserPlacements",
            {"id": "player-id", "paginationRequest": {"pageSize": 100}},
        ),
        call(
            "UserService",
            "GetUserPlacements",
            {
                "id": "player-id",
                "paginationRequest": {
                    "pageSize": 100,
                    "cursor": {"lastId": "melee-event"},
                },
            },
        ),
    ]

