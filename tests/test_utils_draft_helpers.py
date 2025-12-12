"""
Unit tests for draft helper functions in utils/draft_helpers.py.

These tests verify:
1. calculate_pick_details() correctly handles linear and snake draft formats
2. calculate_overall_from_round_position() is the inverse of calculate_pick_details()
3. validate_cap_space() correctly validates roster cap space with team-specific caps
4. Other helper functions work correctly

Why these tests matter:
- Draft pick calculations are critical for correct draft order
- Cap space validation prevents illegal roster configurations
- These functions are used throughout the draft system
"""

import pytest
from utils.draft_helpers import (
    calculate_pick_details,
    calculate_overall_from_round_position,
    validate_cap_space,
    format_pick_display,
    get_next_pick_overall,
    is_draft_complete,
    get_round_name,
)


class TestCalculatePickDetails:
    """Tests for calculate_pick_details() function."""

    def test_round_1_pick_1(self):
        """
        Overall pick 1 should be Round 1, Pick 1.

        Why: First pick of the draft is the simplest case.
        """
        round_num, position = calculate_pick_details(1)
        assert round_num == 1
        assert position == 1

    def test_round_1_pick_16(self):
        """
        Overall pick 16 should be Round 1, Pick 16.

        Why: Last pick of round 1 in a 16-team draft.
        """
        round_num, position = calculate_pick_details(16)
        assert round_num == 1
        assert position == 16

    def test_round_2_pick_1(self):
        """
        Overall pick 17 should be Round 2, Pick 1.

        Why: First pick of round 2 (linear format for rounds 1-10).
        """
        round_num, position = calculate_pick_details(17)
        assert round_num == 2
        assert position == 1

    def test_round_10_pick_16(self):
        """
        Overall pick 160 should be Round 10, Pick 16.

        Why: Last pick of linear draft section.
        """
        round_num, position = calculate_pick_details(160)
        assert round_num == 10
        assert position == 16

    def test_round_11_pick_1_snake_begins(self):
        """
        Overall pick 161 should be Round 11, Pick 1.

        Why: First pick of snake draft. Same team as Round 10 Pick 16
        gets first pick of Round 11.
        """
        round_num, position = calculate_pick_details(161)
        assert round_num == 11
        assert position == 1

    def test_round_11_pick_16(self):
        """
        Overall pick 176 should be Round 11, Pick 16.

        Why: Last pick of round 11 (odd snake round = forward order).
        """
        round_num, position = calculate_pick_details(176)
        assert round_num == 11
        assert position == 16

    def test_round_12_snake_reverses(self):
        """
        Round 12 should be in reverse order (snake).

        Why: Even rounds in snake draft reverse the order.
        """
        # Pick 177 = Round 12, Pick 16 (starts with last team)
        round_num, position = calculate_pick_details(177)
        assert round_num == 12
        assert position == 16

        # Pick 192 = Round 12, Pick 1 (ends with first team)
        round_num, position = calculate_pick_details(192)
        assert round_num == 12
        assert position == 1


class TestCalculateOverallFromRoundPosition:
    """Tests for calculate_overall_from_round_position() function."""

    def test_round_1_pick_1(self):
        """Round 1, Pick 1 should be overall pick 1."""
        overall = calculate_overall_from_round_position(1, 1)
        assert overall == 1

    def test_round_1_pick_16(self):
        """Round 1, Pick 16 should be overall pick 16."""
        overall = calculate_overall_from_round_position(1, 16)
        assert overall == 16

    def test_round_10_pick_16(self):
        """Round 10, Pick 16 should be overall pick 160."""
        overall = calculate_overall_from_round_position(10, 16)
        assert overall == 160

    def test_round_11_pick_1(self):
        """Round 11, Pick 1 should be overall pick 161."""
        overall = calculate_overall_from_round_position(11, 1)
        assert overall == 161

    def test_round_12_pick_16_snake(self):
        """Round 12, Pick 16 should be overall pick 177 (snake reverses)."""
        overall = calculate_overall_from_round_position(12, 16)
        assert overall == 177

    def test_inverse_relationship_linear(self):
        """
        calculate_overall_from_round_position should be inverse of calculate_pick_details
        for linear rounds (1-10).

        Why: These functions must be inverses for draft logic to work correctly.
        """
        for overall in range(1, 161):  # All linear picks
            round_num, position = calculate_pick_details(overall)
            calculated_overall = calculate_overall_from_round_position(round_num, position)
            assert calculated_overall == overall, f"Failed for overall={overall}"

    def test_inverse_relationship_snake(self):
        """
        calculate_overall_from_round_position should be inverse of calculate_pick_details
        for snake rounds (11+).

        Why: These functions must be inverses for draft logic to work correctly.
        """
        for overall in range(161, 257):  # First 6 snake rounds
            round_num, position = calculate_pick_details(overall)
            calculated_overall = calculate_overall_from_round_position(round_num, position)
            assert calculated_overall == overall, f"Failed for overall={overall}"


