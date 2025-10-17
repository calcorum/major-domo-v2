"""
Giphy Service Wrapper for Soak Commands

This module provides backwards compatibility for existing soak commands
by re-exporting functions from the centralized GiphyService in services/.

All new code should import from services.giphy_service instead.
"""
from services import giphy_service

# Re-export tier configuration for backwards compatibility
from services.giphy_service import DISAPPOINTMENT_TIERS


def get_tier_for_seconds(seconds_elapsed):
    """
    Determine disappointment tier based on elapsed time.

    This is a wrapper function for backwards compatibility.
    Use services.giphy_service.GiphyService.get_tier_for_seconds() directly in new code.

    Args:
        seconds_elapsed: Seconds since last soak, or None for first ever

    Returns:
        Tier key string (e.g., 'tier_1', 'first_ever')
    """
    return giphy_service.get_tier_for_seconds(seconds_elapsed)


def get_random_phrase_for_tier(tier_key):
    """
    Get a random search phrase from the specified tier.

    This is a wrapper function for backwards compatibility.
    Use services.giphy_service.GiphyService.get_random_phrase_for_tier() directly in new code.

    Args:
        tier_key: Tier identifier (e.g., 'tier_1', 'first_ever')

    Returns:
        Random search phrase from that tier
    """
    return giphy_service.get_random_phrase_for_tier(tier_key)


def get_tier_description(tier_key):
    """
    Get the human-readable description for a tier.

    This is a wrapper function for backwards compatibility.
    Use services.giphy_service.GiphyService.get_tier_description() directly in new code.

    Args:
        tier_key: Tier identifier

    Returns:
        Description string
    """
    return giphy_service.get_tier_description(tier_key)


async def get_disappointment_gif(tier_key):
    """
    Fetch a GIF from Giphy based on disappointment tier.

    This is a wrapper function for backwards compatibility.
    Use services.giphy_service.GiphyService.get_disappointment_gif() directly in new code.

    Randomly selects a search phrase from the tier and queries Giphy.
    Filters out Trump GIFs (legacy behavior).
    Falls back to trying other phrases if first fails.

    Args:
        tier_key: Tier identifier (e.g., 'tier_1', 'first_ever')

    Returns:
        GIF URL string, or None if all attempts fail
    """
    try:
        return await giphy_service.get_disappointment_gif(tier_key)
    except Exception:
        # Return None for backwards compatibility with old error handling
        return None
