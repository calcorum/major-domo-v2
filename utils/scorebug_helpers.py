"""
Scorebug Display Helpers

Utility functions for formatting and displaying scorebug information.
"""
import discord
from typing import Optional

from views.embeds import EmbedColors


def create_scorebug_embed(
    scorebug_data,
    away_team,
    home_team,
    full_length: bool = True
) -> discord.Embed:
    """
    Create a rich embed from scorebug data.

    Args:
        scorebug_data: ScorebugData object with game information
        away_team: Away team object (optional)
        home_team: Home team object (optional)
        full_length: If True, includes pitcher/batter/runners/summary; if False, compact view

    Returns:
        Discord embed with scorebug information
    """
    # Determine embed color based on win probability (not score!)
    # This creates a fun twist where the favored team's color shows,
    # even if they're currently losing
    if scorebug_data.win_percentage > 50 and home_team:
        embed_color = home_team.get_color_int()  # Home team favored
    elif scorebug_data.win_percentage < 50 and away_team:
        embed_color = away_team.get_color_int()  # Away team favored
    else:
        embed_color = EmbedColors.INFO  # Even game (50/50)

    # Create embed with header as title
    embed = discord.Embed(
        title=scorebug_data.header,
        color=embed_color
    )

    # Get team abbreviations for use throughout
    away_abbrev = away_team.abbrev if away_team else "AWAY"
    home_abbrev = home_team.abbrev if home_team else "HOME"

    # Create ASCII scorebug with bases visualization
    occupied = '●'
    unoccupied = '○'

    # runners[0]=Catcher, [1]=On First, [2]=On Second, [3]=On Third
    first_base = unoccupied if not scorebug_data.runners[1] or not scorebug_data.runners[1][0] else occupied
    second_base = unoccupied if not scorebug_data.runners[2] or not scorebug_data.runners[2][0] else occupied
    third_base = unoccupied if not scorebug_data.runners[3] or not scorebug_data.runners[3][0] else occupied
    half = '▲' if scorebug_data.which_half == 'Top' else '▼'

    if not scorebug_data.is_final:
        inning = f'{half} {scorebug_data.inning}'
        outs = f'{scorebug_data.outs} Out{"s" if scorebug_data.outs != 1 else ""}'
    else:
        # Final inning display
        final_inning = scorebug_data.inning if scorebug_data.which_half == "Bot" else scorebug_data.inning - 1
        inning = f'F/{final_inning}'
        outs = ''

    game_state_text = (
        f'```\n'
        f'{away_abbrev: ^4}{scorebug_data.away_score: ^3}   {second_base}{inning: >10}\n'
        f'{home_abbrev: ^4}{scorebug_data.home_score: ^3} {third_base}   {first_base}{outs: >8}\n'
        f'```'
    )

    # Add win probability bar
    embed.add_field(
        name='Win Probability',
        value=create_team_progress_bar(
            scorebug_data.win_percentage,
            away_abbrev,
            home_abbrev
        ),
        inline=False
    )

    # Add game state
    embed.add_field(
        name='Game State',
        value=game_state_text,
        inline=False
    )

    # If not full_length, return compact version
    if not full_length:
        return embed

    # Full length - add pitcher and batter info
    if scorebug_data.pitcher_name:
        embed.add_field(
            name='Pitcher',
            value=f'[{scorebug_data.pitcher_name}]({scorebug_data.pitcher_url})\n{scorebug_data.pitcher_stats}',
            inline=True
        )

    if scorebug_data.batter_name:
        embed.add_field(
            name='Batter',
            value=f'[{scorebug_data.batter_name}]({scorebug_data.batter_url})\n{scorebug_data.batter_stats}',
            inline=True
        )

    # Add baserunners if present
    on_first = scorebug_data.runners[1] if scorebug_data.runners[1] else ''
    on_second = scorebug_data.runners[2] if scorebug_data.runners[2] else ''
    on_third = scorebug_data.runners[3] if scorebug_data.runners[3] else ''
    have_baserunners = len(on_first[0]) + len(on_second[0]) + len(on_third[0]) > 0

    if have_baserunners > 0:
        br_string = ''
        if len(on_first) > 0:
            br_string += f'On First: [{on_first[0]}]({on_first[1]})\n'
        if len(on_second) > 0:
            br_string += f'On Second: [{on_second[0]}]({on_second[1]})\n'
        if len(on_third) > 0:
            br_string += f'On Third: [{on_third[0]}]({on_third[1]})\n'

        embed.add_field(name=' ', value=' ', inline=False)  # Spacer
        embed.add_field(
            name='Baserunners',
            value=br_string,
            inline=True
        )

        # Add catcher
        if scorebug_data.runners[0] and scorebug_data.runners[0][0]:
            embed.add_field(
                name='Catcher',
                value=f'[{scorebug_data.runners[0][0]}]({scorebug_data.runners[0][1]})',
                inline=True
            )

    # Add inning summary if not final
    if not scorebug_data.is_final and scorebug_data.summary:
        i_string = ''
        for line in scorebug_data.summary:
            if line and len(line) >= 2 and line[0]:
                i_string += f'- Play {line[0]}: {line[1]}\n'

        if i_string and "IFERROR" not in i_string:
            embed.add_field(
                name='Inning Summary',
                value=i_string,
                inline=False
            )

    return embed


def create_team_progress_bar(
    win_percentage: float,
    away_abbrev: str,
    home_abbrev: str,
    length: int = 10
) -> str:
    """
    Create a proportional progress bar showing each team's win probability.

    Args:
        win_percentage: Home team's win percentage (0-100)
        away_abbrev: Away team abbreviation (e.g., "POR")
        home_abbrev: Home team abbreviation (e.g., "WV")
        length: Total bar length in blocks (default 10)

    Returns:
        Formatted bar with dark blocks (▓) weighted toward winning team.
        Arrow extends from the side with the advantage.
        Examples:
            Home winning: "POR ░▓▓▓▓▓▓▓▓▓► WV  95.0%"
            Away winning: "POR ◄▓▓▓▓▓▓▓░░░ WV  30.0%"
            Even game:    "POR =▓▓▓▓▓▓▓▓▓▓= WV  50.0%"
    """
    # Calculate blocks for each team (home team's percentage)
    home_blocks = int((win_percentage / 100) * length)
    away_blocks = length - home_blocks

    if win_percentage > 50:
        # Home team (right side) is winning
        away_char = '░'  # Light blocks for losing team
        home_char = '▓'  # Dark blocks for winning team
        bar = away_char * away_blocks + home_char * home_blocks
        # Arrow extends from right side
        return f'{away_abbrev} {bar}► {home_abbrev}  {win_percentage:.1f}%'
    elif win_percentage < 50:
        # Away team (left side) is winning
        away_char = '▓'  # Dark blocks for winning team
        home_char = '░'  # Light blocks for losing team
        bar = away_char * away_blocks + home_char * home_blocks
        # Arrow extends from left side
        return f'{away_abbrev} ◄{bar} {home_abbrev}  {win_percentage:.1f}%'
    else:
        # Even game (50/50)
        away_char = '▓'
        home_char = '▓'
        bar = away_char * away_blocks + home_char * home_blocks
        # Arrows on both sides for balanced display
        return f'{away_abbrev} ={bar}= {home_abbrev}  {win_percentage:.1f}%'
