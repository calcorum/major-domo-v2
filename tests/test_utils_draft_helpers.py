"""
Unit tests for draft helper functions in utils/draft_helpers.py.

These tests verify:
1. calculate_pick_details() correctly handles linear and snake draft formats
2. calculate_overall_from_round_position() is the inverse of calculate_pick_details()
3. validate_cap_space() correctly validates roster cap space during draft
4. Other helper functions work correctly

Why these tests matter:
- Draft pick calculations are critical for correct draft order
- Cap space validation prevents illegal roster configurations
- These functions are used throughout the draft system

IMPORTANT: Cap validation during draft uses "max_zeroes" logic:
- Teams draft up to 32 players, then drop to 26
- max_zeroes = 32 - current_roster_size (remaining draft picks)
- players_counted = 26 - max_zeroes (how many current players count toward cap)
- This allows teams to draft expensive players knowing they'll drop cheap ones later
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


class TestValidateCapSpaceDraftBehavior:
    """
    Tests for validate_cap_space() function - DRAFT-TIME behavior.

    During the draft, the "max_zeroes" logic applies:
    - max_zeroes = 32 - projected_roster_size (remaining draft slots)
    - players_counted = 26 - max_zeroes (current players that count toward cap)
    - This allows teams to accumulate expensive players during draft knowing
      they'll drop cheap depth later
    """

    @pytest.mark.asyncio
    async def test_early_draft_no_players_count(self):
        """
        With only 2 players, no current players count toward cap during draft.

        Why: Team has 30 more picks to fill (32 - 2).
        players_counted = 26 - 30 = -4 → 0 players count
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
        new_player_wara = 10.0  # Even expensive player is allowed

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        # With 3 players total, max_zeroes = 32 - 3 = 29
        # players_counted = 26 - 29 = -3 → 0
        assert is_valid is True
        assert projected_total == 0.0  # No players count yet
        assert cap_limit == 32.0

    @pytest.mark.asyncio
    async def test_mid_draft_some_players_count(self):
        """
        With 18 players, only 13 cheapest count toward cap during draft.

        Why: Team has 13 more picks (32 - 19 after adding new player).
        players_counted = 26 - 13 = 13 players count
        """
        # Create 18 cheap depth players at 1.0 WAR each
        players = [
            {'id': i, 'name': f'Player {i}', 'wara': 1.0}
            for i in range(1, 19)
        ]
        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)
            }
        }
        new_player_wara = 1.0

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        # With 19 players total, max_zeroes = 32 - 19 = 13
        # players_counted = 26 - 13 = 13 players count
        # All 19 players at 1.0 WAR, cheapest 13 = 13.0
        assert is_valid is True
        assert projected_total == 13.0
        assert cap_limit == 32.0

    @pytest.mark.asyncio
    async def test_late_draft_pick_19_like_wai(self):
        """
        Simulate WAI scenario: 18 players, drafting 19th, with 29.5 cap.

        Why: This is the exact scenario that triggered the bug fix.
        With 19 players total:
        - max_zeroes = 32 - 19 = 13
        - players_counted = 26 - 13 = 13
        Only 13 cheapest players count, not all 19.
        """
        # Create 18 players - simulate realistic WAR values
        players = [
            {'id': 1, 'name': 'Star', 'wara': 5.0},
            {'id': 2, 'name': 'Good', 'wara': 3.5},
        ]
        # Add 16 depth players at 1.0 WAR each
        for i in range(3, 19):
            players.append({'id': i, 'name': f'Depth {i}', 'wara': 1.0})

        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)
            }
        }

        team = {'abbrev': 'WAI', 'salary_cap': 29.5}
        new_player_wara = 2.5  # Zach Neto-like player

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara, team)

        # With 19 players total:
        # max_zeroes = 32 - 19 = 13
        # players_counted = 26 - 13 = 13
        # Sorted ascending: 1.0 x 16, 2.5 (new), 3.5, 5.0
        # Cheapest 13 = 1.0 x 13 = 13.0 (only depth players count!)
        assert is_valid is True
        assert projected_total == 13.0  # 13 x 1.0 (all depth players)
        assert cap_limit == 29.5

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
    async def test_empty_roster_first_pick(self):
        """
        Empty roster (first pick) should allow any player.

        Why: With 0 players, max_zeroes = 32 - 1 = 31, players_counted = 0.
        No players count toward cap for the first pick.
        """
        roster = {
            'active': {
                'players': [],
                'WARa': 0.0
            }
        }
        new_player_wara = 10.0  # Any value should work

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        assert is_valid is True
        assert projected_total == 0.0  # No players count yet


