import pytest

from api import create_app
from api.extensions import db as _db
from api.models import Season, Team, Player, Tournament, TournamentEntry


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_ENGINE_OPTIONS": {},
        "RATELIMIT_ENABLED": False,
        "WTF_CSRF_ENABLED": False,
    })
    return app


@pytest.fixture
def db(app):
    with app.app_context():
        _db.drop_all()
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def admin_client(client):
    with client.session_transaction() as session:
        session["is_admin"] = True
    return client


@pytest.fixture
def make_season(db):
    def _make(name="Season 2", status="draft"):
        season = Season(name=name, status=status)
        db.session.add(season)
        db.session.commit()
        return season
    return _make


@pytest.fixture
def make_player(db):
    def _make(name, slug=None):
        player = Player(display_name=name, startgg_slug=slug)
        db.session.add(player)
        db.session.commit()
        return player
    return _make


@pytest.fixture
def make_team(db):
    def _make(season, name="Team Alpha", players=None, captain=None):
        team = Team(name=name, season_id=season.id, captain_id=captain.id if captain else None)
        if players:
            team.roster.extend(players)
        db.session.add(team)
        db.session.commit()
        return team
    return _make


@pytest.fixture
def make_tournament(db):
    def _make(season, name="Tournament", total_entrants=64, removed=False):
        tournament = Tournament(
            name=name,
            season_id=season.id,
            total_entrants=total_entrants,
            removed=removed,
        )
        db.session.add(tournament)
        db.session.commit()
        return tournament
    return _make


@pytest.fixture
def make_entry(db):
    def _make(player, tournament, points, seed=None, placement=None):
        entry = TournamentEntry(
            player_id=player.id,
            tournament_id=tournament.id,
            points=points,
            seed=seed,
            placement=placement,
        )
        db.session.add(entry)
        db.session.commit()
        return entry
    return _make
