from api.models import Player, Team


def test_import_standard_block_creates_team_with_captain_on_roster(admin_client, db, make_season):
    season = make_season()
    text = """Team Alpha
Captain, user/captain
Player One, user/one
Player Two, user/two"""

    res = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert res.status_code == 200
    assert res.get_json()["teams_imported"] == 1
    team = Team.query.filter_by(name="Team Alpha").one()
    assert team.captain.display_name == "Captain"
    assert {player.display_name for player in team.roster} == {"Captain", "Player One", "Player Two"}


def test_import_no_captain_marker_creates_captainless_team(admin_client, make_season):
    season = make_season()
    text = """Team Beta
No Captain
Player One, user/one
Player Two, user/two
Player Three, user/three
Player Four, user/four
Player Five, user/five
Player Six, user/six"""

    res = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert res.status_code == 200
    team = Team.query.filter_by(name="Team Beta").one()
    assert team.captain_id is None
    assert len(team.roster) == 6
    assert {player.display_name for player in team.roster} == {
        "Player One",
        "Player Two",
        "Player Three",
        "Player Four",
        "Player Five",
        "Player Six",
    }


def test_import_no_captain_marker_is_case_insensitive(admin_client, make_season):
    season = make_season()
    text = """Team Gamma
nO cApTaIn
Player One, user/one"""

    res = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert res.status_code == 200
    team = Team.query.filter_by(name="Team Gamma").one()
    assert team.captain_id is None


def test_import_bad_captain_line_still_errors(admin_client, make_season):
    season = make_season()
    text = """Team Bad
Captain Without Slug
Player One, user/one"""

    res = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert res.status_code == 400
    body = res.get_json()
    assert body["errors"] == ["Bad captain line in 'Team Bad': Captain Without Slug"]


def test_import_bad_player_line_still_errors(admin_client, make_season):
    season = make_season()
    text = """Team Bad
Captain, user/captain
Player Without Slug"""

    res = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert res.status_code == 400
    body = res.get_json()
    assert body["errors"] == ["Bad player line in 'Team Bad': Player Without Slug"]


def test_import_duplicate_player_across_teams_is_atomic_conflict(admin_client, make_season):
    season = make_season()
    text = """Team One
Captain One, user/captain-one
Shared, user/shared
---
Team Two
Captain Two, user/captain-two
Shared, user/shared"""

    res = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert res.status_code == 409
    body = res.get_json()
    assert "multiple imported teams" in body["error"]
    assert Team.query.count() == 0
    assert Player.query.count() == 0


def test_invalid_import_block_has_no_player_side_effects(admin_client, make_season):
    season = make_season()
    text = """Team Bad
Captain, user/captain
Player Without Slug"""

    response = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert response.status_code == 400
    assert Team.query.count() == 0
    assert Player.query.count() == 0


def test_import_keeps_omitted_teams_and_supports_roster_swaps(
    admin_client, make_season, make_player, make_team
):
    season = make_season()
    one = make_player("One", "user/one")
    two = make_player("Two", "user/two")
    retained = make_player("Retained", "user/retained")
    team_one = make_team(season, name="Team One", players=[one])
    team_two = make_team(season, name="Team Two", players=[two])
    omitted = make_team(season, name="Omitted", players=[retained])
    text = """Team One
No Captain
Two, user/two
---
Team Two
No Captain
One, user/one"""

    response = admin_client.post(f"/api/admin/seasons/{season.id}/import", json={"text": text})

    assert response.status_code == 200
    assert {p.display_name for p in team_one.roster} == {"Two"}
    assert {p.display_name for p in team_two.roster} == {"One"}
    assert {p.display_name for p in omitted.roster} == {"Retained"}


def test_active_import_requires_accurate_merge_confirmation(admin_client, make_season):
    season = make_season(status="active")
    text = """Team
No Captain
Player, user/player"""

    missing = admin_client.post(
        f"/api/admin/seasons/{season.id}/import", json={"text": text}
    )
    accepted = admin_client.post(
        f"/api/admin/seasons/{season.id}/import",
        json={"text": text, "overwrite_confirm": f"Confirm import {season.name}"},
    )

    assert missing.status_code == 409
    assert missing.get_json()["required"] == f"Confirm import {season.name}"
    assert accepted.status_code == 200


def test_import_rejects_ambiguous_legacy_duplicate_slug_atomically(
    admin_client, make_season, make_player
):
    season = make_season()
    make_player("One", "user/duplicate")
    make_player("Two", "user/duplicate")
    text = """Team
No Captain
Player, user/duplicate"""

    response = admin_client.post(
        f"/api/admin/seasons/{season.id}/import", json={"text": text}
    )

    assert response.status_code == 409
    assert Team.query.count() == 0


def test_import_rejects_cross_identity_mismatch_and_restores_roster(
    admin_client, make_season, make_player, make_team
):
    season = make_season()
    slug_owner = make_player("Slug Owner", "user/slug-owner")
    name_owner = make_player("Name Owner", "user/name-owner")
    retained = make_player("Retained", "user/retained")
    team = make_team(season, name="Team", players=[retained])
    text = """Team
No Captain
Name Owner, user/slug-owner"""

    response = admin_client.post(
        f"/api/admin/seasons/{season.id}/import", json={"text": text}
    )

    assert response.status_code == 409
    assert "different existing players" in response.get_json()["error"]
    assert {player.id for player in team.roster} == {retained.id}
    assert Player.query.count() == 3
    assert slug_owner.startgg_slug == "user/slug-owner"
    assert name_owner.startgg_slug == "user/name-owner"
