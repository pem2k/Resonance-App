from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import patch

from api.models import AutoSyncState


NOW = datetime(2026, 7, 21, 20, 0, 0)


def _active_season(make_season, db):
    season = make_season(status="active")
    season.sync_from = date(2026, 7, 1)
    season.sync_to = date(2026, 7, 31)
    db.session.commit()
    return season


def _result(*, players_synced=1, errors=None):
    return {
        "players_synced": players_synced,
        "players_skipped": 0,
        "tournaments_created": 0,
        "entries_upserted": 0,
        "entries_pending": 0,
        "tournaments_auto_removed": 0,
        "entries_stranded_by_dedup": [],
        "errors": errors or [],
    }


def test_auto_sync_runs_due_active_season_and_persists_completion(app, db, make_season):
    season = _active_season(make_season, db)

    with (
        patch("api.autosync._utc_now", return_value=NOW),
        patch("api.autosync.sync_service.sync_season", return_value=_result()) as sync,
    ):
        response = app.test_cli_runner().invoke(args=["auto-sync"])

    assert response.exit_code == 0, response.output
    sync.assert_called_once()
    state = db.session.get(AutoSyncState, season.id)
    assert state.last_started_at == NOW
    assert state.last_completed_at == NOW
    assert state.last_status == "success"
    assert "completed" in response.output.lower()


def test_auto_sync_skips_season_until_four_hour_interval_expires(
    app, db, make_season
):
    season = _active_season(make_season, db)
    db.session.add(AutoSyncState(
        season_id=season.id,
        last_started_at=NOW - timedelta(hours=2),
        last_completed_at=NOW - timedelta(hours=2),
        last_status="success",
    ))
    db.session.commit()

    with (
        patch("api.autosync._utc_now", return_value=NOW),
        patch("api.autosync.sync_service.sync_season") as sync,
    ):
        response = app.test_cli_runner().invoke(args=["auto-sync"])

    assert response.exit_code == 0, response.output
    sync.assert_not_called()
    assert "not due" in response.output.lower()


def test_auto_sync_runs_again_when_interval_has_elapsed(app, db, make_season):
    season = _active_season(make_season, db)
    db.session.add(AutoSyncState(
        season_id=season.id,
        last_started_at=NOW - timedelta(hours=5),
        last_completed_at=NOW - timedelta(hours=5),
        last_status="success",
    ))
    db.session.commit()

    with (
        patch("api.autosync._utc_now", return_value=NOW),
        patch("api.autosync.sync_service.sync_season", return_value=_result()) as sync,
    ):
        response = app.test_cli_runner().invoke(args=["auto-sync"])

    assert response.exit_code == 0, response.output
    sync.assert_called_once()


def test_auto_sync_dry_run_reports_due_season_without_writes(app, db, make_season):
    season = _active_season(make_season, db)

    with (
        patch("api.autosync._utc_now", return_value=NOW),
        patch("api.autosync.sync_service.sync_season") as sync,
    ):
        response = app.test_cli_runner().invoke(args=["auto-sync", "--dry-run"])

    assert response.exit_code == 0, response.output
    sync.assert_not_called()
    assert db.session.get(AutoSyncState, season.id) is None
    assert "would sync" in response.output.lower()


def test_auto_sync_skips_cleanly_when_another_job_holds_the_lock(
    app, db, make_season
):
    _active_season(make_season, db)

    @contextmanager
    def busy_lock():
        yield False

    with (
        patch("api.autosync.try_auto_sync_lock", busy_lock),
        patch("api.autosync.sync_service.sync_season") as sync,
    ):
        response = app.test_cli_runner().invoke(args=["auto-sync"])

    assert response.exit_code == 0, response.output
    sync.assert_not_called()
    assert "already running" in response.output.lower()


def test_auto_sync_records_failure_and_returns_nonzero(app, db, make_season):
    season = _active_season(make_season, db)

    with (
        patch("api.autosync._utc_now", return_value=NOW),
        patch(
            "api.autosync.sync_service.sync_season",
            side_effect=RuntimeError("provider unavailable"),
        ),
    ):
        response = app.test_cli_runner().invoke(args=["auto-sync"])

    assert response.exit_code != 0
    state = db.session.get(AutoSyncState, season.id)
    assert state.last_started_at == NOW
    assert state.last_completed_at is None
    assert state.last_status == "failed"
    assert "provider unavailable" in state.last_summary


def test_auto_sync_treats_total_provider_failure_as_failed(app, db, make_season):
    season = _active_season(make_season, db)
    failed_result = _result(
        players_synced=0,
        errors=[{"player": "Player", "source": "start.gg", "error": "offline"}],
    )

    with (
        patch("api.autosync._utc_now", return_value=NOW),
        patch("api.autosync.sync_service.sync_season", return_value=failed_result),
    ):
        response = app.test_cli_runner().invoke(args=["auto-sync"])

    assert response.exit_code != 0
    state = db.session.get(AutoSyncState, season.id)
    assert state.last_completed_at is None
    assert state.last_status == "failed"
