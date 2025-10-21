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
from views.embeds import EmbedColors, EmbedTemplate


@dataclass
class DiceRoll:
    """Represents the result of a dice roll."""
    dice_notation: str
    num_dice: int
    die_sides: int
    rolls: list[int]
    total: int

INFIELD_X_CHART = {
    'si1': {
        'rp': 'Runner on first: Line drive hits the runner! Runner on first is out. Batter goes to first with single '
              'and all other runners hold.\nNo runner on first: batter singles, runners advance 1 base.',
        'e1': 'Single and Error, batter to second, runners advance 2 bases.',
        'e2': 'Single and Error, batter to third, all runners score.',
        'no': 'Single, runners advance 1 base.'
    },
    'spd': {
        'rp': 'No effect; proceed with speed check',
        'e1': 'Single and Error, batter to second, runners advance 2 bases.',
        'e2': 'Single and Error, batter to third, all runners score.',
        'no': 'Speed check, safe range equals batter\'s running rating, SI* result if safe, gb C if out'
    },
    'po': {
        'rp': 'The batters hits a popup. None of the fielders take charge on the play and the ball drops in the '
              'infield for a single! All runners advance 1 base.',
        'e1': 'The catcher drops a popup for an error. All runners advance 1 base.',
        'e2': 'The catcher grabs a squib in front of the plate and throws it into right field. The batter goes to '
              'second and all runners score.',
        'no': 'The batter pops out to the catcher.'
    },
    'wp': {
        'rp': 'Automatic wild pitch. Catcher has trouble finding it and all base runners advance 2 bases.',
        'no': 'Automatic wild pitch, all runners advance 1 base and batter rolls AB again.'
    },
    'x': {
        'rp': 'Runner(s) on base: pitcher trips during his delivery and the ball sails for automatic wild pitch, '
              'runners advance 1 base and batter rolls AB again.',
        'no': 'Wild pitch check (credited as a PB). If a passed ball occurs, batter rerolls AB. '
              'If no passed ball occurs, the batter fouls out to the catcher.'
    },
    'fo': {
        'rp': 'Batter swings and misses, but is awarded first base on a catcher interference call! Baserunners advance '
              'only if forced.',
        'e1': 'The catcher drops a foul popup for an error. Batter rolls AB again.',
        'e2': 'The catcher drops a foul popup for an error. Batter rolls AB again.',
        'no': 'Runner(s) on base: make a passed ball check. If no passed ball, batter pops out to the catcher. If a '
              'passed ball occurs, batter roll his AB again.\nNo runners: batter pops out to the catcher'
    },
    'g1': {
        'rp': 'Runner on first: runner on first breaks up the double play, but umpires call runner interference and '
              'the batter is out on GIDP.\nNo runners: Batter grounds out.',
        'e1': 'Error, batter to first, runners advance 1 base.',
        'e2': 'Error, batter to second, runners advance 2 bases.',
        'no': 'Consult Groundball Chart: `!gbA`'
    },
    'g2': {
        'rp': 'Batter lines the ball off the pitcher to the fielder who makes the play to first for the out! Runners '
              'advance only if forced.',
        'e1': 'Error, batter to first, runners advance 1 base.',
        'e2': 'Error, batter to second, runners advance 2 bases.',
        'no': 'Consult Groundball Chart: `!gbB`'
    },
    'g3': {
        'rp': 'Batter lines the ball off the mound and deflects to the fielder who makes the play to first for the '
              'out! Runners advance 1 base.',
        'e1': 'Error, batter to first, runners advance 1 base.',
        'e2': 'Error, batter to second, runners advance 2 bases.',
        'no': 'Consult Groundball Chart: `!gbC`'
    },
}
OUTFIELD_X_CHART = {
    'si2': {
        'rp': 'Batter singles, baserunners advance 2 bases. As the batter rounds first, the fielder throws behind him '
              'and catches him off the bag for an out!',
        'e1': 'Single and error, batter to second, runners advance 2 bases.',
        'e2': 'Single and error, batter to third, all runners score.',
        'e3': 'Single and error, batter to third, all runners score',
        'no': 'Single, all runners advance 2 bases.'
    },
    'do2': {
        'rp': 'Batter doubles, runners advance 2 bases. The outfielder throws the ball to the shortstop who executes a '
              'hidden ball trick! Runner on second is called out!',
        'e1': 'Double and error, batter to third, all runners score.',
        'e2': 'Double and error, batter to third, and all runners score.',
        'e3': 'Double and error, batter and all runners score. Little league home run!',
        'no': 'Double, all runners advance 2 bases.'
    },
    'do3': {
        'rp': 'Runner(s) on base: batter doubles and runners advance three bases as the outfielders collide!\n'
              'No runners: Batter doubles, but the play is appealed. The umps rule the batter missed first base so is '
              'out on the appeal!',
        'e1': 'Double and error, batter to third, all runners score.',
        'e2': 'Double and error, batter and all runners score. Little league home run!',
        'e3': 'Double and error, batter and all runners score. Little league home run!',
        'no': 'Double, all runners score.'
    },
    'tr3': {
        'rp': 'Batter hits a ball into the gap and the outfielders collide trying to make the play! The ball rolls to '
              'the wall and the batter trots home with an inside-the-park home run!',
        'e1': 'Triple and error, batter and all runners score. Little league home run!',
        'e2': 'Triple and error, batter and all runners score. Little league home run!',
        'e3': 'Triple and error, batter and all runners score. Little league home run!',
        'no': 'Triple, all runners score.'
    },
    'f1': {
        'rp': 'The outfielder races back and makes a diving catch and collides with the wall! In the time he takes to '
              'recuperate, all baserunners tag-up and advance 2 bases.',
        'e1': '1 base error, runners advance 1 base.',
        'e2': '2 base error, runners advance 2 bases.',
        'e3': '3 base error, batter to third, all runners score.',
        'no': 'Flyball A'
    },
    'f2': {
        'rp': 'The outfielder catches the flyball for an out. If there is a runner on third, he tags-up and scores. '
              'The play is appealed and the umps rule that the runner left early and is out on the appeal!',
        'e1': '1 base error, runners advance 1 base.',
        'e2': '2 base error, runners advance 2 bases.',
        'e3': '3 base error, batter to third, all runners score.',
        'no': 'Flyball B'
    },
    'f3': {
        'rp': 'The outfielder makes a running catch in the gap! The lead runner lost track of the ball and was '
              'advancing - he cannot return in time and is doubled off by the outfielder.',
        'e1': '1 base error, runners advance 1 base.',
        'e2': '2 base error, runners advance 2 bases.',
        'e3': '3 base error, batter to third, all runners score.',
        'no': 'Flyball C'
    }
}

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

        # Create embed for the roll results
        embed = self._create_multi_roll_embed(
            dice_notation, 
            roll_results, 
            interaction.user, 
            set_author=False,
            embed_color=embed_color
        )
        embed.title = f'At bat roll for {interaction.user.display_name}'
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

        # Add rare play
        if d100_result >= 1:
            error_result = self._get_rare_play(position, d20_result)
        else:
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

    def _get_pitcher_range(self, d20_roll: int) -> str:
        """Get pitcher range result based on d20 roll."""
        pitcher_ranges = {
            1: 'G3  ------SI1------',
            2: 'G3  ------SI1------',
            3: '--G3--- ----SI1----',
            4: '----G3----- --SI1--',
            5: '------G3------- SI1',
            6: '------G3------- SI1',
            7: '--------G3---------',
            8: 'G2  ------G3-------',
            9: 'G2  ------G3-------',
            10: 'G1  G2  ----G3-----',
            11: 'G1  G2  ----G3-----',
            12: 'G1  G2  ----G3-----',
            13: '--G1--- G2  --G3---',
            14: '--G1--- --G2--- G3',
            15: '--G1--- ----G2-----',
            16: '--G1--- ----G2-----',
            17: '----G1----- --G2---',
            18: '----G1----- --G2---',
            19: '------G1------- G2',
            20: '--------G1---------'
        }
        return pitcher_ranges.get(d20_roll, 'Unknown')
    
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
        errors = {
            18: '2-base error for e11 -> e18, e32, e33, e37, e53, e62, e65\n1-base error for e4, e8, e19, e21, e22, e27, e41',
            17: '2-base error for e3 -> e10, e17, e18, e25 -> e27, e34 -> e37, e44, e47\n1-base error for e11, e19, e32, e56',
            16: '2-base error for e11 -> e18, e32, e33, e37, e53, e62, e65\n1-base error for e4, e8, e19, e21, e22, e27, e41',
            15: '2-base error for e19 -> 27, e32, e33, e37, e39, e44, e50, e59\n1-base error for e5 -> e8, e11, e14, e15, e17, e18, e28 -> e31, e34',
            14: '2-base error for e28 -> e31, e34, e35, e50\n1-base error for e14, e16, e19, e20, e22, e32, e39, e44, e56, e62',
            13: '2-base error for e41, e47, e53, e59\n1-base error for e10, e15, e23, e25, e28, e30, e32, e33, e35, e44, e65',
            12: '2-base error for e62\n1-base error for e12, e17, e22, e24, e27, e29, e34 -> e50, e56 -> e59, e65',
            11: '2-base error for e56, e65\n1-base error for e13, e18, e20, e21, e23, e26, e28, e31 -> e33, e35, e37, e41 -> e53, e59',
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
            18: '2-base error for e4 -> 16\n1-base error for e2, e3',
            17: '1-base error for e1, e2, e4, e5, e12 -> e14, e16',
            16: '1-base error for e3 -> e5, e7, e12 -> e14, e16',
            15: '1-base error for e7, e8, e12, e13, e15',
            14: '1-base error for e6',
            13: '1-base error for e9',
            12: '1-base error for e10, e14',
            11: '1-base error for e11, e15',
            10: 'No error',
            9: 'No error',
            8: 'No error',
            7: '1-base error for e16',
            6: '1-base error for e8, e12, e13',
            5: 'No error',
            4: '1-base error for e5, e13',
            3: '2-base error for e12 -> e16\n1-base error for e2, e3, e7, e11'
        }
        return errors.get(d6_total, 'No error')

    def _get_pitcher_error(self, d6_total: int) -> str:
        """Get Pitcher error result based on 3d6 total."""
        errors = {
            18: '2-base error for e4 -> e12, e19 -> e28, e34 -> e43, e46 -> e48',
            17: '2-base error for e13 -> e28, e44 -> e50',
            16: '2-base error for e30 -> e48, e50, e51\n1-base error for e8, e11, e16, e23',
            15: '2-base error for e50, e51\n1-base error for e10 -> e12, e19, e20, e24, e26, e30, e35, e38, e40, e46, e47',
            14: '1-base error for e4, e14, e18, e21, e22, e26, e31, e35, e42, e43, e48 -> e51',
            13: '1-base error for e6, e13, e14, e21, e22, e26, e27, e30 -> 34, e38 -> e51',
            12: '1-base error for e7, e11, e12, e15 -> e19, e22 -> e51',
            11: '1-base error for e10, e13, e15, e17, e18, e20, e21, e23, e24, e27 -> 38, e40, e42, e44 -> e51',
            10: '1-base error for e20, e23, e24, e27 -> e51',
            9: '1-base error for e16, e19, e26, e28, e34 -> e36, e39 -> e51',
            8: '1-base error for e22, e33, e38, e39, e43 -> e51',
            7: '1-base error for e14, e21, e36, e39, e42 -> e44, e47 -> e51',
            6: '1-base error for e8, e22, e38, e39, e43 -> e51',
            5: 'No error',
            4: '1-base error for e15, e16, e40',
            3: '2-base error for e8 -> e12, e26 -> e28, e39 -> e43\n1-base error for e2, e3, e7, e14, e15'
        }
        return errors.get(d6_total, 'No error')

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

    def _parse_and_roll_single_dice(self, dice_notation: str) -> Optional[DiceRoll]:
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