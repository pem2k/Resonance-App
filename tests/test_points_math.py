import pytest

from api.utils import calculate_spr, spr_to_points


def test_calculate_spr_known_power_of_two_cases():
    assert calculate_spr(seed=1, placement=1, total_entrants=64) == 0
    assert calculate_spr(seed=8, placement=4, total_entrants=64) == 1
    assert calculate_spr(seed=1, placement=2, total_entrants=64) == -1
    assert calculate_spr(seed=64, placement=32, total_entrants=64) == 1


def test_calculate_spr_boundary_placements_and_log2_floor_edges():
    assert calculate_spr(seed=4, placement=1, total_entrants=64) == 2
    assert calculate_spr(seed=4, placement=2, total_entrants=64) == 1
    assert calculate_spr(seed=4, placement=3, total_entrants=64) == 0
    assert calculate_spr(seed=4, placement=4, total_entrants=64) == 0
    assert calculate_spr(seed=17, placement=16, total_entrants=64) == 1
    assert calculate_spr(seed=16, placement=17, total_entrants=64) == -1


def test_calculate_spr_clamps_seed_and_placement_above_total_entrants():
    assert calculate_spr(seed=128, placement=128, total_entrants=64) == 0
    assert calculate_spr(seed=128, placement=32, total_entrants=64) == 1


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
