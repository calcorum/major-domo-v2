"""
Random content generation utilities for Discord Bot v2.0

Provides fun, random content for bot interactions and responses.
"""
import random
from typing import List, Optional, Union
from utils.logging import get_contextual_logger

logger = get_contextual_logger(__name__)

# Content lists
SILLY_INSULTS = [
    "You absolute walnut!",
    "You're about as useful as a chocolate teapot!",
    "Your brain is running on dial-up speed!",
    "I admire how you never let obstacles like competence get in your way.",
    "I woke up this flawless. Don't get your hopes up - it's not contagious.",
    "Everyone who ever loved you was wrong.",
    "Your summer body is looking like you have a great personality."
    # ... more insults
]

ENCOURAGEMENTS = [
    "You're doing great! 🌟",
    "Keep up the awesome work! 💪",
    "You're a legend! 🏆",
    # ... more encouragements
]

STARTUP_WATCHING = [
    'you little shits',
    'hopes die',
    'records tank',
    'cal suck'
]

def random_insult(mild: bool = True) -> str:
    """Get a random silly insult."""
    return random.choice(SILLY_INSULTS)

def random_from_list(items: List[str]) -> Optional[str]:
    """Get random item from a list."""
    return random.choice(items) if items else None

def weighted_choice(choices: List[tuple[str, float]]) -> str:
    """Choose randomly with weights."""
    return random.choices([item for item, _ in choices],
                        weights=[weight for _, weight in choices])[0]

def random_reaction_emoji() -> str:
    """Get a random reaction emoji."""
    reactions = ["😂", "🤔", "😅", "🙄", "💯", "🔥", "⚡", "🎯"]
    return random.choice(reactions)