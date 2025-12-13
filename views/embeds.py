"""
Embed Templates for Discord Bot v2.0

Provides consistent embed styling and templates for common use cases.
"""
from typing import Optional, Union, Any, List
from datetime import datetime
from dataclasses import dataclass

from config import get_config

import discord



@dataclass(frozen=True)
class EmbedColors:
    """Standard color palette for embeds."""
    PRIMARY: int = 0xa6ce39      # SBA green
    SUCCESS: int = 0x28a745      # Green
    WARNING: int = 0xffc107      # Yellow
    ERROR: int = 0xdc3545        # Red
    INFO: int = 0x17a2b8         # Blue
    SECONDARY: int = 0x6c757d    # Gray
    DARK: int = 0x343a40         # Dark gray
    LIGHT: int = 0xf8f9fa        # Light gray


class EmbedTemplate:
    """Base embed template with consistent styling."""
    
    @staticmethod
    def create_base_embed(
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Union[int, discord.Color] = EmbedColors.PRIMARY,
        timestamp: bool = True
    ) -> discord.Embed:
        """Create a base embed with standard formatting."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        
        if timestamp:
            embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    @staticmethod
    def success(
        title: str = "Success",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a success embed."""
        return EmbedTemplate.create_base_embed(
            title=f"✅ {title}",
            description=description,
            color=EmbedColors.SUCCESS,
            **kwargs
        )
    
    @staticmethod
    def error(
        title: str = "Error",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create an error embed."""
        return EmbedTemplate.create_base_embed(
            title=f"❌ {title}",
            description=description,
            color=EmbedColors.ERROR,
            **kwargs
        )
    
    @staticmethod
    def warning(
        title: str = "Warning",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a warning embed."""
        return EmbedTemplate.create_base_embed(
            title=f"⚠️ {title}",
            description=description,
            color=EmbedColors.WARNING,
            **kwargs
        )
    
    @staticmethod
    def info(
        title: str = "Information",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create an info embed."""
        return EmbedTemplate.create_base_embed(
            title=f"ℹ️ {title}",
            description=description,
            color=EmbedColors.INFO,
            **kwargs
        )
    
    @staticmethod
    def loading(
        title: str = "Loading",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a loading embed."""
        return EmbedTemplate.create_base_embed(
            title=f"⏳ {title}",
            description=description,
            color=EmbedColors.SECONDARY,
            **kwargs
        )


class SBAEmbedTemplate(EmbedTemplate):
    """SBA-specific embed templates."""
    
    @staticmethod
    def player_card(
        player_name: str,
        position: str,
        team_abbrev: Optional[str] = None,
        team_name: Optional[str] = None,
        wara: Optional[float] = None,
        season: Optional[int] = None,
        player_image: Optional[str] = None,
        team_color: Optional[str] = None,
        additional_fields: Optional[List[dict]] = None
    ) -> discord.Embed:
        """Create a player card embed."""
        color = int(team_color, 16) if team_color else EmbedColors.PRIMARY
        
        embed = EmbedTemplate.create_base_embed(
            title=f"🏟️ {player_name}",
            color=color
        )
        
        # Basic player info
        embed.add_field(name="Position", value=position, inline=True)
        
        if team_abbrev and team_name:
            embed.add_field(name="Team", value=f"{team_abbrev} - {team_name}", inline=True)
        elif team_abbrev:
            embed.add_field(name="Team", value=team_abbrev, inline=True)
        
        if wara is not None:
            embed.add_field(name="WARA", value=f"{wara:.2f}", inline=True)
        
        embed.add_field(
            name="Season", 
            value=str(season or get_config().sba_season), 
            inline=True
        )
        
        # Add additional fields if provided
        if additional_fields:
            for field in additional_fields:
                embed.add_field(
                    name=field.get("name", "Field"),
                    value=field.get("value", "N/A"),
                    inline=field.get("inline", True)
                )
        
        # Set player image
        if player_image:
            embed.set_thumbnail(url=player_image)
        
        return embed
    
    @staticmethod
    def team_info(
        team_abbrev: str,
        team_name: str,
        season: Optional[int] = None,
        short_name: Optional[str] = None,
        stadium: Optional[str] = None,
        division: Optional[str] = None,
        record: Optional[str] = None,
        team_color: Optional[str] = None,
        team_thumbnail: Optional[str] = None,
        additional_fields: Optional[List[dict]] = None
    ) -> discord.Embed:
        """Create a team information embed."""
        color = int(team_color, 16) if team_color else EmbedColors.PRIMARY
        
        embed = EmbedTemplate.create_base_embed(
            title=f"{team_abbrev} - {team_name}",
            description=f"Season {season or get_config().sba_season} Team Information",
            color=color
        )
        
        # Basic team info
        if short_name:
            embed.add_field(name="Short Name", value=short_name, inline=True)
        
        embed.add_field(name="Abbreviation", value=team_abbrev, inline=True)
        embed.add_field(name="Season", value=str(season or get_config().sba_season), inline=True)
        
        if stadium:
            embed.add_field(name="Stadium", value=stadium, inline=True)
        
        if division:
            embed.add_field(name="Division", value=division, inline=True)
        
        if record:
            embed.add_field(name="Record", value=record, inline=True)
        
        # Add additional fields if provided
        if additional_fields:
            for field in additional_fields:
                embed.add_field(
                    name=field.get("name", "Field"),
                    value=field.get("value", "N/A"),
                    inline=field.get("inline", True)
                )
        
        # Set team thumbnail
        if team_thumbnail:
            embed.set_thumbnail(url=team_thumbnail)
        
        return embed
    
    @staticmethod
    def league_status(
        season: Optional[int] = None,
        week: Optional[int] = None,
        phase: Optional[str] = None,
        additional_info: Optional[str] = None,
        teams_count: Optional[int] = None,
        active_players: Optional[int] = None
    ) -> discord.Embed:
        """Create a league status embed."""
        embed = EmbedTemplate.create_base_embed(
            title="🏆 SBA League Status",
            color=EmbedColors.PRIMARY
        )
        
        if season:
            embed.add_field(name="Season", value=str(season), inline=True)
        
        if week:
            embed.add_field(name="Week", value=str(week), inline=True)
        
        if phase:
            embed.add_field(name="Phase", value=phase, inline=True)
        
        if teams_count:
            embed.add_field(name="Teams", value=str(teams_count), inline=True)
        
        if active_players:
            embed.add_field(name="Active Players", value=str(active_players), inline=True)
        
        if additional_info:
            embed.add_field(name="Additional Info", value=additional_info, inline=False)
        
        return embed
    
    @staticmethod
    def roster_display(
        team_abbrev: str,
        team_name: str,
        roster_type: str = "Full Roster",
        season: Optional[int] = None,
        team_color: Optional[str] = None,
        player_groups: Optional[dict] = None
    ) -> discord.Embed:
        """Create a roster display embed."""
        color = int(team_color, 16) if team_color else EmbedColors.PRIMARY
        
        embed = EmbedTemplate.create_base_embed(
            title=f"{team_abbrev} - {roster_type}",
            description=f"{team_name} • Season {season or get_config().sba_season}",
            color=color
        )
        
        if player_groups:
            for group_name, players in player_groups.items():
                if players:
                    player_list = "\n".join([
                        f"• {player.get('name', 'Unknown')} ({player.get('position', 'N/A')})"
                        for player in players[:10]  # Limit to 10 players per field
                    ])
                    
                    if len(players) > 10:
                        player_list += f"\n... and {len(players) - 10} more"
                    
                    embed.add_field(
                        name=f"{group_name} ({len(players)})",
                        value=player_list or "No players",
                        inline=True
                    )
        
        return embed
    
    @staticmethod
    def search_results(
        search_term: str,
        results: List[dict],
        result_type: str = "Results",
        max_results: int = 10
    ) -> discord.Embed:
        """Create a search results embed."""
        embed = EmbedTemplate.create_base_embed(
            title=f"🔍 Search Results for '{search_term}'",
            color=EmbedColors.INFO
        )
        
        if not results:
            embed.description = "No results found."
            embed.color = EmbedColors.WARNING
            return embed
        
        # Show limited results
        displayed_results = results[:max_results]
        result_text = "\n".join([
            f"• {result.get('name', 'Unknown')} ({result.get('detail', 'N/A')})"
            for result in displayed_results
        ])
        
        if len(results) > max_results:
            result_text += f"\n\n... and {len(results) - max_results} more results"
        
        embed.add_field(
            name=f"{result_type} ({len(results)} found)",
            value=result_text,
            inline=False
        )
        
        embed.set_footer(text="Please be more specific if you see multiple results.")
        
        return embed


class EmbedBuilder:
    """Fluent interface for building complex embeds."""
    
    def __init__(self, embed: Optional[discord.Embed] = None):
        self._embed = embed or discord.Embed()
    
    def title(self, title: str) -> 'EmbedBuilder':
        """Set embed title."""
        self._embed.title = title
        return self
    
    def description(self, description: str) -> 'EmbedBuilder':
        """Set embed description."""
        self._embed.description = description
        return self
    
    def color(self, color: Union[int, discord.Color]) -> 'EmbedBuilder':
        """Set embed color."""
        self._embed.color = color
        return self
    
    def field(self, name: str, value: str, inline: bool = True) -> 'EmbedBuilder':
        """Add a field to the embed."""
        self._embed.add_field(name=name, value=value, inline=inline)
        return self
    
    def thumbnail(self, url: str) -> 'EmbedBuilder':
        """Set embed thumbnail."""
        self._embed.set_thumbnail(url=url)
        return self
    
    def image(self, url: str) -> 'EmbedBuilder':
        """Set embed image."""
        self._embed.set_image(url=url)
        return self
    
    def footer(self, text: str, icon_url: Optional[str] = None) -> 'EmbedBuilder':
        """Set embed footer."""
        self._embed.set_footer(text=text, icon_url=icon_url)
        return self
    
    def timestamp(self, timestamp: Optional[datetime] = None) -> 'EmbedBuilder':
        """Set embed timestamp."""
        self._embed.timestamp = timestamp or discord.utils.utcnow()
        return self
    
    def author(self, name: str, url: Optional[str] = None, icon_url: Optional[str] = None) -> 'EmbedBuilder':
        """Set embed author."""
        self._embed.set_author(name=name, url=url, icon_url=icon_url)
        return self
    
    def build(self) -> discord.Embed:
        """Build and return the embed."""
        return self._embed