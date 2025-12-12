"""
Unit tests for salary cap helper functions in utils/helpers.py.

These tests verify:
1. get_team_salary_cap() returns correct cap values with fallback behavior
2. exceeds_salary_cap() correctly identifies when WAR exceeds team cap
3. Edge cases around None values and floating point tolerance

Why these tests matter:
- Salary cap validation is critical for league integrity during trades/drafts
- The helper functions centralize logic previously scattered across commands
- Proper fallback behavior ensures backwards compatibility
"""

import pytest
from utils.helpers import (
    DEFAULT_SALARY_CAP,
    SALARY_CAP_TOLERANCE,
    get_team_salary_cap,
    exceeds_salary_cap
)


class TestGetTeamSalaryCap:
    """Tests for get_team_salary_cap() function."""

    def test_returns_team_salary_cap_when_set(self):
        """
        When a team has a custom salary_cap value set, return that value.

        Why: Some teams may have different caps (expansion teams, penalties, etc.)
        """
        team = {'abbrev': 'TEST', 'salary_cap': 35.0}
        result = get_team_salary_cap(team)
        assert result == 35.0

    def test_returns_default_when_salary_cap_is_none(self):
        """
        When team.salary_cap is None, return the default cap (32.0).

        Why: Most teams use the standard cap; None indicates no custom value.
        """
        team = {'abbrev': 'TEST', 'salary_cap': None}
        result = get_team_salary_cap(team)
        assert result == DEFAULT_SALARY_CAP
        assert result == 32.0

    def test_returns_default_when_salary_cap_key_missing(self):
        """
        When the salary_cap key doesn't exist in team dict, return default.

        Why: Backwards compatibility with older team data structures.
        """
        team = {'abbrev': 'TEST', 'sname': 'Test Team'}
        result = get_team_salary_cap(team)
        assert result == DEFAULT_SALARY_CAP

    def test_returns_default_when_team_is_none(self):
        """
        When team is None, return the default cap.

        Why: Defensive programming - callers may pass None in edge cases.
        """
        result = get_team_salary_cap(None)
        assert result == DEFAULT_SALARY_CAP

    def test_returns_default_when_team_is_empty_dict(self):
        """
        When team is an empty dict, return the default cap.

        Why: Edge case handling for malformed team data.
        """
        result = get_team_salary_cap({})
        assert result == DEFAULT_SALARY_CAP

    def test_respects_zero_salary_cap(self):
        """
        When salary_cap is explicitly 0, return 0 (not default).

        Why: Zero is a valid value (e.g., suspended team), distinct from None.
        """
        team = {'abbrev': 'BANNED', 'salary_cap': 0.0}
        result = get_team_salary_cap(team)
        assert result == 0.0

    def test_handles_integer_salary_cap(self):
        """
        When salary_cap is an integer, return it as-is.

        Why: API may return int instead of float; function should handle both.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 30}
        result = get_team_salary_cap(team)
        assert result == 30


class TestExceedsSalaryCap:
    """Tests for exceeds_salary_cap() function."""

    def test_returns_false_when_under_cap(self):
        """
        WAR of 30.0 should not exceed default cap of 32.0.

        Why: Normal case - team is under cap and should pass validation.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 32.0}
        result = exceeds_salary_cap(30.0, team)
        assert result is False

    def test_returns_false_when_exactly_at_cap(self):
        """
        WAR of exactly 32.0 should not exceed cap (within tolerance).

        Why: Teams should be allowed to be exactly at cap limit.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 32.0}
        result = exceeds_salary_cap(32.0, team)
        assert result is False

    def test_returns_false_within_tolerance(self):
        """
        WAR slightly above cap but within tolerance should not exceed.

        Why: Floating point math may produce values like 32.0000001;
        tolerance prevents false positives from rounding errors.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 32.0}
        # 32.0005 is within 0.001 tolerance of 32.0
        result = exceeds_salary_cap(32.0005, team)
        assert result is False

    def test_returns_true_when_over_cap(self):
        """
        WAR of 33.0 clearly exceeds cap of 32.0.

        Why: Core validation - must reject teams over cap.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 32.0}
        result = exceeds_salary_cap(33.0, team)
        assert result is True

    def test_returns_true_just_over_tolerance(self):
        """
        WAR just beyond tolerance should exceed cap.

        Why: Tolerance has a boundary; values beyond it must fail.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 32.0}
        # 32.002 is beyond 0.001 tolerance
        result = exceeds_salary_cap(32.002, team)
        assert result is True

    def test_uses_team_custom_cap(self):
        """
        Should use team's custom cap, not default.

        Why: Teams with higher/lower caps must be validated correctly.
        """
        team = {'abbrev': 'EXPANSION', 'salary_cap': 28.0}
        # 30.0 is under default 32.0 but over custom 28.0
        result = exceeds_salary_cap(30.0, team)
        assert result is True

    def test_uses_default_cap_when_team_cap_none(self):
        """
        When team has no custom cap, use default for comparison.

        Why: Backwards compatibility - existing teams without salary_cap field.
        """
        team = {'abbrev': 'TEST', 'salary_cap': None}
        result = exceeds_salary_cap(33.0, team)
        assert result is True

        result = exceeds_salary_cap(31.0, team)
        assert result is False

    def test_handles_none_team(self):
        """
        When team is None, use default cap for comparison.

        Why: Defensive programming for edge cases.
        """
        result = exceeds_salary_cap(33.0, None)
        assert result is True

        result = exceeds_salary_cap(31.0, None)
        assert result is False


