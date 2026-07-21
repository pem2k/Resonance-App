from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from api import sync as sync_service
from api.models import Tournament


def test_sync_status_excludes_removed_tournaments_and_entries(
    admin_client, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    player = make_player("Player", "user/player")
    make_team(season, players=[player])
    active = make_tournament(season, name="Active")
    removed = make_tournament(season, name="Removed", removed=True)
    make_entry(player, active, points=2)
    make_entry(player, removed, points=20)

    body = admin_client.get(f"/api/admin/sync/season/{season.id}/status").get_json()

    assert body["players"][0]["entries_this_season"] == 1
    assert [row["name"] for row in body["tournaments"]] == ["Active"]


def test_sync_status_handles_dated_and_undated_tournaments(
    admin_client, make_season, make_tournament
):
    season = make_season()
    make_tournament(season, name="Undated")
    dated = make_tournament(season, name="Dated")
    dated.date = date(2026, 7, 18)

    response = admin_client.get(f"/api/admin/sync/season/{season.id}/status")

    assert response.status_code == 200
    assert [row["name"] for row in response.get_json()["tournaments"]] == ["Undated", "Dated"]


def test_single_player_sync_rejects_outsider_and_missing_slug(
    admin_client, make_season, make_player, make_team
):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    outsider = make_player("Outsider", "user/outsider")
    missing_slug = make_player("Missing")
    make_team(season, players=[missing_slug])

    with patch("api.routes.sync._start_job") as start_job:
        outsider_response = admin_client.post(
            f"/api/admin/sync/season/{season.id}/player/{outsider.id}"
        )
        missing_response = admin_client.post(
            f"/api/admin/sync/season/{season.id}/player/{missing_slug.id}"
        )

    assert outsider_response.status_code == 400
    assert missing_response.status_code == 400
    start_job.assert_not_called()


def test_single_player_sync_starts_for_rostered_player(
    admin_client, make_season, make_player, make_team
):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    player = make_player("Player", "user/player")
    make_team(season, players=[player])

    with patch("api.routes.sync._start_job", return_value=True) as start_job:
        response = admin_client.post(
            f"/api/admin/sync/season/{season.id}/player/{player.id}"
        )

    assert response.status_code == 202
    start_job.assert_called_once()


def test_single_player_sync_starts_for_parry_only_player(
    admin_client, db, make_season, make_player, make_team
):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    player = make_player("Player")
    player.parrygg_id = "019585f3-1ccf-7c90-bff6-7fdd9a2e5178"
    make_team(season, players=[player])
    db.session.commit()

    with patch("api.routes.sync._start_job", return_value=True) as start_job:
        response = admin_client.post(
            f"/api/admin/sync/season/{season.id}/player/{player.id}"
        )

    assert response.status_code == 202
    start_job.assert_called_once()
    status = admin_client.get(f"/api/admin/sync/season/{season.id}/status").get_json()
    assert status["players"][0]["has_source"] is True
    assert status["players"][0]["parrygg_id"] == player.parrygg_id


def test_single_player_sync_returns_the_summary_shape_rendered_by_the_admin_ui(
    make_season, make_player, make_team
):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    player = make_player("Player", "user/player")
    make_team(season, players=[player])

    with patch("api.sync.startgg.get_player_events", return_value=[]):
        result = sync_service.sync_player(player, season)

    assert result == {
        "players_synced": 1,
        "players_skipped": 0,
        "tournaments_created": 0,
        "entries_upserted": 0,
        "entries_pending": 0,
        "tournaments_auto_removed": 0,
        "entries_stranded_by_dedup": [],
        "errors": [],
    }


def test_dual_source_sync_keeps_startgg_results_when_parry_fails(
    db, make_season, make_player, make_team
):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    player = make_player("Player", "user/player")
    player.parrygg_id = "019585f3-1ccf-7c90-bff6-7fdd9a2e5178"
    make_team(season, players=[player])
    db.session.commit()
    event = {**_event(1_784_442_600), "seed": 8, "placement": 4}

    with (
        patch("api.sync.startgg.get_player_events", return_value=[event]),
        patch("api.sync.parrygg.get_player_events", side_effect=RuntimeError("offline")),
    ):
        result = sync_service.sync_player(player, season)

    assert result["players_synced"] == 1
    assert result["entries_upserted"] == 1
    assert result["errors"] == [{
        "player": "Player",
        "source": "parry.gg",
        "error": "offline",
    }]


def test_cross_source_copy_of_same_tournament_does_not_duplicate_points(
    db, make_season, make_player, make_team
):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    player = make_player("Player", "user/player")
    player.parrygg_id = "019585f3-1ccf-7c90-bff6-7fdd9a2e5178"
    make_team(season, players=[player])
    db.session.commit()
    start_event = {**_event(1_784_442_600), "seed": 10, "placement": 4}
    parry_event = {
        **start_event,
        "source": "parrygg",
        "event_id": "parry-event",
        "tournament_id": "parry-tournament",
        "tournament_slug": "late-local",
    }

    with (
        patch("api.sync.startgg.get_player_events", return_value=[start_event]),
        patch("api.sync.parrygg.get_player_events", return_value=[parry_event]),
    ):
        result = sync_service.sync_player(player, season)

    assert result["entries_upserted"] == 2
    assert len(season.tournaments) == 1
    assert len(season.tournaments[0].entries) == 1
    assert season.tournaments[0].startgg_event_id == "event-1"
    assert season.tournaments[0].parrygg_event_id == "parry-event"


def test_sync_service_rejects_outsider(make_season, make_player):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    outsider = make_player("Outsider", "user/outsider")

    with pytest.raises(ValueError, match="not rostered"):
        sync_service.sync_player(outsider, season)


def _event(timestamp):
    return {
        "event_id": "event-1",
        "tournament_id": "tournament-1",
        "tournament_name": "Late Local",
        "tournament_slug": "tournament/late-local",
        "tournament_date": timestamp,
        "num_entrants": 64,
    }


def test_tournament_date_uses_pacific_time_and_repairs_existing(
    db, make_season, make_tournament
):
    season = make_season()
    timestamp = int(
        datetime(2026, 7, 18, 23, 30, tzinfo=ZoneInfo("America/Los_Angeles")).timestamp()
    )
    existing = make_tournament(season, name="Old UTC Date")
    existing.startgg_event_id = "event-1"
    existing.date = date(2026, 7, 19)
    db.session.commit()

    result = sync_service._get_or_create_tournament(_event(timestamp), season)

    assert result.id == existing.id
    assert result.date == date(2026, 7, 18)


def test_restore_rejects_active_duplicate_bracket(
    admin_client, db, make_season, make_tournament
):
    season = make_season()
    active = make_tournament(season, name="Kept")
    active.startgg_id = "same-tournament"
    removed = make_tournament(season, name="Duplicate", removed=True)
    removed.startgg_id = "same-tournament"
    db.session.commit()

    response = admin_client.post(f"/api/admin/tournaments/{removed.id}/restore")

    assert response.status_code == 409
    db.session.refresh(removed)
    assert removed.removed is True


def test_soft_delete_and_restore_preserve_entries_and_public_points(
    admin_client, db, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    player = make_player("Player")
    team = make_team(season, players=[player])
    tournament = make_tournament(season)
    entry = make_entry(player, tournament, points=9)

    removed = admin_client.delete(f"/api/admin/tournaments/{tournament.id}")
    without_points = admin_client.get(f"/api/teams/{team.id}").get_json()
    restored = admin_client.post(f"/api/admin/tournaments/{tournament.id}/restore")
    with_points = admin_client.get(f"/api/teams/{team.id}").get_json()

    assert removed.status_code == 200
    assert without_points["total_points"] == 0
    assert db.session.get(type(entry), entry.id) is not None
    assert restored.status_code == 200
    assert with_points["total_points"] == 9


def test_removed_tournament_stays_unchanged_during_later_sync(
    db, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    player = make_player("Player", "user/player")
    make_team(season, players=[player])
    tournament = make_tournament(season, removed=True)
    tournament.startgg_event_id = "event-1"
    entry = make_entry(player, tournament, points=9, seed=8, placement=4)
    event = {**_event(1_784_442_600), "seed": 1, "placement": 1}

    with patch("api.sync.startgg.get_player_events", return_value=[event]):
        result = sync_service.sync_player(player, season)

    db.session.refresh(tournament)
    db.session.refresh(entry)
    assert result["entries_upserted"] == 0
    assert tournament.removed is True
    assert entry.seed == 8
    assert entry.placement == 4
    assert entry.points == 9


def test_sync_window_respects_spring_and_fall_dst_day_lengths(make_season):
    season = make_season()
    season.sync_from = season.sync_to = date(2026, 3, 8)
    spring_start, spring_end = sync_service._sync_window(season)
    season.sync_from = season.sync_to = date(2026, 11, 1)
    fall_start, fall_end = sync_service._sync_window(season)

    assert spring_end - spring_start == (23 * 60 * 60) - 1
    assert fall_end - fall_start == (25 * 60 * 60) - 1


def test_sync_status_serializes_naive_utc_timestamp_with_z_suffix(
    admin_client, db, make_season, make_tournament
):
    season = make_season()
    tournament = make_tournament(season)
    tournament.synced_at = datetime(2026, 7, 18, 23, 30)
    db.session.commit()

    body = admin_client.get(f"/api/admin/sync/season/{season.id}/status").get_json()

    assert body["tournaments"][0]["synced_at"] == "2026-07-18T23:30:00Z"