class TestValidateCapSpacePostDraft:
    """
    Tests for validate_cap_space() function - POST-DRAFT behavior.

    After draft is complete (32 players), normal cap rules apply:
    - max_zeroes = 0 (no more draft picks)
    - players_counted = 26 (full cap counting)
    - Only cheapest 26 players count toward cap
    """

    @pytest.mark.asyncio
    async def test_full_roster_cheapest_26_count(self):
        """
        With 31 players, adding 32nd player, only cheapest 26 count.

        Why: At 32 players, max_zeroes = 0, players_counted = 26.
        Normal cap rules apply.
        """
        # Create 31 players: 5 expensive (5.0 WAR) and 26 cheap (1.0 WAR)
        players = [{'id': i, 'name': f'Expensive {i}', 'wara': 5.0} for i in range(1, 6)]
        for i in range(6, 32):
            players.append({'id': i, 'name': f'Cheap {i}', 'wara': 1.0})

        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)
            }
        }
        new_player_wara = 1.0  # Adding another cheap player

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        # With 32 players: max_zeroes = 0, players_counted = 26
        # 27 players at 1.0 WAR, 5 at 5.0 WAR
        # Sorted ascending: 1.0 x 27, then 5.0 x 5
        # Cheapest 26 = 26 x 1.0 = 26.0 (all expensive players excluded!)
        assert is_valid is True
        assert projected_total == 26.0
        assert cap_limit == 32.0

    @pytest.mark.asyncio
    async def test_full_roster_over_cap(self):
        """
        Full roster that exceeds cap should be invalid.

        Why: With 32 players and cheapest 26 exceeding cap, should fail.
        """
        # Create 31 players all at 1.5 WAR = 26 * 1.5 = 39.0 > 32.0
        players = [{'id': i, 'name': f'Player {i}', 'wara': 1.5} for i in range(1, 32)]
        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)
            }
        }
        new_player_wara = 1.5

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara)

        # 32 players at 1.5, cheapest 26 = 39.0 > 32.0
        assert is_valid is False
        assert projected_total == 39.0
        assert cap_limit == 32.0

    @pytest.mark.asyncio
    async def test_star_exclusion_post_draft(self):
        """
        After draft, expensive stars can be excluded if enough cheap depth.

        Why: This is the key feature - teams can build around stars by
        surrounding them with cheap depth players.
        """
        # 26 cheap players at 1.0 WAR each
        players = [{'id': i, 'name': f'Depth {i}', 'wara': 1.0} for i in range(26)]
        # Add 5 expensive stars at 8.0 WAR each
        for i in range(26, 31):
            players.append({'id': i, 'name': f'Star {i}', 'wara': 8.0})

        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)
            }
        }

        # Drafting another 8.0 WAR superstar
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 8.0)

        # With 32 players: max_zeroes = 0, players_counted = 26
        # 27 players at 1.0, 6 at 8.0
        # Cheapest 26 = 26 x 1.0 = 26.0 (ALL stars excluded!)
        assert is_valid is True
        assert projected_total == 26.0

    @pytest.mark.asyncio
    async def test_tolerance_boundary(self):
        """
        Values at or just below cap + tolerance should be valid.

        Why: Floating point tolerance prevents false positives.
        """
        # Create a full roster (31 players) that will hit exactly 32.0 when adding 32nd
        # With 32 players, cheapest 26 count. Need 26 players summing to ~32.0
        # 25 players at 1.28 each = 32.0, plus new 0.0 player = still 32.0 for cheapest 26
        players = [{'id': i, 'name': f'Player {i}', 'wara': 1.28} for i in range(1, 26)]
        # Add 6 expensive players that won't count (need 31 total)
        for i in range(26, 32):
            players.append({'id': i, 'name': f'Expensive {i}', 'wara': 10.0})

        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)
            }
        }

        # Adding a 0.0 WAR player to get to 32 total
        # cheapest 26 = 25 * 1.28 + 0.0 = 32.0
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 0.0)

        # With 32 players, cheapest 26 = 25 * 1.28 + 0.0 = 32.0
        assert is_valid is True
        assert abs(projected_total - 32.0) < 0.01


