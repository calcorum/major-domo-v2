"""
Draft Views for Discord Bot v2.0

Provides embeds and UI components for draft system.
"""
from typing import Optional, List
from datetime import datetime

import discord

from models.draft_pick import DraftPick
from models.draft_data import DraftData
from models.team import Team
from models.player import Player
from models.draft_list import DraftList
from views.embeds import EmbedTemplate, EmbedColors
from utils.draft_helpers import format_pick_display, get_round_name
from config import get_config


async def create_on_the_clock_embed(
    current_pick: DraftPick,
    draft_data: DraftData,
    recent_picks: List[DraftPick],
    upcoming_picks: List[DraftPick],
    team_roster_swar: Optional[float] = None
) -> discord.Embed:
    """
    Create "on the clock" embed showing current pick info.

    Args:
        current_pick: Current DraftPick being made
        draft_data: Current draft configuration
        recent_picks: List of recent draft picks
        upcoming_picks: List of upcoming draft picks
        team_roster_swar: Current team sWAR (optional)

    Returns:
        Discord embed with pick information
    """
    if not current_pick.owner:
        raise ValueError("Pick must have owner")

    # Create base embed with team colors
    embed = EmbedTemplate.create_base_embed(
        title=f"⏰ {current_pick.owner.lname} On The Clock",
        description=format_pick_display(current_pick.overall),
        color=EmbedColors.PRIMARY
    )

    # Add team info
    if current_pick.owner.sname:
        embed.add_field(
            name="Team",
            value=f"{current_pick.owner.abbrev} {current_pick.owner.sname}",
            inline=True
        )

    # Add timer info
    if draft_data.pick_deadline:
        deadline_timestamp = int(draft_data.pick_deadline.timestamp())
        embed.add_field(
            name="Deadline",
            value=f"<t:{deadline_timestamp}:R>",
            inline=True
        )

    # Add team sWAR if provided
    if team_roster_swar is not None:
        from utils.helpers import get_team_salary_cap
        cap_limit = get_team_salary_cap(current_pick.owner)
        embed.add_field(
            name="Current sWAR",
            value=f"{team_roster_swar:.2f} / {cap_limit:.2f}",
            inline=True
        )

    # Add recent picks
    if recent_picks:
        recent_str = ""
        for pick in recent_picks[:5]:
            if pick.player:
                recent_str += f"**#{pick.overall}** - {pick.player.name}\n"
        if recent_str:
            embed.add_field(
                name="📋 Last 5 Picks",
                value=recent_str or "None",
                inline=False
            )

    # Add upcoming picks
    if upcoming_picks:
        upcoming_str = ""
        for pick in upcoming_picks[:5]:
            upcoming_str += f"**#{pick.overall}** - {pick.owner.sname if pick.owner else 'Unknown'}\n"
        if upcoming_str:
            embed.add_field(
                name="🔜 Next 5 Picks",
                value=upcoming_str,
                inline=False
            )

    # Add footer
    if current_pick.is_traded:
        embed.set_footer(text="📝 This pick was traded")

    return embed


async def create_draft_status_embed(
    draft_data: DraftData,
    current_pick: DraftPick,
    lock_status: str = "🔓 No pick in progress"
) -> discord.Embed:
    """
    Create draft status embed showing current state.

    Args:
        draft_data: Current draft configuration
        current_pick: Current DraftPick
        lock_status: Lock status message

    Returns:
        Discord embed with draft status
    """
    embed = EmbedTemplate.info(
        title="Draft Status",
        description=f"Currently on {format_pick_display(draft_data.currentpick)}"
    )

    # On the clock
    if current_pick.owner:
        embed.add_field(
            name="On the Clock",
            value=f"{current_pick.owner.abbrev} {current_pick.owner.sname}",
            inline=True
        )

    # Timer status
    timer_status = "✅ Active" if draft_data.timer else "⏹️ Inactive"
    embed.add_field(
        name="Timer",
        value=f"{timer_status} ({draft_data.pick_minutes} min)",
        inline=True
    )

    # Deadline
    if draft_data.pick_deadline:
        deadline_timestamp = int(draft_data.pick_deadline.timestamp())
        embed.add_field(
            name="Deadline",
            value=f"<t:{deadline_timestamp}:R>",
            inline=True
        )
    else:
        embed.add_field(
            name="Deadline",
            value="None",
            inline=True
        )

    # Lock status
    embed.add_field(
        name="Lock Status",
        value=lock_status,
        inline=False
    )

    return embed


