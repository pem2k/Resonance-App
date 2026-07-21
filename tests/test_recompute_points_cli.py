def test_recompute_points_cli_supports_dry_run_and_commit(
    app, db, make_season, make_player, make_tournament, make_entry
):
    season = make_season(status="active")
    player = make_player("Round Tier Test")
    tournament = make_tournament(season, total_entrants=30)
    entry = make_entry(
        player,
        tournament,
        points=3,
        seed=10,
        placement=4,
    )
    entry.spr = 1
    db.session.commit()
    entry_id = entry.id

    runner = app.test_cli_runner()
    dry_run = runner.invoke(args=["recompute-points", "--dry-run"])

    assert dry_run.exit_code == 0
    assert "Would update 1 of 1 entries" in dry_run.output
    db.session.expire_all()
    unchanged = db.session.get(type(entry), entry_id)
    assert (unchanged.spr, unchanged.points) == (1, 3)

    committed = runner.invoke(args=["recompute-points"])

    assert committed.exit_code == 0
    assert "Updated 1 of 1 entries" in committed.output
    db.session.expire_all()
    updated = db.session.get(type(entry), entry_id)
    assert (updated.spr, updated.points) == (3, 10)