class TestValidateCapSpace:
    """Tests for validate_cap_space() function."""

    @pytest.mark.asyncio
    async def test_valid_under_cap(self):
        """
        Drafting a player that keeps team under cap should be valid.

        Why: Normal case - team is under cap and pick should be allowed.
        The 26 cheapest players are summed (all 3 in this case since < 26).
        """
        roster = {
            'active': {
                'players': [
                    {'id': 1, 'name': 'Player 1', 'wara': 5.0},
                    {'id': 2, 'name': 'Player 2', 'wara': 4.0},
                ],
                'WARa': 9.0
            }
        }
        new_player_wara = 3.0

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        assert is_valid is True
        assert projected_total == 12.0  # 3 + 4 + 5 (all players, sorted ascending)
        assert cap_limit == 32.0  # Default cap

    @pytest.mark.asyncio
    async def test_invalid_over_cap(self):
        """
        Drafting a player that puts team over cap should be invalid.

        Why: Must prevent illegal roster configurations.
        With 26 players all at 1.5 WAR, sum = 39.0 which exceeds 32.0 cap.
        """
        # Create roster with 25 players at 1.5 WAR each
        players = [{'id': i, 'name': f'Player {i}', 'wara': 1.5} for i in range(25)]
        roster = {
            'active': {
                'players': players,
                'WARa': 37.5  # 25 * 1.5
            }
        }
        new_player_wara = 1.5  # Adding another 1.5 player = 26 * 1.5 = 39.0

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        assert is_valid is False
        assert projected_total == 39.0  # 26 * 1.5
        assert cap_limit == 32.0

    @pytest.mark.asyncio
    async def test_team_specific_cap(self):
        """
        Should use team's custom salary cap when provided.

        Why: Some teams have different caps (expansion, penalties, etc.)
        """
        roster = {
            'active': {
                'players': [
                    {'id': 1, 'name': 'Player 1', 'wara': 10.0},
                    {'id': 2, 'name': 'Player 2', 'wara': 10.0},
                ],
                'WARa': 20.0
            }
        }
        team = {'abbrev': 'EXP', 'salary_cap': 25.0}  # Expansion team with lower cap
        new_player_wara = 6.0  # Total = 26.0 which exceeds 25.0 cap

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara, team)

        assert is_valid is False  # Over custom 25.0 cap
        assert projected_total == 26.0  # 6 + 10 + 10 (sorted ascending)
        assert cap_limit == 25.0

    @pytest.mark.asyncio
    async def test_team_with_none_cap_uses_default(self):
        """
        Team with salary_cap=None should use default cap.

        Why: Backwards compatibility for teams without custom caps.
        """
        roster = {
            'active': {
                'players': [
                    {'id': 1, 'name': 'Player 1', 'wara': 10.0},
                ],
                'WARa': 10.0
            }
        }
        team = {'abbrev': 'STD', 'salary_cap': None}
        new_player_wara = 5.0

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara, team)

        assert is_valid is True
        assert projected_total == 15.0  # 5 + 10
        assert cap_limit == 32.0  # Default

    @pytest.mark.asyncio
    async def test_cap_counting_logic_cheapest_26(self):
        """
        Only the 26 CHEAPEST players should count toward cap.

        Why: League rules - expensive stars can be "excluded" if you have
        enough cheap depth players. This rewards roster construction.
        """
        # Create 27 players: 1 expensive star (10.0) and 26 cheap players (1.0 each)
        players = [{'id': 0, 'name': 'Star', 'wara': 10.0}]  # Expensive star
        for i in range(1, 27):
            players.append({'id': i, 'name': f'Cheap {i}', 'wara': 1.0})

        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)  # 10 + 26 = 36
            }
        }
        new_player_wara = 1.0  # Adding another cheap player

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        # With 28 players total, only cheapest 26 count
        # Sorted ascending: 27 players at 1.0, then 1 at 10.0
        # Cheapest 26 = 26 * 1.0 = 26.0 (the star is EXCLUDED)
        assert is_valid is True
        assert projected_total == 26.0
        assert cap_limit == 32.0

    @pytest.mark.asyncio
    async def test_invalid_roster_structure(self):
        """
        Invalid roster structure should raise ValueError.

        Why: Defensive programming - catch malformed data early.
        """
        with pytest.raises(ValueError, match="Invalid roster structure"):
            await validate_cap_space({}, 1.0)

        with pytest.raises(ValueError, match="Invalid roster structure"):
            await validate_cap_space(None, 1.0)

        with pytest.raises(ValueError, match="Invalid roster structure"):
            await validate_cap_space({'other': {}}, 1.0)

    @pytest.mark.asyncio
    async def test_empty_roster(self):
        """
        Empty roster should allow any player (well under cap).

        Why: First pick of draft has empty roster.
        """
        roster = {
            'active': {
                'players': [],
                'WARa': 0.0
            }
        }
        new_player_wara = 5.0

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        assert is_valid is True
        assert projected_total == 5.0

    @pytest.mark.asyncio
    async def test_tolerance_boundary(self):
        """
        Values at or just below cap + tolerance should be valid.

        Why: Floating point tolerance prevents false positives.
        """
        # Create 25 players at 1.28 WAR each = 32.0 total
        players = [{'id': i, 'name': f'Player {i}', 'wara': 1.28} for i in range(25)]
        roster = {
            'active': {
                'players': players,
                'WARa': 32.0
            }
        }

        # Adding 0.0 WAR player keeps us at exactly cap - should be valid
        is_valid, projected_total, _ = await validate_cap_space(roster, 0.0)
        assert is_valid is True
        assert abs(projected_total - 32.0) < 0.01

        # Adding 0.002 WAR player puts us just over tolerance - should be invalid
        is_valid, _, _ = await validate_cap_space(roster, 0.003)
        assert is_valid is False

    @pytest.mark.asyncio
    async def test_star_exclusion_scenario(self):
        """
        Test realistic scenario where an expensive star is excluded from cap.

        Why: This is the key feature - teams can build around stars by
        surrounding them with cheap depth players.
        """
        # 26 cheap players at 1.0 WAR each
        players = [{'id': i, 'name': f'Depth {i}', 'wara': 1.0} for i in range(26)]
        roster = {
            'active': {
                'players': players,
                'WARa': 26.0
            }
        }

        # Drafting a 10.0 WAR superstar
        # With 27 players, cheapest 26 count = 26 * 1.0 = 26.0 (star excluded!)
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 10.0)

        assert is_valid is True
        assert projected_total == 26.0  # Star is excluded from cap calculation
        assert cap_limit == 32.0