async def create_player_draft_card(
    player: Player,
    draft_pick: DraftPick
) -> discord.Embed:
    """
    Create player draft card embed.

    Args:
        player: Player being drafted
        draft_pick: DraftPick information

    Returns:
        Discord embed with player info
    """
    if not draft_pick.owner:
        raise ValueError("Pick must have owner")

    embed = EmbedTemplate.success(
        title=f"{player.name} Drafted!",
        description=format_pick_display(draft_pick.overall)
    )

    # Team info
    embed.add_field(
        name="Selected By",
        value=f"{draft_pick.owner.abbrev} {draft_pick.owner.sname}",
        inline=True
    )

    # Player info
    if hasattr(player, 'pos_1') and player.pos_1:
        embed.add_field(
            name="Position",
            value=player.pos_1,
            inline=True
        )

    if hasattr(player, 'wara') and player.wara is not None:
        embed.add_field(
            name="sWAR",
            value=f"{player.wara:.2f}",
            inline=True
        )

    # Add player image if available
    if hasattr(player, 'image') and player.image:
        embed.set_thumbnail(url=player.image)

    return embed


async def create_draft_list_embed(
    team: Team,
    draft_list: List[DraftList]
) -> discord.Embed:
    """
    Create draft list embed showing team's auto-draft queue.

    Args:
        team: Team owning the list
        draft_list: List of DraftList entries

    Returns:
        Discord embed with draft list
    """
    embed = EmbedTemplate.info(
        title=f"{team.sname} Draft List",
        description=f"Auto-draft queue for {team.abbrev}"
    )

    if not draft_list:
        embed.add_field(
            name="Queue Empty",
            value="No players in auto-draft queue",
            inline=False
        )
    else:
        # Group players by rank
        list_str = ""
        for entry in draft_list[:25]:  # Limit to 25 for embed size
            player_name = entry.player.name if entry.player else f"Player {entry.player_id}"
            player_swar = f" ({entry.player.wara:.2f})" if entry.player and hasattr(entry.player, 'wara') else ""
            list_str += f"**{entry.rank}.** {player_name}{player_swar}\n"

        embed.add_field(
            name=f"Queue ({len(draft_list)} players)",
            value=list_str,
            inline=False
        )

    embed.set_footer(text="Commands: /draft-list-add, /draft-list-remove, /draft-list-clear")

    return embed


async def create_draft_board_embed(
    round_num: int,
    picks: List[DraftPick]
) -> discord.Embed:
    """
    Create draft board embed showing all picks in a round.

    Args:
        round_num: Round number
        picks: List of DraftPick for this round

    Returns:
        Discord embed with draft board
    """
    embed = EmbedTemplate.create_base_embed(
        title=f"📋 {get_round_name(round_num)}",
        description=f"Draft board for round {round_num}",
        color=EmbedColors.PRIMARY
    )

    if not picks:
        embed.add_field(
            name="No Picks",
            value="No picks found for this round",
            inline=False
        )
    else:
        # Create picks display
        picks_str = ""
        for pick in picks:
            if pick.player:
                player_display = pick.player.name
            else:
                player_display = "TBD"

            team_display = pick.owner.abbrev if pick.owner else "???"
            picks_str += f"**Pick {pick.overall % 16 or 16}:** {team_display} - {player_display}\n"

        embed.add_field(
            name="Picks",
            value=picks_str,
            inline=False
        )

    embed.set_footer(text="Use /draft-board [round] to view different rounds")

    return embed


