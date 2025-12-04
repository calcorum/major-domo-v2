"""
Trade Commands

Interactive multi-team trade builder with real-time validation and elegant UX.
"""
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from config import get_config
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.autocomplete import player_autocomplete, major_league_team_autocomplete, team_autocomplete
from utils.team_utils import validate_user_has_team, get_team_by_abbrev_with_validation

from services.trade_builder import (
    TradeBuilder,
    get_trade_builder,
    get_trade_builder_by_team,
    clear_trade_builder,
    clear_trade_builder_by_team,
)
from services.player_service import player_service
from models.team import RosterType
from views.trade_embed import TradeEmbedView, create_trade_embed
from commands.transactions.trade_channels import TradeChannelManager
from commands.transactions.trade_channel_tracker import TradeChannelTracker


class TradeCommands(commands.Cog):
    """Multi-team trade builder commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TradeCommands')

        # Initialize trade channel management
        self.channel_tracker = TradeChannelTracker()
        self.channel_manager = TradeChannelManager(self.channel_tracker)

    # Create the trade command group
    trade_group = app_commands.Group(name="trade", description="Multi-team trade management")

    def _get_trade_channel(self, guild: discord.Guild, trade_id: str) -> Optional[discord.TextChannel]:
        """Get the trade channel for a given trade ID."""
        channel_data = self.channel_tracker.get_channel_by_trade_id(trade_id)
        if not channel_data:
            return None

        channel_id = int(channel_data["channel_id"])
        channel = guild.get_channel(channel_id)

        if channel and isinstance(channel, discord.TextChannel):
            return channel
        return None

    def _is_in_trade_channel(self, interaction: discord.Interaction, trade_id: str) -> bool:
        """Check if the interaction is happening in the trade's dedicated channel."""
        trade_channel = self._get_trade_channel(interaction.guild, trade_id)
        if not trade_channel:
            return False
        return interaction.channel_id == trade_channel.id

    async def _post_to_trade_channel(
        self,
        guild: discord.Guild,
        trade_id: str,
        embed: discord.Embed,
        view: Optional[discord.ui.View] = None,
        content: Optional[str] = None
    ) -> bool:
        """
        Post the trade embed to the trade channel.

        Returns:
            True if successfully posted, False otherwise
        """
        trade_channel = self._get_trade_channel(guild, trade_id)
        if not trade_channel:
            self.logger.warning(f"Could not find trade channel for trade {trade_id}")
            return False

        try:
            await trade_channel.send(content=content, embed=embed, view=view)
            self.logger.debug(f"Posted trade update to channel {trade_channel.name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to post to trade channel: {e}")
            return False

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

        # Create trade discussion channel
        channel = await self.channel_manager.create_trade_channel(
            guild=interaction.guild,
            trade_id=trade_builder.trade_id,
            team1=user_team,
            team2=other_team_obj,
            creator_id=interaction.user.id
        )

        # Show trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        # Build success message with channel mention if created
        success_msg = f"✅ **Trade initiated between {user_team.abbrev} and {other_team_obj.abbrev}**"
        if channel:
            success_msg += f"\n📝 Discussion channel: {channel.mention}"
        else:
            success_msg += f"\n⚠️  **Warning:** Failed to create discussion channel. Check bot permissions or contact an admin."
            self.logger.warning(f"Failed to create trade channel for trade {trade_builder.trade_id}")

        await interaction.followup.send(
            content=success_msg,
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
        await interaction.response.defer(ephemeral=False)

        # Get user's team first
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Look up trade by user's team (allows any GM in the trade to participate)
        trade_builder = get_trade_builder_by_team(user_team.id)
        if not trade_builder:
            await interaction.followup.send(
                "❌ Your team is not part of an active trade. Use `/trade initiate` first.",
                ephemeral=True
            )
            return

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

        # Add team to trade discussion channel
        channel_updated = await self.channel_manager.add_team_to_channel(
            guild=interaction.guild,
            trade_id=trade_builder.trade_id,
            new_team=team_to_add
        )

        # Show updated trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        # Build success message
        success_msg = f"✅ **Added {team_to_add.abbrev} to the trade**"
        if channel_updated:
            success_msg += f"\n📝 {team_to_add.abbrev} has been added to the discussion channel"

        await interaction.followup.send(
            content=success_msg,
            embed=embed,
            view=view,
            ephemeral=True
        )

        # If command was executed outside trade channel, post update to trade channel
        if not self._is_in_trade_channel(interaction, trade_builder.trade_id):
            await self._post_to_trade_channel(
                guild=interaction.guild,
                trade_id=trade_builder.trade_id,
                embed=embed,
                view=view,
                content=success_msg
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
        await interaction.response.defer(ephemeral=False)

        # Get user's team first
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Look up trade by user's team (allows any GM in the trade to participate)
        trade_builder = get_trade_builder_by_team(user_team.id)
        if not trade_builder:
            await interaction.followup.send(
                "❌ Your team is not part of an active trade. Use `/trade initiate` or ask another GM to add your team.",
                ephemeral=True
            )
            return

        # Find the player
        players = await player_service.search_players(player_name, limit=10, season=get_config().sba_season)
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
        # The service will validate that the player is actually on the user's team organization
        from_roster = RosterType.MAJOR_LEAGUE  # Default assumption
        to_roster = RosterType.MAJOR_LEAGUE    # Default destination

        # Add the player move (service layer will validate)
        success, error_msg = await trade_builder.add_player_move(
            player=player,
            from_team=user_team,
            to_team=dest_team,
            from_roster=from_roster,
            to_roster=to_roster
        )

        if not success:
            await interaction.followup.send(
                f"❌ {error_msg}",
                ephemeral=True
            )
            return

        # Show updated trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)
        success_msg = f"✅ **Added {player.name}: {user_team.abbrev} → {dest_team.abbrev}**"

        await interaction.followup.send(
            content=success_msg,
            embed=embed,
            view=view,
            ephemeral=True
        )

        # If command was executed outside trade channel, post update to trade channel
        if not self._is_in_trade_channel(interaction, trade_builder.trade_id):
            await self._post_to_trade_channel(
                guild=interaction.guild,
                trade_id=trade_builder.trade_id,
                embed=embed,
                view=view,
                content=success_msg
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
        await interaction.response.defer(ephemeral=False)

        # Get user's team first
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Look up trade by user's team (allows any GM in the trade to participate)
        trade_builder = get_trade_builder_by_team(user_team.id)
        if not trade_builder:
            await interaction.followup.send(
                "❌ Your team is not part of an active trade. Use `/trade initiate` or ask another GM to add your team.",
                ephemeral=True
            )
            return

        # Find the player
        players = await player_service.search_players(player_name, limit=10, season=get_config().sba_season)
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
        success_msg = f"✅ **Added supplementary move: {player.name} → {destination.upper()}**"

        await interaction.followup.send(
            content=success_msg,
            embed=embed,
            view=view,
            ephemeral=True
        )

        # If command was executed outside trade channel, post update to trade channel
        if not self._is_in_trade_channel(interaction, trade_builder.trade_id):
            await self._post_to_trade_channel(
                guild=interaction.guild,
                trade_id=trade_builder.trade_id,
                embed=embed,
                view=view,
                content=success_msg
            )

        self.logger.info(f"Supplementary move added to trade {trade_builder.trade_id}: {player.name} to {destination}")

    @trade_group.command(
        name="view",
        description="View your current trade"
    )
    @logged_command("/trade view")
    async def trade_view(self, interaction: discord.Interaction):
        """View the current trade."""
        await interaction.response.defer(ephemeral=False)

        # Get user's team first
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Look up trade by user's team (allows any GM in the trade to view)
        trade_builder = get_trade_builder_by_team(user_team.id)
        if not trade_builder:
            await interaction.followup.send(
                "❌ Your team is not part of an active trade.",
                ephemeral=True
            )
            return

        # Show trade interface
        embed = await create_trade_embed(trade_builder)
        view = TradeEmbedView(trade_builder, interaction.user.id)

        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True
        )

        # If command was executed outside trade channel, post update to trade channel
        if not self._is_in_trade_channel(interaction, trade_builder.trade_id):
            await self._post_to_trade_channel(
                guild=interaction.guild,
                trade_id=trade_builder.trade_id,
                embed=embed,
                view=view
            )

    @trade_group.command(
        name="clear",
        description="Clear your current trade"
    )
    @logged_command("/trade clear")
    async def trade_clear(self, interaction: discord.Interaction):
        """Clear the current trade."""
        await interaction.response.defer(ephemeral=False)

        # Get user's team first
        user_team = await validate_user_has_team(interaction)
        if not user_team:
            return

        # Look up trade by user's team (allows any GM in the trade to clear)
        trade_builder = get_trade_builder_by_team(user_team.id)
        if not trade_builder:
            await interaction.followup.send(
                "❌ Your team is not part of an active trade.",
                ephemeral=True
            )
            return

        trade_id = trade_builder.trade_id

        # Delete associated trade channel if it exists
        await self.channel_manager.delete_trade_channel(
            guild=interaction.guild,
            trade_id=trade_id
        )

        # Clear the trade builder using team-based function
        clear_trade_builder_by_team(user_team.id)

        await interaction.followup.send(
            "✅ The trade has been cleared.",
            ephemeral=True
        )


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(TradeCommands(bot))