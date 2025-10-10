"""
Trade Channel Management

Handles creation and management of private text channels for trade discussions.
"""
from typing import Optional

import discord

from models.team import Team
from utils.logging import get_contextual_logger
from commands.transactions.trade_channel_tracker import TradeChannelTracker

logger = get_contextual_logger(f'{__name__}.TradeChannelManager')


class TradeChannelManager:
    """
    Manages text channels for trade discussions between teams.

    Features:
    - Creates private channels with team-specific permissions
    - Tracks channels for cleanup
    - Handles permission setup for team roles
    - Supports adding teams to existing channels for multi-team trades
    """

    def __init__(self, tracker: TradeChannelTracker):
        """
        Initialize the trade channel manager.

        Args:
            tracker: TradeChannelTracker instance for persistence
        """
        self.tracker = tracker
        self.logger = logger

    async def create_trade_channel(
        self,
        guild: discord.Guild,
        trade_id: str,
        team1: Team,
        team2: Team,
        creator_id: int
    ) -> Optional[discord.TextChannel]:
        """
        Create a private text channel for trade discussion.

        Args:
            guild: Discord guild where channel will be created
            trade_id: Unique trade identifier
            team1: First participating team
            team2: Second participating team
            creator_id: Discord user ID who initiated the trade

        Returns:
            Created TextChannel or None if creation failed
        """
        # Get Transactions category
        transactions_category = discord.utils.get(guild.categories, name="Transactions")
        if not transactions_category:
            self.logger.warning("'Transactions' category not found, channel will be created without category")

        # Build channel name: trade-{team1}-{team2}-{short_id}
        channel_name = f"trade-{team1.abbrev.lower()}-{team2.abbrev.lower()}-{trade_id[:4]}"

        # Get team roles
        team1_role = discord.utils.get(guild.roles, name=team1.lname)
        team2_role = discord.utils.get(guild.roles, name=team2.lname)

        # Setup permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
        }

        # Add team permissions if roles exist
        roles_found = []
        if team1_role:
            overwrites[team1_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            roles_found.append(team1.lname)
        else:
            self.logger.warning(f"Role not found for team: {team1.lname}")

        if team2_role:
            overwrites[team2_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )
            roles_found.append(team2.lname)
        else:
            self.logger.warning(f"Role not found for team: {team2.lname}")

        try:
            self.logger.info(f"Attempting to create trade channel: {channel_name}")
            self.logger.debug(f"Permissions configured for {len(overwrites)} roles/members")

            # Create the text channel
            channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                category=transactions_category,
                topic=f"Trade discussion: {team1.abbrev} ↔ {team2.abbrev} | Trade ID: {trade_id}"
            )

            self.logger.info(f"Successfully created channel: {channel.name} (ID: {channel.id})")

            # Add to tracker
            self.tracker.add_channel(
                channel=channel,
                trade_id=trade_id,
                team1_abbrev=team1.abbrev,
                team2_abbrev=team2.abbrev,
                creator_id=creator_id
            )

            # Send welcome message mentioning the team roles
            welcome_parts = ["Welcome to this trade discussion channel!"]

            if team1_role and team2_role:
                welcome_parts.append(f"{team1_role.mention} and {team2_role.mention}, you can use this private channel to discuss your trade.")
            elif team1_role:
                welcome_parts.append(f"{team1_role.mention}, you can use this private channel to discuss your trade.")
            elif team2_role:
                welcome_parts.append(f"{team2_role.mention}, you can use this private channel to discuss your trade.")
            else:
                welcome_parts.append("Both teams can use this private channel to discuss your trade.")

            welcome_parts.append(f"\n**Trade ID:** `{trade_id}`")
            welcome_message = "\n".join(welcome_parts)

            try:
                await channel.send(welcome_message)
            except Exception as e:
                self.logger.warning(f"Failed to send welcome message to trade channel: {e}")

            self.logger.info(
                f"Created trade channel: {channel.name} for trade {trade_id} "
                f"({team1.abbrev} ↔ {team2.abbrev})"
            )

            return channel

        except discord.Forbidden as e:
            self.logger.error(
                f"Missing permissions to create trade channel. "
                f"Discord error: {e.text if hasattr(e, 'text') else str(e)}. "
                f"Code: {e.code if hasattr(e, 'code') else 'unknown'}"
            )
            return None
        except Exception as e:
            self.logger.error(f"Failed to create trade channel: {type(e).__name__}: {e}", exc_info=True)
            return None

    async def add_team_to_channel(
        self,
        guild: discord.Guild,
        trade_id: str,
        new_team: Team
    ) -> bool:
        """
        Add a team to an existing trade channel's permissions.

        Args:
            guild: Discord guild containing the channel
            trade_id: Trade identifier
            new_team: Team to add to the channel

        Returns:
            True if team was added successfully, False otherwise
        """
        # Find channel in tracker
        channel_data = self.tracker.get_channel_by_trade_id(trade_id)
        if not channel_data:
            self.logger.warning(f"No tracked channel found for trade {trade_id}")
            return False

        channel_id = int(channel_data["channel_id"])
        channel = guild.get_channel(channel_id)

        if not channel or not isinstance(channel, discord.TextChannel):
            self.logger.warning(f"Channel {channel_id} not found or is not a text channel")
            return False

        # Get the new team's role
        team_role = discord.utils.get(guild.roles, name=new_team.lname)
        if not team_role:
            self.logger.warning(f"Role not found for team: {new_team.lname}")
            return False

        try:
            # Add permissions for the new team
            await channel.set_permissions(
                team_role,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                reason=f"Added {new_team.abbrev} to trade {trade_id}"
            )

            # Update channel topic to include new team
            current_topic = channel.topic or ""
            if "Trade discussion:" in current_topic:
                # Extract existing teams and add new one
                topic_parts = current_topic.split("|")
                teams_part = topic_parts[0].strip()
                # Add new team abbreviation
                updated_topic = f"{teams_part} + {new_team.abbrev} | Trade ID: {trade_id}"
                await channel.edit(topic=updated_topic)

            # Send welcome message for the new team
            if team_role:
                welcome_message = f"Welcome {team_role.mention}! You've been added to this trade discussion. This is now a multi-team trade."
            else:
                welcome_message = f"Welcome **{new_team.lname}**! You've been added to this trade discussion. This is now a multi-team trade."

            try:
                await channel.send(welcome_message)
            except Exception as e:
                self.logger.warning(f"Failed to send welcome message to trade channel: {e}")

            self.logger.info(
                f"Added team {new_team.abbrev} to trade channel {channel.name} (Trade: {trade_id})"
            )
            return True

        except discord.Forbidden:
            self.logger.error(f"Missing permissions to modify channel {channel_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to add team to channel {channel_id}: {e}")
            return False

    async def delete_trade_channel(self, guild: discord.Guild, trade_id: str) -> bool:
        """
        Delete a trade channel by trade ID.

        Args:
            guild: Discord guild containing the channel
            trade_id: Trade identifier

        Returns:
            True if channel was deleted, False otherwise
        """
        # Find channel in tracker
        channel_data = self.tracker.get_channel_by_trade_id(trade_id)
        if not channel_data:
            self.logger.debug(f"No tracked channel found for trade {trade_id}")
            return False

        channel_id = int(channel_data["channel_id"])

        # Get the channel from Discord
        channel = guild.get_channel(channel_id)
        if not channel:
            # Channel doesn't exist in Discord, just remove from tracker
            self.logger.warning(f"Channel {channel_id} not found in Discord, removing from tracker")
            self.tracker.remove_channel(channel_id)
            return False

        try:
            # Delete the channel
            await channel.delete(reason=f"Trade {trade_id} cleared")

            # Remove from tracker
            self.tracker.remove_channel(channel_id)

            self.logger.info(f"Deleted trade channel for trade {trade_id}")
            return True

        except discord.Forbidden:
            self.logger.error(f"Missing permissions to delete channel {channel_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete trade channel {channel_id}: {e}")
            return False

    async def delete_channel_by_id(self, guild: discord.Guild, channel_id: int) -> bool:
        """
        Delete a trade channel by channel ID.

        Args:
            guild: Discord guild containing the channel
            channel_id: Discord channel ID

        Returns:
            True if channel was deleted, False otherwise
        """
        channel = guild.get_channel(channel_id)
        if not channel:
            self.logger.warning(f"Channel {channel_id} not found in Discord")
            # Remove from tracker anyway if it exists
            if self.tracker.get_channel_by_id(channel_id):
                self.tracker.remove_channel(channel_id)
            return False

        try:
            # Delete the channel
            await channel.delete(reason="Trade channel cleanup")

            # Remove from tracker
            self.tracker.remove_channel(channel_id)

            self.logger.info(f"Deleted trade channel {channel_id}")
            return True

        except discord.Forbidden:
            self.logger.error(f"Missing permissions to delete channel {channel_id}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete trade channel {channel_id}: {e}")
            return False
