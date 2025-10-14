"""
Giphy Service for Soak Easter Egg

Provides async interface to Giphy API with disappointment-based search phrases.
"""
import random
import logging
from typing import List, Optional
import aiohttp

logger = logging.getLogger(f'{__name__}.GiphyService')

# Giphy API configuration
GIPHY_API_KEY = 'H86xibttEuUcslgmMM6uu74IgLEZ7UOD'
GIPHY_TRANSLATE_URL = 'https://api.giphy.com/v1/gifs/translate'

# Disappointment tier configuration
DISAPPOINTMENT_TIERS = {
    'tier_1': {
        'max_seconds': 1800,  # 30 minutes
        'phrases': [
            "extremely disappointed",
            "so disappointed",
            "are you kidding me",
            "seriously",
            "unbelievable"
        ],
        'description': "Maximum Disappointment"
    },
    'tier_2': {
        'max_seconds': 7200,  # 2 hours
        'phrases': [
            "very disappointed",
            "can't believe you",
            "not happy",
            "shame on you",
            "facepalm"
        ],
        'description': "Severe Disappointment"
    },
    'tier_3': {
        'max_seconds': 21600,  # 6 hours
        'phrases': [
            "disappointed",
            "not impressed",
            "shaking head",
            "eye roll",
            "really"
        ],
        'description': "Strong Disappointment"
    },
    'tier_4': {
        'max_seconds': 86400,  # 24 hours
        'phrases': [
            "mildly disappointed",
            "not great",
            "could be better",
            "sigh",
            "seriously"
        ],
        'description': "Moderate Disappointment"
    },
    'tier_5': {
        'max_seconds': 604800,  # 7 days
        'phrases': [
            "slightly disappointed",
            "oh well",
            "shrug",
            "meh",
            "not bad"
        ],
        'description': "Mild Disappointment"
    },
    'tier_6': {
        'max_seconds': float('inf'),  # 7+ days
        'phrases': [
            "not disappointed",
            "relieved",
            "proud",
            "been worse",
            "fine i guess"
        ],
        'description': "Minimal Disappointment"
    },
    'first_ever': {
        'phrases': [
            "here we go",
            "oh boy",
            "uh oh",
            "getting started",
            "and so it begins"
        ],
        'description': "The Beginning"
    }
}


def get_tier_for_seconds(seconds_elapsed: Optional[int]) -> str:
    """
    Determine disappointment tier based on elapsed time.

    Args:
        seconds_elapsed: Seconds since last soak, or None for first ever

    Returns:
        Tier key string (e.g., 'tier_1', 'first_ever')
    """
    if seconds_elapsed is None:
        return 'first_ever'

    for tier_key in ['tier_1', 'tier_2', 'tier_3', 'tier_4', 'tier_5', 'tier_6']:
        if seconds_elapsed <= DISAPPOINTMENT_TIERS[tier_key]['max_seconds']:
            return tier_key

    return 'tier_6'  # Fallback to lowest disappointment


def get_random_phrase_for_tier(tier_key: str) -> str:
    """
    Get a random search phrase from the specified tier.

    Args:
        tier_key: Tier identifier (e.g., 'tier_1', 'first_ever')

    Returns:
        Random search phrase from that tier
    """
    phrases = DISAPPOINTMENT_TIERS[tier_key]['phrases']
    return random.choice(phrases)


def get_tier_description(tier_key: str) -> str:
    """
    Get the human-readable description for a tier.

    Args:
        tier_key: Tier identifier

    Returns:
        Description string
    """
    return DISAPPOINTMENT_TIERS[tier_key]['description']


async def get_disappointment_gif(tier_key: str) -> Optional[str]:
    """
    Fetch a GIF from Giphy based on disappointment tier.

    Randomly selects a search phrase from the tier and queries Giphy.
    Filters out Trump GIFs (legacy behavior).
    Falls back to trying other phrases if first fails.

    Args:
        tier_key: Tier identifier (e.g., 'tier_1', 'first_ever')

    Returns:
        GIF URL string, or None if all attempts fail
    """
    phrases = DISAPPOINTMENT_TIERS[tier_key]['phrases']

    # Shuffle phrases for variety and retry capability
    shuffled_phrases = random.sample(phrases, len(phrases))

    async with aiohttp.ClientSession() as session:
        for phrase in shuffled_phrases:
            try:
                url = f"{GIPHY_TRANSLATE_URL}?s={phrase}&api_key={GIPHY_API_KEY}"

                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()

                        # Filter out Trump GIFs (legacy behavior)
                        gif_title = data.get('data', {}).get('title', '').lower()
                        if 'trump' in gif_title:
                            logger.debug(f"Filtered out Trump GIF for phrase: {phrase}")
                            continue

                        gif_url = data.get('data', {}).get('url')
                        if gif_url:
                            logger.info(f"Successfully fetched GIF for phrase: {phrase}")
                            return gif_url
                        else:
                            logger.warning(f"No GIF URL in response for phrase: {phrase}")
                    else:
                        logger.warning(f"Giphy API returned status {resp.status} for phrase: {phrase}")

            except aiohttp.ClientError as e:
                logger.error(f"HTTP error fetching GIF for phrase '{phrase}': {e}")
            except Exception as e:
                logger.error(f"Unexpected error fetching GIF for phrase '{phrase}': {e}")

    # All phrases failed
    logger.error(f"Failed to fetch any GIF for tier: {tier_key}")
    return None
