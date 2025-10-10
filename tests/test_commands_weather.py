"""
Tests for Weather Command (Discord interactions)

Validates weather command functionality, team resolution, and embed creation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import discord

from commands.utilities.weather import WeatherCommands
from tests.factories import TeamFactory, GameFactory, CurrentFactory


class TestWeatherCommands:
    """Test WeatherCommands Discord command functionality."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock Discord bot."""
        bot = MagicMock()
        bot.user = MagicMock()
        bot.user.id = 123456789
        bot.get_emoji = MagicMock(return_value=None)  # Default: no custom emoji
        return bot

    @pytest.fixture
    def commands_cog(self, mock_bot):
        """Create WeatherCommands cog instance."""
        return WeatherCommands(mock_bot)

    @pytest.fixture
    def mock_interaction(self):
        """Create mock Discord interaction."""
        interaction = AsyncMock()
        interaction.user = MagicMock()
        interaction.user.id = 258104532423147520
        interaction.user.name = "TestUser"
        interaction.response = AsyncMock()
        interaction.followup = AsyncMock()

        # Mock text channel
        interaction.channel = MagicMock(spec=discord.TextChannel)
        interaction.channel.name = "test-channel"

        return interaction

    @pytest.fixture
    def mock_team(self):
        """Create mock team data."""
        return TeamFactory.create(
            id=499,
            abbrev='NYY',
            sname='Yankees',
            lname='New York Yankees',
            season=12,
            color='a6ce39',
            stadium='https://example.com/yankee-stadium.jpg',
            thumbnail='https://example.com/yankee-thumbnail.png'
        )

    @pytest.fixture
    def mock_current(self):
        """Create mock current league state."""
        return CurrentFactory.create(
            week=10,
            season=12,
            freeze=False,
            trade_deadline=14,
            playoffs_begin=19
        )

    @pytest.fixture
    def mock_games(self):
        """Create mock game schedule."""
        # Create teams for the games
        yankees = TeamFactory.create(id=499, abbrev='NYY', sname='Yankees', lname='New York Yankees', season=12)
        red_sox = TeamFactory.create(id=500, abbrev='BOS', sname='Red Sox', lname='Boston Red Sox', season=12)

        # 2 completed games, 2 upcoming games
        games = [
            GameFactory.completed(id=1, season=12, week=10, game_num=1, away_team=yankees, home_team=red_sox, away_score=5, home_score=3),
            GameFactory.completed(id=2, season=12, week=10, game_num=2, away_team=yankees, home_team=red_sox, away_score=2, home_score=7),
            GameFactory.upcoming(id=3, season=12, week=10, game_num=3, away_team=yankees, home_team=red_sox),
            GameFactory.upcoming(id=4, season=12, week=10, game_num=4, away_team=yankees, home_team=red_sox),
        ]
        return games

    @pytest.mark.asyncio
    async def test_weather_explicit_team(self, commands_cog, mock_interaction, mock_team, mock_current, mock_games):
        """Test weather command with explicit team abbreviation."""
        with patch('commands.utilities.weather.league_service') as mock_league_service, \
             patch('commands.utilities.weather.schedule_service') as mock_schedule_service, \
             patch('commands.utilities.weather.team_service') as mock_team_service:

            # Mock service responses
            mock_league_service.get_current_state = AsyncMock(return_value=mock_current)
            mock_schedule_service.get_week_schedule = AsyncMock(return_value=mock_games)
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=mock_team)

            # Execute command
            await commands_cog.weather.callback(commands_cog, mock_interaction, team_abbrev='NYY')

            # Verify interaction flow
            mock_interaction.response.defer.assert_called_once()
            mock_interaction.followup.send.assert_called_once()

            # Verify team lookup
            mock_team_service.get_team_by_abbrev.assert_called_once_with('NYY', 12)

            # Check embed was sent
            embed_call = mock_interaction.followup.send.call_args
            assert 'embed' in embed_call.kwargs
            embed = embed_call.kwargs['embed']
            assert embed.title == "🌤️ Weather Check"

    @pytest.mark.asyncio
    async def test_weather_channel_name_resolution(self, commands_cog, mock_interaction, mock_team, mock_current, mock_games):
        """Test weather command resolving team from channel name."""
        # Set channel name to format: <abbrev>-<park name>
        mock_interaction.channel.name = "NYY-Yankee-Stadium"

        with patch('commands.utilities.weather.league_service') as mock_league_service, \
             patch('commands.utilities.weather.schedule_service') as mock_schedule_service, \
             patch('commands.utilities.weather.team_service') as mock_team_service, \
             patch('commands.utilities.weather.get_user_major_league_team') as mock_get_team:

            mock_league_service.get_current_state = AsyncMock(return_value=mock_current)
            mock_schedule_service.get_week_schedule = AsyncMock(return_value=mock_games)
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=mock_team)
            mock_get_team.return_value = None

            # Execute without explicit team parameter
            await commands_cog.weather.callback(commands_cog, mock_interaction, team_abbrev=None)

            # Should resolve team from channel name "NYY-Yankee-Stadium" -> "NYY"
            mock_team_service.get_team_by_abbrev.assert_called_once_with('NYY', 12)
            mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_user_owned_team_fallback(self, commands_cog, mock_interaction, mock_team, mock_current, mock_games):
        """Test weather command falling back to user's owned team."""
        # Set channel name that won't match a team
        mock_interaction.channel.name = "general-chat"

        with patch('commands.utilities.weather.league_service') as mock_league_service, \
             patch('commands.utilities.weather.schedule_service') as mock_schedule_service, \
             patch('commands.utilities.weather.team_service') as mock_team_service, \
             patch('commands.utilities.weather.get_user_major_league_team') as mock_get_team:

            mock_league_service.get_current_state = AsyncMock(return_value=mock_current)
            mock_schedule_service.get_week_schedule = AsyncMock(return_value=mock_games)
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=None)
            mock_get_team.return_value = mock_team

            await commands_cog.weather.callback(commands_cog, mock_interaction, team_abbrev=None)

            # Should fall back to user ownership
            mock_get_team.assert_called_once_with(258104532423147520, 12)
            mock_interaction.followup.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_weather_no_team_found(self, commands_cog, mock_interaction, mock_current):
        """Test weather command when no team can be resolved."""
        with patch('commands.utilities.weather.league_service') as mock_league_service, \
             patch('commands.utilities.weather.team_service') as mock_team_service, \
             patch('commands.utilities.weather.get_user_major_league_team') as mock_get_team:

            mock_league_service.get_current_state = AsyncMock(return_value=mock_current)
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=None)
            mock_get_team.return_value = None

            await commands_cog.weather.callback(commands_cog, mock_interaction, team_abbrev=None)

            # Should send error message
            embed_call = mock_interaction.followup.send.call_args
            embed = embed_call.kwargs['embed']
            assert "Team Not Found" in embed.title
            assert "Could not find a team" in embed.description

    @pytest.mark.asyncio
    async def test_weather_league_state_unavailable(self, commands_cog, mock_interaction):
        """Test weather command when league state is unavailable."""
        with patch('commands.utilities.weather.league_service') as mock_league_service:
            mock_league_service.get_current_state = AsyncMock(return_value=None)

            await commands_cog.weather.callback(commands_cog, mock_interaction)

            # Should send error about league state
            embed_call = mock_interaction.followup.send.call_args
            embed = embed_call.kwargs['embed']
            assert "League State Unavailable" in embed.title

    @pytest.mark.asyncio
    async def test_season_display_spring(self, commands_cog):
        """Test season display for spring (weeks 1-5)."""
        assert commands_cog._get_season_display(1) == "🌼 Spring"
        assert commands_cog._get_season_display(3) == "🌼 Spring"
        assert commands_cog._get_season_display(5) == "🌼 Spring"

    @pytest.mark.asyncio
    async def test_season_display_summer(self, commands_cog):
        """Test season display for summer (weeks 6-14)."""
        assert commands_cog._get_season_display(6) == "🏖️ Summer"
        assert commands_cog._get_season_display(10) == "🏖️ Summer"
        assert commands_cog._get_season_display(14) == "🏖️ Summer"

    @pytest.mark.asyncio
    async def test_season_display_fall(self, commands_cog):
        """Test season display for fall (weeks 15+)."""
        assert commands_cog._get_season_display(15) == "🍂 Fall"
        assert commands_cog._get_season_display(18) == "🍂 Fall"
        assert commands_cog._get_season_display(20) == "🍂 Fall"

    @pytest.mark.asyncio
    async def test_time_of_day_zero_games_played(self, commands_cog, mock_games):
        """Test time of day when 0 games have been played (non-division week)."""
        # Filter to only upcoming games (no scores)
        upcoming_games = [g for g in mock_games if not g.is_completed]

        time_of_day = commands_cog._get_time_of_day(upcoming_games, week=10)
        assert time_of_day == "🌙 Night"

    @pytest.mark.asyncio
    async def test_time_of_day_one_game_played(self, commands_cog, mock_games):
        """Test time of day when 1 game has been played (non-division week)."""
        # Take first game only (completed)
        one_game = [mock_games[0]]

        time_of_day = commands_cog._get_time_of_day(one_game, week=10)
        assert time_of_day == "🌞 Day"

    @pytest.mark.asyncio
    async def test_time_of_day_two_games_played(self, commands_cog, mock_games):
        """Test time of day when 2 games have been played."""
        # Take first two games (both completed)
        two_games = mock_games[:2]

        time_of_day = commands_cog._get_time_of_day(two_games, week=10)
        assert time_of_day == "🌙 Night"

    @pytest.mark.asyncio
    async def test_time_of_day_three_games_played(self, commands_cog, mock_games):
        """Test time of day when 3 games have been played."""
        # Mark third game as completed
        games = list(mock_games)
        games[2].away_score = 4
        games[2].home_score = 2

        time_of_day = commands_cog._get_time_of_day(games, week=10)
        assert time_of_day == "🌞 Day"

    @pytest.mark.asyncio
    async def test_time_of_day_division_week(self, commands_cog, mock_games):
        """Test time of day logic in division week."""
        # Division week 6, 1 game played
        one_game = [mock_games[0]]

        time_of_day = commands_cog._get_time_of_day(one_game, week=6)
        # In division week, 1 game played = Night (not Day)
        assert time_of_day == "🌙 Night"

    @pytest.mark.asyncio
    async def test_time_of_day_no_games_scheduled(self, commands_cog):
        """Test time of day when no games are scheduled."""
        # Regular week
        time_of_day = commands_cog._get_time_of_day([], week=10)
        assert time_of_day == "🌙 Night / 🌞 Day / 🌙 Night / 🌞 Day"

        # Division week
        time_of_day = commands_cog._get_time_of_day([], week=6)
        assert time_of_day == "🌙 Night / 🌙 Night / 🌙 Night / 🌞 Day"

    @pytest.mark.asyncio
    async def test_weather_roll(self, commands_cog):
        """Test weather roll generates valid d20 result."""
        # Test multiple rolls to ensure they're all in valid range
        for _ in range(100):
            roll = commands_cog._roll_weather()
            assert 1 <= roll <= 20

    @pytest.mark.asyncio
    async def test_create_weather_embed(self, commands_cog, mock_team, mock_current):
        """Test weather embed creation."""
        embed = commands_cog._create_weather_embed(
            team=mock_team,
            current=mock_current,
            season_display="🏖️ Summer",
            time_of_day="🌙 Night",
            weather_roll=14,
            games_played=2,
            total_games=4,
            username="TestUser"
        )

        # Check embed basics
        assert isinstance(embed, discord.Embed)
        assert embed.title == "🌤️ Weather Check"
        assert embed.color.value == int(mock_team.color, 16)

        # Check fields
        field_names = [field.name for field in embed.fields]
        assert "Season" in field_names
        assert "Time of Day" in field_names
        assert "Week" in field_names
        assert "Weather roll for TestUser" in field_names

        # Check field values
        season_field = next(f for f in embed.fields if f.name == "Season")
        assert season_field.value == "🏖️ Summer"

        time_field = next(f for f in embed.fields if f.name == "Time of Day")
        assert time_field.value == "🌙 Night"

        week_field = next(f for f in embed.fields if f.name == "Week")
        assert "10" in week_field.value
        assert "2/4" in week_field.value

        roll_field = next(f for f in embed.fields if "Weather roll" in f.name)
        assert "14" in roll_field.value
        assert "1d20" in roll_field.value

        # Check stadium image
        assert embed.image.url == mock_team.stadium

    @pytest.mark.asyncio
    async def test_full_weather_workflow(self, commands_cog, mock_interaction, mock_team, mock_current, mock_games):
        """Test complete weather workflow with realistic data."""
        with patch('commands.utilities.weather.league_service') as mock_league_service, \
             patch('commands.utilities.weather.schedule_service') as mock_schedule_service, \
             patch('commands.utilities.weather.team_service') as mock_team_service:

            mock_league_service.get_current_state = AsyncMock(return_value=mock_current)
            mock_schedule_service.get_week_schedule = AsyncMock(return_value=mock_games)
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=mock_team)

            await commands_cog.weather.callback(commands_cog, mock_interaction, team_abbrev='NYY')

            # Verify complete flow
            mock_interaction.response.defer.assert_called_once()
            mock_league_service.get_current_state.assert_called_once()
            mock_schedule_service.get_week_schedule.assert_called_once_with(12, 10)
            mock_team_service.get_team_by_abbrev.assert_called_once_with('NYY', 12)

            # Check final embed
            embed_call = mock_interaction.followup.send.call_args
            embed = embed_call.kwargs['embed']

            # Validate embed structure
            assert "Weather Check" in embed.title
            assert len(embed.fields) == 4  # Season, Time, Week, Roll
            assert embed.image.url == mock_team.stadium
            assert embed.color.value == int(mock_team.color, 16)

    @pytest.mark.asyncio
    async def test_team_resolution_priority(self, commands_cog, mock_interaction, mock_current):
        """Test that team resolution follows correct priority order."""
        team1 = TeamFactory.create(id=1, abbrev='NYY', sname='Yankees', lname='New York Yankees', season=12)
        team2 = TeamFactory.create(id=2, abbrev='BOS', sname='Red Sox', lname='Boston Red Sox', season=12)
        team3 = TeamFactory.create(id=3, abbrev='LAD', sname='Dodgers', lname='Los Angeles Dodgers', season=12)

        # Test Priority 1: Explicit parameter (should return team1)
        with patch('commands.utilities.weather.team_service') as mock_team_service:
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=team1)

            result = await commands_cog._resolve_team(mock_interaction, 'NYY', 12)
            assert result.abbrev == 'NYY'
            assert result.id == 1

        # Test Priority 2: Channel name (should return team2)
        mock_interaction.channel.name = "BOS-Fenway-Park"
        with patch('commands.utilities.weather.team_service') as mock_team_service:
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=team2)

            result = await commands_cog._resolve_team(mock_interaction, None, 12)
            assert result.abbrev == 'BOS'
            assert result.id == 2

        # Test Priority 3: User ownership (should return team3)
        mock_interaction.channel.name = "general"
        with patch('commands.utilities.weather.team_service') as mock_team_service, \
             patch('commands.utilities.weather.get_user_major_league_team') as mock_get_team:
            mock_team_service.get_team_by_abbrev = AsyncMock(return_value=None)
            mock_get_team.return_value = team3

            result = await commands_cog._resolve_team(mock_interaction, None, 12)
            assert result.abbrev == 'LAD'
            assert result.id == 3


