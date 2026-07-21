"""Production-safe orchestration for scheduled season synchronization."""

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from api import sync as sync_service
from api.extensions import db
from api.models import AutoSyncState, Season


_POSTGRES_LOCK_KEY = 0x5245534F4E414E43  # "RESONANC"
_local_lock = threading.Lock()


def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@contextmanager
def try_auto_sync_lock():
    """Yield whether this process acquired the cross-process autosync lock."""
    if db.engine.dialect.name != "postgresql":
        acquired = _local_lock.acquire(blocking=False)
        try:
            yield acquired
        finally:
            if acquired:
                _local_lock.release()
        return

    connection = db.engine.connect()
    acquired = False
    try:
        acquired = bool(connection.execute(
            db.text("SELECT pg_try_advisory_lock(:key)"),
            {"key": _POSTGRES_LOCK_KEY},
        ).scalar())
        yield acquired
    finally:
        if acquired:
            connection.execute(
                db.text("SELECT pg_advisory_unlock(:key)"),
                {"key": _POSTGRES_LOCK_KEY},
            )
        connection.close()


def run_auto_sync(*, min_interval_hours=4.0, force=False, dry_run=False):
    """Sync due active seasons and persist enough state for safe scheduling."""
    now = _utc_now()
    interval = timedelta(hours=min_interval_hours)
    summary = {
        "already_running": False,
        "synced": 0,
        "skipped": 0,
        "failures": [],
        "messages": [],
    }

    with try_auto_sync_lock() as acquired:
        if not acquired:
            summary["already_running"] = True
            summary["messages"].append("Autosync is already running; skipping this invocation.")
            return summary

        seasons = Season.query.filter_by(status="active").order_by(Season.id).all()
        eligible = [season for season in seasons if season.sync_from and season.sync_to]
        if not eligible:
            summary["messages"].append("No active seasons with a sync window found.")
            return summary

        for season in eligible:
            state = db.session.get(AutoSyncState, season.id)
            due = (
                force
                or state is None
                or state.last_completed_at is None
                or state.last_completed_at <= now - interval
            )
            if not due:
                summary["skipped"] += 1
                summary["messages"].append(
                    f"{season.name}: not due; last completed at "
                    f"{state.last_completed_at.isoformat()}Z."
                )
                continue

            if dry_run:
                summary["messages"].append(f"{season.name}: would sync now.")
                continue

            state = state or AutoSyncState(season_id=season.id)
            db.session.add(state)
            state.last_started_at = now
            state.last_status = "running"
            state.last_summary = None
            db.session.commit()

            try:
                result = sync_service.sync_season(season)
                if result.get("errors") and not result.get("players_synced"):
                    raise RuntimeError(
                        "All tournament providers failed: "
                        + json.dumps(result["errors"], sort_keys=True)
                    )
            except Exception as exc:
                db.session.rollback()
                state = db.session.get(AutoSyncState, season.id)
                state.last_status = "failed"
                state.last_summary = str(exc)
                db.session.commit()
                summary["failures"].append({
                    "season_id": season.id,
                    "season": season.name,
                    "error": str(exc),
                })
                summary["messages"].append(f"{season.name}: failed — {exc}")
                continue

            state = db.session.get(AutoSyncState, season.id)
            state.last_completed_at = now
            state.last_status = "partial" if result.get("errors") else "success"
            state.last_summary = json.dumps(result, sort_keys=True, default=str)
            db.session.commit()
            summary["synced"] += 1
            summary["messages"].append(
                f"{season.name}: completed with status {state.last_status}."
            )

    return summary
