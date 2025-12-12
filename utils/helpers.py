"""
Helper functions for Discord Bot v2.0

Contains utility functions for salary cap calculations and other common operations.
"""
from typing import Union
from config import get_config

# Get default values from config
_config = get_config()

# Salary cap constants - default from config, tolerance for float comparisons
DEFAULT_SALARY_CAP = _config.swar_cap_limit  # 32.0
SALARY_CAP_TOLERANCE = 0.001  # Small tolerance for floating point comparisons


def get_team_salary_cap(team) -> float:
    """
    Get the salary cap for a team, falling back to the default if not set.

    Args:
        team: Team data - can be a dict or Pydantic model with 'salary_cap' attribute.

    Returns:
        float: The team's salary cap, or DEFAULT_SALARY_CAP (32.0) if not set.

    Why: Teams may have custom salary caps (e.g., for expansion teams or penalties).
    This centralizes the fallback logic so all cap checks use the same source of truth.
    """
    if team is None:
        return DEFAULT_SALARY_CAP

    # Handle both dict and Pydantic model (or any object with salary_cap attribute)
    if isinstance(team, dict):
        salary_cap = team.get('salary_cap')
    else:
        salary_cap = getattr(team, 'salary_cap', None)

    if salary_cap is not None:
        return salary_cap
    return DEFAULT_SALARY_CAP


def exceeds_salary_cap(wara: float, team) -> bool:
    """
    Check if a WAR total exceeds the team's salary cap.

    Args:
        wara: The total WAR value to check
        team: Team data - can be a dict or Pydantic model

    Returns:
        bool: True if wara exceeds the team's salary cap (with tolerance)

    Why: Centralizes the salary cap comparison logic with proper floating point
    tolerance handling. All cap validation should use this function.
    """
    cap = get_team_salary_cap(team)
    return wara > (cap + SALARY_CAP_TOLERANCE)
