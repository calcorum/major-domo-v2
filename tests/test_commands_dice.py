"""
Tests for dice rolling commands

Validates dice rolling functionality, parsing, and embed creation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord
from discord.ext import commands

from commands.dice.rolls import DiceRollCommands, DiceRoll


class TestDiceRollCommands:
    """Test dice rolling command functionality."""

    @pytest.fixture
    def bot(self):
        """Create a mock bot instance."""
        bot = AsyncMock(spec=commands.Bot)
        return bot

    @pytest.fixture
    def dice_cog(self, bot):
        """Create DiceRollCommands cog instance."""
        return DiceRollCommands(bot)

    @pytest.fixture
    def mock_interaction(self):
        """Create a mock Discord interaction."""
        interaction = AsyncMock(spec=discord.Interaction)

        # Mock the user
        user = MagicMock(spec=discord.User)
        user.display_name = "TestUser"
        user.display_avatar.url = "https://example.com/avatar.png"
        interaction.user = user

        # Mock response methods
        interaction.response.defer = AsyncMock()
        interaction.followup.send = AsyncMock()

        return interaction

    @pytest.fixture
    def mock_context(self):
        """Create a mock Discord context for prefix commands."""
        ctx = AsyncMock(spec=commands.Context)

        # Mock the author (user)
        author = MagicMock(spec=discord.User)
        author.display_name = "TestUser"
        author.display_avatar.url = "https://example.com/avatar.png"
        author.id = 12345  # Add user ID
        ctx.author = author

        # Mock send method
        ctx.send = AsyncMock()

        return ctx

    def test_parse_valid_dice_notation(self, dice_cog):
        """Test parsing valid dice notation."""
        # Test basic notation
        results = dice_cog._parse_and_roll_multiple_dice("2d6")
        assert len(results) == 1
        result = results[0]
        assert result.num_dice == 2
        assert result.die_sides == 6
        assert len(result.rolls) == 2
        assert all(1 <= roll <= 6 for roll in result.rolls)
        assert result.total == sum(result.rolls)

        # Test single die
        results = dice_cog._parse_and_roll_multiple_dice("1d20")
        assert len(results) == 1
        result = results[0]
        assert result.num_dice == 1
        assert result.die_sides == 20
        assert len(result.rolls) == 1
        assert 1 <= result.rolls[0] <= 20

    def test_parse_invalid_dice_notation(self, dice_cog):
        """Test parsing invalid dice notation."""
        # Invalid formats
        assert dice_cog._parse_and_roll_multiple_dice("invalid") == []
        assert dice_cog._parse_and_roll_multiple_dice("2d") == []
        assert dice_cog._parse_and_roll_multiple_dice("d6") == []
        assert dice_cog._parse_and_roll_multiple_dice("2d6+5") == []  # No modifiers in simple version
        assert dice_cog._parse_and_roll_multiple_dice("") == []

        # Out of bounds values
        assert dice_cog._parse_and_roll_multiple_dice("0d6") == []  # num_dice < 1
        assert dice_cog._parse_and_roll_multiple_dice("2d1") == []  # die_sides < 2
        assert dice_cog._parse_and_roll_multiple_dice("101d6") == []  # num_dice > 100
        assert dice_cog._parse_and_roll_multiple_dice("1d1001") == []  # die_sides > 1000

    def test_parse_multiple_dice(self, dice_cog):
        """Test parsing multiple dice rolls."""
        # Test multiple rolls
        results = dice_cog._parse_and_roll_multiple_dice("1d6;2d8;1d20")
        assert len(results) == 3

        assert results[0].dice_notation == '1d6'
        assert results[0].num_dice == 1
        assert results[0].die_sides == 6

        assert results[1].dice_notation == '2d8'
        assert results[1].num_dice == 2
        assert results[1].die_sides == 8

        assert results[2].dice_notation == '1d20'
        assert results[2].num_dice == 1
        assert results[2].die_sides == 20

    def test_parse_case_insensitive(self, dice_cog):
        """Test that dice notation parsing is case insensitive."""
        result_lower = dice_cog._parse_and_roll_multiple_dice("2d6")
        result_upper = dice_cog._parse_and_roll_multiple_dice("2D6")

        assert len(result_lower) == 1
        assert len(result_upper) == 1
        assert result_lower[0].num_dice == result_upper[0].num_dice
        assert result_lower[0].die_sides == result_upper[0].die_sides

    def test_parse_whitespace_handling(self, dice_cog):
        """Test that whitespace is handled properly."""
        results = dice_cog._parse_and_roll_multiple_dice("  2d6  ")
        assert len(results) == 1
        assert results[0].num_dice == 2
        assert results[0].die_sides == 6

        results = dice_cog._parse_and_roll_multiple_dice("2 d 6")
        assert len(results) == 1
        assert results[0].num_dice == 2
        assert results[0].die_sides == 6

    @pytest.mark.asyncio
    async def test_roll_dice_valid_input(self, dice_cog, mock_interaction):
        """Test roll_dice command with valid input."""
        await dice_cog.roll_dice.callback(dice_cog, mock_interaction, "2d6")

        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()

        # Verify followup was sent with embed
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs

        # Verify embed is a Discord embed
        embed = call_args.kwargs['embed']
        assert isinstance(embed, discord.Embed)
        assert embed.title == "🎲 Dice Roll"

    @pytest.mark.asyncio
    async def test_roll_dice_invalid_input(self, dice_cog, mock_interaction):
        """Test roll_dice command with invalid input."""
        await dice_cog.roll_dice.callback(dice_cog, mock_interaction, "invalid")

        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()

        # Verify error message was sent
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert "Invalid dice notation" in call_args.args[0]
        assert call_args.kwargs['ephemeral'] is True

    def test_create_multi_roll_embed_single_die(self, dice_cog, mock_interaction):
        """Test embed creation for single die roll."""
        roll_results = [
            DiceRoll(
                dice_notation='1d20',
                num_dice=1,
                die_sides=20,
                rolls=[15],
                total=15
            )
        ]

        embed = dice_cog._create_multi_roll_embed("1d20", roll_results, mock_interaction.user)

        assert embed.title == "🎲 Dice Roll"
        assert embed.author.name == "TestUser"
        assert embed.author.icon_url == "https://example.com/avatar.png"

        # Check the formatted field content
        assert len(embed.fields) == 1
        assert embed.fields[0].name == 'Result'
        expected_value = "```md\n# 15\nDetails:[1d20 (15)]```"
        assert embed.fields[0].value == expected_value

    def test_create_multi_roll_embed_multiple_dice(self, dice_cog, mock_interaction):
        """Test embed creation for multiple dice rolls."""
        roll_results = [
            DiceRoll(
                dice_notation='1d6',
                num_dice=1,
                die_sides=6,
                rolls=[5],
                total=5
            ),
            DiceRoll(
                dice_notation='2d6',
                num_dice=2,
                die_sides=6,
                rolls=[5, 6],
                total=11
            ),
            DiceRoll(
                dice_notation='1d20',
                num_dice=1,
                die_sides=20,
                rolls=[13],
                total=13
            )
        ]

        embed = dice_cog._create_multi_roll_embed("1d6;2d6;1d20", roll_results, mock_interaction.user)

        assert embed.title == "🎲 Dice Roll"
        assert embed.author.name == "TestUser"

        # Check the formatted field content matches the expected format
        assert len(embed.fields) == 1
        assert embed.fields[0].name == 'Result'
        expected_value = "```md\n# 5,11,13\nDetails:[1d6;2d6;1d20 (5 - 5 6 - 13)]```"
        assert embed.fields[0].value == expected_value

    def test_dice_roll_randomness(self, dice_cog):
        """Test that dice rolls produce different results."""
        results = []
        for _ in range(20):  # Roll 20 times
            result = dice_cog._parse_and_roll_multiple_dice("1d20")
            results.append(result[0].rolls[0])

        # Should have some variation in results (very unlikely all 20 rolls are the same)
        unique_results = set(results)
        assert len(unique_results) > 1, f"All rolls were the same: {results}"

    def test_dice_boundaries(self, dice_cog):
        """Test dice rolling at boundaries."""
        # Test maximum allowed dice
        results = dice_cog._parse_and_roll_multiple_dice("100d2")
        assert len(results) == 1
        result = results[0]
        assert len(result.rolls) == 100
        assert all(roll in [1, 2] for roll in result.rolls)

        # Test maximum die size
        results = dice_cog._parse_and_roll_multiple_dice("1d1000")
        assert len(results) == 1
        result = results[0]
        assert 1 <= result.rolls[0] <= 1000

        # Test minimum valid values
        results = dice_cog._parse_and_roll_multiple_dice("1d2")
        assert len(results) == 1
        result = results[0]
        assert result.rolls[0] in [1, 2]

    @pytest.mark.asyncio
    async def test_prefix_command_valid_input(self, dice_cog, mock_context):
        """Test prefix command with valid input."""
        await dice_cog.roll_dice_prefix.callback(dice_cog, mock_context, dice="2d6")

        # Verify send was called with embed
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        # Check if embed was passed as positional or keyword argument
        if call_args.args:
            embed = call_args.args[0]
        else:
            embed = call_args.kwargs.get('embed')
        assert isinstance(embed, discord.Embed)
        assert embed.title == "🎲 Dice Roll"

    @pytest.mark.asyncio
    async def test_prefix_command_invalid_input(self, dice_cog, mock_context):
        """Test prefix command with invalid input."""
        await dice_cog.roll_dice_prefix.callback(dice_cog, mock_context, dice="invalid")

        # Verify error message was sent
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        error_msg = call_args[0][0]
        assert "Invalid dice notation" in error_msg

    @pytest.mark.asyncio
    async def test_prefix_command_no_input(self, dice_cog, mock_context):
        """Test prefix command with no input."""
        await dice_cog.roll_dice_prefix.callback(dice_cog, mock_context, dice=None)

        # Verify usage message was sent
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        usage_msg = call_args[0][0]
        assert "Please provide dice notation" in usage_msg

    @pytest.mark.asyncio
    async def test_prefix_command_multiple_dice(self, dice_cog, mock_context):
        """Test prefix command with multiple dice rolls."""
        await dice_cog.roll_dice_prefix.callback(dice_cog, mock_context, dice="1d6;2d8;1d20")

        # Verify send was called with embed
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        # Check if embed was passed as positional or keyword argument
        if call_args.args:
            embed = call_args.args[0]
        else:
            embed = call_args.kwargs.get('embed')

        assert isinstance(embed, discord.Embed)
        assert embed.title == "🎲 Dice Roll"
        # Should have summary format with 3 totals in field
        assert len(embed.fields) == 1
        assert embed.fields[0].name == 'Result'
        assert embed.fields[0].value.startswith("```md\n#")
        assert "Details:[1d6;2d8;1d20" in embed.fields[0].value

    def test_prefix_command_attributes(self, dice_cog):
        """Test that prefix command has correct attributes."""
        # Check command exists and has correct name
        assert hasattr(dice_cog, 'roll_dice_prefix')
        command = dice_cog.roll_dice_prefix
        assert command.name == "roll"
        assert command.aliases == ["r", "dice"]

    @pytest.mark.asyncio
    async def test_ab_command_slash(self, dice_cog, mock_interaction):
        """Test ab slash command."""
        await dice_cog.ab_dice.callback(dice_cog, mock_interaction)

        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()

        # Verify followup was sent with embed
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs

        # Verify embed has the correct format
        embed = call_args.kwargs['embed']
        assert isinstance(embed, discord.Embed)
        assert embed.title == "At bat roll for TestUser"
        assert len(embed.fields) == 1
        assert "Details:[1d6;2d6;1d20" in embed.fields[0].value

    @pytest.mark.asyncio
    async def test_ab_command_prefix(self, dice_cog, mock_context):
        """Test ab prefix command."""
        await dice_cog.ab_dice_prefix.callback(dice_cog, mock_context)

        # Verify send was called with embed
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args

        # Check if embed was passed as positional or keyword argument
        if call_args.args:
            embed = call_args.args[0]
        else:
            embed = call_args.kwargs.get('embed')

        assert isinstance(embed, discord.Embed)
        assert embed.title == "At bat roll for TestUser"
        assert len(embed.fields) == 1
        assert "Details:[1d6;2d6;1d20" in embed.fields[0].value

    def test_ab_command_attributes(self, dice_cog):
        """Test that ab prefix command has correct attributes."""
        # Check command exists and has correct name
        assert hasattr(dice_cog, 'ab_dice_prefix')
        command = dice_cog.ab_dice_prefix
        assert command.name == "ab"
        assert command.aliases == ["atbat"]

    def test_ab_command_dice_combination(self, dice_cog):
        """Test that ab command uses the correct dice combination."""
        dice_notation = "1d6;2d6;1d20"
        results = dice_cog._parse_and_roll_multiple_dice(dice_notation)

        # Should have 3 dice groups
        assert len(results) == 3

        # Check each dice type
        assert results[0].dice_notation == '1d6'
        assert results[0].num_dice == 1
        assert results[0].die_sides == 6

        assert results[1].dice_notation == '2d6'
        assert results[1].num_dice == 2
        assert results[1].die_sides == 6

        assert results[2].dice_notation == '1d20'
        assert results[2].num_dice == 1
        assert results[2].die_sides == 20

    # Fielding command tests
    @pytest.mark.asyncio
    async def test_fielding_command_slash(self, dice_cog, mock_interaction):
        """Test fielding slash command with valid position."""
        # Mock a position choice
        position_choice = MagicMock()
        position_choice.value = '3B'

        await dice_cog.fielding_roll.callback(dice_cog, mock_interaction, position_choice)

        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()

        # Verify followup was sent with embed
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs

        # Verify embed has the correct format
        embed = call_args.kwargs['embed']
        assert isinstance(embed, discord.Embed)
        assert embed.title == "SA Fielding roll for TestUser"
        assert len(embed.fields) >= 2  # Range and Error fields

    @pytest.mark.asyncio
    async def test_fielding_command_prefix_valid(self, dice_cog, mock_context):
        """Test fielding prefix command with valid position."""
        await dice_cog.fielding_roll_prefix.callback(dice_cog, mock_context, "SS")

        # Verify send was called with embed
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args

        # Check if embed was passed as positional or keyword argument
        if call_args.args:
            embed = call_args.args[0]
        else:
            embed = call_args.kwargs.get('embed')

        assert isinstance(embed, discord.Embed)
        assert embed.title == "SA Fielding roll for TestUser"
        assert len(embed.fields) >= 2  # Range and Error fields

    @pytest.mark.asyncio
    async def test_fielding_command_prefix_no_position(self, dice_cog, mock_context):
        """Test fielding prefix command with no position."""
        await dice_cog.fielding_roll_prefix.callback(dice_cog, mock_context, None)

        # Verify error message was sent
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        error_msg = call_args[0][0]
        assert "Please specify a position" in error_msg

    @pytest.mark.asyncio
    async def test_fielding_command_prefix_invalid_position(self, dice_cog, mock_context):
        """Test fielding prefix command with invalid position."""
        await dice_cog.fielding_roll_prefix.callback(dice_cog, mock_context, "INVALID")

        # Verify error message was sent
        mock_context.send.assert_called_once()
        call_args = mock_context.send.call_args
        error_msg = call_args[0][0]
        assert "Invalid position" in error_msg

    def test_fielding_command_attributes(self, dice_cog):
        """Test that fielding prefix command has correct attributes."""
        # Check command exists and has correct name
        assert hasattr(dice_cog, 'fielding_roll_prefix')
        command = dice_cog.fielding_roll_prefix
        assert command.name == "f"
        assert command.aliases == ["fielding", "saf"]

    def test_fielding_range_charts(self, dice_cog):
        """Test that fielding range charts work for all positions."""
        # Test infield range (applies to 1B, 2B, 3B, SS)
        infield_result = dice_cog._get_infield_range(10)
        assert isinstance(infield_result, str)
        assert len(infield_result) > 0

        # Test outfield range (applies to LF, CF, RF)
        outfield_result = dice_cog._get_outfield_range(10)
        assert isinstance(outfield_result, str)
        assert len(outfield_result) > 0

        # Test catcher range
        catcher_result = dice_cog._get_catcher_range(10)
        assert isinstance(catcher_result, str)
        assert len(catcher_result) > 0

    def test_fielding_error_charts(self, dice_cog):
        """Test that error charts work for all positions."""
        # Test all position error methods
        test_total = 10

        # Test 1B error
        error_1b = dice_cog._get_1b_error(test_total)
        assert isinstance(error_1b, str)

        # Test 2B error
        error_2b = dice_cog._get_2b_error(test_total)
        assert isinstance(error_2b, str)

        # Test 3B error
        error_3b = dice_cog._get_3b_error(test_total)
        assert isinstance(error_3b, str)

        # Test SS error
        error_ss = dice_cog._get_ss_error(test_total)
        assert isinstance(error_ss, str)

        # Test corner OF error
        error_corner = dice_cog._get_corner_of_error(test_total)
        assert isinstance(error_corner, str)

        # Test CF error
        error_cf = dice_cog._get_cf_error(test_total)
        assert isinstance(error_cf, str)

        # Test catcher error
        error_catcher = dice_cog._get_catcher_error(test_total)
        assert isinstance(error_catcher, str)

    def test_get_error_result_all_positions(self, dice_cog):
        """Test _get_error_result for all valid positions."""
        test_total = 12
        positions = ['1B', '2B', '3B', 'SS', 'LF', 'RF', 'CF', 'C']

        for position in positions:
            result = dice_cog._get_error_result(position, test_total)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_get_error_result_invalid_position(self, dice_cog):
        """Test _get_error_result with invalid position raises error."""
        with pytest.raises(ValueError, match="Unknown position"):
            dice_cog._get_error_result("INVALID", 10)

    def test_fielding_dice_combination(self, dice_cog):
        """Test that fielding uses correct dice combination (1d20;3d6)."""
        dice_notation = "1d20;3d6"
        results = dice_cog._parse_and_roll_multiple_dice(dice_notation)

        # Should have 2 dice groups
        assert len(results) == 2

        # Check 1d20
        assert results[0].dice_notation == '1d20'
        assert results[0].num_dice == 1
        assert results[0].die_sides == 20

        # Check 3d6
        assert results[1].dice_notation == '3d6'
        assert results[1].num_dice == 3
        assert results[1].die_sides == 6

    def test_weighted_scout_dice_batter(self, dice_cog):
        """Test that batter scout dice always rolls 1-3 for first d6."""
        # Roll 20 times to ensure consistency
        for _ in range(20):
            results = dice_cog._roll_weighted_scout_dice("batter")

            # Should have 3 dice groups (1d6, 2d6, 1d20)
            assert len(results) == 3

            # First d6 should ALWAYS be 1-3 for batter
            first_d6 = results[0].rolls[0]
            assert 1 <= first_d6 <= 3, f"Batter first d6 was {first_d6}, expected 1-3"

            # Second roll (2d6) should be normal
            assert results[1].num_dice == 2
            assert results[1].die_sides == 6
            assert all(1 <= roll <= 6 for roll in results[1].rolls)

            # Third roll (1d20) should be normal
            assert results[2].num_dice == 1
            assert results[2].die_sides == 20
            assert 1 <= results[2].rolls[0] <= 20

    def test_weighted_scout_dice_pitcher(self, dice_cog):
        """Test that pitcher scout dice always rolls 4-6 for first d6."""
        # Roll 20 times to ensure consistency
        for _ in range(20):
            results = dice_cog._roll_weighted_scout_dice("pitcher")

            # Should have 3 dice groups (1d6, 2d6, 1d20)
            assert len(results) == 3

            # First d6 should ALWAYS be 4-6 for pitcher
            first_d6 = results[0].rolls[0]
            assert 4 <= first_d6 <= 6, f"Pitcher first d6 was {first_d6}, expected 4-6"

            # Second roll (2d6) should be normal
            assert results[1].num_dice == 2
            assert results[1].die_sides == 6
            assert all(1 <= roll <= 6 for roll in results[1].rolls)

            # Third roll (1d20) should be normal
            assert results[2].num_dice == 1
            assert results[2].die_sides == 20
            assert 1 <= results[2].rolls[0] <= 20

    @pytest.mark.asyncio
    async def test_scout_command_batter(self, dice_cog, mock_interaction):
        """Test scout slash command with batter card type."""
        # Mock a card_type choice
        card_type_choice = MagicMock()
        card_type_choice.value = 'batter'
        card_type_choice.name = 'Batter'

        await dice_cog.scout_dice.callback(dice_cog, mock_interaction, card_type_choice)

        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()

        # Verify followup was sent with embed
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs

        # Verify embed has the correct format
        embed = call_args.kwargs['embed']
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Scouting roll for TestUser (Batter)"
        assert len(embed.fields) == 1
        assert "Details:[1d6;2d6;1d20" in embed.fields[0].value

    @pytest.mark.asyncio
    async def test_scout_command_pitcher(self, dice_cog, mock_interaction):
        """Test scout slash command with pitcher card type."""
        # Mock a card_type choice
        card_type_choice = MagicMock()
        card_type_choice.value = 'pitcher'
        card_type_choice.name = 'Pitcher'

        await dice_cog.scout_dice.callback(dice_cog, mock_interaction, card_type_choice)

        # Verify response was deferred
        mock_interaction.response.defer.assert_called_once()

        # Verify followup was sent with embed
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert 'embed' in call_args.kwargs

        # Verify embed has the correct format
        embed = call_args.kwargs['embed']
        assert isinstance(embed, discord.Embed)
        assert embed.title == "Scouting roll for TestUser (Pitcher)"
        assert len(embed.fields) == 1
        assert "Details:[1d6;2d6;1d20" in embed.fields[0].value