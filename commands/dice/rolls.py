"""
Dice Rolling Commands

Implements slash commands for dice rolling functionality required for gameplay.
"""
import random
import re
from typing import Optional

import discord
from discord.ext import commands

from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from views.embeds import EmbedColors, EmbedTemplate


class DiceRollCommands(commands.Cog):
    """Dice rolling command handlers for gameplay."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = get_contextual_logger(f'{__name__}.DiceRollCommands')

    @discord.app_commands.command(
        name="roll",
        description="Roll polyhedral dice using XdY notation (e.g., 2d6, 1d20, 3d8)"
    )
    @discord.app_commands.describe(
        dice="Dice notation - single or multiple separated by semicolon (e.g., 2d6, 1d20;2d6;1d6)"
    )
    @logged_command("/roll")
    async def roll_dice(
        self,
        interaction: discord.Interaction,
        dice: str
    ):
        """Roll dice using standard XdY dice notation. Supports multiple rolls separated by semicolon."""
        await interaction.response.defer()

        # Parse and validate dice notation (supports multiple rolls)
        roll_results = self._parse_and_roll_multiple_dice(dice)
        if not roll_results:
            await interaction.followup.send(
                "❌ Invalid dice notation. Use format like: 2d6, 1d20, or 1d6;2d6;1d20",
                ephemeral=True
            )
            return

        # Create embed for the roll results
        embed = self._create_multi_roll_embed(dice, roll_results, interaction.user)
        await interaction.followup.send(embed=embed)

    @commands.command(name="roll", aliases=["r", "dice"])
    async def roll_dice_prefix(self, ctx: commands.Context, *, dice: str | None = None):
        """Roll dice using prefix commands (!roll, !r, !dice)."""
        self.logger.info(f"Prefix roll command started by {ctx.author.display_name}", dice_input=dice)

        if dice is None:
            self.logger.debug("No dice input provided")
            await ctx.send("❌ Please provide dice notation. Usage: `!roll 2d6` or `!roll 1d6;2d6;1d20`")
            return

        # Parse and validate dice notation (supports multiple rolls)
        roll_results = self._parse_and_roll_multiple_dice(dice)
        if not roll_results:
            self.logger.warning("Invalid dice notation provided", dice_input=dice)
            await ctx.send("❌ Invalid dice notation. Use format like: 2d6, 1d20, or 1d6;2d6;1d20")
            return

        self.logger.info(f"Dice rolled successfully", roll_count=len(roll_results))

        # Create embed for the roll results
        embed = self._create_multi_roll_embed(dice, roll_results, ctx.author)
        await ctx.send(embed=embed)

    @discord.app_commands.command(
        name="ab",
        description="Roll baseball at-bat dice (1d6;2d6;1d20)"
    )
    @logged_command("/ab")
    async def ab_dice(self, interaction: discord.Interaction):
        """Roll the standard baseball at-bat dice combination."""
        await interaction.response.defer()

        # Use the standard baseball dice combination
        dice_notation = "1d6;2d6;1d20"
        roll_results = self._parse_and_roll_multiple_dice(dice_notation)

        # Create embed for the roll results
        embed = self._create_multi_roll_embed(dice_notation, roll_results, interaction.user)
        embed.title = f'At bat roll for {interaction.user.display_name}'
        await interaction.followup.send(embed=embed)

    @commands.command(name="ab", aliases=["atbat"])
    async def ab_dice_prefix(self, ctx: commands.Context):
        """Roll baseball at-bat dice using prefix commands (!ab, !atbat)."""
        self.logger.info(f"At Bat dice command started by {ctx.author.display_name}")

        # Use the standard baseball dice combination
        dice_notation = "1d6;2d6;1d20"
        roll_results = self._parse_and_roll_multiple_dice(dice_notation)

        self.logger.info("At Bat dice rolled successfully", roll_count=len(roll_results))

        # Create embed for the roll results
        embed = self._create_multi_roll_embed(dice_notation, roll_results, ctx.author)
        embed.title = f'At bat roll for {ctx.author.display_name}'
        await ctx.send(embed=embed)

    @discord.app_commands.command(
        name="scout",
        description="Roll weighted scouting dice (1d6;2d6;1d20) based on card type"
    )
    @discord.app_commands.describe(
        card_type="Type of card being scouted"
    )
    @discord.app_commands.choices(card_type=[
        discord.app_commands.Choice(name="Batter", value="batter"),
        discord.app_commands.Choice(name="Pitcher", value="pitcher")
    ])
    @logged_command("/scout")
    async def scout_dice(
        self,
        interaction: discord.Interaction,
        card_type: discord.app_commands.Choice[str]
    ):
        """Roll weighted scouting dice based on card type (batter or pitcher)."""
        await interaction.response.defer()

        # Get the card type value
        card_type_value = card_type.value

        # Roll weighted scouting dice
        roll_results = self._roll_weighted_scout_dice(card_type_value)

        # Create embed for the roll results
        embed = self._create_multi_roll_embed("1d6;2d6;1d20", roll_results, interaction.user)
        embed.title = f'Scouting roll for {interaction.user.display_name} ({card_type.name})'
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="fielding",
        description="Roll Super Advanced fielding dice for a defensive position"
    )
    @discord.app_commands.describe(
        position="Defensive position"
    )
    @discord.app_commands.choices(position=[
        discord.app_commands.Choice(name="Catcher (C)", value="C"),
        discord.app_commands.Choice(name="First Base (1B)", value="1B"),
        discord.app_commands.Choice(name="Second Base (2B)", value="2B"),
        discord.app_commands.Choice(name="Third Base (3B)", value="3B"),
        discord.app_commands.Choice(name="Shortstop (SS)", value="SS"),
        discord.app_commands.Choice(name="Left Field (LF)", value="LF"),
        discord.app_commands.Choice(name="Center Field (CF)", value="CF"),
        discord.app_commands.Choice(name="Right Field (RF)", value="RF")
    ])
    @logged_command("/fielding")
    async def fielding_roll(
        self,
        interaction: discord.Interaction,
        position: discord.app_commands.Choice[str]
    ):
        """Roll Super Advanced fielding dice for a defensive position."""
        await interaction.response.defer()

        # Get the position value from the choice
        pos_value = position.value

        # Roll the dice - 1d20 and 3d6
        dice_notation = "1d20;3d6"
        roll_results = self._parse_and_roll_multiple_dice(dice_notation)

        # Create fielding embed
        embed = self._create_fielding_embed(pos_value, roll_results, interaction.user)
        await interaction.followup.send(embed=embed)

    @commands.command(name="f", aliases=["fielding", "saf"])
    async def fielding_roll_prefix(self, ctx: commands.Context, position: str | None = None):
        """Roll Super Advanced fielding dice using prefix commands (!f, !fielding, !saf)."""
        self.logger.info(f"SA Fielding command started by {ctx.author.display_name}", position=position)

        if position is None:
            await ctx.send("❌ Please specify a position. Usage: `!f 3B` or `!fielding SS`")
            return

        # Parse and validate position
        parsed_position = self._parse_position(position)
        if not parsed_position:
            await ctx.send("❌ Invalid position. Use: C, 1B, 2B, 3B, SS, LF, CF, RF")
            return

        # Roll the dice - 1d20 and 3d6
        dice_notation = "1d20;3d6"
        roll_results = self._parse_and_roll_multiple_dice(dice_notation)

        self.logger.info("SA Fielding dice rolled successfully", position=parsed_position, d20=roll_results[0]['total'], d6_total=roll_results[1]['total'])

        # Create fielding embed
        embed = self._create_fielding_embed(parsed_position, roll_results, ctx.author)
        await ctx.send(embed=embed)

    def _parse_position(self, position: str) -> str | None:
        """Parse and validate fielding position input for prefix commands."""
        if not position:
            return None

        pos = position.upper().strip()

        # Map common inputs to standard position names
        position_map = {
            'C': 'C', 'CATCHER': 'C',
            '1': '1B', '1B': '1B', 'FIRST': '1B', 'FIRSTBASE': '1B',
            '2': '2B', '2B': '2B', 'SECOND': '2B', 'SECONDBASE': '2B',
            '3': '3B', '3B': '3B', 'THIRD': '3B', 'THIRDBASE': '3B',
            'SS': 'SS', 'SHORT': 'SS', 'SHORTSTOP': 'SS',
            'LF': 'LF', 'LEFT': 'LF', 'LEFTFIELD': 'LF',
            'CF': 'CF', 'CENTER': 'CF', 'CENTERFIELD': 'CF',
            'RF': 'RF', 'RIGHT': 'RF', 'RIGHTFIELD': 'RF'
        }

        return position_map.get(pos)

    def _create_fielding_embed(self, position: str, roll_results: list[dict], user) -> discord.Embed:
        """Create an embed for fielding roll results."""
        d20_result = roll_results[0]['total']
        d6_total = roll_results[1]['total']
        d6_rolls = roll_results[1]['rolls']

        # Create base embed
        embed = EmbedTemplate.create_base_embed(
            title=f"SA Fielding roll for {user.display_name}",
            color=EmbedColors.PRIMARY
        )

        # Set user info
        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url
        )

        # Add dice results in standard format
        dice_notation = "1d20;3d6"
        embed_dice = self._create_multi_roll_embed(dice_notation, roll_results, user)

        # Extract just the dice result part from the field
        dice_field_value = embed_dice.fields[0].value
        embed.add_field(
            name="Dice Results",
            value=dice_field_value,
            inline=False
        )

        # Add fielding check summary
        range_result = self._get_range_result(position, d20_result)
        embed.add_field(
            name=f"{position} Fielding Check Summary",
            value=f"```\nRange Result\n 1 | 2 | 3 | 4 | 5\n{range_result}```",
            inline=False
        )

        # Add error result
        error_result = self._get_error_result(position, d6_total)
        if error_result:
            embed.add_field(
                name="Error Result",
                value=error_result,
                inline=False
            )

        # Add help commands
        embed.add_field(
            name="Help Commands",
            value="Run !<result> for full chart readout (e.g. !g1 or !do3)",
            inline=False
        )

        # Add references
        embed.add_field(
            name="References",
            value="Range Chart / Error Chart / Result Reference",
            inline=False
        )

        return embed

    def _get_range_result(self, position: str, d20_roll: int) -> str:
        """Get the range result display for a position and d20 roll."""
        # Infield positions share the same range chart
        if position in ['1B', '2B', '3B', 'SS']:
            return self._get_infield_range(d20_roll)
        elif position in ['LF', 'CF', 'RF']:
            return self._get_outfield_range(d20_roll)
        elif position == 'C':
            return self._get_catcher_range(d20_roll)
        return "Unknown position"

    def _get_infield_range(self, d20_roll: int) -> str:
        """Get infield range result based on d20 roll."""
        infield_ranges = {
            1: 'G3# SI1 ----SI2----',
            2: 'G2# SI1 ----SI2----',
            3: 'G2# G3# SI1 --SI2--',
            4: 'G2# G3# SI1 --SI2--',
            5: 'G1  --G3#-- SI1 SI2',
            6: 'G1  G2# G3# SI1 SI2',
            7: 'G1  G2  --G3#-- SI1',
            8: 'G1  G2  --G3#-- SI1',
            9: 'G1  G2  G3  --G3#--',
            10: '--G1--- G2  --G3#--',
            11: '--G1--- G2  G3  G3#',
            12: '--G1--- G2  G3  G3#',
            13: '--G1--- G2  --G3---',
            14: '--G1--- --G2--- G3',
            15: '----G1----- G2  G3',
            16: '----G1----- G2  G3',
            17: '------G1------- G3',
            18: '------G1------- G2',
            19: '------G1------- G2',
            20: '--------G1---------'
        }
        return infield_ranges.get(d20_roll, 'Unknown')

    def _get_outfield_range(self, d20_roll: int) -> str:
        """Get outfield range result based on d20 roll."""
        outfield_ranges = {
            1: 'F1  DO2 DO3 --TR3--',
            2: 'F2  SI2 DO2 DO3 TR3',
            3: 'F2  SI2 --DO2-- DO3',
            4: 'F2  F1  SI2 DO2 DO3',
            5: '--F2--- --SI2-- DO2',
            6: '--F2--- --SI2-- DO2',
            7: '--F2--- F1  SI2 DO2',
            8: '--F2--- F1  --SI2--',
            9: '----F2----- --SI2--',
            10: '----F2----- --SI2--',
            11: '----F2----- --SI2--',
            12: '----F2----- F1  SI2',
            13: '----F2----- F1  SI2',
            14: 'F3  ----F2----- SI2',
            15: 'F3  ----F2----- SI2',
            16: '--F3--- --F2--- F1',
            17: '----F3----- F2  F1',
            18: '----F3----- F2  F1',
            19: '------F3------- F2',
            20: '--------F3---------'
        }
        return outfield_ranges.get(d20_roll, 'Unknown')

    def _get_catcher_range(self, d20_roll: int) -> str:
        """Get catcher range result based on d20 roll."""
        catcher_ranges = {
            1: 'G3  ------SI1------',
            2: 'G3  SPD ----SI1----',
            3: '--G3--- SPD --SI1--',
            4: 'G2  G3  --SPD-- SI1',
            5: 'G2  --G3--- --SPD--',
            6: '--G2--- G3  --SPD--',
            7: 'PO  G2  G3  --SPD--',
            8: 'PO  --G2--- G3  SPD',
            9: '--PO--- G2  G3  SPD',
            10: 'FO  PO  G2  G3  SPD',
            11: 'FO  --PO--- G2  G3',
            12: '--FO--- PO  G2  G3',
            13: 'G1  FO  PO  G2  G3',
            14: 'G1  --FO--- PO  G2',
            15: '--G1--- FO  PO  G2',
            16: '--G1--- FO  PO  G2',
            17: '----G1----- FO  PO',
            18: '----G1----- FO  PO',
            19: '----G1----- --FO---',
            20: '------G1------- FO'
        }
        return catcher_ranges.get(d20_roll, 'Unknown')

    def _get_error_result(self, position: str, d6_total: int) -> str:
        """Get the error result for a position and 3d6 total."""
        # Get the appropriate error chart
        if position == '1B':
            return self._get_1b_error(d6_total)
        elif position == '2B':
            return self._get_2b_error(d6_total)
        elif position == '3B':
            return self._get_3b_error(d6_total)
        elif position == 'SS':
            return self._get_ss_error(d6_total)
        elif position in ['LF', 'RF']:
            return self._get_corner_of_error(d6_total)
        elif position == 'CF':
            return self._get_cf_error(d6_total)
        elif position == 'C':
            return self._get_catcher_error(d6_total)

        # Should never reach here due to position validation, but follow "Raise or Return" pattern
        raise ValueError(f"Unknown position: {position}")

    def _get_3b_error(self, d6_total: int) -> str:
        """Get 3B error result based on 3d6 total."""
        errors = {
            18: '2-base error for e11 -> e18, e32, e33, e37, e53, e62, e65\n1-base error for e4, e8, e19, e21, e22, e27, e41',
            17: '2-base error for e3 -> e10, e17, e18, e25 -> e27, e34 -> e37, e44, e47\n1-base error for e11, e19, e32, e56',
            16: '2-base error for e11 -> e18, e32, e33, e37, e53, e62, e65\n1-base error for e4, e8, e19, e21, e22, e27, e41',
            15: '2-base error for e19 -> 27, e32, e33, e37, e39, e44, e50, e59\n1-base error for e5 -> e8, e11, e14, e15, e17, e18, e28 -> e31, e34',
            14: '2-base error for e28 -> e31, e34, e35, e50\n1-base error for e14, e16, e19, e20, e22, e32, e39, e44, e56, e62',
            13: '2-base error for e41, e47, e53, e59\n1-base error for e10, e15, e23, e25, e28, e30, e32, e33, e35, e44, e65',
            12: '2-base error for e62\n1-base error for e12, e17, e22, e24, e27, e29, e34 -> e50, e56 -> e59, e65',
            11: '2-base error for e56, e65\n1-base error for e13, e18, e20, e21, e23, e26, e28, e31 -> e33, e35, e37, e41 -> e53, e59, e65',
            10: '1-base error for e26, e31, e41, e53 -> 65',
            9: '1-base error for e24, e27, e29, e34, e37, e39, e47 -> e65',
            8: '1-base error for e25, e30, e33, e47, e53, e56, e62, e65',
            7: '1-base error for e16, e19, e39, e59 -> e65',
            6: '1-base error for e21, e25, e30, e34, e53',
            5: 'No error',
            4: '1-base error for e2, e3, e6, e14, e16, e44',
            3: '2-base error for e10, e15, e16, e23, e24, e56\n1-base error for e1 -> e4, e8, e14'
        }
        return errors.get(d6_total, 'No error')

    def _get_1b_error(self, d6_total: int) -> str:
        """Get 1B error result based on 3d6 total."""
        errors = {
            18: '2-base error for e3 -> e12, e19 -> e28\n1-base error for e1, e2, e30',
            17: '2-base error for e13 -> e28\n1-base error for e1, e5, e8, e9, e29',
            16: '2-base error for e29, e30\n1-base error for e2, e8, e16, e19, e23',
            15: '1-base error for e3, e8, e10 -> e12, e20, e26, e30',
            14: '1-base error for e4, e5, e9, e15, e18, e22, e24 -> e28',
            13: '1-base error for e6, e13, e24, e26 -> e28, e30',
            12: '1-base error for e14 -> e18, e21 -> e26, e28 -> e30',
            11: '1-base error for e10, e13, e16 -> e20, e23 -> e25, e27 -> e30',
            10: '1-base error for e19 -> e21, e23, e29',
            9: '1-base error for e7, e12, e14, e21, e25, e26, e29',
            8: '1-base error for e11, e27',
            7: '1-base error for e9, e15, e22, e27, e28',
            6: '1-base error for e8, e11, e12, e17, e20',
            5: 'No error',
            4: 'No error',
            3: '2-base error for e8 -> e12, e24 -> e28\n1-base error for e2, e3, e6, e7, e14, e16, e17, e21'
        }
        return errors.get(d6_total, 'No error')

    def _get_2b_error(self, d6_total: int) -> str:
        """Get 2B error result based on 3d6 total."""
        errors = {
            18: '2-base error for e4 -> e19, e28 -> e41, e53 -> e65\n1-base error for e22, e24, e25, e27, e44, e50',
            17: '2-base error for e20 -> e41, e68, e71\n1-base error for e3, e4, e8 -> e12, e15, e16, e19',
            16: '2-base error for e53 -> 71\n1-base error for e5 -> 10, e14, e16, e29, e37',
            15: '1-base error for e11, e12, e14, e16, e17, e19, e26 -> e28, e30, e32, e37, e50 -> e62, e71',
            14: '1-base error for e13, e15, e34, e47, e65',
            13: '1-base error for e18, e20, e21, e26 -> e28, e39, e41, e50, e56, e59, e65, e71',
            12: '1-base error for e22, e30, e34, e39, e44, e47, e53, e56, e62, e68, e71',
            11: '1-base error for e23 -> e25, e29, e32, e37, e41, e50, e53, e59, e62, e68',
            10: '1-base error for e68',
            9: '1-base error for e44',
            8: 'No error',
            7: '1-base error for e47, e65',
            6: '1-base error for e17, e19, e56 -> 62',
            5: 'No error',
            4: '1-base error for e10, e21',
            3: '2-base error for e12 -> e19, e37 -> e41, e59 -> e65\n1-base error for e2 -> e4, e6, e20, e25, e28, e29'
        }
        return errors.get(d6_total, 'No error')

    def _get_ss_error(self, d6_total: int) -> str:
        """Get SS error result based on 3d6 total."""
        errors = {
            18: '2-base error for e4 -> e12, e22 -> e32, e40 -> e48, e64, e68\n1-base error for e1, e18, e34, e52, e56',
            17: '2-base error for e14 -> 32, e52, e56, e72 -> e84\n1-base error for e3 -> e5, e8 ,e10, e36',
            16: '2-base error for e33 -> 56, e72\n1-base error for e6 -> e10, e17, e18, e20, e28, e31, e88',
            15: '2-base error for e60 -> e68, e76 -> 84\n1-base error for e12, e14, e17, e18, e20 -> e22, e24, e28, e31 -> 36, e40, e48, e72',
            14: '1-base error for e16, e19, e38, e42, e60, e68',
            13: '1-base error for e23, e25, e32 -> 38, e44, e52, e72 -> 84',
            12: '1-base error for e26, e27, e30, e42, e48, e56, e64, e68, e76 -> e88',
            11: '1-base error for e29, e40, e52 -> e60, e72, e80 -> e88',
            10: '1-base error for e84',
            9: '1-base error for e64, e68, e76, e88',
            8: '1-base error for e44',
            7: '1-base error for e60',
            6: '1-base error for e21, e22, e24, e28, e31, e48, e64, e72',
            5: 'No error',
            4: '2-base error for e72\n1-base error for e14, e19, e20, e24, e25, e30, e31, e80',
            3: '2-base error for e10, e12, e28 -> e32, e48, e84\n1-base error for e2, e5, e7, e23, e27'
        }
        return errors.get(d6_total, 'No error')

    def _get_corner_of_error(self, d6_total: int) -> str:
        """Get LF/RF error result based on 3d6 total."""
        errors = {
            18: '3-base error for e4 -> e12, e19 -> e25\n2-base error for e18\n1-base error for e2, e3, e15',
            17: '3-base error for e13 -> e25\n2-base error for e1, e6, e8, e10',
            16: '2-base error for e2\n1-base error for e7 -> 12, e22, e24, e25',
            15: '2-base error for e3, e4, e7, e8, e10, e11, e13, e20, e21',
            14: '2-base error for e5, e6, e10, e12, e14, e15, e22, e23',
            13: '2-base error for e11, e12, e16, e20, e24, e25',
            12: '2-base error for e13 -> e18, e21 -> e23, e25',
            11: '2-base error for e9, e18 -> e21, e23 -> e25',
            10: '2-base error for e19',
            9: '2-base error for e22',
            8: '2-base error for e24',
            7: '1-base error for e19 -> e21, e23',
            6: '2-base error for e7, e8\n1-base error for e13 -> e18, e22, e24, e25',
            5: 'No error',
            4: '2-base error for e1, e5, e6, e9\n1-base error for e14 -> e16, e20 -> e23',
            3: '3-base error for e16 -> e25\n2-base error for e1, e3, e4, e7, e9, e11\n1-base error for e17'
        }
        return errors.get(d6_total, 'No error')

    def _get_cf_error(self, d6_total: int) -> str:
        """Get CF error result based on 3d6 total."""
        errors = {
            18: '3-base error for e8 -> e16, e24 -> e32\n2-base error for e1, e2, e40\n1-base error for e17, e19, e21, e36',
            17: '3-base error for e17 -> e32, e34, e36, e38\n2-base error for e3 -> e7, e10, e12, e14, e22',
            16: '2-base error for e1, e2, e4, e8 -> e12, e17, e19, e24, e26, e28, e32, e34',
            15: '2-base error for e5 -> e8, e13, e15 -> e19, e21, e24, e28, e30, e36, e38, e40',
            14: '2-base error for e9 -> e11, e14, e20, e22, e26, e30, e34, e38',
            13: '2-base error for e12 -> e21, e23, e25, e26, e32, e36, e40',
            12: '2-base error for e22 -> e25, e27 -> e32, e34 -> e40',
            11: '2-base error for e26, e27, e29 -> e34, e36 -> e40',
            10: '2-base error for e28',
            9: '2-base error for e29',
            8: '2-base error for e30',
            7: '1-base error for e27, e28, e31, e32, e35',
            6: '2-base error for e15, e16\n1-base error for e23 -> e32, e34 -> e40',
            5: 'No error',
            4: '2-base error for e9 -> e13, e17, e19 -> e21\n1-base error for e24, e25, e29 -> e38',
            3: '3-base error for e24 -> e32, e36 -> e40\n2-base error for e1 -> e8, e10, e14\n1-base error for e15'
        }
        return errors.get(d6_total, 'No error')

    def _get_catcher_error(self, d6_total: int) -> str:
        """Get Catcher error result based on 3d6 total."""
        errors = {
            18: 'Passed ball for sb2 -> sb12, sb16 -> sb26\nNo error for sb14',
            17: 'Passed ball for sb3 -> sb12, sb17 -> sb26\nNo error for sb1, sb13 -> sb15',
            16: 'Passed ball for sb4 -> sb12, sb18 -> sb26',
            15: 'Passed ball for sb5 -> sb12, sb19 -> sb26',
            14: 'Passed ball for sb6 -> sb12, sb20 -> sb26',
            13: 'Passed ball for sb7 -> sb12, sb21 -> sb26',
            12: 'Passed ball for sb8 -> sb12, sb22 -> sb26',
            11: 'Passed ball for sb9 -> sb12, sb23 -> sb26',
            10: 'Passed ball for sb10 -> sb12, sb24 -> sb26',
            9: 'Passed ball for sb11, sb12, sb25, sb26',
            8: 'No error',
            7: 'No error',
            6: 'No error',
            5: 'No error',
            4: 'Passed ball for sb1 -> sb12, sb15 -> sb26\nNo error for sb13, sb14',
            3: 'Passed ball for sb1 -> sb26'
        }
        return errors.get(d6_total, 'No error')

    def _parse_and_roll_multiple_dice(self, dice_notation: str) -> list[dict]:
        """Parse dice notation (supports multiple rolls) and return roll results."""
        # Split by semicolon for multiple rolls
        dice_parts = [part.strip() for part in dice_notation.split(';')]
        results = []

        for dice_part in dice_parts:
            result = self._parse_and_roll_single_dice(dice_part)
            if result is None:
                return []  # Return empty list if any part is invalid
            results.append(result)

        return results

    def _parse_and_roll_single_dice(self, dice_notation: str) -> Optional[dict]:
        """Parse single dice notation and return roll results."""
        # Clean the input
        dice_notation = dice_notation.strip().lower().replace(' ', '')

        # Pattern: XdY
        pattern = r'^(\d+)d(\d+)$'
        match = re.match(pattern, dice_notation)

        if not match:
            return None

        num_dice = int(match.group(1))
        die_sides = int(match.group(2))

        # Validate reasonable limits
        if num_dice > 100 or die_sides > 1000 or num_dice < 1 or die_sides < 2:
            return None

        # Roll the dice
        rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
        total = sum(rolls)

        return {
            'dice_notation': dice_notation,
            'num_dice': num_dice,
            'die_sides': die_sides,
            'rolls': rolls,
            'total': total
        }

    def _roll_weighted_scout_dice(self, card_type: str) -> list[dict]:
        """
        Roll scouting dice with weighted first d6 based on card type.

        Args:
            card_type: Either "batter" (1-3) or "pitcher" (4-6) for first d6

        Returns:
            List of 3 roll result dicts: weighted 1d6, normal 2d6, normal 1d20
        """
        # First die (1d6) - weighted based on card type
        if card_type == "batter":
            first_roll = random.randint(1, 3)
        else:  # pitcher
            first_roll = random.randint(4, 6)

        first_d6_result = {
            'dice_notation': '1d6',
            'num_dice': 1,
            'die_sides': 6,
            'rolls': [first_roll],
            'total': first_roll
        }

        # Second roll (2d6) - normal
        second_result = self._parse_and_roll_single_dice("2d6")

        # Third roll (1d20) - normal
        third_result = self._parse_and_roll_single_dice("1d20")

        return [first_d6_result, second_result, third_result]

    def _create_multi_roll_embed(self, dice_notation: str, roll_results: list[dict], user: discord.User | discord.Member) -> discord.Embed:
        """Create an embed for multiple dice roll results."""
        embed = EmbedTemplate.create_base_embed(
            title="🎲 Dice Roll",
            color=EmbedColors.PRIMARY
        )

        # Set user info
        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url
        )

        # Create summary line with totals
        totals = [str(result['total']) for result in roll_results]
        summary = f"# {','.join(totals)}"

        # Create details line in the specified format: Details:[1d6;2d6;1d20 (5 - 5 6 - 13)]
        dice_notations = [result['dice_notation'] for result in roll_results]

        # Create the rolls breakdown part - group dice within each roll, separate roll groups with dashes
        roll_groups = []
        for result in roll_results:
            rolls = result['rolls']
            if len(rolls) == 1:
                # Single die: just the number
                roll_groups.append(str(rolls[0]))
            else:
                # Multiple dice: space-separated within the group
                roll_groups.append(' '.join(str(r) for r in rolls))

        details = f"Details:[{';'.join(dice_notations)} ({' - '.join(roll_groups)})]"

        # Set as description
        embed.add_field(
            name='Result',
            value=f"```md\n{summary}\n{details}```"
        )

        return embed


async def setup(bot: commands.Bot):
    """Load the dice roll commands cog."""
    await bot.add_cog(DiceRollCommands(bot))