async def create_pick_illegal_embed(
    reason: str,
    details: Optional[str] = None
) -> discord.Embed:
    """
    Create embed for illegal pick attempt.

    Args:
        reason: Main reason pick is illegal
        details: Additional details (optional)

    Returns:
        Discord error embed
    """
    embed = EmbedTemplate.error(
        title="Invalid Pick",
        description=reason
    )

    if details:
        embed.add_field(
            name="Details",
            value=details,
            inline=False
        )

    return embed


async def create_pick_success_embed(
    player: Player,
    team: Team,
    pick_overall: int,
    projected_swar: float,
    cap_limit: float = None
) -> discord.Embed:
    """
    Create embed for successful pick.

    Args:
        player: Player drafted
        team: Team that drafted player
        pick_overall: Overall pick number
        projected_swar: Projected team sWAR after pick
        cap_limit: Team's salary cap limit (optional, uses helper if not provided)

    Returns:
        Discord success embed
    """
    from utils.helpers import get_team_salary_cap

    embed = EmbedTemplate.success(
        title="Pick Confirmed",
        description=f"{team.abbrev} selects **{player.name}**"
    )

    embed.add_field(
        name="Pick",
        value=format_pick_display(pick_overall),
        inline=True
    )

    if hasattr(player, 'wara') and player.wara is not None:
        embed.add_field(
            name="Player sWAR",
            value=f"{player.wara:.2f}",
            inline=True
        )

    # Use provided cap_limit or get from team
    if cap_limit is None:
        cap_limit = get_team_salary_cap(team)

    embed.add_field(
        name="Projected Team sWAR",
        value=f"{projected_swar:.2f} / {cap_limit:.2f}",
        inline=True
    )

    return embed


async def create_admin_draft_info_embed(
    draft_data: DraftData,
    current_pick: Optional[DraftPick] = None
) -> discord.Embed:
    """
    Create detailed admin view of draft status.

    Args:
        draft_data: Current draft configuration
        current_pick: Current DraftPick (optional)

    Returns:
        Discord embed with admin information
    """
    embed = EmbedTemplate.create_base_embed(
        title="⚙️ Draft Administration",
        description="Current draft configuration and state",
        color=EmbedColors.INFO
    )

    # Current pick
    embed.add_field(
        name="Current Pick",
        value=str(draft_data.currentpick),
        inline=True
    )

    # Timer status
    timer_emoji = "✅" if draft_data.timer else "⏹️"
    embed.add_field(
        name="Timer Status",
        value=f"{timer_emoji} {'Active' if draft_data.timer else 'Inactive'}",
        inline=True
    )

    # Timer duration
    embed.add_field(
        name="Pick Duration",
        value=f"{draft_data.pick_minutes} minutes",
        inline=True
    )

    # Channels
    ping_channel_value = f"<#{draft_data.ping_channel}>" if draft_data.ping_channel else "Not configured"
    embed.add_field(
        name="Ping Channel",
        value=ping_channel_value,
        inline=True
    )

    result_channel_value = f"<#{draft_data.result_channel}>" if draft_data.result_channel else "Not configured"
    embed.add_field(
        name="Result Channel",
        value=result_channel_value,
        inline=True
    )

    # Deadline
    if draft_data.pick_deadline:
        deadline_timestamp = int(draft_data.pick_deadline.timestamp())
        embed.add_field(
            name="Current Deadline",
            value=f"<t:{deadline_timestamp}:F>",
            inline=True
        )

    # Current pick owner
    if current_pick and current_pick.owner:
        embed.add_field(
            name="On The Clock",
            value=f"{current_pick.owner.abbrev} {current_pick.owner.sname}",
            inline=False
        )

    embed.set_footer(text="Use /draft-admin to modify draft settings")

    return embed
