"""
Transaction Freeze/Thaw Task for Discord Bot v2.0

Automated weekly system for freezing and processing transactions.
Runs on a schedule to increment weeks and process contested transactions.
"""
import asyncio
import random
from datetime import datetime, UTC
from typing import Dict, List, Tuple, Set
from dataclasses import dataclass

import discord
from discord.ext import commands, tasks

from services.league_service import league_service
from services.transaction_service import transaction_service
from services.standings_service import standings_service
from models.current import Current
from models.transaction import Transaction
from utils.logging import get_contextual_logger
from views.embeds import EmbedTemplate, EmbedColors
from config import get_config


@dataclass
class TransactionPriority:
    """
    Data class for transaction priority calculation.
    Used to resolve contested transactions (multiple teams wanting same player).
    """
    transaction: Transaction
    team_win_percentage: float
    tiebreaker: float  # win% + small random number for randomized tiebreak

    def __lt__(self, other):
        """Allow sorting by tiebreaker value."""
        return self.tiebreaker < other.tiebreaker


async def resolve_contested_transactions(
    transactions: List[Transaction],
    season: int
) -> Tuple[List[str], List[str]]:
    """
    Resolve contested transactions where multiple teams want the same player.

    This is extracted as a pure function for testability.

    Args:
        transactions: List of all frozen transactions for the week
        season: Current season number

    Returns:
        Tuple of (winning_move_ids, losing_move_ids)
    """
    logger = get_contextual_logger(f'{__name__}.resolve_contested_transactions')

    # Group transactions by player name
    player_transactions: Dict[str, List[Transaction]] = {}

    for transaction in transactions:
        player_name = transaction.player.name.lower()

        # Only consider transactions where a team is acquiring a player (not FA drops)
        if transaction.newteam.abbrev.upper() != 'FA':
            if player_name not in player_transactions:
                player_transactions[player_name] = []
            player_transactions[player_name].append(transaction)

    # Identify contested players (multiple teams want same player)
    contested_players: Dict[str, List[Transaction]] = {}
    non_contested_moves: Set[str] = set()

    for player_name, player_transactions_list in player_transactions.items():
        if len(player_transactions_list) > 1:
            contested_players[player_name] = player_transactions_list
            logger.info(f"Contested player: {player_name} ({len(player_transactions_list)} teams)")
        else:
            # Non-contested, automatically wins
            non_contested_moves.add(player_transactions_list[0].moveid)

    # Resolve contests using team priority (win% + random tiebreaker)
    winning_move_ids: Set[str] = set()
    losing_move_ids: Set[str] = set()

    for player_name, contested_transactions in contested_players.items():
        priorities: List[TransactionPriority] = []

        for transaction in contested_transactions:
            # Get team for priority calculation
            # If adding to MiL team, use the parent ML team for standings
            if transaction.newteam.abbrev.endswith('MiL'):
                team_abbrev = transaction.newteam.abbrev[:-3]  # Remove 'MiL' suffix
            else:
                team_abbrev = transaction.newteam.abbrev

            try:
                # Get team standings to calculate win percentage
                standings = await standings_service.get_team_standings(team_abbrev, season)

                if standings and standings.wins is not None and standings.losses is not None:
                    total_games = standings.wins + standings.losses
                    win_pct = standings.wins / total_games if total_games > 0 else 0.0
                else:
                    win_pct = 0.0
                    logger.warning(f"Could not get standings for {team_abbrev}, using 0.0 win%")

                # Add small random component for tiebreaking (5 decimal precision)
                random_component = random.randint(10000, 99999) * 0.00000001
                tiebreaker = win_pct + random_component

                priorities.append(TransactionPriority(
                    transaction=transaction,
                    team_win_percentage=win_pct,
                    tiebreaker=tiebreaker
                ))

            except Exception as e:
                logger.error(f"Error calculating priority for {team_abbrev}: {e}")
                # Give them 0.0 priority on error
                priorities.append(TransactionPriority(
                    transaction=transaction,
                    team_win_percentage=0.0,
                    tiebreaker=random.randint(10000, 99999) * 0.00000001
                ))

        # Sort by tiebreaker (lowest win% wins - worst teams get priority)
        priorities.sort()

        # First team wins, rest lose
        if priorities:
            winner = priorities[0]
            winning_move_ids.add(winner.transaction.moveid)

            logger.info(
                f"Contest resolved for {player_name}: {winner.transaction.newteam.abbrev} wins "
                f"(win%: {winner.team_win_percentage:.3f}, tiebreaker: {winner.tiebreaker:.8f})"
            )

            for loser in priorities[1:]:
                losing_move_ids.add(loser.transaction.moveid)
                logger.info(
                    f"Contest lost for {player_name}: {loser.transaction.newteam.abbrev} "
                    f"(win%: {loser.team_win_percentage:.3f}, tiebreaker: {loser.tiebreaker:.8f})"
                )

    # Add non-contested moves to winners
    winning_move_ids.update(non_contested_moves)

    return list(winning_move_ids), list(losing_move_ids)


