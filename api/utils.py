import math

# Valid placement tiers in a standard double-elimination bracket sequence
# Tier 0: 1, Tier 1: 2, Tier 2: 3, Tier 3: 4, Tier 4: 5, Tier 5: 7, Tier 6: 9, Tier 7: 13, etc.
VALID_PLACEMENTS = [
    1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 257, 513, 1025
]

def get_placement_tier(val: int) -> int:
    """
    Finds the index/tier in double-elimination valid placement tiers.
    Rounds `val` UP to the nearest valid placement (e.g., 10 -> 9th tier).
    """
    for index, placement in enumerate(VALID_PLACEMENTS):
        if placement >= val:
            return index
    
    # Fallback for massive brackets exceeding the static array length:
    # Pattern after 5th place follows: (2^k) + 1 for k >= 2
    # Places: 5, 7, 9, 13, 17, 25, 33...
    return len(VALID_PLACEMENTS)


def calculate_spr(seed: int, placement: int, total_entrants: int) -> int:
    """
    Compute Seed Performance Rating from bracket seed, final placement,
    and total number of entrants in the tournament.

    Formula: expected_seed_tier_index - actual_placement_tier_index
    """
    if seed <= 0 or placement <= 0 or total_entrants <= 0:
        raise ValueError("seed, placement, and total_entrants must be positive integers")

    # Clamp bounds to total_entrants
    seed = min(seed, total_entrants)
    placement = min(placement, total_entrants)

    # Convert both projected seed and actual placement to their tier indices
    expected_tier = get_placement_tier(seed)
    actual_tier = get_placement_tier(placement)

    # SPR is how many tiers ahead of (or behind) projection they placed
    return expected_tier - actual_tier


def spr_to_points(spr: int) -> int:
    """
    Convert a Seed Performance Rating to league points.
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