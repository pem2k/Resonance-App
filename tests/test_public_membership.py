def _player_by_name(rows, name):
    return next(row for row in rows if row["display_name"] == name)


def test_player_leaderboard_uses_current_roster_and_includes_zero_rows(
    client, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    rostered = make_player("Rostered")
    zero = make_player("Zero Events")
    former = make_player("Former")
    team = make_team(season, players=[rostered, zero])
    tournament = make_tournament(season)
    make_entry(rostered, tournament, points=8)
    make_entry(former, tournament, points=30)

    rows = client.get(f"/api/seasons/{season.id}/players").get_json()

    assert {row["display_name"] for row in rows} == {"Rostered", "Zero Events"}
    assert _player_by_name(rows, "Rostered")["total_points"] == 8
    zero_row = _player_by_name(rows, "Zero Events")
    assert zero_row["total_points"] == 0
    assert zero_row["events_attended"] == 0
    assert zero_row["points_per_event"] is None
    assert zero_row["team"] == {"id": team.id, "name": team.name}


def test_removed_only_entry_leaves_rostered_player_at_zero(
    client, make_season, make_player, make_team, make_tournament, make_entry
):
    season = make_season()
    player = make_player("Player")
    make_team(season, players=[player])
    removed = make_tournament(season, removed=True)
    make_entry(player, removed, points=12)

    rows = client.get(f"/api/seasons/{season.id}/players").get_json()

    assert rows[0]["display_name"] == "Player"
    assert rows[0]["total_points"] == 0
    assert rows[0]["events_attended"] == 0
