"""
Command decorators for Discord bot v2.0

This module provides decorators to reduce boilerplate code in Discord commands,
particularly for logging and error handling.
"""

import inspect
from functools import wraps
from typing import List, Optional
from utils.logging import set_discord_context, get_contextual_logger


def logged_command(
    command_name: Optional[str] = None, 
    log_params: bool = True,
    exclude_params: Optional[List[str]] = None
):
    """
    Decorator for Discord commands that adds comprehensive logging.
    
    This decorator automatically handles:
    - Setting Discord context with interaction details
    - Starting/ending operation timing
    - Logging command start/completion/failure
    - Preserving function metadata and signature
    
    Args:
        command_name: Override command name (defaults to function name with slashes)
        log_params: Whether to log command parameters (default: True)
        exclude_params: List of parameter names to exclude from logging
        
    Example:
        @logged_command("/roster", exclude_params=["sensitive_data"])
        async def team_roster(self, interaction, team_name: str, season: int = None):
            # Clean business logic only - no logging boilerplate needed
            team = await team_service.find_team(team_name)
            players = await team_service.get_roster(team.id, season)
            embed = create_roster_embed(team, players)
            await interaction.followup.send(embed=embed)
    
    Side Effects:
        - Automatically sets Discord context for all subsequent log entries
        - Creates trace_id for request correlation
        - Logs command execution timing and results
        - Re-raises all exceptions after logging (preserves original behavior)
    
    Requirements:
        - The decorated class must have a 'logger' attribute, or one will be created
        - Function must be an async method with (self, interaction, ...) signature
        - Preserves Discord.py command registration compatibility
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction, *args, **kwargs):
            # Auto-detect command name if not provided
            cmd_name = command_name or f"/{func.__name__.replace('_', '-')}"
            
            # Build context with safe parameter logging
            context = {"command": cmd_name}
            if log_params:
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())[2:]  # Skip self, interaction
                exclude_set = set(exclude_params or [])
                
                for i, (name, value) in enumerate(zip(param_names, args)):
                    if name not in exclude_set:
                        context[f"param_{name}"] = value
            
            set_discord_context(interaction=interaction, **context)
            
            # Get logger from the class instance or create one
            logger = getattr(self, 'logger', get_contextual_logger(f'{self.__class__.__module__}.{self.__class__.__name__}'))
            trace_id = logger.start_operation(f"{func.__name__}_command")
            
            try:
                logger.info(f"{cmd_name} command started")
                result = await func(self, interaction, *args, **kwargs)
                logger.info(f"{cmd_name} command completed successfully")
                logger.end_operation(trace_id, "completed")
                return result
                
            except Exception as e:
                logger.error(f"{cmd_name} command failed", error=e)
                logger.end_operation(trace_id, "failed")
                # Re-raise to maintain original exception handling behavior
                raise
        
        # Preserve signature for Discord.py command registration
        wrapper.__signature__ = inspect.signature(func)
        return wrapper
    return decorator