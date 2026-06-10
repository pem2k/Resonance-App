"""
One-time migration: copy all data from the local SQLite DB to Postgres.

Usage:
    venv/bin/python scripts/migrate_sqlite_to_postgres.py 'postgresql://...'

Creates the schema on the target (via the app's models), copies every table
in FK-dependency order, and resets Postgres ID sequences. Refuses to run if
the target already contains data.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text  # noqa: E402

# Copy order matters: parents before children
TABLES = [
    "players",
    "seasons",
    "teams",
    "team_roster",
    "tournaments",
    "tournament_entries",
    "admin_users",
]


def main():
    if len(sys.argv) != 2 or not sys.argv[1].startswith(("postgres://", "postgresql://")):
        print(__doc__)
        sys.exit(1)

    pg_url = sys.argv[1]
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    # Build the schema on the target using the app's own models
    os.environ["DATABASE_URL"] = pg_url
    from api import create_app
    from api.extensions import db

    app = create_app()  # runs db.create_all() against Postgres

    sqlite_path = os.path.join(os.path.dirname(__file__), "..", "instance", "resonance.db")
    if not os.path.exists(sqlite_path):
        print(f"SQLite DB not found at {sqlite_path}")
        sys.exit(1)

    src = create_engine(f"sqlite:///{os.path.abspath(sqlite_path)}")

    with app.app_context():
        dst = db.engine

        # Safety: refuse to overwrite a target that already has data
        with dst.connect() as conn:
            for t in TABLES:
                n = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                if n:
                    print(f"Target table '{t}' already has {n} rows — aborting. "
                          f"Wipe the target DB first if you really want to re-migrate.")
                    sys.exit(1)

        # SQLite stores booleans as 0/1 ints — Postgres needs real booleans.
        # Use the app's model metadata to find boolean columns per table.
        from sqlalchemy import Boolean
        bool_cols = {
            t: {c.name for c in db.metadata.tables[t].columns if isinstance(c.type, Boolean)}
            for t in TABLES
        }

        with src.connect() as sconn, dst.begin() as dconn:
            for t in TABLES:
                rows = [dict(r._mapping) for r in sconn.execute(text(f"SELECT * FROM {t}"))]
                if not rows:
                    print(f"{t}: 0 rows")
                    continue
                for row in rows:
                    for c in bool_cols[t]:
                        if row[c] is not None:
                            row[c] = bool(row[c])
                cols = ", ".join(rows[0].keys())
                params = ", ".join(f":{c}" for c in rows[0].keys())
                dconn.execute(text(f"INSERT INTO {t} ({cols}) VALUES ({params})"), rows)
                print(f"{t}: {len(rows)} rows copied")

            # Reset Postgres sequences so future inserts don't collide
            for t in TABLES:
                if t == "team_roster":  # join table, no id column
                    continue
                dconn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {t}), 0) + 1, false)"
                ))
            print("ID sequences reset.")

        # Verify counts match
        with src.connect() as sconn, dst.connect() as dconn:
            ok = True
            for t in TABLES:
                a = sconn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                b = dconn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
                status = "OK" if a == b else "MISMATCH"
                if a != b:
                    ok = False
                print(f"verify {t}: sqlite={a} postgres={b} {status}")
            print("MIGRATION COMPLETE" if ok else "MIGRATION FAILED — counts differ")
            sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
