import math


def get_placement_tier(rank: int) -> int:
    """Return the ordered double-elimination finish tier containing ``rank``.

    Finish groups progress as 1st, 2nd, 3rd, 4th, 5th–6th, 7th–8th,
    9th–12th, 13th–16th, and so on. Each group is one placement round.
    """
    if rank <= 2:
        return rank - 1

    exponent = math.floor(math.log2(rank - 1))
    group_start = 2**exponent
    second_group_start = group_start + (group_start // 2) + 1
    return (2 * exponent) + int(rank >= second_group_start)


def calculate_spr(seed: int, placement: int, total_entrants: int) -> int:
    """
    Compute Seed Performance Rating from bracket seed, final placement,
    and total number of entrants in the tournament.

    This compares the double-elimination finish tier projected by the seed
    with the tier containing the final placement. For example, a 10th seed is
    projected to finish 9th; placing 4th advances through 7th, 5th, and 4th
    for SPR +3.
    """
    if seed <= 0 or placement <= 0 or total_entrants <= 0:
        raise ValueError("seed, placement, and total_entrants must be positive integers")

    # start.gg can report values above numEntrants after DQs or bracket pruning.
    seed = min(seed, total_entrants)
    placement = min(placement, total_entrants)

    expected_tier = get_placement_tier(seed)
    actual_tier = get_placement_tier(placement)
    return expected_tier - actual_tier


def spr_to_points(spr: int) -> int:
    """Convert a Seed Performance Rating to league points."""
    if spr <= -1:
        return 1
    if spr == 0:
        return 2
    if spr == 1:
        return 3
    if spr == 2:
        return 5
    if spr == 3:
        return 10
    return 15 + (spr - 4) * 5
