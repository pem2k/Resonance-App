import pytest

from api.models import Player, Team, TournamentEntry


def test_admin_routes_require_json_authentication(client, make_season):
    season = make_season()

    response = client.post("/api/admin/teams", json={"name": "Nope", "season_id": season.id})

    assert response.status_code == 401
    assert response.is_json
    assert response.get_json() == {"error": "Unauthorized"}
    assert Team.query.count() == 0


def test_team_create_and_rename_validate_names_and_conflicts(admin_client, make_season, make_team):
    season = make_season()
    existing = make_team(season, name="Team Alpha")

    blank = admin_client.post("/api/admin/teams", json={"name": "   ", "season_id": season.id})
    duplicate = admin_client.post(
        "/api/admin/teams", json={"name": " team alpha ", "season_id": season.id}
    )
    created = admin_client.post(
        "/api/admin/teams", json={"name": "  Team Beta  ", "season_id": season.id}
    )
    renamed = admin_client.put(
        f"/api/admin/teams/{created.get_json()['id']}", json={"name": " Team Gamma "}
    )
    rename_conflict = admin_client.put(
        f"/api/admin/teams/{created.get_json()['id']}", json={"name": existing.name.lower()}
    )

    assert blank.status_code == 400
    assert duplicate.status_code == 409
    assert created.status_code == 201
    assert created.get_json()["name"] == "Team Beta"
    assert renamed.status_code == 200
    assert renamed.get_json()["name"] == "Team Gamma"
    assert rename_conflict.status_code == 409


def test_team_create_rejects_unknown_season_and_initial_captain(
    admin_client, make_season, make_player
):
    season = make_season()
    player = make_player("Captain")

    unknown_season = admin_client.post(
        "/api/admin/teams", json={"name": "Team", "season_id": 999999}
    )
    captain = admin_client.post(
        "/api/admin/teams",
        json={"name": "Team", "season_id": season.id, "captain_id": player.id},
    )

    assert unknown_season.status_code == 404
    assert captain.status_code == 400
    assert "roster" in captain.get_json()["error"].lower()


