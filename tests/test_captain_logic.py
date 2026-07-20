def _team_by_name(rows, name):
    return next(row for row in rows if row["name"] == name)


def test_team_with_captain_excludes_captain_from_public_totals_and_leaderboard(
    client, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    captain = make_player("Captain")
    player_one = make_player("Player One")
    player_two = make_player("Player Two")
    team = make_team(season, players=[captain, player_one, player_two], captain=captain)
    tournament = make_tournament(season)
    make_entry(captain, tournament, points=50)
    make_entry(player_one, tournament, points=7)
    make_entry(player_two, tournament, points=11)

    standings = client.get(f"/api/seasons/{season.id}/standings").get_json()
    assert _team_by_name(standings, team.name)["total_points"] == 18

    detail = client.get(f"/api/teams/{team.id}").get_json()
    assert detail["total_points"] == 18

    leaderboard = client.get(f"/api/seasons/{season.id}/players").get_json()
    assert {row["display_name"] for row in leaderboard} == {"Player One", "Player Two"}


def test_team_without_captain_counts_all_six_roster_players(
    client, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    players = [make_player(f"Player {i}") for i in range(1, 7)]
    team = make_team(season, players=players, captain=None)
    tournament = make_tournament(season)
    for index, player in enumerate(players, start=1):
        make_entry(player, tournament, points=index)

    standings = client.get(f"/api/seasons/{season.id}/standings").get_json()
    assert _team_by_name(standings, team.name)["total_points"] == 21

    detail = client.get(f"/api/teams/{team.id}").get_json()
    assert detail["total_points"] == 21

    leaderboard = client.get(f"/api/seasons/{season.id}/players").get_json()
    assert {row["display_name"] for row in leaderboard} == {p.display_name for p in players}


def test_removing_captain_from_roster_clears_captain_and_counts_remaining_players(
    admin_client, db, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    captain = make_player("Captain")
    player = make_player("Scorer")
    team = make_team(season, players=[captain, player], captain=captain)
    tournament = make_tournament(season)
    make_entry(captain, tournament, points=20)
    make_entry(player, tournament, points=9)

    res = admin_client.delete(f"/api/admin/teams/{team.id}/roster/{captain.id}")

    assert res.status_code == 200
    assert res.get_json()["captain"] is None
    db.session.refresh(team)
    assert team.captain_id is None
    standings = admin_client.get(f"/api/seasons/{season.id}/standings").get_json()
    assert _team_by_name(standings, team.name)["total_points"] == 9


def test_update_team_rejects_captain_not_on_roster(admin_client, make_season, make_player, make_team):
    season = make_season()
    roster_player = make_player("Roster Player")
    outsider = make_player("Outsider")
    team = make_team(season, players=[roster_player])

    res = admin_client.put(f"/api/admin/teams/{team.id}", json={"captain_id": outsider.id})

    assert res.status_code == 400
    assert "Captain must be on the team roster" in res.get_json()["error"]


def test_update_team_allows_null_captain(admin_client, db, make_season, make_player, make_team):
    season = make_season()
    captain = make_player("Captain")
    team = make_team(season, players=[captain], captain=captain)

    res = admin_client.put(f"/api/admin/teams/{team.id}", json={"captain_id": None})

    assert res.status_code == 200
    assert res.get_json()["captain"] is None
    db.session.refresh(team)
    assert team.captain_id is None
