import math

# Valid placement tiers in a standard double-elimination bracket sequence.
# Tiers: 1st, 2nd, 3rd, 4th, 5th, 7th, 9th, 13th, 17th, 25th, 33rd, 49th, 65th, 97th, 129th, etc.
VALID_PLACEMENTS = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 257, 513, 1025
]


def get_placement_tier(val: int) -> int:
    """
    Finds the index of the corresponding double-elimination placement tier.
    
    For seeds: Maps to the projected finish threshold (e.g., Seed 10 -> 9th, Seed 20 -> 17th).
    For actual placements: Maps exact tournament finishes to their tier index.
    """
    tier_idx = 0
    for idx, placement in enumerate(VALID_PLACEMENTS):
        if placement <= val:
            tier_idx = idx
        else:
            break
    return tier_idx


def calculate_spr(seed: int, placement: int, total_entrants: int) -> int:
    """
    Compute Seed Performance Rating (SPR) from bracket seed, final placement,
    and total number of entrants in a double-elimination tournament.

    Formula: expected_seed_tier_index - actual_placement_tier_index

    Examples:
      seed=10, placement=9   →  0  (Expected 9th, finished 9th)
      seed=20, placement=17  →  0  (Expected 17th, finished 17th)
      seed=20, placement=13  → +1  (Expected 17th, outperformed to 13th)
      seed=10, placement=4   → +2  (Expected 9th, outperformed to 4th)
      seed=8,  placement=4   → +1  (Expected 7th, outperformed to 4th)
      seed=4,  placement=3   → +1  (Expected 4th, outperformed to 3rd)
      seed=1,  placement=2   → -1  (Expected 1st, underperformed to 2nd)
    """
    if seed <= 0 or placement <= 0 or total_entrants <= 0:
        raise ValueError("seed, placement, and total_entrants must be positive integers")

    # Clamp bounds to total_entrants (handles DQs and bracket pruning from start.gg)
    seed = min(seed, total_entrants)
    placement = min(placement, total_entrants)

    # Convert projected seed and actual placement to their double-elimination tier indices
    expected_tier = get_placement_tier(seed)
    actual_tier = get_placement_tier(placement)

    # Positive SPR means outperforming expectations; negative means underperforming
    return expected_tier - actual_tier


def spr_to_points(spr: int) -> int:
    """
    Convert a Seed Performance Rating to league points.

    SPR <= -1  → 1   (attended, underperformed)
    SPR  0     → 2   (placed seed)
    SPR +1     → 3
    SPR +2     → 5
    SPR +3     → 10
    SPR +4+    → 15, 20, 25 ... (+5 per step starting at +4)
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
    return 15 + (spr - 4) * 5