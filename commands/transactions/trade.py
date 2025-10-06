"""
Trade Commands

Interactive multi-team trade builder with real-time validation and elegant UX.
"""
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.autocomplete import player_autocomplete, major_league_team_autocomplete, team_autocomplete
from utils.team_utils import validate_user_has_team, get_team_by_abbrev_with_validation
from constants import SBA_CURRENT_SEASON

from services.trade_builder import (
    TradeBuilder,
    get_trade_builder,
    clear_trade_builder
)
from services.player_service import player_service
from models.team import RosterType
from views.trade_embed import TradeEmbedView, create_trade_embed


class TradeCommands(commands.Cog):
    """Multi-team trade builder commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TradeCommands')

    # Create the trade command group
    trade_group = app_commands.Group(name="trade", description="Multi-team trade management")

    @trade_group.command(
        name="initiate",
        description="Start a new trade with another team"
    )
    @app_commands.describe(
        other_team="Team abbreviation to trade with"
    )
    @app_commands.autocomplete(other_team=major_league_team_autocomplete)
    @logged_command("/trade initiate")
    async def trade_initiate(
        self,
        interaction: discord.Interaction,
        other_team: str
    ):
        """Initiate a new trade with another team."""
        await interaction.response.defer(ephemeral=True)

        # Get user's major league team
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Get the other team
        other_team_obj = await get_team_by_abbrev_with_validation(other_team, interaction)
        if not other_team_obj:
            return

        # Check if it's the same team
        if user_team.id == other_team_obj.id:
            await interaction.followup.send(
                "❌ You cannot initiate a trade with yourself.",
                ephemeral=True
            )
            return

        # Clear any existing trade and create new one
        clear_trade_builder(interaction.user.id)
        trade_builder = get_trade_builder(interaction.user.id, user_team)

        # Add the other team
        success, error_msg = await trade_builder.add_team(other_team_obj)
        if not success:
            await interaction.followup.send(
                f"❌ Failed to add {other_team_obj.abbrev} to trade: {error_msg}",
                ephemeral=True
            )
            return

        # Show trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        await interaction.followup.send(
            content=f"✅ **Trade initiated between {user_team.abbrev} and {other_team_obj.abbrev}**",
            embed=embed,
            view=view,
            ephemeral=True
        )

        self.logger.info(f"Trade initiated: {user_team.abbrev} ↔ {other_team_obj.abbrev}")

    @trade_group.command(
        name="add-team",
        description="Add another team to your current trade (for 3+ team trades)"
    )
    @app_commands.describe(
        other_team="Team abbreviation to add to the trade"
    )
    @app_commands.autocomplete(other_team=major_league_team_autocomplete)
    @logged_command("/trade add-team")
    async def trade_add_team(
        self,
        interaction: discord.Interaction,
        other_team: str
    ):
        """Add a team to an existing trade."""
        await interaction.response.defer(ephemeral=True)

        # Check if user has an active trade
        trade_key = f"{interaction.user.id}:trade"
        from services.trade_builder import _active_trade_builders
        if trade_key not in _active_trade_builders:
            await interaction.followup.send(
                "❌ You don't have an active trade. Use `/trade initiate` first.",
                ephemeral=True
            )
            return

        trade_builder = _active_trade_builders[trade_key]

        # Get the team to add
        team_to_add = await get_team_by_abbrev_with_validation(other_team, interaction)
        if not team_to_add:
            return

        # Add the team
        success, error_msg = await trade_builder.add_team(team_to_add)
        if not success:
            await interaction.followup.send(
                f"❌ Failed to add {team_to_add.abbrev}: {error_msg}",
                ephemeral=True
            )
            return

        # Show updated trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        await interaction.followup.send(
            content=f"✅ **Added {team_to_add.abbrev} to the trade**",
            embed=embed,
            view=view,
            ephemeral=True
        )

        self.logger.info(f"Team added to trade {trade_builder.trade_id}: {team_to_add.abbrev}")

    @trade_group.command(
        name="add-player",
        description="Add a player to the trade"
    )
    @app_commands.describe(
        player_name="Player name; begin typing for autocomplete",
        destination_team="Team abbreviation where the player will go"
    )
    @app_commands.autocomplete(player_name=player_autocomplete)
    @app_commands.autocomplete(destination_team=team_autocomplete)
    @logged_command("/trade add-player")
    async def trade_add_player(
        self,
        interaction: discord.Interaction,
        player_name: str,
        destination_team: str
    ):
        """Add a player move to the trade."""
        await interaction.response.defer(ephemeral=True)

        # Check if user has an active trade
        trade_key = f"{interaction.user.id}:trade"
        from services.trade_builder import _active_trade_builders
        if trade_key not in _active_trade_builders:
            await interaction.followup.send(
                "❌ You don't have an active trade. Use `/trade initiate` first.",
                ephemeral=True
            )
            return

        trade_builder = _active_trade_builders[trade_key]

        # Get user's team
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Find the player
        players = await player_service.search_players(player_name, limit=10, season=SBA_CURRENT_SEASON)
        if not players:
            await interaction.followup.send(
                f"❌ Player '{player_name}' not found.",
                ephemeral=True
            )
            return

        # Use exact match if available, otherwise first result
        player = None
        for p in players:
            if p.name.lower() == player_name.lower():
                player = p
                break
        if not player:
            player = players[0]

        # Get destination team
        dest_team = await get_team_by_abbrev_with_validation(destination_team, interaction)
        if not dest_team:
            return

        # Determine source team and roster locations
        # For now, assume player comes from user's team and goes to ML of destination
        # TODO: More sophisticated logic to determine current roster location
        from_roster = RosterType.MAJOR_LEAGUE  # Default assumption
        to_roster = RosterType.MAJOR_LEAGUE    # Default destination

        # Add the player move
        success, error_msg = await trade_builder.add_player_move(
            player=player,
            from_team=user_team,
            to_team=dest_team,
            from_roster=from_roster,
            to_roster=to_roster
        )

        if not success:
            await interaction.followup.send(
                f"❌ Failed to add player move: {error_msg}",
                ephemeral=True
            )
            return

        # Show updated trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        await interaction.followup.send(
            content=f"✅ **Added {player.name}: {user_team.abbrev} → {dest_team.abbrev}**",
            embed=embed,
            view=view,
            ephemeral=True
        )

        self.logger.info(f"Player added to trade {trade_builder.trade_id}: {player.name} to {dest_team.abbrev}")

    @trade_group.command(
        name="supplementary",
        description="Add a supplementary move within your organization for roster legality"
    )
    @app_commands.describe(
        player_name="Player name; begin typing for autocomplete",
        destination="Where to move the player: Major League, Minor League, or Free Agency"
    )
    @app_commands.autocomplete(player_name=player_autocomplete)
    @app_commands.choices(destination=[
        app_commands.Choice(name="Major League", value="ml"),
        app_commands.Choice(name="Minor League", value="mil"),
        app_commands.Choice(name="Free Agency", value="fa")
    ])
    @logged_command("/trade supplementary")
    async def trade_supplementary(
        self,
        interaction: discord.Interaction,
        player_name: str,
        destination: str
    ):
        """Add a supplementary (internal organization) move for roster legality."""
        await interaction.response.defer(ephemeral=True)

        # Check if user has an active trade
        trade_key = f"{interaction.user.id}:trade"
        from services.trade_builder import _active_trade_builders
        if trade_key not in _active_trade_builders:
            await interaction.followup.send(
                "❌ You don't have an active trade. Use `/trade initiate` first.",
                ephemeral=True
            )
            return

        trade_builder = _active_trade_builders[trade_key]

        # Get user's team
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Find the player
        players = await player_service.search_players(player_name, limit=10, season=SBA_CURRENT_SEASON)
        if not players:
            await interaction.followup.send(
                f"❌ Player '{player_name}' not found.",
                ephemeral=True
            )
            return

        player = players[0]  # Use first match

        # Parse destination
        destination_map = {
            "ml": RosterType.MAJOR_LEAGUE,
            "mil": RosterType.MINOR_LEAGUE,
            "fa": RosterType.FREE_AGENCY
        }

        to_roster = destination_map.get(destination.lower())
        if not to_roster:
            await interaction.followup.send(
                f"❌ Invalid destination: {destination}",
                ephemeral=True
            )
            return

        # Determine current roster (default assumption)
        from_roster = RosterType.MINOR_LEAGUE if to_roster == RosterType.MAJOR_LEAGUE else RosterType.MAJOR_LEAGUE

        # Add supplementary move
        success, error_msg = await trade_builder.add_supplementary_move(
            team=user_team,
            player=player,
            from_roster=from_roster,
            to_roster=to_roster
        )

        if not success:
            await interaction.followup.send(
                f"❌ Failed to add supplementary move: {error_msg}",
                ephemeral=True
            )
            return

        # Show updated trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        await interaction.followup.send(
            content=f"✅ **Added supplementary move: {player.name} → {destination.upper()}**",
            embed=embed,
            view=view,
            ephemeral=True
        )

        self.logger.info(f"Supplementary move added to trade {trade_builder.trade_id}: {player.name} to {destination}")

    @trade_group.command(
        name="view",
        description="View your current trade"
    )
    @logged_command("/trade view")
    async def trade_view(self, interaction: discord.Interaction):
        """View the current trade."""
        await interaction.response.defer(ephemeral=True)

        trade_key = f"{interaction.user.id}:trade"
        from services.trade_builder import _active_trade_builders
        if trade_key not in _active_trade_builders:
            await interaction.followup.send(
                "❌ You don't have an active trade.",
                ephemeral=True
            )
            return

        trade_builder = _active_trade_builders[trade_key]

        # Show trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )

    @trade_group.command(
        name="clear",
        description="Clear your current trade"
    )
    @logged_command("/trade clear")
    async def trade_clear(self, interaction: discord.Interaction):
        """Clear the current trade."""
        await interaction.response.defer(ephemeral=True)

        clear_trade_builder(interaction.user.id)

        await interaction.followup.send(
            "✅ Your trade has been cleared.",
            ephemeral=True
        )


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(TradeCommands(bot))