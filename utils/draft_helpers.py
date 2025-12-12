"""
Draft utility functions for Discord Bot v2.0

Provides helper functions for draft order calculation and cap space validation.
"""
import math
from typing import Tuple
from utils.logging import get_contextual_logger
from config import get_config

logger = get_contextual_logger(__name__)


def calculate_pick_details(overall: int) -> Tuple[int, int]:
    """
    Calculate round number and pick position from overall pick number.

    Hybrid draft format:
    - Rounds 1-10: Linear (same order every round)
    - Rounds 11+: Snake (reverse order on even rounds)

    Special rule: Round 11, Pick 1 belongs to the team that had Round 10, Pick 16
    (last pick of linear rounds transitions to first pick of snake rounds).

    Args:
        overall: Overall pick number (1-512 for 32-round, 16-team draft)

    Returns:
        (round_num, position): Round number (1-32) and position within round (1-16)

    Examples:
        >>> calculate_pick_details(1)
        (1, 1)  # Round 1, Pick 1

        >>> calculate_pick_details(16)
        (1, 16)  # Round 1, Pick 16

        >>> calculate_pick_details(160)
        (10, 16)  # Round 10, Pick 16 (last linear pick)

        >>> calculate_pick_details(161)
        (11, 1)  # Round 11, Pick 1 (first snake pick - same team as 160)

        >>> calculate_pick_details(176)
        (11, 16)  # Round 11, Pick 16

        >>> calculate_pick_details(177)
        (12, 16)  # Round 12, Pick 16 (snake reverses)
    """
    config = get_config()
    team_count = config.draft_team_count
    linear_rounds = config.draft_linear_rounds

    round_num = math.ceil(overall / team_count)

    if round_num <= linear_rounds:
        # Linear draft: position is same calculation every round
        position = ((overall - 1) % team_count) + 1
    else:
        # Snake draft: reverse on even rounds
        if round_num % 2 == 1:  # Odd rounds (11, 13, 15...)
            position = ((overall - 1) % team_count) + 1
        else:  # Even rounds (12, 14, 16...)
            position = team_count - ((overall - 1) % team_count)

    return round_num, position


def calculate_overall_from_round_position(round_num: int, position: int) -> int:
    """
    Calculate overall pick number from round and position.

    Inverse operation of calculate_pick_details().

    Args:
        round_num: Round number (1-32)
        position: Position within round (1-16)

    Returns:
        Overall pick number

    Examples:
        >>> calculate_overall_from_round_position(1, 1)
        1

        >>> calculate_overall_from_round_position(10, 16)
        160

        >>> calculate_overall_from_round_position(11, 1)
        161

        >>> calculate_overall_from_round_position(12, 16)
        177
    """
    config = get_config()
    team_count = config.draft_team_count
    linear_rounds = config.draft_linear_rounds

    if round_num <= linear_rounds:
        # Linear draft
        return (round_num - 1) * team_count + position
    else:
        # Snake draft
        picks_before_round = (round_num - 1) * team_count
        if round_num % 2 == 1:  # Odd snake rounds
            return picks_before_round + position
        else:  # Even snake rounds (reversed)
            return picks_before_round + (team_count + 1 - position)


async def validate_cap_space(
    roster: dict,
    new_player_wara: float,
    team=None
) -> Tuple[bool, float, float]:
    """
    Validate team has cap space to draft player.

    Cap calculation:
    - Maximum 32 players on active roster
    - Only top 26 players count toward cap
    - Cap limit: Team-specific or default 32.00 sWAR

    Args:
        roster: Roster dictionary from API with structure:
            {
                'active': {
                    'players': [{'id': int, 'name': str, 'wara': float}, ...],
                    'WARa': float  # Current roster sWAR
                }
            }
        new_player_wara: sWAR value of player being drafted
        team: Optional team object/dict for team-specific salary cap

    Returns:
        (valid, projected_total, cap_limit): True if under cap, projected total sWAR, and cap limit used

    Raises:
        ValueError: If roster structure is invalid
    """
    from utils.helpers import get_team_salary_cap, SALARY_CAP_TOLERANCE

    config = get_config()
    cap_limit = get_team_salary_cap(team)
    cap_player_count = config.cap_player_count

    if not roster or not roster.get('active'):
        raise ValueError("Invalid roster structure - missing 'active' key")

    active_roster = roster['active']
    current_players = active_roster.get('players', [])

    # Calculate how many players count toward cap after adding new player
    current_roster_size = len(current_players)
    projected_roster_size = current_roster_size + 1

    # Cap counting rules:
    # - The 26 CHEAPEST (lowest WAR) players on the roster count toward the cap
    # - If roster has fewer than 26 players, all of them count
    # - If roster has 26+ players, only the bottom 26 by WAR count
    # - This allows expensive stars to be "excluded" if you have enough cheap depth
    players_counted = min(projected_roster_size, cap_player_count)

    # Sort all players (including new) by sWAR ASCENDING (cheapest first)
    all_players_wara = [p['wara'] for p in current_players] + [new_player_wara]
    sorted_wara = sorted(all_players_wara)  # Ascending order

    # Sum bottom N players (the cheapest ones)
    projected_total = sum(sorted_wara[:players_counted])

    # Allow tiny floating point tolerance
    is_valid = projected_total <= (cap_limit + SALARY_CAP_TOLERANCE)

    logger.debug(
        f"Cap validation: roster_size={current_roster_size}, "
        f"projected_size={projected_roster_size}, "
        f"players_counted={players_counted}, "
        f"new_player_wara={new_player_wara:.2f}, "
        f"projected_total={projected_total:.2f}, "
        f"cap_limit={cap_limit:.2f}, "
        f"valid={is_valid}"
    )

    return is_valid, projected_total, cap_limit


def format_pick_display(overall: int) -> str:
    """
    Format pick number for display.

    Args:
        overall: Overall pick number

    Returns:
        Formatted string like "Round 1, Pick 3 (Overall #3)"

    Examples:
        >>> format_pick_display(1)
        "Round 1, Pick 1 (Overall #1)"

        >>> format_pick_display(45)
        "Round 3, Pick 13 (Overall #45)"
    """
    round_num, position = calculate_pick_details(overall)
    return f"Round {round_num}, Pick {position} (Overall #{overall})"


def get_next_pick_overall(current_overall: int) -> int:
    """
    Get the next overall pick number.

    Simply increments by 1, but provided for completeness and future logic changes.

    Args:
        current_overall: Current overall pick number

    Returns:
        Next overall pick number
    """
    return current_overall + 1


def is_draft_complete(current_overall: int, total_picks: int = None) -> bool:
    """
    Check if draft is complete.

    Args:
        current_overall: Current overall pick number
        total_picks: Total number of picks in draft (None uses config value)

    Returns:
        True if draft is complete
    """
    if total_picks is None:
        config = get_config()
        total_picks = config.draft_total_picks

    return current_overall > total_picks


def get_round_name(round_num: int) -> str:
    """
    Get display name for round.

    Args:
        round_num: Round number

    Returns:
        Display name like "Round 1" or "Round 11 (Snake Draft Begins)"
    """
    if round_num == 1:
        return "Round 1"
    elif round_num == 11:
        return "Round 11 (Snake Draft Begins)"
    else:
        return f"Round {round_num}"
