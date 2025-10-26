"""
Decorators for Discord bot v2.0

This module provides decorators to reduce boilerplate code in Discord commands,
particularly for logging, error handling, and caching.
"""

import inspect
import logging
from functools import wraps
from typing import List, Optional, Callable, Any
from utils.logging import set_discord_context, get_contextual_logger

cache_logger = logging.getLogger(f'{__name__}.CacheDecorators')
period_check_logger = logging.getLogger(f'{__name__}.PeriodCheckDecorators')


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
        wrapper.__signature__ = inspect.signature(func)  # type: ignore
        return wrapper
    return decorator


def requires_draft_period(func):
    """
    Decorator to restrict commands to draft period (week <= 0).

    This decorator checks if the league is in the draft period (offseason)
    before allowing the command to execute. If the league is in-season,
    it returns an error message to the user.

    Example:
        @discord.app_commands.command(name="draft")
        @requires_draft_period
        @logged_command("/draft")
        async def draft_pick(self, interaction, player: str):
            # Command only runs during draft period (week <= 0)
            pass

    Side Effects:
        - Checks league current state via league_service
        - Returns error embed if check fails
        - Logs restriction events

    Requirements:
        - Must be applied to async methods with (self, interaction, ...) signature
        - Should be placed before @logged_command decorator
        - league_service must be available via import
    """
    @wraps(func)
    async def wrapper(self, interaction, *args, **kwargs):
        # Import here to avoid circular imports
        from services.league_service import league_service
        from views.embeds import EmbedTemplate

        try:
            # Check current league state
            current = await league_service.get_current_state()

            if not current:
                period_check_logger.error("Could not retrieve league state for draft period check")
                embed = EmbedTemplate.error(
                    "System Error",
                    "Could not verify draft period status. Please try again later."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Check if in draft period (week <= 0)
            if current.week > 0:
                period_check_logger.info(
                    f"Draft command blocked - current week: {current.week}",
                    extra={
                        "user_id": interaction.user.id,
                        "command": func.__name__,
                        "current_week": current.week
                    }
                )
                embed = EmbedTemplate.error(
                    "Not Available",
                    "Draft commands are only available in the offseason."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # Week <= 0, allow command to proceed
            period_check_logger.debug(
                f"Draft period check passed - week {current.week}",
                extra={"user_id": interaction.user.id, "command": func.__name__}
            )
            return await func(self, interaction, *args, **kwargs)

        except Exception as e:
            period_check_logger.error(
                f"Error in draft period check: {e}",
                exc_info=True,
                extra={"user_id": interaction.user.id, "command": func.__name__}
            )
            # Re-raise to let error handling in logged_command handle it
            raise

    # Preserve signature for Discord.py command registration
    wrapper.__signature__ = inspect.signature(func)  # type: ignore
    return wrapper


def cached_api_call(ttl: Optional[int] = None, cache_key_suffix: str = ""):
    """
    Decorator to add Redis caching to service methods that return List[T].
    
    This decorator will:
    1. Check cache for existing data using generated key
    2. Return cached data if found
    3. Execute original method if cache miss
    4. Cache the result for future calls
    
    Args:
        ttl: Time-to-live override in seconds (uses service default if None)
        cache_key_suffix: Additional suffix for cache key differentiation
        
    Usage:
        @cached_api_call(ttl=600, cache_key_suffix="by_season")
        async def get_teams_by_season(self, season: int) -> List[Team]:
            # Original method implementation
            
    Requirements:
        - Method must be async
        - Method must return List[T] where T is a model
        - Class must have self.cache (CacheManager instance)
        - Class must have self._generate_cache_key, self._get_cached_items, self._cache_items methods
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> List[Any]:
            # Check if caching is available (service has cache manager)
            if not hasattr(self, 'cache') or not hasattr(self, '_generate_cache_key'):
                # No caching available, execute original method
                return await func(self, *args, **kwargs)
                
            # Generate cache key from method name, args, and kwargs
            method_name = f"{func.__name__}{cache_key_suffix}"
            
            # Convert args and kwargs to params list for consistent cache key
            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()
            
            # Skip 'self' and convert to params format
            params = []
            for param_name, param_value in bound_args.arguments.items():
                if param_name != 'self' and param_value is not None:
                    params.append((param_name, param_value))
            
            cache_key = self._generate_cache_key(method_name, params)
            
            # Try to get from cache
            if hasattr(self, '_get_cached_items'):
                cached_result = await self._get_cached_items(cache_key)
                if cached_result is not None:
                    cache_logger.debug(f"Cache hit: {method_name}")
                    return cached_result
            
            # Cache miss - execute original method
            cache_logger.debug(f"Cache miss: {method_name}")
            result = await func(self, *args, **kwargs)
            
            # Cache the result if we have items and caching methods
            if result and hasattr(self, '_cache_items'):
                await self._cache_items(cache_key, result, ttl)
                cache_logger.debug(f"Cached {len(result)} items for {method_name}")
            
            return result
            
        return wrapper
    return decorator


def cached_single_item(ttl: Optional[int] = None, cache_key_suffix: str = ""):
    """
    Decorator to add Redis caching to service methods that return Optional[T].
    
    Similar to cached_api_call but for methods returning a single model instance.
    
    Args:
        ttl: Time-to-live override in seconds
        cache_key_suffix: Additional suffix for cache key differentiation
        
    Usage:
        @cached_single_item(ttl=300, cache_key_suffix="by_id")
        async def get_player(self, player_id: int) -> Optional[Player]:
            # Original method implementation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> Optional[Any]:
            # Check if caching is available
            if not hasattr(self, 'cache') or not hasattr(self, '_generate_cache_key'):
                return await func(self, *args, **kwargs)
                
            # Generate cache key
            method_name = f"{func.__name__}{cache_key_suffix}"
            
            sig = inspect.signature(func)
            bound_args = sig.bind(self, *args, **kwargs)
            bound_args.apply_defaults()
            
            params = []
            for param_name, param_value in bound_args.arguments.items():
                if param_name != 'self' and param_value is not None:
                    params.append((param_name, param_value))
            
            cache_key = self._generate_cache_key(method_name, params)
            
            # Try cache first
            try:
                cached_data = await self.cache.get(cache_key)
                if cached_data:
                    cache_logger.debug(f"Cache hit: {method_name}")
                    return self.model_class.from_api_data(cached_data)
            except Exception as e:
                cache_logger.warning(f"Error reading single item cache for {cache_key}: {e}")
            
            # Cache miss - execute original method
            cache_logger.debug(f"Cache miss: {method_name}")
            result = await func(self, *args, **kwargs)
            
            # Cache the single result
            if result:
                try:
                    cache_data = result.model_dump()
                    await self.cache.set(cache_key, cache_data, ttl)
                    cache_logger.debug(f"Cached single item for {method_name}")
                except Exception as e:
                    cache_logger.warning(f"Error caching single item for {cache_key}: {e}")
            
            return result
            
        return wrapper
    return decorator


def cache_invalidate(*cache_patterns: str):
    """
    Decorator to invalidate cache entries when data is modified.
    
    Args:
        cache_patterns: Cache key patterns to invalidate (supports prefix matching)
        
    Usage:
        @cache_invalidate("players_by_team", "teams_by_season")
        async def update_player(self, player_id: int, updates: dict) -> Optional[Player]:
            # Original method implementation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Execute original method first
            result = await func(self, *args, **kwargs)
            
            # Invalidate specified cache patterns
            if hasattr(self, 'cache'):
                for pattern in cache_patterns:
                    try:
                        cleared = await self.cache.clear_prefix(f"sba:{self.endpoint}_{pattern}")
                        if cleared > 0:
                            cache_logger.info(f"Invalidated {cleared} cache entries for pattern: {pattern}")
                    except Exception as e:
                        cache_logger.warning(f"Error invalidating cache pattern {pattern}: {e}")
            
            return result
            
        return wrapper
    return decorator