class TestFormatPickDisplay:
    """Tests for format_pick_display() function."""

    def test_format_pick_1(self):
        """First pick should display correctly."""
        result = format_pick_display(1)
        assert result == "Round 1, Pick 1 (Overall #1)"

    def test_format_pick_45(self):
        """Middle pick should display correctly."""
        result = format_pick_display(45)
        assert "Round 3" in result
        assert "Overall #45" in result

    def test_format_pick_161(self):
        """First snake pick should display correctly."""
        result = format_pick_display(161)
        assert "Round 11" in result
        assert "Overall #161" in result


class TestGetNextPickOverall:
    """Tests for get_next_pick_overall() function."""

    def test_next_pick(self):
        """Next pick should increment by 1."""
        assert get_next_pick_overall(1) == 2
        assert get_next_pick_overall(160) == 161
        assert get_next_pick_overall(512) == 513


class TestIsDraftComplete:
    """Tests for is_draft_complete() function."""

    def test_draft_not_complete(self):
        """Draft should not be complete before total picks."""
        assert is_draft_complete(1, total_picks=512) is False
        assert is_draft_complete(511, total_picks=512) is False
        assert is_draft_complete(512, total_picks=512) is False

    def test_draft_complete(self):
        """Draft should be complete after total picks."""
        assert is_draft_complete(513, total_picks=512) is True
        assert is_draft_complete(600, total_picks=512) is True


