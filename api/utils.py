import math


def calculate_spr(seed: int, placement: int, total_entrants: int) -> int:
    """
    Compute Seed Performance Rating from bracket seed, final placement,
    and total number of entrants in the tournament.

    Formula: floor(log2(N / placement)) - floor(log2(N / seed))

    This counts actual rounds survived vs rounds expected based on seed,
    anchored to the real bracket size. Works correctly for non-power-of-2
    entrant counts (e.g. Genesis with 1000+ players).

    Examples (N=1000):
      seed=1000, placement=1000 →  0  (attended, lost round 1 as expected)
      seed=1000, placement=499  → +1  (survived round 1, one better than expected)
      seed=8,    placement=4    → +1
      seed=1,    placement=2    → -1  (seeded 1st, lost in finals)
    """
    if seed <= 0 or placement <= 0 or total_entrants <= 0:
        raise ValueError("seed, placement, and total_entrants must be positive integers")
    # start.gg can report seeds/placements above numEntrants after DQs or
    # bracket pruning. Clamp to N: both mean "expected/finished dead last",
    # i.e. zero rounds — same as seed/placement == N.
    seed = min(seed, total_entrants)
    placement = min(placement, total_entrants)

    seed_rounds = math.floor(math.log2(total_entrants / seed))
    placement_rounds = math.floor(math.log2(total_entrants / placement))
    return placement_rounds - seed_rounds


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