def test_team_delete_preserves_players_and_historical_entries(
    admin_client, db, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    player = make_player("Player")
    team = make_team(season, players=[player])
    tournament = make_tournament(season)
    entry = make_entry(player, tournament, points=7)

    response = admin_client.delete(f"/api/admin/teams/{team.id}")

    assert response.status_code == 200
    assert db.session.get(Team, team.id) is None
    assert db.session.get(Player, player.id) is not None
    assert db.session.get(TournamentEntry, entry.id) is not None


def test_admin_player_catalog_includes_unrostered_zero_entry_players(
    admin_client, make_player
):
    player = make_player("Unrostered")

    response = admin_client.get("/api/admin/players")

    assert response.status_code == 200
    assert any(row["id"] == player.id for row in response.get_json())


def test_player_creation_rejects_duplicate_identity_and_normalizes_values(
    admin_client, make_player
):
    existing = make_player("Existing", "user/existing")

    duplicate_slug = admin_client.post(
        "/api/admin/players",
        json={"display_name": "Another", "startgg_slug": " USER/EXISTING "},
    )
    duplicate_name = admin_client.post(
        "/api/admin/players", json={"display_name": " existing ", "startgg_slug": ""}
    )
    created = admin_client.post(
        "/api/admin/players", json={"display_name": " New Player ", "startgg_slug": " "}
    )

    assert duplicate_slug.status_code == 409
    assert duplicate_slug.get_json()["existing_player"]["id"] == existing.id
    assert duplicate_name.status_code == 409
    assert created.status_code == 201
    assert created.get_json()["display_name"] == "New Player"
    assert created.get_json()["startgg_slug"] is None


def test_player_update_can_rename_and_clear_slug(admin_client, make_player):
    player = make_player("Old Name", "user/old")

    response = admin_client.put(
        f"/api/admin/players/{player.id}",
        json={"display_name": " New Name ", "startgg_slug": ""},
    )

    assert response.status_code == 200
    assert response.get_json()["display_name"] == "New Name"
    assert response.get_json()["startgg_slug"] is None


def test_player_accepts_parry_profile_url_and_rejects_duplicate_identity(admin_client):
    profile_id = "019585f3-1ccf-7c90-bff6-7fdd9a2e5178"
    created = admin_client.post(
        "/api/admin/players",
        json={
            "display_name": "Parry Player",
            "parrygg_id": f"https://parry.gg/profile/{profile_id}",
        },
    )
    duplicate = admin_client.post(
        "/api/admin/players",
        json={"display_name": "Duplicate", "parrygg_id": profile_id.upper()},
    )

    assert created.status_code == 201
    assert created.get_json()["parrygg_id"] == profile_id
    assert duplicate.status_code == 409


@pytest.mark.parametrize("value", ["not-a-uuid", "https://example.com/profile/abc"])
def test_player_rejects_invalid_parry_profile_id(admin_client, value):
    response = admin_client.post(
        "/api/admin/players",
        json={"display_name": "Player", "parrygg_id": value},
    )

    assert response.status_code == 400
    assert "Parry.gg" in response.get_json()["error"]


def test_player_can_be_renamed_while_legacy_duplicate_slug_is_unchanged(
    admin_client, make_player
):
    player = make_player("One", "user/duplicate")
    make_player("Two", "user/duplicate")

    response = admin_client.put(
        f"/api/admin/players/{player.id}",
        json={"display_name": "Renamed", "startgg_slug": "user/duplicate"},
    )

    assert response.status_code == 200
    assert response.get_json()["display_name"] == "Renamed"


def test_player_delete_rejects_dependencies_and_allows_unreferenced(
    admin_client, db, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    referenced = make_player("Referenced")
    unreferenced = make_player("Unreferenced")
    make_team(season, players=[referenced])
    tournament = make_tournament(season)
    entry = make_entry(referenced, tournament, points=3)

    blocked = admin_client.delete(f"/api/admin/players/{referenced.id}")
    deleted = admin_client.delete(f"/api/admin/players/{unreferenced.id}")

    assert blocked.status_code == 409
    assert db.session.get(Player, referenced.id) is not None
    assert db.session.get(TournamentEntry, entry.id) is not None
    assert deleted.status_code == 200
    assert db.session.get(Player, unreferenced.id) is None


def test_malformed_json_and_dates_return_stable_json_errors(admin_client, make_season):
    season = make_season()

    malformed = admin_client.post(
        "/api/admin/teams", data="not-json", content_type="application/json"
    )
    bad_date = admin_client.put(
        f"/api/admin/seasons/{season.id}", json={"start_date": "not-a-date"}
    )

    assert malformed.status_code == 400
    assert malformed.is_json
    assert bad_date.status_code == 400
    assert bad_date.is_json


def test_existing_player_roster_reuse_contract(
    admin_client, make_season, make_player, make_team
):
    season = make_season()
    other_season = make_season("Other Season")
    player = make_player("Reusable")
    team_one = make_team(season, name="One")
    team_two = make_team(season, name="Two")
    other_team = make_team(other_season, name="Other")

    first = admin_client.post(
        f"/api/admin/teams/{team_one.id}/roster", json={"player_id": player.id}
    )
    idempotent = admin_client.post(
        f"/api/admin/teams/{team_one.id}/roster", json={"player_id": player.id}
    )
    conflict = admin_client.post(
        f"/api/admin/teams/{team_two.id}/roster", json={"player_id": player.id}
    )
    cross_season = admin_client.post(
        f"/api/admin/teams/{other_team.id}/roster", json={"player_id": player.id}
    )

    assert first.status_code == 200
    assert idempotent.status_code == 200
    assert conflict.status_code == 409
    assert cross_season.status_code == 200


def test_season_creation_persists_sync_dates_and_validates_status(admin_client):
    created = admin_client.post(
        "/api/admin/seasons",
        json={
            "name": "Season",
            "status": "draft",
            "sync_from": "2026-07-01",
            "sync_to": "2026-07-31",
        },
    )
    invalid = admin_client.post(
        "/api/admin/seasons", json={"name": "Bad", "status": "surprise"}
    )

    assert created.status_code == 201
    assert created.get_json()["sync_from"] == "2026-07-01"
    assert created.get_json()["sync_to"] == "2026-07-31"
    assert invalid.status_code == 400


def test_season_status_rejects_non_string_json_values(admin_client, make_season):
    season = make_season()

    for value in (None, [], {}):
        created = admin_client.post(
            "/api/admin/seasons", json={"name": "Bad", "status": value}
        )
        updated = admin_client.put(
            f"/api/admin/seasons/{season.id}", json={"status": value}
        )

        assert created.status_code == 400
        assert updated.status_code == 400


def test_date_fields_reject_false_and_zero_instead_of_clearing(admin_client, make_season):
    season = make_season()

    for value in (False, 0):
        response = admin_client.put(
            f"/api/admin/seasons/{season.id}", json={"start_date": value}
        )

        assert response.status_code == 400


def test_duplicate_manual_entry_is_rejected(
    admin_client, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    player = make_player("Player")
    make_team(season, players=[player])
    tournament = make_tournament(season)
    make_entry(player, tournament, points=2)

    response = admin_client.post(
        f"/api/admin/tournaments/{tournament.id}/entries",
        json={"player_id": player.id, "seed": 1, "placement": 1},
    )

    assert response.status_code == 409


def test_derived_score_inputs_cannot_be_cleared_without_recomputation(
    admin_client, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    player = make_player("Player")
    make_team(season, players=[player])
    tournament = make_tournament(season)
    entry = make_entry(player, tournament, points=3, seed=8, placement=4)

    clear_entrants = admin_client.put(
        f"/api/admin/tournaments/{tournament.id}", json={"total_entrants": None}
    )
    clear_seed = admin_client.put(
        f"/api/admin/entries/{entry.id}", json={"seed": None}
    )

    assert clear_entrants.status_code == 400
    assert clear_seed.status_code == 400


def test_tournament_entrant_count_always_validates_scalar_type(
    admin_client, make_season, make_tournament
):
    season = make_season()
    tournament = make_tournament(season, total_entrants=64)

    for value in (64.0, True):
        response = admin_client.put(
            f"/api/admin/tournaments/{tournament.id}",
            json={"total_entrants": value},
        )

        assert response.status_code == 400