class TestPydanticModelSupport:
    """Tests for Pydantic model support in helper functions."""

    def test_get_team_salary_cap_with_pydantic_model(self):
        """
        Should work with Pydantic models that have salary_cap attribute.

        Why: Team objects in the codebase are often Pydantic models,
        not just dicts. The helper must support both.
        """
        class MockTeam:
            salary_cap = 35.0
            abbrev = 'TEST'

        team = MockTeam()
        result = get_team_salary_cap(team)
        assert result == 35.0

    def test_get_team_salary_cap_with_pydantic_model_none_cap(self):
        """
        Pydantic model with salary_cap=None should return default.

        Why: Many existing Team objects have salary_cap=None.
        """
        class MockTeam:
            salary_cap = None
            abbrev = 'TEST'

        team = MockTeam()
        result = get_team_salary_cap(team)
        assert result == DEFAULT_SALARY_CAP

    def test_get_team_salary_cap_with_object_missing_attribute(self):
        """
        Object without salary_cap attribute should return default.

        Why: Defensive handling for objects that don't have the attribute.
        """
        class MockTeam:
            abbrev = 'TEST'

        team = MockTeam()
        result = get_team_salary_cap(team)
        assert result == DEFAULT_SALARY_CAP

    def test_exceeds_salary_cap_with_pydantic_model(self):
        """
        exceeds_salary_cap should work with Pydantic-like objects.

        Why: Draft and transaction code passes Team objects directly.
        """
        class MockTeam:
            salary_cap = 28.0
            abbrev = 'EXPANSION'

        team = MockTeam()
        # 30.0 exceeds custom cap of 28.0
        result = exceeds_salary_cap(30.0, team)
        assert result is True

        # 27.0 does not exceed custom cap of 28.0
        result = exceeds_salary_cap(27.0, team)
        assert result is False


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_negative_salary_cap(self):
        """
        Negative salary cap should be returned as-is (even if nonsensical).

        Why: Function should not validate business logic - just return the value.
        If someone sets a negative cap, that's a data issue, not a helper issue.
        """
        team = {'abbrev': 'BROKE', 'salary_cap': -5.0}
        result = get_team_salary_cap(team)
        assert result == -5.0

    def test_negative_wara_under_cap(self):
        """
        Negative WAR should not exceed any positive cap.

        Why: Teams with negative WAR (all bad players) are clearly under cap.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 32.0}
        result = exceeds_salary_cap(-10.0, team)
        assert result is False

    def test_negative_wara_with_negative_cap(self):
        """
        Negative WAR vs negative cap - WAR higher than cap exceeds it.

        Why: Edge case where both values are negative. -3.0 > -5.0 + 0.001
        """
        team = {'abbrev': 'BROKE', 'salary_cap': -5.0}
        # -3.0 > -4.999 (which is -5.0 + 0.001), so it exceeds
        result = exceeds_salary_cap(-3.0, team)
        assert result is True

        # -6.0 < -4.999, so it does not exceed
        result = exceeds_salary_cap(-6.0, team)
        assert result is False

    def test_very_large_salary_cap(self):
        """
        Very large salary cap values should work correctly.

        Why: Ensure no overflow or precision issues with large numbers.
        """
        team = {'abbrev': 'RICH', 'salary_cap': 1000000.0}
        result = get_team_salary_cap(team)
        assert result == 1000000.0

        result = exceeds_salary_cap(999999.0, team)
        assert result is False

        result = exceeds_salary_cap(1000001.0, team)
        assert result is True

    def test_very_small_salary_cap(self):
        """
        Very small (but positive) salary cap should work.

        Why: Some hypothetical penalty scenario with tiny cap.
        """
        team = {'abbrev': 'TINY', 'salary_cap': 0.5}
        result = exceeds_salary_cap(0.4, team)
        assert result is False

        result = exceeds_salary_cap(0.6, team)
        assert result is True

    def test_float_precision_boundary(self):
        """
        Test exact boundary of tolerance (cap + 0.001).

        Why: Ensure the boundary condition is handled correctly.
        The check is wara > (cap + tolerance), so exactly at boundary should NOT exceed.
        """
        team = {'abbrev': 'TEST', 'salary_cap': 32.0}
        # Exactly at cap + tolerance = 32.001
        result = exceeds_salary_cap(32.001, team)
        assert result is False  # Not greater than, equal to

        # Just barely over
        result = exceeds_salary_cap(32.0011, team)
        assert result is True


class TestRealTeamModel:
    """Tests using the actual Team Pydantic model from models/team.py."""

    def test_with_real_team_model(self):
        """
        Test with the actual Team Pydantic model used in production.

        Why: Ensures the helper works with real Team objects, not just mocks.
        """
        from models.team import Team

        team = Team(
            id=1,
            abbrev='TEST',
            sname='Test Team',
            lname='Test Team Long Name',
            season=12,
            salary_cap=28.5
        )
        result = get_team_salary_cap(team)
        assert result == 28.5

    def test_with_real_team_model_none_cap(self):
        """
        Real Team model with salary_cap=None should use default.

        Why: This is the most common case in production.
        """
        from models.team import Team

        team = Team(
            id=2,
            abbrev='STD',
            sname='Standard Team',
            lname='Standard Team Long Name',
            season=12,
            salary_cap=None
        )
        result = get_team_salary_cap(team)
        assert result == DEFAULT_SALARY_CAP

    def test_exceeds_with_real_team_model(self):
        """
        exceeds_salary_cap with real Team model.

        Why: End-to-end test with actual production model.
        """
        from models.team import Team

        team = Team(
            id=3,
            abbrev='EXP',
            sname='Expansion',
            lname='Expansion Team',
            season=12,
            salary_cap=28.0
        )
        # 30.0 exceeds 28.0 cap
        assert exceeds_salary_cap(30.0, team) is True
        # 27.0 does not exceed 28.0 cap
        assert exceeds_salary_cap(27.0, team) is False


class TestConstants:
    """Tests for salary cap constants."""

    def test_default_salary_cap_value(self):
        """
        DEFAULT_SALARY_CAP should be 32.0 (league standard).

        Why: Ensures constant wasn't accidentally changed.
        """
        assert DEFAULT_SALARY_CAP == 32.0

    def test_tolerance_value(self):
        """
        SALARY_CAP_TOLERANCE should be 0.001.

        Why: Tolerance must be small enough to catch real violations
        but large enough to handle floating point imprecision.
        """
        assert SALARY_CAP_TOLERANCE == 0.001