class TestValidateCapSpaceTeamSpecificCaps:
    """Tests for team-specific salary cap handling."""

    @pytest.mark.asyncio
    async def test_team_with_custom_cap(self):
        """
        Should use team's custom salary cap when provided.

        Why: Some teams have different caps (expansion, penalties, etc.)
        """
        # Create full roster to get normal cap counting
        players = [{'id': i, 'name': f'Player {i}', 'wara': 1.0} for i in range(31)]
        roster = {
            'active': {
                'players': players,
                'WARa': 31.0
            }
        }
        team = {'abbrev': 'EXP', 'salary_cap': 25.0}  # Lower cap
        new_player_wara = 1.0  # Total cheapest 26 = 26.0 > 25.0 cap

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara, team)

        assert is_valid is False  # Over custom 25.0 cap
        assert projected_total == 26.0  # 26 * 1.0
        assert cap_limit == 25.0

    @pytest.mark.asyncio
    async def test_team_with_none_cap_uses_default(self):
        """
        Team with salary_cap=None should use default cap.

        Why: Backwards compatibility for teams without custom caps.
        """
        players = [{'id': i, 'name': f'Player {i}', 'wara': 1.0} for i in range(31)]
        roster = {
            'active': {
                'players': players,
                'WARa': 31.0
            }
        }
        team = {'abbrev': 'STD', 'salary_cap': None}
        new_player_wara = 1.0

        is_valid, projected_total, cap_limit = await validate_cap_space(roster, new_player_wara, team)

        assert is_valid is True  # 26.0 < 32.0 default cap
        assert projected_total == 26.0
        assert cap_limit == 32.0  # Default


class TestValidateCapSpaceRealTeamModel:
    """Integration tests using the actual Team Pydantic model."""

    @pytest.mark.asyncio
    async def test_validate_cap_space_with_real_team_model(self):
        """
        validate_cap_space should work with real Team Pydantic model.

        Why: End-to-end test with actual production model.
        """
        from models.team import Team

        # Full roster for normal cap counting
        players = [{'id': i, 'name': f'Player {i}', 'wara': 1.0} for i in range(31)]
        roster = {
            'active': {
                'players': players,
                'WARa': 31.0
            }
        }

        # Team with custom cap of 25.0
        team = Team(
            id=1,
            abbrev='EXP',
            sname='Expansion',
            lname='Expansion Team',
            season=12,
            salary_cap=25.0
        )

        # Adding 1.0 WAR player: cheapest 26 = 26.0 > 25.0 cap
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 1.0, team)

        assert is_valid is False  # Over custom 25.0 cap
        assert projected_total == 26.0
        assert cap_limit == 25.0

    @pytest.mark.asyncio
    async def test_realistic_draft_scenario_full_roster(self):
        """
        Test a realistic scenario with full roster and star exclusion.

        Why: Validates the complete workflow with real Team model and
        demonstrates the cap exclusion mechanic working as intended.
        """
        from models.team import Team

        # Team has completed draft with 2 superstars and 29 depth players
        players = [
            {'id': 0, 'name': 'Superstar 1', 'wara': 8.0},
            {'id': 1, 'name': 'Superstar 2', 'wara': 7.0},
        ]
        for i in range(2, 31):
            players.append({'id': i, 'name': f'Depth {i}', 'wara': 1.0})

        roster = {
            'active': {
                'players': players,
                'WARa': sum(p['wara'] for p in players)
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

        # Draft final player (1.0 WAR depth)
        is_valid, projected_total, cap_limit = await validate_cap_space(roster, 1.0, team)

        # With 32 players: max_zeroes = 0, players_counted = 26
        # 30 players at 1.0, 2 at 7.0 and 8.0
        # Cheapest 26 = 26 x 1.0 = 26.0 (both superstars excluded!)
        assert is_valid is True
        assert projected_total == 26.0
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
