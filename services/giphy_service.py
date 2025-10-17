"""
Giphy Service for Discord Bot v2.0

Provides async interface to Giphy API with disappointment-based search phrases.
Used for Easter egg features like the soak command.
"""
import random
from typing import List, Optional
import aiohttp

from utils.logging import get_contextual_logger
from config import get_config
from exceptions import APIException


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


class GiphyService:
    """Service for fetching GIFs from Giphy API based on disappointment tiers."""

    def __init__(self):
        """Initialize Giphy service with configuration."""
        self.config = get_config()
        self.api_key = self.config.giphy_api_key
        self.translate_url = self.config.giphy_translate_url
        self.logger = get_contextual_logger(f'{__name__}.GiphyService')

    def get_tier_for_seconds(self, seconds_elapsed: Optional[int]) -> str:
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

    def get_random_phrase_for_tier(self, tier_key: str) -> str:
        """
        Get a random search phrase from the specified tier.

        Args:
            tier_key: Tier identifier (e.g., 'tier_1', 'first_ever')

        Returns:
            Random search phrase from that tier

        Raises:
            ValueError: If tier_key is invalid
        """
        if tier_key not in DISAPPOINTMENT_TIERS:
            raise ValueError(f"Invalid tier key: {tier_key}")

        phrases = DISAPPOINTMENT_TIERS[tier_key]['phrases']
        return random.choice(phrases)

    def get_tier_description(self, tier_key: str) -> str:
        """
        Get the human-readable description for a tier.

        Args:
            tier_key: Tier identifier

        Returns:
            Description string

        Raises:
            ValueError: If tier_key is invalid
        """
        if tier_key not in DISAPPOINTMENT_TIERS:
            raise ValueError(f"Invalid tier key: {tier_key}")

        return DISAPPOINTMENT_TIERS[tier_key]['description']

    async def get_disappointment_gif(self, tier_key: str) -> str:
        """
        Fetch a GIF from Giphy based on disappointment tier.

        Randomly selects a search phrase from the tier and queries Giphy.
        Filters out Trump GIFs (legacy behavior).
        Falls back to trying other phrases if first fails.

        Args:
            tier_key: Tier identifier (e.g., 'tier_1', 'first_ever')

        Returns:
            GIF URL string

        Raises:
            ValueError: If tier_key is invalid
            APIException: If all GIF fetch attempts fail
        """
        if tier_key not in DISAPPOINTMENT_TIERS:
            raise ValueError(f"Invalid tier key: {tier_key}")

        phrases = DISAPPOINTMENT_TIERS[tier_key]['phrases']

        # Shuffle phrases for variety and retry capability
        shuffled_phrases = random.sample(phrases, len(phrases))

        async with aiohttp.ClientSession() as session:
            for phrase in shuffled_phrases:
                try:
                    url = f"{self.translate_url}?s={phrase}&api_key={self.api_key}"

                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()

                            # Filter out Trump GIFs (legacy behavior)
                            gif_title = data.get('data', {}).get('title', '').lower()
                            if 'trump' in gif_title:
                                self.logger.debug(f"Filtered out Trump GIF for phrase: {phrase}")
                                continue

                            # Get the actual GIF image URL, not the web page URL
                            gif_url = data.get('data', {}).get('images', {}).get('original', {}).get('url')
                            if gif_url:
                                self.logger.info(f"Successfully fetched GIF for phrase: {phrase}", gif_url=gif_url)
                                return gif_url
                            else:
                                self.logger.warning(f"No GIF URL in response for phrase: {phrase}")
                        else:
                            self.logger.warning(f"Giphy API returned status {resp.status} for phrase: {phrase}")

                except aiohttp.ClientError as e:
                    self.logger.error(f"HTTP error fetching GIF for phrase '{phrase}': {e}")
                except Exception as e:
                    self.logger.error(f"Unexpected error fetching GIF for phrase '{phrase}': {e}")

        # All phrases failed
        error_msg = f"Failed to fetch any GIF for tier: {tier_key}"
        self.logger.error(error_msg)
        raise APIException(error_msg)
    
    async def get_gif(self, phrase: Optional[str] = None, phrase_options: Optional[List[str]] = None) -> str:
        """
        Fetch a GIF from Giphy based on a phrase or list of phrase options.

        Args:
            phrase: Specific search phrase to use
            phrase_options: List of phrases to randomly choose from

        Returns:
            GIF URL string

        Raises:
            ValueError: If neither phrase nor phrase_options is provided
            APIException: If all GIF fetch attempts fail
        """
        if phrase is None and phrase_options is None:
            raise ValueError('To get a gif, one of `phrase` or `phrase_options` must be provided')

        search_phrase = 'send help'
        if phrase is not None:
            search_phrase = phrase
        elif phrase_options is not None:
            search_phrase = random.choice(phrase_options)

        async with aiohttp.ClientSession() as session:
            attempts = 0
            while attempts < 3:
                attempts += 1
                try:
                    url = f"{self.translate_url}?s={search_phrase}&api_key={self.api_key}"

                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status != 200:
                            self.logger.warning(f"Giphy API returned status {resp.status} for phrase: {search_phrase}")
                            continue

                        data = await resp.json()

                        # Filter out Trump GIFs (legacy behavior)
                        gif_title = data.get('data', {}).get('title', '').lower()
                        if 'trump' in gif_title:
                            self.logger.debug(f"Filtered out Trump GIF for phrase: {search_phrase}")
                            continue

                        # Get the actual GIF image URL, not the web page URL
                        gif_url = data.get('data', {}).get('images', {}).get('original', {}).get('url')
                        if gif_url:
                            self.logger.info(f"Successfully fetched GIF for phrase: {search_phrase}", gif_url=gif_url)
                            return gif_url
                        else:
                            self.logger.warning(f"No GIF URL in response for phrase: {search_phrase}")

                except aiohttp.ClientError as e:
                    self.logger.error(f"HTTP error fetching GIF for phrase '{search_phrase}': {e}")
                except Exception as e:
                    self.logger.error(f"Unexpected error fetching GIF for phrase '{search_phrase}': {e}")

        # All attempts failed
        error_msg = f"Failed to fetch any GIF for phrase: {search_phrase}"
        self.logger.error(error_msg)
        raise APIException(error_msg)
