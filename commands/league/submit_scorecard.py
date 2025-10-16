"""
Scorecard Submission Commands

Implements the /submit-scorecard command for submitting Google Sheets
scorecards with play-by-play data, pitching decisions, and game results.
"""
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from services.sheets_service import SheetsService
from services.game_service import game_service
from services.play_service import play_service
from services.decision_service import decision_service
from services.standings_service import standings_service
from services.league_service import league_service
from services.team_service import team_service
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.discord_helpers import send_to_channel, format_key_plays
from utils.team_utils import get_user_major_league_team
from views.embeds import EmbedTemplate
from views.confirmations import ConfirmationView
from constants import (
    SBA_NETWORK_NEWS_CHANNEL,
    SBA_PLAYERS_ROLE_NAME
)
from exceptions import SheetsException, APIException
from models.team import Team
from models.player import Player

DRY_RUN = False


class SubmitScorecardCommands(commands.Cog):
    """Scorecard submission command handlers."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.SubmitScorecardCommands')
        self.sheets_service = SheetsService()  # Will use config automatically
        self.logger.info("SubmitScorecardCommands cog initialized")

    @app_commands.command(
        name="submit-scorecard",
        description="Submit a Google Sheets scorecard with game results and play data"
    )
    @app_commands.describe(
        sheet_url="Full URL to the Google Sheets scorecard"
    )
    @app_commands.checks.has_any_role(SBA_PLAYERS_ROLE_NAME)
    @logged_command("/submit-scorecard")
    async def submit_scorecard(
        self,
        interaction: discord.Interaction,
        sheet_url: str
    ):
        """
        Submit scorecard with full transaction rollback support.

        Workflow:
        1. Validate scorecard access and version
        2. Extract game metadata
        3. Check permissions (user must own one of the teams)
        4. Handle duplicate games (with confirmation)
        5. Read play and decision data
        6. Submit data with transaction rollback on errors
        7. Post results to news channel
        8. Recalculate standings
        """
        # Always defer since this is a long-running operation
        await interaction.response.defer()

        # Track rollback state
        rollback_state = None
        game_id = None

        try:
            # Phase 1: Initial Validation
            await interaction.edit_original_response(
                content="📋 Accessing scorecard..."
            )

            current = await league_service.get_current_state()
            if not current:
                raise APIException("Unable to retrieve current league state")

            # Open scorecard
            try:
                scorecard = await self.sheets_service.open_scorecard(sheet_url)
            except SheetsException:
                await interaction.edit_original_response(
                    content="❌ Is that sheet public? I can't access it."
                )
                return

            # Read setup data
            setup_data = await self.sheets_service.read_setup_data(scorecard)

            # Validate scorecard version
            if setup_data['version'] != current.bet_week:
                await interaction.edit_original_response(
                    content=(
                        f"❌ This scorecard appears out of date (version {setup_data['version']}, "
                        f"expected {current.bet_week}). Did you create a new card at the start "
                        f"of the game? If so, contact an admin about this error."
                    )
                )
                return

            # Phase 2: Team & Manager Lookup
            await interaction.edit_original_response(
                content="🔍 Looking up teams and managers..."
            )

            away_team = await team_service.get_team_by_abbrev(
                setup_data['away_team_abbrev'],
                current.season
            )
            home_team = await team_service.get_team_by_abbrev(
                setup_data['home_team_abbrev'],
                current.season
            )

            if not away_team or not home_team:
                await interaction.edit_original_response(
                    content="❌ One or both teams not found in database."
                )
                return

            # Match managers
            away_manager = self._match_manager(
                away_team,
                setup_data['away_manager_name']
            )
            home_manager = self._match_manager(
                home_team,
                setup_data['home_manager_name']
            )

            # Phase 3: Permission Check
            user_team = await get_user_major_league_team(
                interaction.user.id,
                current.season
            )

            if user_team is None:
                # Check if user is bot owner
                app_info = await self.bot.application_info()
                if interaction.user.id != app_info.owner.id:
                    await interaction.edit_original_response(
                        content="❌ Only a GM of the two teams can submit scorecards."
                    )
                    return
            elif user_team.id not in [away_team.id, home_team.id]:
                await interaction.edit_original_response(
                    content="❌ Only a GM of the two teams can submit scorecards."
                )
                return

            # Phase 4: Duplicate Game Check
            duplicate_game = await game_service.find_duplicate_game(
                current.season,
                setup_data['week'],
                setup_data['game_num'],
                away_team.id,
                home_team.id
            )

            if duplicate_game:
                view = ConfirmationView(
                    responders=[interaction.user],
                    timeout=30.0
                )
                await interaction.edit_original_response(
                    content=(
                        f"⚠️ This game has already been played!\n"
                        f"Would you like me to wipe the old one and re-submit?"
                    ),
                    view=view
                )
                await view.wait()

                if view.confirmed:
                    await interaction.edit_original_response(
                        content="🗑️ Wiping old game data...",
                        view=None
                    )

                    # Delete old data
                    try:
                        await play_service.delete_plays_for_game(duplicate_game.id)
                    except:
                        pass  # May not exist

                    try:
                        await decision_service.delete_decisions_for_game(duplicate_game.id)
                    except:
                        pass  # May not exist

                    await game_service.wipe_game_data(duplicate_game.id)

                else:
                    await interaction.edit_original_response(
                        content="❌ You think on it some more and get back to me later.",
                        view=None
                    )
                    return

            # Phase 5: Find Scheduled Game
            scheduled_game = await game_service.find_scheduled_game(
                current.season,
                setup_data['week'],
                away_team.id,
                home_team.id
            )

            if not scheduled_game:
                await interaction.edit_original_response(
                    content=(
                        f"❌ I don't see any games between {away_team.abbrev} and "
                        f"{home_team.abbrev} in week {setup_data['week']}."
                    )
                )
                return

            game_id = scheduled_game.id

            # Phase 6: Read Scorecard Data
            await interaction.edit_original_response(
                content="📊 Reading play-by-play data..."
            )

            plays_data = await self.sheets_service.read_playtable_data(scorecard)

            # Add game_id to each play
            for play in plays_data:
                play['game_id'] = game_id

            # Phase 7: POST Plays
            await interaction.edit_original_response(
                content="💾 Submitting plays to database..."
            )

            try:
                if not DRY_RUN:
                    await play_service.create_plays_batch(plays_data)
                self.logger.info(f'Posting plays_data (1 and 2): {plays_data[0]} / {plays_data[1]}')
                rollback_state = "PLAYS_POSTED"
            except APIException as e:
                await interaction.edit_original_response(
                    content=(
                        f"❌ The following errors were found in your "
                        f"**wk{setup_data['week']}g{setup_data['game_num']}** scorecard:\n\n"
                        f"{str(e)}\n\n"
                        f"Please resolve them and resubmit - thanks!"
                    )
                )
                return

            # Phase 8: Read Box Score
            box_score = await self.sheets_service.read_box_score(scorecard)

            # Phase 9: PATCH Game
            await interaction.edit_original_response(
                content="⚾ Updating game result..."
            )

            try:
                if not DRY_RUN:
                    await game_service.update_game_result(
                        game_id,
                        box_score['away'][0],  # Runs
                        box_score['home'][0],  # Runs
                        away_manager.id,
                        home_manager.id,
                        setup_data['game_num'],
                        sheet_url
                    )
                self.logger.info(f'Updating game ID {game_id}, {box_score['away'][0]} @ {box_score['home'][0]}, {away_manager.id} vs {home_manager.id}')
                rollback_state = "GAME_PATCHED"
            except APIException as e:
                # Rollback plays
                await play_service.delete_plays_for_game(game_id)
                await interaction.edit_original_response(
                    content=f"❌ Unable to log game result. Error: {str(e)}"
                )
                return

            # Phase 10: Read Pitching Decisions
            decisions_data = await self.sheets_service.read_pitching_decisions(scorecard)

            # Add game metadata to each decision
            for decision in decisions_data:
                decision['game_id'] = game_id
                decision['season'] = current.season
                decision['week'] = setup_data['week']
                decision['game_num'] = setup_data['game_num']

            # Validate WP and LP exist and fetch Player objects
            wp, lp, sv, holders, _blown_saves = \
                await decision_service.find_winning_losing_pitchers(decisions_data)

            if wp is None or lp is None:
                # Rollback
                await game_service.wipe_game_data(game_id)
                await play_service.delete_plays_for_game(game_id)
                await interaction.edit_original_response(
                    content="❌ Your card is missing either a Winning Pitcher or Losing Pitcher"
                )
                return

            # Phase 11: POST Decisions
            await interaction.edit_original_response(
                content="🎯 Submitting pitching decisions..."
            )

            try:
                if not DRY_RUN:
                    await decision_service.create_decisions_batch(decisions_data)
                rollback_state = "COMPLETE"
            except APIException as e:
                # Rollback everything
                await game_service.wipe_game_data(game_id)
                await play_service.delete_plays_for_game(game_id)
                await interaction.edit_original_response(
                    content=(
                        f"❌ The following errors were found in your "
                        f"**wk{setup_data['week']}g{setup_data['game_num']}** "
                        f"pitching decisions:\n\n{str(e)}\n\n"
                        f"Please resolve them and resubmit - thanks!"
                    )
                )
                return

            # Phase 12: Create Results Embed
            await interaction.edit_original_response(
                content="📰 Posting results..."
            )

            results_embed = await self._create_results_embed(
                away_team,
                home_team,
                box_score,
                setup_data,
                current,
                sheet_url,
                wp,
                lp,
                sv,
                holders,
                game_id
            )

            # Phase 13: Post to News Channel
            await send_to_channel(
                self.bot,
                SBA_NETWORK_NEWS_CHANNEL,
                content=None,
                embed=results_embed
            )

            # Phase 14: Recalculate Standings
            await interaction.edit_original_response(
                content="📊 Tallying standings..."
            )

            try:
                await standings_service.recalculate_standings(current.season)
            except:
                # Non-critical error
                self.logger.error("Failed to recalculate standings")

            # Success!
            await interaction.edit_original_response(
                content="✅ You are all set!"
            )

        except Exception as e:
            # Unexpected error - attempt rollback
            self.logger.error(f"Unexpected error in scorecard submission: {e}", exc_info=True)

            if rollback_state and game_id:
                try:
                    if rollback_state == "GAME_PATCHED":
                        await game_service.wipe_game_data(game_id)
                        await play_service.delete_plays_for_game(game_id)
                    elif rollback_state == "PLAYS_POSTED":
                        await play_service.delete_plays_for_game(game_id)
                except:
                    pass  # Best effort rollback

            await interaction.edit_original_response(
                content=f"❌ An unexpected error occurred: {str(e)}"
            )

    def _match_manager(self, team: Team, manager_name: str):
        """
        Match manager name from sheet to team's manager1 or manager2.

        Args:
            team: Team object
            manager_name: Manager name from scorecard

        Returns:
            Manager object (manager1 or manager2)
        """
        if team.manager2 and team.manager2.name.lower() == manager_name.lower():
            return team.manager2
        else:
            return team.manager1

    async def _create_results_embed(
        self,
        away_team: Team,
        home_team: Team,
        box_score: dict,
        setup_data: dict,
        current,
        sheet_url: str,
        wp: Optional[Player],
        lp: Optional[Player],
        sv: Optional[Player],
        holders: List[Player],
        game_id: int
    ):
        """
        Create rich embed with game results.

        Args:
            away_team: Away team object
            home_team: Home team object
            box_score: Box score data dict with 'away' and 'home' keys
            setup_data: Game setup data from scorecard
            current: Current league state
            sheet_url: URL to scorecard
            wp: Winning pitcher Player object
            lp: Losing pitcher Player object
            sv: Save pitcher Player object (optional)
            holders: List of Player objects with holds
            game_id: Game ID for key plays lookup

        Returns:
            Discord Embed with game results
        """

        # Determine winner and loser
        away_score = box_score['away'][0]
        home_score = box_score['home'][0]

        if away_score > home_score:
            winning_team = away_team
            losing_team = home_team
            winner_abbrev = away_team.abbrev
            loser_abbrev = home_team.abbrev
            winner_score = away_score
            loser_score = home_score
        else:
            winning_team = home_team
            losing_team = away_team
            winner_abbrev = home_team.abbrev
            loser_abbrev = away_team.abbrev
            winner_score = home_score
            loser_score = away_score

        # Create embed
        embed = EmbedTemplate.create_base_embed(
            title=f"{winner_abbrev} defeats {loser_abbrev} {winner_score}-{loser_score}",
            description=f"Season {current.season}, Week {setup_data['week']}, Game {setup_data['game_num']}"
        )
        embed.color = winning_team.get_color_int()
        if winning_team.thumbnail:
            embed.set_thumbnail(url=winning_team.thumbnail)

        # Add box score
        box_score_text = (
            f"```\n"
            f"{'Team':<6} {'R':<3} {'H':<3} {'E':<3}\n"
            f"{away_team.abbrev:<6} {box_score['away'][0]:<3} {box_score['away'][1]:<3} {box_score['away'][2]:<3}\n"
            f"{home_team.abbrev:<6} {box_score['home'][0]:<3} {box_score['home'][1]:<3} {box_score['home'][2]:<3}\n"
            f"```"
        )
        embed.add_field(name="Box Score", value=box_score_text, inline=False)

        # Add pitching decisions - much simpler now!
        decisions_text = ""

        if wp:
            decisions_text += f"**WP:** {wp.display_name}\n"

        if lp:
            decisions_text += f"**LP:** {lp.display_name}\n"

        if holders:
            hold_names = [holder.display_name for holder in holders]
            decisions_text += f"**HLD:** {', '.join(hold_names)}\n"

        if sv:
            decisions_text += f"**SV:** {sv.display_name}\n"

        if decisions_text:
            embed.add_field(name="Pitching Decisions", value=decisions_text, inline=True)

        # Add scorecard link
        embed.add_field(
            name="Scorecard",
            value=f"[View Full Scorecard]({sheet_url})",
            inline=True
        )

        # Try to get key plays (non-critical)
        try:
            key_plays = await play_service.get_top_plays_by_wpa(game_id, limit=3)
            if key_plays:
                key_plays_text = format_key_plays(key_plays, away_team, home_team)
                if key_plays_text:
                    embed.add_field(name="Key Plays", value=key_plays_text, inline=False)
        except Exception as e:
            self.logger.warning(f"Failed to get key plays: {e}")

        return embed


async def setup(bot: commands.Bot):
    """Load the submit scorecard commands cog."""
    await bot.add_cog(SubmitScorecardCommands(bot))
