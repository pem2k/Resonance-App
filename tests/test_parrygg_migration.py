import sqlite3

from sqlalchemy import inspect

from api import create_app
from api.extensions import db


def test_migrate_parrygg_adds_columns_to_legacy_database(tmp_path):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    connection.executescript("""
        CREATE TABLE players (
            id INTEGER PRIMARY KEY,
            display_name VARCHAR(100) NOT NULL,
            startgg_id VARCHAR(50),
            startgg_slug VARCHAR(100)
        );
        CREATE TABLE tournaments (
            id INTEGER PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            season_id INTEGER NOT NULL,
            startgg_id VARCHAR(50),
            startgg_slug VARCHAR(200),
            startgg_event_id VARCHAR(50)
        );
    """)
    connection.close()
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "RATELIMIT_ENABLED": False,
    })

    result = app.test_cli_runner().invoke(args=["migrate-parrygg"])

    assert result.exit_code == 0, result.output
    with app.app_context():
        columns = {
            table: {column["name"] for column in inspect(db.engine).get_columns(table)}
            for table in ("players", "tournaments")
        }
        indexes = inspect(db.engine).get_indexes("players")
    assert "parrygg_id" in columns["players"]
    assert {"parrygg_id", "parrygg_slug", "parrygg_event_id"} <= columns["tournaments"]
    assert any(
        index["unique"] and index["column_names"] == ["parrygg_id"]
        for index in indexes
    )
    assert "Added 4 Parry.gg columns; unique player identity index added." in result.output