class TestGetRoundName:
    """Tests for get_round_name() function."""

    def test_round_1(self):
        """Round 1 should just say 'Round 1'."""
        assert get_round_name(1) == "Round 1"

    def test_round_11_snake_begins(self):
        """Round 11 should indicate snake draft begins."""
        result = get_round_name(11)
        assert "Round 11" in result
        assert "Snake" in result

    def test_regular_round(self):
        """Regular rounds should just show round number."""
        assert get_round_name(5) == "Round 5"
        assert get_round_name(20) == "Round 20"


class TestRealTeamModelIntegration:
    """Integration tests using the actual Team Pydantic model."""

    @pytest.mark.asyncio
    async def test_validate_cap_space_with_real_team_model(self):
        """
        validate_cap_space should work with real Team Pydantic model.

        Why: End-to-end test with actual production model.
        """
        from models.team import Team

        roster = {
            'active': {
                'players': [
                    {'id': 1, 'name': 'Star', 'wara': 8.0},
                    {'id': 2, 'name': 'Good', 'wara': 4.0},
                ],
                'WARa': 12.0
            }
        }

        # Team with custom cap of 20.0
        team = Team(
            id=1,
            abbrev='EXP',
            sname='Expansion',
            lname='Expansion Team',
            season=12,
            salary_cap=20.0
        )

        # Adding 10.0 WAR player: sorted ascending [4.0, 8.0, 10.0] = 22.0 total
        # 22.0 > 20.0 cap, so invalid
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 10.0, team)

        assert is_valid is False
        assert projected_total == 22.0  # 4 + 8 + 10
        assert cap_limit == 20.0

        # Adding 5.0 WAR player: sorted ascending [4.0, 5.0, 8.0] = 17.0 total
        # 17.0 < 20.0 cap, so valid
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 5.0, team)

        assert is_valid is True
        assert projected_total == 17.0  # 4 + 5 + 8
        assert cap_limit == 20.0

    @pytest.mark.asyncio
    async def test_realistic_draft_scenario(self):
        """
        Test a realistic draft scenario where team has built around stars.

        Why: Validates the complete workflow with real Team model and
        demonstrates the cap exclusion mechanic working as intended.
        """
        from models.team import Team

        # Team has 2 superstars (8.0, 7.0) and 25 cheap depth players (1.0 each)
        players = [
            {'id': 0, 'name': 'Superstar 1', 'wara': 8.0},
            {'id': 1, 'name': 'Superstar 2', 'wara': 7.0},
        ]
        for i in range(2, 27):
            players.append({'id': i, 'name': f'Depth {i}', 'wara': 1.0})

        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)  # 8 + 7 + 25 = 40.0
            }
        }

        team = Team(
            id=1,
            abbrev='STR',
            sname='Stars',
            lname='All-Stars Team',
            season=12,
            salary_cap=None  # Use default 32.0
        )

        # Draft another 1.0 WAR depth player
        # With 28 players, only cheapest 26 count
        # Sorted: [1.0 x 26, 7.0, 8.0] - cheapest 26 = 26 * 1.0 = 26.0
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 1.0, team)

        assert is_valid is True
        assert projected_total == 26.0  # Both superstars excluded!
        assert cap_limit == 32.0
