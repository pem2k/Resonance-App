import math


def calculate_spr(seed: int, placement: int, total_entrants: int) -> int:
    """
    Compute Seed Performance Rating from bracket seed, final placement,
    and total number of entrants in the tournament.

    Formula: ceil(log2(seed)) - ceil(log2(placement))

    This compares the placement round tier with the seed round tier. Round
    boundaries are 1, 2, 3-4, 5-8, 9-16, and so on, independent of the
    tournament's entrant count. The entrant count remains a validation and
    clamping boundary for anomalous start.gg values.

    Examples:
      seed=10, placement=4  → +2
      seed=8,  placement=4  → +1
      seed=4,  placement=3  →  0
      seed=1,  placement=2  → -1
    """
    if seed <= 0 or placement <= 0 or total_entrants <= 0:
        raise ValueError("seed, placement, and total_entrants must be positive integers")
    # start.gg can report seeds/placements above numEntrants after DQs or
    # bracket pruning. Clamp to N: both mean "expected/finished dead last",
    # i.e. zero rounds — same as seed/placement == N.
    seed = min(seed, total_entrants)
    placement = min(placement, total_entrants)

    seed_tier = math.ceil(math.log2(seed))
    placement_tier = math.ceil(math.log2(placement))
    return seed_tier - placement_tier


def spr_to_points(spr: int) -> int:
    """
    Convert a Seed Performance Rating to league points.

    SPR <= -1  → 1   (attended, underperformed)
    SPR  0     → 2   (placed seed)
    SPR +1     → 3
    SPR +2     → 5
    SPR +3     → 10
    SPR +4     → 15
    SPR +5     → 20
    SPR +6     → 25  (continues +5 per additional round)
    """
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
    # SPR 4+ : 15, 20, 25, 30 ... (+5 per step starting at 4)
    return 15 + (spr - 4) * 5