class TransactionFreezeTask:
    """Automated weekly freeze/thaw system for transactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.TransactionFreezeTask')

        # Track last execution to prevent duplicate operations
        self.last_freeze_week: int | None = None
        self.last_thaw_week: int | None = None

        # Track error notifications separately
        self.error_notification_sent = False

        self.logger.info("Transaction freeze/thaw task initialized")

        # Start the weekly loop
        self.weekly_loop.start()

    def cog_unload(self):
        """Stop the task when cog is unloaded."""
        self.weekly_loop.cancel()

    @tasks.loop(minutes=1)
    async def weekly_loop(self):
        """
        Main loop that checks time and triggers freeze/thaw operations.

        Runs every minute and checks:
        - Monday 00:00 -> Begin freeze (increment week, set freeze flag)
        - Saturday 00:00 -> End freeze (process frozen transactions)
        """
        try:
            self.logger.info("Weekly loop check starting")
            config = get_config()

            # Skip if offseason mode is enabled
            if config.offseason_flag:
                self.logger.info("Skipping freeze/thaw operations - offseason mode enabled")
                return

            # Get current league state
            current = await league_service.get_current_state()
            if not current:
                self.logger.warning("Could not get current league state")
                return

            now = datetime.now()
            self.logger.info(
                f"Weekly loop check",
                datetime=now.isoformat(),
                weekday=now.weekday(),
                hour=now.hour,
                current_week=current.week,
                freeze_status=current.freeze
            )

            # BEGIN FREEZE: Monday at 00:00, not already frozen
            if now.weekday() == 0 and now.hour == 0 and not current.freeze:
                # Only run if we haven't already frozen this week
                # Track the week we're freezing FROM (before increment)
                if self.last_freeze_week != current.week:
                    self.logger.info("Triggering freeze begin", current_week=current.week)
                    await self._begin_freeze(current)
                    self.last_freeze_week = current.week  # Track the week we froze (before increment)
                    self.error_notification_sent = False  # Reset error flag for new cycle
                else:
                    self.logger.debug("Freeze already executed for week", week=current.week)

            # END FREEZE: Saturday at 00:00, currently frozen
            elif now.weekday() == 5 and now.hour == 0 and current.freeze:
                # Only run if we haven't already thawed this week
                if self.last_thaw_week != current.week:
                    self.logger.info("Triggering freeze end", current_week=current.week)
                    await self._end_freeze(current)
                    self.last_thaw_week = current.week
                    self.error_notification_sent = False  # Reset error flag for new cycle
                else:
                    self.logger.debug("Thaw already executed for week", week=current.week)

            else:
                self.logger.debug("No freeze/thaw action needed at this time")

        except Exception as e:
            self.logger.error(f"Unhandled exception in weekly_loop: {e}", error=e)
            error_message = (
                f"⚠️ **Weekly Freeze Task Failed**\n"
                f"```\n"
                f"Error: {str(e)}\n"
                f"Time: {datetime.now(UTC).isoformat()}\n"
                f"Task: weekly_loop in transaction_freeze.py\n"
                f"```"
            )

            try:
                if not self.error_notification_sent:
                    await self._send_owner_notification(error_message)
                    self.error_notification_sent = True
            except Exception as notify_error:
                self.logger.error(f"Failed to send error notification: {notify_error}")

    @weekly_loop.before_loop
    async def before_weekly_loop(self):
        """Wait for bot to be ready before starting."""
        await self.bot.wait_until_ready()
        self.logger.info("Bot is ready, transaction freeze/thaw task starting")

    async def _begin_freeze(self, current: Current):
        """
        Begin weekly freeze period.

        Actions:
        1. Increment current week
        2. Set freeze flag to True
        3. Run regular transactions for current week
        4. Send freeze announcement
        5. Post weekly info (weeks 1-18 only)
        """
        try:
            self.logger.info(f"Beginning freeze for week {current.week}")

            # Increment week and set freeze via service
            new_week = current.week + 1
            updated_current = await league_service.update_current_state(
                week=new_week,
                freeze=True
            )

            if not updated_current:
                raise Exception("Failed to update current state during freeze begin")

            self.logger.info(f"Week incremented to {new_week}, freeze set to True")

            # Update local current object with returned data
            current.week = updated_current.week
            current.freeze = updated_current.freeze

            # Run regular transactions for the new week
            await self._run_transactions(current)

            # Send freeze announcement
            await self._send_freeze_announcement(current.week, is_beginning=True)

            # Post weekly info for weeks 1-18
            if 1 <= current.week <= 18:
                await self._post_weekly_info(current)

            self.logger.info(f"Freeze begin completed for week {current.week}")

        except Exception as e:
            self.logger.error(f"Error in _begin_freeze: {e}", exc_info=True)
            raise

    async def _end_freeze(self, current: Current):
        """
        End weekly freeze period.

        Actions:
        1. Process frozen transactions with priority resolution
        2. Set freeze flag to False
        3. Send thaw announcement
        """
        try:
            self.logger.info(f"Ending freeze for week {current.week}")

            # Process frozen transactions BEFORE unfreezing
            await self._process_frozen_transactions(current)

            # Set freeze to False via service
            updated_current = await league_service.update_current_state(freeze=False)

            if not updated_current:
                raise Exception("Failed to update current state during freeze end")

            self.logger.info(f"Freeze set to False for week {current.week}")

            # Update local current object
            current.freeze = updated_current.freeze

            # Send thaw announcement
            await self._send_freeze_announcement(current.week, is_beginning=False)

            self.logger.info(f"Freeze end completed for week {current.week}")

        except Exception as e:
            self.logger.error(f"Error in _end_freeze: {e}", exc_info=True)
            raise

    async def _run_transactions(self, current: Current):
        """
        Process regular (non-frozen) transactions for the current week.

        These are transactions that take effect immediately.
        """
        try:
            # Get all non-frozen transactions for current week
            client = await transaction_service.get_client()
            params = [
                ('season', str(current.season)),
                ('week_start', str(current.week)),
                ('week_end', str(current.week))
            ]

            response = await client.get('transactions', params=params)

            if not response or response.get('count', 0) == 0:
                self.logger.info(f"No regular transactions to process for week {current.week}")
                return

            transactions = response.get('transactions', [])
            self.logger.info(f"Processing {len(transactions)} regular transactions for week {current.week}")

            # Execute player roster updates for all transactions
            success_count = 0
            failure_count = 0

            for transaction in transactions:
                try:
                    # Update player's team via PATCH /players/{player_id}?team_id={new_team_id}
                    await self._execute_player_update(
                        player_id=transaction['player']['id'],
                        new_team_id=transaction['newteam']['id'],
                        player_name=transaction['player']['name']
                    )
                    success_count += 1

                    # Rate limiting: 100ms delay between requests to avoid API overload
                    await asyncio.sleep(0.1)

                except Exception as e:
                    self.logger.error(
                        f"Failed to execute transaction for {transaction['player']['name']}",
                        player_id=transaction['player']['id'],
                        new_team_id=transaction['newteam']['id'],
                        error=str(e)
                    )
                    failure_count += 1

            self.logger.info(
                f"Transaction execution complete for week {current.week}",
                success=success_count,
                failures=failure_count,
                total=len(transactions)
            )

        except Exception as e:
            self.logger.error(f"Error running transactions: {e}", exc_info=True)

    async def _process_frozen_transactions(self, current: Current):
        """
        Process frozen transactions with priority resolution.

        Uses the NEW transaction logic (no backup implementation).

        Steps:
        1. Get all frozen transactions for current week
        2. Resolve contested transactions (multiple teams want same player)
        3. Cancel losing transactions
        4. Unfreeze and post winning transactions
        """
        try:
            # Get all frozen transactions for current week via service
            transactions = await transaction_service.get_frozen_transactions_by_week(
                season=current.season,
                week_start=current.week,
                week_end=current.week + 1
            )

            if not transactions:
                self.logger.warning(f"No frozen transactions to process for week {current.week}")
                return

            self.logger.info(f"Processing {len(transactions)} frozen transactions for week {current.week}")

            # Resolve contested transactions
            winning_move_ids, losing_move_ids = await resolve_contested_transactions(
                transactions,
                current.season
            )

            # Cancel losing transactions via service
            for losing_move_id in losing_move_ids:
                try:
                    # Get all moves with this moveid (could be multiple players in one transaction)
                    losing_moves = [t for t in transactions if t.moveid == losing_move_id]

                    if losing_moves:
                        # Cancel the entire transaction (all moves with same moveid)
                        for move in losing_moves:
                            success = await transaction_service.cancel_transaction(move.moveid)
                            if not success:
                                self.logger.warning(f"Failed to cancel transaction {move.moveid}")

                        # Notify the GM(s) about cancellation
                        first_move = losing_moves[0]

                        # Determine which team to notify (the team that was trying to acquire)
                        team_for_notification = (first_move.newteam
                                                if first_move.newteam.abbrev.upper() != 'FA'
                                                else first_move.oldteam)

                        await self._notify_gm_of_cancellation(first_move, team_for_notification)

                        contested_players = [move.player.name for move in losing_moves]
                        self.logger.info(
                            f"Cancelled transaction {losing_move_id} due to contested players: "
                            f"{contested_players}"
                        )

                except Exception as e:
                    self.logger.error(f"Error cancelling transaction {losing_move_id}: {e}")

            # Unfreeze winning transactions and post to log via service
            for winning_move_id in winning_move_ids:
                try:
                    # Get all moves with this moveid
                    winning_moves = [t for t in transactions if t.moveid == winning_move_id]

                    for move in winning_moves:
                        # Unfreeze the transaction via service
                        success = await transaction_service.unfreeze_transaction(move.moveid)
                        if not success:
                            self.logger.warning(f"Failed to unfreeze transaction {move.moveid}")

                    # Post to transaction log
                    await self._post_transaction_to_log(winning_move_id, transactions)

                    self.logger.info(f"Processed successful transaction {winning_move_id}")

                except Exception as e:
                    self.logger.error(f"Error processing winning transaction {winning_move_id}: {e}")

            self.logger.info(
                f"Freeze processing complete: {len(winning_move_ids)} successful transactions, "
                f"{len(losing_move_ids)} cancelled transactions"
            )

        except Exception as e:
            self.logger.error(f"Error during freeze processing: {e}", exc_info=True)
            raise

    async def _execute_player_update(
        self,
        player_id: int,
        new_team_id: int,
        player_name: str
    ) -> bool:
        """
        Execute a player roster update via API PATCH.

        Args:
            player_id: Player database ID
            new_team_id: New team ID to assign
            player_name: Player name for logging

        Returns:
            True if update successful, False otherwise

        Raises:
            Exception: If API call fails
        """
        try:
            self.logger.info(
                f"Updating player roster",
                player_id=player_id,
                player_name=player_name,
                new_team_id=new_team_id
            )

            # Get API client from transaction service
            client = await transaction_service.get_client()

            # Execute PATCH request to update player's team
            response = await client.patch(
                f'players/{player_id}',
                params=[('team_id', str(new_team_id))]
            )

            # Verify response (200 or 204 indicates success)
            if response is not None:
                self.logger.info(
                    f"Successfully updated player roster",
                    player_id=player_id,
                    player_name=player_name,
                    new_team_id=new_team_id
                )
                return True
            else:
                self.logger.warning(
                    f"Player update returned no response",
                    player_id=player_id,
                    player_name=player_name,
                    new_team_id=new_team_id
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Failed to update player roster",
                player_id=player_id,
                player_name=player_name,
                new_team_id=new_team_id,
                error=str(e),
                exc_info=True
            )
            raise

    async def _send_freeze_announcement(self, week: int, is_beginning: bool):
        """
        Send freeze/thaw announcement to transaction log channel.

        Args:
            week: Current week number
            is_beginning: True for freeze begin, False for freeze end
        """
        try:
            config = get_config()
            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                self.logger.warning("Could not find guild for freeze announcement")
                return

            channel = discord.utils.get(guild.text_channels, name='transaction-log')
            if not channel:
                self.logger.warning("Could not find transaction-log channel")
                return

            # Create announcement message (formatted like legacy bot)
            week_num = f'Week {week}'
            stars = '*' * 32

            if is_beginning:
                message = (
                    f'```\n'
                    f'{stars}\n'
                    f'{week_num:>9} Freeze Period Begins\n'
                    f'{stars}\n'
                    f'```'
                )
            else:
                message = (
                    f'```\n'
                    f'{"*" * 30}\n'
                    f'{week_num:>9} Freeze Period Ends\n'
                    f'{"*" * 30}\n'
                    f'```'
                )

            await channel.send(message)
            self.logger.info(f"Freeze announcement sent for week {week} ({'begin' if is_beginning else 'end'})")

        except Exception as e:
            self.logger.error(f"Error sending freeze announcement: {e}")

    async def _post_weekly_info(self, current: Current):
        """
        Post weekly schedule information to #weekly-info channel.

        Args:
            current: Current league state
        """
        try:
            config = get_config()
            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                return

            info_channel = discord.utils.get(guild.text_channels, name='weekly-info')
            if not info_channel:
                self.logger.warning("Could not find weekly-info channel")
                return

            # Clear recent messages (last 25)
            async for message in info_channel.history(limit=25):
                try:
                    await message.delete()
                except:
                    pass  # Ignore deletion errors

            # Determine season emoji
            if current.week <= 5:
                season_str = "🌼 **Spring**"
            elif current.week > 14:
                season_str = "🍂 **Fall**"
            else:
                season_str = "🏖️ **Summer**"

            # Determine day/night schedule
            night_str = "🌙 Night"
            day_str = "🌞 Day"
            is_div_week = current.week in [1, 3, 6, 14, 16, 18]

            weekly_str = (
                f'**Season**: {season_str}\n'
                f'**Time of Day**: {night_str} / {night_str if is_div_week else day_str} / '
                f'{night_str} / {day_str}'
            )

            # Send info messages
            await info_channel.send(
                content=(
                    f'Each team has manage permissions in their home ballpark. '
                    f'They may pin messages and rename the channel.\n\n'
                    f'**Make sure your ballpark starts with your team abbreviation.**'
                )
            )
            await info_channel.send(weekly_str)

            self.logger.info(f"Weekly info posted for week {current.week}")

        except Exception as e:
            self.logger.error(f"Error posting weekly info: {e}")

    async def _post_transaction_to_log(
        self,
        move_id: str,
        all_transactions: List[Transaction]
    ):
        """
        Post a transaction to the transaction log channel.

        Args:
            move_id: Transaction move ID
            all_transactions: List of all transactions to find moves with this ID
        """
        try:
            config = get_config()
            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                return

            channel = discord.utils.get(guild.text_channels, name='transaction-log')
            if not channel:
                return

            # Get all moves with this moveid
            moves = [t for t in all_transactions if t.moveid == move_id]
            if not moves:
                return

            # Determine the team for the embed (team making the moves)
            first_move = moves[0]
            if first_move.newteam.abbrev.upper() != 'FA' and 'IL' not in first_move.newteam.abbrev:
                this_team = first_move.newteam
            elif first_move.oldteam.abbrev.upper() != 'FA' and 'IL' not in first_move.oldteam.abbrev:
                this_team = first_move.oldteam
            else:
                # Default to newteam if both are FA/IL
                this_team = first_move.newteam

            # Build move string
            move_string = ""
            week_num = first_move.week

            for move in moves:
                move_string += (
                    f'**{move.player.name}** ({move.player.wara:.2f}) '
                    f'from {move.oldteam.abbrev} to {move.newteam.abbrev}\n'
                )

            # Create embed
            embed = EmbedTemplate.create_base_embed(
                title=f'Week {week_num} Transaction',
                description=this_team.sname if hasattr(this_team, 'sname') else this_team.lname,
                color=EmbedColors.INFO
            )

            # Set team color if available
            if hasattr(this_team, 'color') and this_team.color:
                try:
                    embed.color = discord.Color(int(this_team.color.replace('#', ''), 16))
                except:
                    pass  # Use default color on error

            embed.add_field(name='Player Moves', value=move_string, inline=False)

            await channel.send(embed=embed)
            self.logger.info(f"Transaction posted to log: {move_id}")

        except Exception as e:
            self.logger.error(f"Error posting transaction to log: {e}")

    async def _notify_gm_of_cancellation(
        self,
        transaction: Transaction,
        team
    ):
        """
        Send DM to GM(s) about cancelled transaction.

        Args:
            transaction: The cancelled transaction
            team: Team whose GMs should be notified
        """
        try:
            config = get_config()
            guild = self.bot.get_guild(config.guild_id)
            if not guild:
                return

            cancel_text = (
                f'Your transaction for **{transaction.player.name}** has been cancelled '
                f'because another team successfully claimed them during the freeze period.'
            )

            # Notify GM1
            if hasattr(team, 'gmid') and team.gmid:
                try:
                    gm_one = guild.get_member(team.gmid)
                    if gm_one:
                        await gm_one.send(cancel_text)
                        self.logger.info(f"Cancellation notification sent to GM1 of {team.abbrev}")
                except Exception as e:
                    self.logger.error(f"Could not notify GM1 of {team.abbrev}: {e}")

            # Notify GM2 if exists
            if hasattr(team, 'gmid2') and team.gmid2:
                try:
                    gm_two = guild.get_member(team.gmid2)
                    if gm_two:
                        await gm_two.send(cancel_text)
                        self.logger.info(f"Cancellation notification sent to GM2 of {team.abbrev}")
                except Exception as e:
                    self.logger.error(f"Could not notify GM2 of {team.abbrev}: {e}")

        except Exception as e:
            self.logger.error(f"Error notifying GM of cancellation: {e}")

    async def _send_owner_notification(self, message: str):
        """
        Send error notification to bot owner.

        Args:
            message: Error message to send
        """
        try:
            app_info = await self.bot.application_info()
            if app_info.owner:
                await app_info.owner.send(message)
                self.logger.info("Owner notification sent")
        except Exception as e:
            self.logger.error(f"Could not send owner notification: {e}")


def setup_freeze_task(bot: commands.Bot) -> TransactionFreezeTask:
    """Set up the transaction freeze/thaw task."""
    return TransactionFreezeTask(bot)
