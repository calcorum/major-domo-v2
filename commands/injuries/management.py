"""
Injury management slash commands for Discord Bot v2.0

Modern implementation for player injury tracking with three subcommands:
- /injury roll <player> - Roll for injury using player's injury rating (format: #p## e.g., 1p70, 4p50)
- /injury set-new - Set a new injury for a player
- /injury clear - Clear a player's active injury

The injury rating format (#p##) encodes both games played and rating:
- First character: Games played in series (1-6)
- Remaining: Injury rating (p70, p65, p60, p50, p40, p30, p20)
"""
import math
import random
import discord
from discord import app_commands
from discord.ext import commands

from config import get_config
from services.player_service import player_service
from services.injury_service import injury_service
from services.league_service import league_service
from services.giphy_service import GiphyService
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.autocomplete import player_autocomplete
from views.embeds import EmbedTemplate
from exceptions import BotException


class InjuryGroup(app_commands.Group):
    """Injury management command group with roll, set-new, and clear subcommands."""

    def __init__(self):
        super().__init__(
            name="injury",
            description="Injury management commands"
        )
        self.logger = get_contextual_logger(f'{__name__}.InjuryGroup')
        self.logger.info("InjuryGroup initialized")

    def has_player_role(self, interaction: discord.Interaction) -> bool:
        """Check if user has the SBA Players role."""
        # Cast to Member to access roles (User doesn't have roles attribute)
        if not isinstance(interaction.user, discord.Member):
            return False

        player_role = discord.utils.get(
            interaction.guild.roles,
            name=get_config().sba_players_role_name
        )
        return player_role in interaction.user.roles if player_role else False

    @app_commands.command(name="roll", description="Roll for injury based on player's injury rating")
    @app_commands.describe(player_name="Player name")
    @app_commands.autocomplete(player_name=player_autocomplete)
    @logged_command("/injury roll")
    async def injury_roll(self, interaction: discord.Interaction, player_name: str):
        """Roll for injury using 3d6 dice and injury tables."""
        await interaction.response.defer()

        # Get current season
        current = await league_service.get_current_state()
        if not current:
            raise BotException("Failed to get current season information")

        # Search for player
        players = await player_service.get_players_by_name(player_name, current.season)

        if not players:
            embed = EmbedTemplate.error(
                title="Player Not Found",
                description=f"I did not find anybody named **{player_name}**."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player = players[0]

        # Check for injury_rating field
        if not player.injury_rating:
            embed = EmbedTemplate.error(
                title="No Injury Rating",
                description=f"{player.name} does not have an injury rating set."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Parse injury_rating format: "1p70" where first char is games_played, rest is rating
        try:
            games_played = int(player.injury_rating[0])
            injury_rating = player.injury_rating[1:]

            # Validate games_played range
            if games_played < 1 or games_played > 6:
                raise ValueError("Games played must be between 1 and 6")

            # Validate rating format (should start with 'p')
            if not injury_rating.startswith('p'):
                raise ValueError("Invalid rating format")

        except (ValueError, IndexError):
            embed = EmbedTemplate.error(
                title="Invalid Injury Rating Format",
                description=f"{player.name} has an invalid injury rating: `{player.injury_rating}`\n\nExpected format: `#p##` (e.g., `1p70`, `4p50`)"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Roll 3d6
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        d3 = random.randint(1, 6)
        roll_total = d1 + d2 + d3

        # Get injury result from table
        injury_result = self._get_injury_result(injury_rating, games_played, roll_total)

        # Create response embed
        embed = EmbedTemplate.warning(
            title=f"Injury roll for {interaction.user.name}"
        )
        if player.team.thumbnail is not None:
            embed.set_thumbnail(url=player.team.thumbnail)

        embed.add_field(
            name="Player",
            value=f"{player.name} ({player.primary_position})",
            inline=True
        )

        embed.add_field(
            name="Injury Rating",
            value=f"{player.injury_rating}",
            inline=True
        )

        # embed.add_field(name='', value='', inline=False) # Embed line break

        # Format dice roll in markdown (same format as /ab roll)
        dice_result = f"```md\n# {roll_total}\nDetails:[3d6 ({d1} {d2} {d3})]```"
        embed.add_field(
            name="Dice Roll",
            value=dice_result,
            inline=False
        )

        # Format result
        if isinstance(injury_result, int):
            result_text = f"**{injury_result} game{'s' if injury_result > 1 else ''}**"
            embed.color = discord.Color.orange()
            if injury_result > 6:
                gif_search_text = ['well shit', 'well fuck', 'god dammit']
            else:
                gif_search_text = ['bummer', 'well damn']
        elif injury_result == 'REM':
            if player.is_pitcher:
                result_text = '**FATIGUED**'
                embed.set_footer(text='For pitchers, add their current rest to the injury')
            else:
                result_text = "**REMAINDER OF GAME**"
            embed.color = discord.Color.gold()
            gif_search_text = ['this is fine', 'not even mad', 'could be worse']
        else:  # 'OK'
            result_text = "**No injury!**"
            embed.color = discord.Color.green()
            gif_search_text = ['we are so back', 'all good', 'totally fine']

        # embed.add_field(name='', value='', inline=False)

        embed.add_field(
            name="Injury Length",
            value=result_text,
            inline=True
        )
        
        try:
            injury_gif = await GiphyService().get_gif(
                phrase_options=gif_search_text
            )
        except Exception:
            injury_gif = ''
        
        embed.set_image(url=injury_gif)

        await interaction.followup.send(embed=embed)

    def _get_injury_result(self, rating: str, games_played: int, roll: int):
        """
        Get injury result from the injury table.

        Args:
            rating: Injury rating (e.g., 'p70', 'p65', etc.)
            games_played: Number of games played (1-6)
            roll: 3d6 roll result (3-18)

        Returns:
            Injury result: int (games), 'REM', or 'OK'
        """
        # Injury table mapping
        inj_data = {
            'one': {
                'p70': ['OK', 'OK', 'OK', 'OK', 'OK', 'OK', 'REM', 'REM', 1, 1, 2, 2, 3, 3, 4, 4],
                'p65': [2, 2, 'OK', 'REM', 1, 2, 3, 3, 4, 4, 4, 4, 5, 6, 8, 12],
                'p60': ['OK', 'OK', 'REM', 1, 2, 3, 4, 4, 4, 5, 5, 6, 8, 12, 16, 16],
                'p50': ['OK', 'REM', 1, 2, 3, 4, 4, 5, 5, 6, 8, 8, 12, 16, 16, 'OK'],
                'p40': ['OK', 1, 2, 3, 4, 4, 5, 6, 6, 8, 8, 12, 16, 24, 'REM', 'OK'],
                'p30': ['OK', 4, 1, 3, 4, 5, 6, 8, 8, 12, 16, 24, 4, 2, 'REM', 'OK'],
                'p20': ['OK', 1, 2, 4, 5, 8, 8, 24, 16, 12, 12, 6, 4, 3, 'REM', 'OK']
            },
            'two': {
                'p70': [4, 3, 2, 2, 1, 1, 'REM', 'OK', 'REM', 'OK', 2, 1, 2, 2, 3, 4],
                'p65': [8, 5, 4, 2, 2, 'OK', 1, 'OK', 'REM', 1, 'REM', 2, 3, 4, 6, 12],
                'p60': [1, 3, 4, 5, 2, 2, 'OK', 1, 3, 'REM', 4, 4, 6, 8, 12, 3],
                'p50': [4, 'OK', 'OK', 'REM', 1, 2, 4, 3, 4, 5, 4, 6, 8, 12, 12, 'OK'],
                'p40': ['OK', 'OK', 'REM', 1, 2, 3, 4, 4, 5, 4, 6, 8, 12, 16, 16, 'OK'],
                'p30': ['OK', 'REM', 1, 2, 3, 4, 4, 5, 6, 5, 8, 12, 16, 24, 'REM', 'OK'],
                'p20': ['OK', 1, 4, 4, 5, 5, 6, 6, 12, 8, 16, 24, 8, 3, 2, 'REM']
            },
            'three': {
                'p70': [],
                'p65': ['OK', 'OK', 'REM', 1, 3, 'OK', 'REM', 1, 2, 1, 2, 3, 4, 4, 5, 'REM'],
                'p60': ['OK', 5, 'OK', 'REM', 1, 2, 2, 3, 4, 4, 1, 3, 5, 6, 8, 'REM'],
                'p50': ['OK', 'OK', 'REM', 1, 2, 3, 4, 4, 5, 4, 4, 6, 8, 8, 12, 'REM'],
                'p40': ['OK', 1, 1, 2, 3, 4, 4, 5, 6, 5, 6, 8, 8, 12, 4, 'REM'],
                'p30': ['OK', 1, 2, 3, 4, 5, 4, 6, 5, 6, 8, 8, 12, 16, 1, 'REM'],
                'p20': ['OK', 1, 2, 4, 4, 8, 8, 6, 5, 12, 6, 16, 24, 3, 4, 'REM']
            },
            'four': {
                'p70': [],
                'p65': [],
                'p60': ['OK', 'OK', 'REM', 3, 3, 'OK', 'REM', 1, 2, 1, 4, 4, 5, 6, 8, 'REM'],
                'p50': ['OK', 6, 4, 'OK', 'REM', 1, 2, 4, 4, 3, 5, 3, 6, 8, 12, 'REM'],
                'p40': ['OK', 'OK', 'REM', 1, 2, 3, 4, 4, 5, 4, 4, 6, 8, 8, 12, 'REM'],
                'p30': ['OK', 1, 1, 2, 3, 4, 4, 5, 6, 5, 6, 8, 8, 12, 4, 'REM'],
                'p20': ['OK', 1, 2, 3, 4, 5, 4, 6, 5, 6, 12, 8, 8, 16, 1, 'REM']
            },
            'five': {
                'p70': [],
                'p65': [],
                'p60': ['OK', 'REM', 'REM', 'REM', 3, 'OK', 1, 'REM', 2, 1, 'OK', 4, 5, 2, 6, 8],
                'p50': ['OK', 'OK', 'REM', 1, 1, 'OK', 'REM', 3, 2, 4, 4, 5, 5, 6, 8, 12],
                'p40': ['OK', 6, 6, 'OK', 1, 3, 2, 4, 4, 5, 'REM', 3, 8, 6, 12, 1],
                'p30': ['OK', 'OK', 'REM', 4, 1, 2, 5, 4, 6, 3, 4, 8, 5, 6, 12, 'REM'],
                'p20': ['OK', 'REM', 2, 3, 4, 4, 5, 4, 6, 5, 8, 6, 8, 1, 12, 'REM']
            },
            'six': {
                'p70': [],
                'p65': [],
                'p60': [],
                'p50': [],
                'p40': ['OK', 6, 6, 'OK', 1, 3, 2, 4, 4, 5, 'REM', 3, 8, 6, 1, 12],
                'p30': ['OK', 'OK', 'REM', 5, 1, 3, 6, 4, 5, 2, 4, 8, 3, 5, 12, 'REM'],
                'p20': ['OK', 'REM', 4, 6, 2, 3, 6, 4, 8, 5, 5, 6, 3, 1, 12, 'REM']
            }
        }

        # Map games_played to key
        games_map = {1: 'one', 2: 'two', 3: 'three', 4: 'four', 5: 'five', 6: 'six'}
        games_key = games_map.get(games_played)

        if not games_key:
            return 'OK'

        # Get the injury table for this rating and games played
        injury_table = inj_data.get(games_key, {}).get(rating, [])

        # If no table exists (e.g., p70 with 3+ games), no injury
        if not injury_table:
            return 'OK'

        # Get result from table (roll 3-18 maps to index 0-15)
        table_index = roll - 3
        if 0 <= table_index < len(injury_table):
            return injury_table[table_index]

        return 'OK'

    @app_commands.command(name="set-new", description="Set a new injury for a player (requires SBA Players role)")
    @app_commands.describe(
        player_name="Player name to injure",
        this_week="Current week number",
        this_game="Current game number (1-4)",
        injury_games="Number of games player will be out"
    )
    @logged_command("/injury set-new")
    async def injury_set_new(
        self,
        interaction: discord.Interaction,
        player_name: str,
        this_week: int,
        this_game: int,
        injury_games: int
    ):
        """Set a new injury for a player on your team."""
        # Check role permissions
        if not self.has_player_role(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"This command requires the **{get_config().sba_players_role_name}** role."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Validate inputs
        if this_game < 1 or this_game > 4:
            embed = EmbedTemplate.error(
                title="Invalid Input",
                description="Game number must be between 1 and 4."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if injury_games < 1:
            embed = EmbedTemplate.error(
                title="Invalid Input",
                description="Injury duration must be at least 1 game."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Get current season
        current = await league_service.get_current_state()
        if not current:
            raise BotException("Failed to get current season information")

        # Search for player
        players = await player_service.get_players_by_name(player_name, current.season)

        if not players:
            embed = EmbedTemplate.error(
                title="Player Not Found",
                description=f"I did not find anybody named **{player_name}**."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player = players[0]

        # Check if player is on user's team
        # Note: This assumes you have a function to get team by owner
        # For now, we'll skip this check - you can add it if needed
        # TODO: Add team ownership verification

        # Check if player already has an active injury
        existing_injury = await injury_service.get_active_injury(player.id, current.season)
        if existing_injury:
            embed = EmbedTemplate.error(
                title="Already Injured",
                description=f"Hm. It looks like {player.name} is already hurt."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Calculate return date
        out_weeks = math.floor(injury_games / 4)
        out_games = injury_games % 4

        return_week = this_week + out_weeks
        return_game = this_game + 1 + out_games

        if return_game > 4:
            return_week += 1
            return_game -= 4

        # Adjust start date if injury starts after game 4
        start_week = this_week if this_game != 4 else this_week + 1
        start_game = this_game + 1 if this_game != 4 else 1

        return_date = f'w{return_week:02d}g{return_game}'

        # Create injury record
        injury = await injury_service.create_injury(
            season=current.season,
            player_id=player.id,
            total_games=injury_games,
            start_week=start_week,
            start_game=start_game,
            end_week=return_week,
            end_game=return_game
        )

        if not injury:
            embed = EmbedTemplate.error(
                title="Error",
                description="Well that didn't work. Failed to create injury record."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Update player's il_return field
        await player_service.update_player(player.id, {'il_return': return_date})

        # Success response
        embed = EmbedTemplate.success(
            title="Injury Recorded",
            description=f"{player.name} has been placed on the injured list."
        )

        embed.add_field(
            name="Player",
            value=f"{player.name} ({player.pos_1})",
            inline=True
        )

        embed.add_field(
            name="Duration",
            value=f"{injury_games} game{'s' if injury_games > 1 else ''}",
            inline=True
        )

        embed.add_field(
            name="Return Date",
            value=return_date,
            inline=True
        )

        if player.team:
            embed.add_field(
                name="Team",
                value=f"{player.team.lname} ({player.team.abbrev})",
                inline=False
            )

        await interaction.followup.send(embed=embed)

        # Log for debugging
        self.logger.info(
            f"Injury set for {player.name}: {injury_games} games, returns {return_date}",
            player_id=player.id,
            season=current.season,
            injury_id=injury.id
        )

    @app_commands.command(name="clear", description="Clear a player's injury (requires SBA Players role)")
    @app_commands.describe(player_name="Player name to clear injury")
    @logged_command("/injury clear")
    async def injury_clear(self, interaction: discord.Interaction, player_name: str):
        """Clear a player's active injury."""
        # Check role permissions
        if not self.has_player_role(interaction):
            embed = EmbedTemplate.error(
                title="Permission Denied",
                description=f"This command requires the **{get_config().sba_players_role_name}** role."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        await interaction.response.defer()

        # Get current season
        current = await league_service.get_current_state()
        if not current:
            raise BotException("Failed to get current season information")

        # Search for player
        players = await player_service.get_players_by_name(player_name, current.season)

        if not players:
            embed = EmbedTemplate.error(
                title="Player Not Found",
                description=f"I did not find anybody named **{player_name}**."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player = players[0]

        # Get active injury
        injury = await injury_service.get_active_injury(player.id, current.season)

        if not injury:
            embed = EmbedTemplate.error(
                title="No Active Injury",
                description=f"{player.name} isn't injured."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Clear the injury
        success = await injury_service.clear_injury(injury.id)

        if not success:
            embed = EmbedTemplate.error(
                title="Error",
                description="Failed to clear the injury. Please try again."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Clear player's il_return field
        await player_service.update_player(player.id, {'il_return': None})

        # Success response
        embed = EmbedTemplate.success(
            title="Injury Cleared",
            description=f"{player.name} has been cleared and is eligible to play again."
        )

        embed.add_field(
            name="Previous Return Date",
            value=injury.return_date,
            inline=True
        )

        embed.add_field(
            name="Total Games Missed",
            value=injury.duration_display,
            inline=True
        )

        if player.team:
            embed.add_field(
                name="Team",
                value=f"{player.team.lname} ({player.team.abbrev})",
                inline=False
            )

        await interaction.followup.send(embed=embed)

        # Log for debugging
        self.logger.info(
            f"Injury cleared for {player.name}",
            player_id=player.id,
            season=current.season,
            injury_id=injury.id
        )


async def setup(bot: commands.Bot):
    """Setup function for loading the injury commands."""
    bot.tree.add_command(InjuryGroup())
