"""
Dice Rolling Commands

Implements slash commands for dice rolling functionality required for gameplay.
"""
import random
import re
from typing import Optional
from dataclasses import dataclass

import discord
from discord.ext import commands

from models.team import Team
from services.team_service import team_service
from utils import team_utils
from utils.logging import get_contextual_logger
from utils.decorators import logged_command
from utils.team_utils import get_user_major_league_team
from utils.text_utils import split_text_for_fields
from views.embeds import EmbedColors, EmbedTemplate
from .chart_data import (
    INFIELD_X_CHART,
    OUTFIELD_X_CHART,
    INFIELD_RANGES,
    OUTFIELD_RANGES,
    CATCHER_RANGES,
    PITCHER_RANGES,
    FIRST_BASE_ERRORS,
    SECOND_BASE_ERRORS,
    THIRD_BASE_ERRORS,
    SHORTSTOP_ERRORS,
    CORNER_OUTFIELD_ERRORS,
    CENTER_FIELD_ERRORS,
    CATCHER_ERRORS,
    PITCHER_ERRORS,
)


@dataclass
class DiceRoll:
    """Represents the result of a dice roll."""
    dice_notation: str
    num_dice: int
    die_sides: int
    rolls: list[int]
    total: int

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
        embed_color = await self._get_channel_embed_color(interaction)

        # Use the standard baseball dice combination
        dice_notation = "1d6;2d6;1d20"
        roll_results = self._parse_and_roll_multiple_dice(dice_notation)

        injury_risk = (roll_results[0].total == 6) and (roll_results[1].total in [7, 8, 9, 10, 11, 12])
        d6_total = roll_results[1].total

        embed_title = 'At bat roll'
        if roll_results[2].total == 1:
            embed_title = 'Wild pitch roll'
            dice_notation = '1d20'
            roll_results = [self._parse_and_roll_single_dice(dice_notation)]
        elif roll_results[2].total == 2:
            embed_title = 'PB roll'
            dice_notation = '1d20'
            roll_results = [self._parse_and_roll_single_dice(dice_notation)]

        # Create embed for the roll results
        embed = self._create_multi_roll_embed(
            dice_notation,
            roll_results,
            interaction.user,
            set_author=False,
            embed_color=embed_color
        )
        embed.title = f'{embed_title} for {interaction.user.display_name}'

        if injury_risk and embed_title == 'At bat roll':
            embed.add_field(
                name=f'Check injury for pitcher injury rating {13 - d6_total}',
                value='Oops! All injuries!',
                inline=False
            )

        await interaction.followup.send(embed=embed)

    @commands.command(name="ab", aliases=["atbat"])
    async def ab_dice_prefix(self, ctx: commands.Context):
        """Roll baseball at-bat dice using prefix commands (!ab, !atbat)."""
        self.logger.info(f"At Bat dice command started by {ctx.author.display_name}")
        team = await get_user_major_league_team(user_id=ctx.author.id)
        embed_color = EmbedColors.PRIMARY
        if team is not None and team.color is not None:
            embed_color = int(team.color,16)

        # Use the standard baseball dice combination
        dice_notation = "1d6;2d6;1d20"
        roll_results = self._parse_and_roll_multiple_dice(dice_notation)

        self.logger.info("At Bat dice rolled successfully", roll_count=len(roll_results))

        # Create embed for the roll results
        embed = self._create_multi_roll_embed(dice_notation, roll_results, ctx.author, set_author=False, embed_color=embed_color)
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
        embed = self._create_multi_roll_embed("1d6;2d6;1d20", roll_results, interaction.user, set_author=False)
        embed.title = f'Scouting roll for {interaction.user.display_name}'
        await interaction.followup.send(embed=embed)

    @discord.app_commands.command(
        name="fielding",
        description="Roll Super Advanced fielding dice for a defensive position"
    )
    @discord.app_commands.describe(
        position="Defensive position"
    )
    @discord.app_commands.choices(position=[
        discord.app_commands.Choice(name="Pitcher (P)", value="P"),
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
        embed_color = await self._get_channel_embed_color(interaction)

        # Get the position value from the choice
        pos_value = position.value

        # Roll the dice - 1d20 and 3d6
        dice_notation = "1d20;3d6;1d100"
        roll_results = self._parse_and_roll_multiple_dice(dice_notation)

        # Create fielding embed
        embed = self._create_fielding_embed(pos_value, roll_results, interaction.user, embed_color)
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

        self.logger.info("SA Fielding dice rolled successfully", position=parsed_position, d20=roll_results[0].total, d6_total=roll_results[1].total)

        # Create fielding embed
        embed = self._create_fielding_embed(parsed_position, roll_results, ctx.author)
        await ctx.send(embed=embed)

    @discord.app_commands.command(
        name="jump",
        description="Roll for baserunner's jump before stealing"
    )
    @logged_command("/jump")
    async def jump_dice(self, interaction: discord.Interaction):
        """Roll to check for a baserunner's jump before attempting to steal a base."""
        await interaction.response.defer()
        embed_color = await self._get_channel_embed_color(interaction)

        # Roll 1d20 for pickoff/balk check
        check_roll = random.randint(1, 20)

        # Roll 2d6 for jump rating
        jump_result = self._parse_and_roll_single_dice("2d6")

        # Roll another 1d20 for pickoff/balk resolution
        resolution_roll = random.randint(1, 20)

        # Create embed based on check roll
        embed = self._create_jump_embed(
            check_roll,
            jump_result,
            resolution_roll,
            interaction.user,
            embed_color,
            show_author=False
        )
        await interaction.followup.send(embed=embed)

    @commands.command(name="j", aliases=["jump"])
    async def jump_dice_prefix(self, ctx: commands.Context):
        """Roll for baserunner's jump using prefix commands (!j, !jump)."""
        self.logger.info(f"Jump command started by {ctx.author.display_name}")
        team = await get_user_major_league_team(user_id=ctx.author.id)
        embed_color = EmbedColors.PRIMARY
        if team is not None and team.color is not None:
            embed_color = int(team.color, 16)

        # Roll 1d20 for pickoff/balk check
        check_roll = random.randint(1, 20)

        # Roll 2d6 for jump rating
        jump_result = self._parse_and_roll_single_dice("2d6")

        # Roll another 1d20 for pickoff/balk resolution
        resolution_roll = random.randint(1, 20)

        self.logger.info("Jump dice rolled successfully", check=check_roll, jump=jump_result.total if jump_result else None, resolution=resolution_roll)

        # Create embed based on check roll
        embed = self._create_jump_embed(
            check_roll,
            jump_result,
            resolution_roll,
            ctx.author,
            embed_color
        )
        await ctx.send(embed=embed)

    async def _get_channel_embed_color(self, interaction: discord.Interaction) -> int:
        # Check if channel is a type that has a name attribute (DMChannel doesn't have one)
        if isinstance(interaction.channel, (discord.TextChannel, discord.VoiceChannel, discord.Thread)):
            channel_starter = interaction.channel.name[:6]
            if '-' in channel_starter:
                abbrev = channel_starter.split('-')[0]
                channel_team = await team_service.get_team_by_abbrev(abbrev)
                if channel_team is not None and channel_team.color is not None:
                    return int(channel_team.color,16)

        team = await get_user_major_league_team(user_id=interaction.user.id)
        if team is not None and team.color is not None:
            return int(team.color,16)

        return EmbedColors.PRIMARY

    def _parse_position(self, position: str) -> str | None:
        """Parse and validate fielding position input for prefix commands."""
        if not position:
            return None

        pos = position.upper().strip()

        # Map common inputs to standard position names
        position_map = {
            'P': 'P', 'PITCHER': 'P',
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

    def _create_fielding_embed(
            self, 
            position: str, 
            roll_results: list[DiceRoll], 
            user: discord.User | discord.Member, 
            embed_color: int = EmbedColors.PRIMARY
    ) -> discord.Embed:
        """Create an embed for fielding roll results."""
        d20_result = roll_results[0].total
        d6_total = roll_results[1].total
        d6_rolls = roll_results[1].rolls
        d100_result = roll_results[2].total

        # Create base embed
        embed = EmbedTemplate.create_base_embed(
            title=f"SA Fielding roll for {user.display_name}",
            color=embed_color
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
            name=f"{position} Range Result",
            value=f"```md\n 1 | 2 | 3 | 4 | 5\n{range_result}```",
            inline=False
        )

        # Add rare play or error result
        if d100_result == 1:
            error_result = self._get_rare_play(position, d20_result)
            base_field_name = "Rare Play Result"
        else:
            # Add error result
            error_result = self._get_error_result(position, d6_total)
            base_field_name = "Error Result"

        if error_result:
            # Split text if it exceeds Discord's field limit
            result_chunks = split_text_for_fields(error_result, max_length=1024)

            # Add each chunk as a separate field
            for i, chunk in enumerate(result_chunks):
                field_name = base_field_name
                # Add part indicator if multiple chunks
                if len(result_chunks) > 1:
                    field_name += f" (Part {i+1}/{len(result_chunks)})"

                embed.add_field(
                    name=field_name,
                    value=chunk,
                    inline=False
                )

        # Add help commands
        embed.add_field(
            name="Help Commands",
            value="Run /charts for full chart readout",
            inline=False
        )

        # # Add references
        # embed.add_field(
        #     name="References",
        #     value="Range Chart / Error Chart / Result Reference",
        #     inline=False
        # )

        return embed

    def _create_jump_embed(
        self,
        check_roll: int,
        jump_result: DiceRoll | None,
        resolution_roll: int,
        user: discord.User | discord.Member,
        embed_color: int = EmbedColors.PRIMARY,
        show_author: bool = True
    ) -> discord.Embed:
        """Create an embed for jump roll results."""
        # Create base embed
        embed = EmbedTemplate.create_base_embed(
            title=f"Jump roll for {user.name}",
            color=embed_color
        )

        if show_author:
            # Set user info
            embed.set_author(
                name=user.name,
                icon_url=user.display_avatar.url
            )

        # Check for pickoff or balk
        if check_roll == 1:
            # Pickoff attempt
            embed.add_field(
                name="Special",
                value="```md\nCheck pickoff```",
                inline=False
            )
            embed.add_field(
                name="Pickoff roll",
                value=f"```md\n# {resolution_roll}\nDetails:[1d20 ({resolution_roll})]```",
                inline=False
            )
        elif check_roll == 2:
            # Balk
            embed.add_field(
                name="Special",
                value="```md\nCheck balk```",
                inline=False
            )
            embed.add_field(
                name="Balk roll",
                value=f"```md\n# {resolution_roll}\nDetails:[1d20 ({resolution_roll})]```",
                inline=False
            )
        else:
            # Normal jump - show 2d6 result
            if jump_result:
                rolls_str = ' '.join(str(r) for r in jump_result.rolls)
                embed.add_field(
                    name="Result",
                    value=f"```md\n# {jump_result.total}\nDetails:[2d6 ({rolls_str})]```",
                    inline=False
                )

        return embed

    def _get_range_result(self, position: str, d20_roll: int) -> str:
        """Get the range result display for a position and d20 roll."""
        if position == 'P':
            return self._get_pitcher_range(d20_roll)
        elif position in ['1B', '2B', '3B', 'SS']:
            return self._get_infield_range(d20_roll)
        elif position in ['LF', 'CF', 'RF']:
            return self._get_outfield_range(d20_roll)
        elif position == 'C':
            return self._get_catcher_range(d20_roll)
        return "Unknown position"

    def _get_infield_range(self, d20_roll: int) -> str:
        """Get infield range result based on d20 roll."""
        return INFIELD_RANGES.get(d20_roll, 'Unknown')

    def _get_outfield_range(self, d20_roll: int) -> str:
        """Get outfield range result based on d20 roll."""
        return OUTFIELD_RANGES.get(d20_roll, 'Unknown')

    def _get_catcher_range(self, d20_roll: int) -> str:
        """Get catcher range result based on d20 roll."""
        return CATCHER_RANGES.get(d20_roll, 'Unknown')

    def _get_pitcher_range(self, d20_roll: int) -> str:
        """Get pitcher range result based on d20 roll."""
        return PITCHER_RANGES.get(d20_roll, 'Unknown')
    
    def _get_rare_play(self, position: str, d20_total: int) -> str:
        """Get the rare play result for a position and d20 total"""
        starter = 'Rare play! Take the range result from above and consult the chart below.\n\n'
        if position == 'P':
            return starter + self._get_pitcher_rare_play(d20_total)
        elif position == '1B':
            return starter + self._get_infield_rare_play(d20_total)
        elif position == '2B':
            return starter + self._get_infield_rare_play(d20_total)
        elif position == '3B':
            return starter + self._get_infield_rare_play(d20_total)
        elif position == 'SS':
            return starter + self._get_infield_rare_play(d20_total)
        elif position in ['LF', 'RF']:
            return starter + self._get_outfield_rare_play(d20_total)
        elif position == 'CF':
            return starter + self._get_outfield_rare_play(d20_total)
        
        raise ValueError(f'Unknown position: {position}')

    def _get_error_result(self, position: str, d6_total: int) -> str:
        """Get the error result for a position and 3d6 total."""
        # Get the appropriate error chart
        if position == 'P':
            return self._get_pitcher_error(d6_total)
        elif position == '1B':
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
        return THIRD_BASE_ERRORS.get(d6_total, 'No error')

    def _get_1b_error(self, d6_total: int) -> str:
        """Get 1B error result based on 3d6 total."""
        return FIRST_BASE_ERRORS.get(d6_total, 'No error')

    def _get_2b_error(self, d6_total: int) -> str:
        """Get 2B error result based on 3d6 total."""
        return SECOND_BASE_ERRORS.get(d6_total, 'No error')

    def _get_ss_error(self, d6_total: int) -> str:
        """Get SS error result based on 3d6 total."""
        return SHORTSTOP_ERRORS.get(d6_total, 'No error')

    def _get_corner_of_error(self, d6_total: int) -> str:
        """Get LF/RF error result based on 3d6 total."""
        return CORNER_OUTFIELD_ERRORS.get(d6_total, 'No error')

    def _get_cf_error(self, d6_total: int) -> str:
        """Get CF error result based on 3d6 total."""
        return CENTER_FIELD_ERRORS.get(d6_total, 'No error')

    def _get_catcher_error(self, d6_total: int) -> str:
        """Get Catcher error result based on 3d6 total."""
        return CATCHER_ERRORS.get(d6_total, 'No error')

    def _get_pitcher_error(self, d6_total: int) -> str:
        """Get Pitcher error result based on 3d6 total."""
        return PITCHER_ERRORS.get(d6_total, 'No error')

    def _get_pitcher_rare_play(self, d20_total: int) -> str:
        return (
            f'**G3**: {INFIELD_X_CHART["g3"]["rp"]}\n'
            f'**G2**: {INFIELD_X_CHART["g2"]["rp"]}\n'
            f'**G1**: {INFIELD_X_CHART["g1"]["rp"]}\n'
            f'**SI1**: {INFIELD_X_CHART["si1"]["rp"]}\n'
        )

    def _get_infield_rare_play(self, d20_total: int) -> str:
        return (
            f'**G3**: {INFIELD_X_CHART["g3"]["rp"]}\n'
            f'**G2**: {INFIELD_X_CHART["g2"]["rp"]}\n'
            f'**G1**: {INFIELD_X_CHART["g1"]["rp"]}\n'
            f'**SI1**: {INFIELD_X_CHART["si1"]["rp"]}\n'
            f'**SI2**: {OUTFIELD_X_CHART["si2"]["rp"]}\n'
        )

    def _get_outfield_rare_play(self, d20_total: int) -> str:
        return (
            f'**F1**: {OUTFIELD_X_CHART["f1"]["rp"]}\n'
            f'**F2**: {OUTFIELD_X_CHART["f2"]["rp"]}\n'
            f'**F3**: {OUTFIELD_X_CHART["f3"]["rp"]}\n'
            f'**SI2**: {OUTFIELD_X_CHART["si2"]["rp"]}\n'
            f'**DO2**: {OUTFIELD_X_CHART["do2"]["rp"]}\n'
            f'**DO3**: {OUTFIELD_X_CHART["do3"]["rp"]}\n'
            f'**TR3**: {OUTFIELD_X_CHART["tr3"]["rp"]}\n'
        )

    def _parse_and_roll_multiple_dice(self, dice_notation: str) -> list[DiceRoll]:
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

    def _parse_and_roll_single_dice(self, dice_notation: str) -> DiceRoll:
        """Parse single dice notation and return roll results."""
        # Clean the input
        dice_notation = dice_notation.strip().lower().replace(' ', '')

        # Pattern: XdY
        pattern = r'^(\d+)d(\d+)$'
        match = re.match(pattern, dice_notation)

        if not match:
            raise ValueError(f'Cannot parse dice string **{dice_notation}**')

        num_dice = int(match.group(1))
        die_sides = int(match.group(2))

        # Validate reasonable limits
        if num_dice > 100 or die_sides > 1000 or num_dice < 1 or die_sides < 2:
            raise ValueError('I don\'t know, bud, that just doesn\'t seem doable.')

        # Roll the dice
        rolls = [random.randint(1, die_sides) for _ in range(num_dice)]
        total = sum(rolls)

        return DiceRoll(
            dice_notation=dice_notation,
            num_dice=num_dice,
            die_sides=die_sides,
            rolls=rolls,
            total=total
        )

    def _roll_weighted_scout_dice(self, card_type: str) -> list[DiceRoll]:
        """
        Roll scouting dice with weighted first d6 based on card type.

        Args:
            card_type: Either "batter" (1-3) or "pitcher" (4-6) for first d6

        Returns:
            List of 3 roll result dataclasses: weighted 1d6, normal 2d6, normal 1d20
        """
        # First die (1d6) - weighted based on card type
        if card_type == "batter":
            first_roll = random.randint(1, 3)
        else:  # pitcher
            first_roll = random.randint(4, 6)

        first_d6_result = DiceRoll(
            dice_notation='1d6',
            num_dice=1,
            die_sides=6,
            rolls=[first_roll],
            total=first_roll
        )

        # Second roll (2d6) - normal
        second_result = self._parse_and_roll_single_dice("2d6")

        # Third roll (1d20) - normal
        third_result = self._parse_and_roll_single_dice("1d20")

        return [first_d6_result, second_result, third_result]

    def _create_multi_roll_embed(self, dice_notation: str, roll_results: list[DiceRoll], user: discord.User | discord.Member, set_author: bool = True, embed_color: int = EmbedColors.PRIMARY) -> discord.Embed:
        """Create an embed for multiple dice roll results."""
        embed = EmbedTemplate.create_base_embed(
            title="🎲 Dice Roll",
            color=embed_color
        )

        if set_author:
            # Set user info
            embed.set_author(
                name=user.name,
                icon_url=user.display_avatar.url
            )

        # Create summary line with totals
        totals = [str(result.total) for result in roll_results]
        summary = f"# {','.join(totals)}"

        # Create details line in the specified format: Details:[1d6;2d6;1d20 (5 - 5 6 - 13)]
        dice_notations = [result.dice_notation for result in roll_results]

        # Create the rolls breakdown part - group dice within each roll, separate roll groups with dashes
        roll_groups = []
        for result in roll_results:
            rolls = result.rolls
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