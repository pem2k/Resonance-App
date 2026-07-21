import pytest

from api.utils import calculate_spr, spr_to_points


def test_calculate_spr_known_power_of_two_cases():
    assert calculate_spr(seed=1, placement=1, total_entrants=64) == 0
    assert calculate_spr(seed=8, placement=4, total_entrants=64) == 2
    assert calculate_spr(seed=1, placement=2, total_entrants=64) == -1
    assert calculate_spr(seed=64, placement=32, total_entrants=64) == 2


def test_calculate_spr_uses_placement_rounds_in_non_power_of_two_brackets():
    assert calculate_spr(seed=10, placement=4, total_entrants=30) == 3
    assert calculate_spr(seed=19, placement=5, total_entrants=19) == 4


@pytest.mark.parametrize(
    "placement, expected_spr",
    [(10, 0), (9, 0), (8, 1), (7, 1), (6, 2), (5, 2), (4, 3)],
)
def test_calculate_spr_counts_each_double_elimination_finish_step(placement, expected_spr):
    # A 10th seed is projected to finish 9th. Advancing through the distinct
    # 7th-, 5th-, and 4th-place steps earns one SPR for each step.
    assert calculate_spr(seed=10, placement=placement, total_entrants=30) == expected_spr


def test_calculate_spr_round_tiers_do_not_shift_with_bracket_size():
    assert calculate_spr(seed=10, placement=4, total_entrants=30) == 3
    assert calculate_spr(seed=10, placement=4, total_entrants=64) == 3


def test_calculate_spr_boundary_placements_and_finish_step_edges():
    assert calculate_spr(seed=4, placement=1, total_entrants=64) == 3
    assert calculate_spr(seed=4, placement=2, total_entrants=64) == 2
    assert calculate_spr(seed=4, placement=3, total_entrants=64) == 1
    assert calculate_spr(seed=4, placement=4, total_entrants=64) == 0
    assert calculate_spr(seed=17, placement=16, total_entrants=64) == 1
    assert calculate_spr(seed=16, placement=17, total_entrants=64) == -1


def test_calculate_spr_clamps_seed_and_placement_above_total_entrants():
    assert calculate_spr(seed=128, placement=128, total_entrants=64) == 0
    assert calculate_spr(seed=128, placement=32, total_entrants=64) == 2


def test_calculate_spr_supports_brackets_beyond_static_tier_lists():
    assert calculate_spr(seed=5000, placement=2048, total_entrants=8192) == 3


@pytest.mark.parametrize(
    "seed, placement, total_entrants",
    [(0, 1, 64), (1, 0, 64), (1, 1, 0), (-1, 1, 64), (1, -1, 64), (1, 1, -64)],
)
def test_calculate_spr_rejects_non_positive_inputs(seed, placement, total_entrants):
    with pytest.raises(ValueError):
        calculate_spr(seed=seed, placement=placement, total_entrants=total_entrants)


@pytest.mark.parametrize(
    "spr, points",
    [(-3, 1), (-1, 1), (0, 2), (1, 3), (2, 5), (3, 10), (4, 15), (5, 20), (6, 25)],
)
def test_spr_to_points_exact_mapping(spr, points):
    assert spr_to_points(spr) == points
