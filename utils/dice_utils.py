"""
Dice Rolling Utilities

Provides reusable dice rolling functionality for commands that need dice mechanics.
"""
import random
import re
from dataclasses import dataclass


@dataclass
class DiceRoll:
    """Represents the result of a dice roll."""
    dice_notation: str
    num_dice: int
    die_sides: int
    rolls: list[int]
    total: int


def parse_and_roll_multiple_dice(dice_notation: str) -> list[DiceRoll]:
    """Parse dice notation (supports multiple rolls) and return roll results.

    Args:
        dice_notation: Dice notation string, supports multiple rolls separated by semicolon
                      (e.g., "2d6", "1d20;2d6;1d6")

    Returns:
        List of DiceRoll results, or empty list if any part is invalid
    """
    # Split by semicolon for multiple rolls
    dice_parts = [part.strip() for part in dice_notation.split(';')]
    results = []

    for dice_part in dice_parts:
        try:
            result = parse_and_roll_single_dice(dice_part)
            results.append(result)
        except ValueError:
            return []  # Return empty list if any part is invalid

    return results


def parse_and_roll_single_dice(dice_notation: str) -> DiceRoll:
    """Parse single dice notation and return roll results.

    Args:
        dice_notation: Single dice notation string (e.g., "2d6", "1d20")

    Returns:
        DiceRoll result

    Raises:
        ValueError: If dice notation is invalid or values are out of reasonable limits
    """
    # Clean the input
    dice_notation = dice_notation.strip().lower().replace(' ', '')

    # Pattern: XdY
    pattern = r'^(\d+)d(\d+)$'
    match = re.match(pattern, dice_notation)

    if not match:
        raise ValueError(f'Cannot parse dice string **{dice_notation}**')

    num_dice = int(match.group(1))
    die_sides = int(match.group(2))

    # Validate reasonable limits
    if num_dice > 100 or die_sides > 1000 or num_dice < 1 or die_sides < 2:
        raise ValueError('I don\'t know, bud, that just doesn\'t seem doable.')

    # Roll the dice
    rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
    total = sum(rolls)

    return DiceRoll(
        dice_notation=dice_notation,
        num_dice=num_dice,
        die_sides=die_sides,
        rolls=rolls,
        total=total
    )