class TestWeatherCommandsIntegration:
    """Integration tests for weather command with realistic scenarios."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock Discord bot for integration tests."""
        bot = MagicMock()
        bot.get_emoji = MagicMock(return_value=None)
        return bot

    @pytest.fixture
    def commands_cog(self, mock_bot):
        """Create WeatherCommands cog for integration tests."""
        return WeatherCommands(mock_bot)

    @pytest.fixture
    def mock_games(self):
        """Create mock game schedule for integration tests."""
        yankees = TeamFactory.create(id=499, abbrev='NYY', sname='Yankees', lname='New York Yankees', season=12)
        red_sox = TeamFactory.create(id=500, abbrev='BOS', sname='Red Sox', lname='Boston Red Sox', season=12)

        # 1 completed game for division week testing
        games = [
            GameFactory.completed(id=1, season=12, week=10, game_num=1, away_team=yankees, home_team=red_sox, away_score=5, home_score=3)
        ]
        return games

    @pytest.mark.asyncio
    async def test_all_division_weeks(self, commands_cog, mock_games):
        """Test that all division weeks are handled correctly."""
        division_weeks = [1, 3, 6, 14, 16, 18]

        for week in division_weeks:
            # 1 game played in division week should be Night
            one_game = [mock_games[0]]
            time_of_day = commands_cog._get_time_of_day(one_game, week)
            assert "Night" in time_of_day, f"Week {week} should be Night with 1 game in division week"

    @pytest.mark.asyncio
    async def test_season_transitions(self, commands_cog):
        """Test season display transitions at boundaries."""
        assert "Spring" in commands_cog._get_season_display(5)
        assert "Summer" in commands_cog._get_season_display(6)  # Transition
        assert "Summer" in commands_cog._get_season_display(14)
        assert "Fall" in commands_cog._get_season_display(15)  # Transition
