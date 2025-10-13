"""
Custom Commands Service for Discord Bot v2.0

Modern async service layer for managing custom commands with full type safety.
"""
import asyncio
import math
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from utils.logging import get_contextual_logger

from models.custom_command import (
    CustomCommand, 
    CustomCommandCreator, 
    CustomCommandSearchFilters,
    CustomCommandSearchResult,
    CustomCommandStats
)
from services.base_service import BaseService
from exceptions import BotException


class CustomCommandNotFoundError(BotException):
    """Raised when a custom command is not found."""
    pass


class CustomCommandExistsError(BotException):
    """Raised when trying to create a command that already exists."""
    pass


class CustomCommandPermissionError(BotException):
    """Raised when user lacks permission for command operation."""
    pass


class CustomCommandsService(BaseService[CustomCommand]):
    """Service for managing custom commands."""
    
    def __init__(self):
        super().__init__(CustomCommand, 'custom_commands')
        self.logger = get_contextual_logger(f'{__name__}.CustomCommandsService')
        self.logger.info("CustomCommandsService initialized")
    
    # === Command CRUD Operations ===
    
    async def create_command(
        self, 
        name: str, 
        content: str, 
        creator_discord_id: int,
        creator_username: str,
        creator_display_name: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> CustomCommand:
        """
        Create a new custom command.
        
        Args:
            name: Command name (will be validated and normalized)
            content: Command response content
            creator_discord_id: Discord ID of the creator
            creator_username: Discord username
            creator_display_name: Discord display name (optional)
            tags: Optional tags for categorization
            
        Returns:
            The created CustomCommand
            
        Raises:
            CustomCommandExistsError: If command name already exists
            ValidationError: If name or content fails validation
        """
        # Check if command already exists
        try:
            await self.get_command_by_name(name)
            raise CustomCommandExistsError(f"Command '{name}' already exists")
        except CustomCommandNotFoundError:
            # Command doesn't exist, which is what we want
            pass
        
        # Get or create creator
        creator = await self.get_or_create_creator(
            discord_id=creator_discord_id,
            username=creator_username,
            display_name=creator_display_name
        )
        
        # Create command data
        now = datetime.now()
        command_data = {
            'name': name.lower().strip(),
            'content': content.strip(),
            'creator_id': creator.id,
            'created_at': now.isoformat(),
            'last_used': now.isoformat(),  # Set initial last_used to creation time
            'use_count': 0,
            'warning_sent': False,
            'is_active': True,
            'tags': tags or []
        }
        
        # Create via API
        result = await self.create(command_data)
        if not result:
            raise BotException("Failed to create custom command")
        
        # Update creator stats
        await self._update_creator_stats(creator.id)
        
        self.logger.info("Custom command created", 
                        command_name=name,
                        creator_id=creator_discord_id,
                        content_length=len(content))
        
        # Return full command with creator info
        return await self.get_command_by_name(name)
    
    async def get_command_by_name(
        self, 
        name: str
    ) -> CustomCommand:
        """
        Get a custom command by name.
        
        Args:
            name: Command name to search for
            
        Returns:
            CustomCommand if found
            
        Raises:
            CustomCommandNotFoundError: If command not found
        """
        normalized_name = name.lower().strip()
        
        try:
            # Use the dedicated by_name endpoint for exact lookup
            client = await self.get_client()
            data = await client.get(f'custom_commands/by_name/{normalized_name}')
            
            if not data:
                raise CustomCommandNotFoundError(f"Custom command '{name}' not found")
            
            # Convert API data to CustomCommand
            return self.model_class.from_api_data(data)
            
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise CustomCommandNotFoundError(f"Custom command '{name}' not found")
            else:
                self.logger.error("Failed to get command by name",
                                command_name=name,
                                error=e)
                raise BotException(f"Failed to retrieve command '{name}': {e}")
    
    async def update_command(
        self, 
        name: str, 
        new_content: str,
        updater_discord_id: int,
        new_tags: Optional[List[str]] = None
    ) -> CustomCommand:
        """
        Update an existing custom command.
        
        Args:
            name: Command name to update
            new_content: New command content
            updater_discord_id: Discord ID of user making the update
            new_tags: New tags (optional)
            
        Returns:
            Updated CustomCommand
            
        Raises:
            CustomCommandNotFoundError: If command doesn't exist
            CustomCommandPermissionError: If user doesn't own the command
        """
        command = await self.get_command_by_name(name)
        
        # Check permissions
        if command.creator.discord_id != updater_discord_id:
            raise CustomCommandPermissionError("You can only edit commands you created")
        
        # Prepare update data - include all required fields to avoid NULL constraints
        update_data = {
            'name': command.name,
            'content': new_content.strip(),
            'creator_id': command.creator_id,
            'created_at': command.created_at.isoformat(),  # Preserve original creation time
            'updated_at': datetime.now().isoformat(),
            'last_used': command.last_used.isoformat() if command.last_used else None,
            'warning_sent': False,  # Reset warning if command is updated
            'is_active': command.is_active,  # Preserve active status
            'use_count': command.use_count  # Preserve usage count
        }
        
        if new_tags is not None:
            update_data['tags'] = new_tags
        else:
            # Preserve existing tags if not being updated
            update_data['tags'] = command.tags
        
        # Update via API
        result = await self.update_item_by_field('name', name, update_data)
        if not result:
            raise BotException("Failed to update custom command")
        
        self.logger.info("Custom command updated",
                        command_name=name,
                        updater_id=updater_discord_id,
                        new_content_length=len(new_content))
        
        return await self.get_command_by_name(name)
    
    async def delete_command(
        self, 
        name: str, 
        deleter_discord_id: int,
        force: bool = False
    ) -> bool:
        """
        Delete a custom command.
        
        Args:
            name: Command name to delete
            deleter_discord_id: Discord ID of user deleting the command
            force: Whether to force delete (admin override)
            
        Returns:
            True if successfully deleted
            
        Raises:
            CustomCommandNotFoundError: If command doesn't exist
            CustomCommandPermissionError: If user doesn't own the command and force=False
        """
        command = await self.get_command_by_name(name)
        
        # Check permissions (unless force delete)
        if not force and command.creator_id != deleter_discord_id:
            raise CustomCommandPermissionError("You can only delete commands you created")
        
        # Delete via API
        result = await self.delete_item_by_field('name', name)
        if not result:
            raise BotException("Failed to delete custom command")
        
        # Update creator stats
        await self._update_creator_stats(command.creator_id)
        
        self.logger.info("Custom command deleted",
                        command_name=name,
                        deleter_id=deleter_discord_id,
                        was_forced=force)
        
        return True
    
    async def execute_command(self, name: str) -> Tuple[CustomCommand, str]:
        """
        Execute a custom command and update usage statistics.
        
        Args:
            name: Command name to execute
            
        Returns:
            Tuple of (CustomCommand, response_content)
            
        Raises:
            CustomCommandNotFoundError: If command doesn't exist
        """
        normalized_name = name.lower().strip()
        
        try:
            # Use the dedicated execute endpoint which updates stats and returns the command
            client = await self.get_client()
            data = await client.patch(f'custom_commands/by_name/{normalized_name}/execute')
            
            if not data:
                raise CustomCommandNotFoundError(f"Custom command '{name}' not found")
            
            # Convert API data to CustomCommand
            updated_command = self.model_class.from_api_data(data)
            
            self.logger.debug("Custom command executed",
                             command_name=name,
                             new_use_count=updated_command.use_count)
            
            return updated_command, updated_command.content
            
        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise CustomCommandNotFoundError(f"Custom command '{name}' not found")
            else:
                self.logger.error("Failed to execute command",
                                command_name=name,
                                error=e)
                raise BotException(f"Failed to execute command '{name}': {e}")
    
    # === Search and Listing ===
    
    async def search_commands(
        self, 
        filters: CustomCommandSearchFilters
    ) -> CustomCommandSearchResult:
        """
        Search for custom commands with filtering and pagination.
        
        Args:
            filters: Search filters and pagination options
            
        Returns:
            CustomCommandSearchResult with matching commands
        """
        # Build search parameters
        params = []
        
        # Apply filters
        if filters.name_contains:
            params.append(('name__icontains', filters.name_contains))
        
        if filters.creator_id:
            params.append(('creator_id', filters.creator_id))
        
        if filters.min_uses:
            params.append(('use_count__gte', filters.min_uses))
        
        if filters.max_days_unused:
            cutoff_date = datetime.now() - timedelta(days=filters.max_days_unused)
            params.append(('last_used__gte', cutoff_date.isoformat()))
        
        params.append(('is_active', filters.is_active))
        
        # Add sorting
        sort_field = filters.sort_by
        if filters.sort_desc:
            sort_field = f'-{sort_field}'
        params.append(('sort', sort_field))
        
        # Get total count for pagination
        total_count = await self._get_search_count(params)
        total_pages = math.ceil(total_count / filters.page_size)
        
        # Add pagination
        offset = (filters.page - 1) * filters.page_size
        params.extend([
            ('limit', filters.page_size),
            ('offset', offset)
        ])
        
        # Execute search
        commands_data = await self.get_items_with_params(params)
        
        # Convert to CustomCommand objects (creator info is now included in API response)
        commands = []
        for cmd_data in commands_data:
            # The API now returns complete creator data, so we can use it directly
            commands.append(cmd_data)
        
        self.logger.debug("Custom commands search completed",
                         total_results=total_count,
                         page=filters.page,
                         filters_applied=len([p for p in params if not p[0] in ['sort', 'limit', 'offset']]))
        
        return CustomCommandSearchResult(
            commands=commands,
            total_count=total_count,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
            has_more=filters.page < total_pages
        )
    
    async def get_commands_by_creator(
        self, 
        creator_discord_id: int,
        page: int = 1,
        page_size: int = 25
    ) -> CustomCommandSearchResult:
        """Get all commands created by a specific user."""
        try:
            # Use the main custom_commands endpoint with creator_discord_id filter
            client = await self.get_client()
            
            params = [
                ('creator_discord_id', creator_discord_id),
                ('is_active', True),
                ('sort', 'name'),
                ('page', page),
                ('page_size', page_size)
            ]
            
            data = await client.get('custom_commands', params=params)
            
            if not data:
                return CustomCommandSearchResult(
                    commands=[],
                    total_count=0,
                    page=page,
                    page_size=page_size,
                    total_pages=0,
                    has_more=False
                )
            
            # Extract response data
            custom_commands = data.get('custom_commands', [])
            total_count = data.get('total_count', 0)
            total_pages = data.get('total_pages', 0)
            has_more = data.get('has_more', False)
            
            # Convert to CustomCommand objects (creator data is included in API response)
            commands = []
            for cmd_data in custom_commands:
                try:
                    commands.append(self.model_class.from_api_data(cmd_data))
                except Exception as e:
                    self.logger.warning("Failed to create CustomCommand from API data",
                                      command_id=cmd_data.get('id'),
                                      error=e)
                    continue
            
            self.logger.debug("Got commands by creator",
                             creator_discord_id=creator_discord_id,
                             returned_commands=len(commands),
                             total_count=total_count)
            
            return CustomCommandSearchResult(
                commands=commands,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
                has_more=has_more
            )
            
        except Exception as e:
            self.logger.error("Failed to get commands by creator",
                            creator_discord_id=creator_discord_id,
                            error=e)
            # Return empty result on error
            return CustomCommandSearchResult(
                commands=[],
                total_count=0,
                page=page,
                page_size=page_size,
                total_pages=0,
                has_more=False
            )
    
    async def get_popular_commands(self, limit: int = 10) -> List[CustomCommand]:
        """Get the most popular commands by usage."""
        params = [
            ('is_active', True),
            ('sort', '-use_count'),
            ('limit', limit)
        ]

        commands_data = await self.get_items_with_params(params)

        commands = []
        for cmd_data in commands_data:
            try:
                creator = await self.get_creator_by_id(cmd_data.creator_id)
                commands.append(CustomCommand(**cmd_data.model_dump(), creator=creator))
            except BotException as e:
                # Handle missing creator gracefully
                self.logger.warning("Skipping popular command with missing creator",
                                  command_id=cmd_data.id,
                                  command_name=cmd_data.name,
                                  creator_id=cmd_data.creator_id,
                                  error=str(e))
                continue

        return commands
    
    async def get_command_names_for_autocomplete(
        self, 
        partial_name: str = "",
        limit: int = 25
    ) -> List[str]:
        """
        Get command names for Discord autocomplete.
        
        Args:
            partial_name: Partial command name to match
            limit: Maximum number of suggestions
            
        Returns:
            List of command names matching the partial input
        """
        try:
            # Use the dedicated autocomplete endpoint for better performance
            client = await self.get_client()
            params = [('limit', limit)]
            
            if partial_name:
                params.append(('partial_name', partial_name.lower()))
            
            result = await client.get('custom_commands/autocomplete', params=params)
            
            # The autocomplete endpoint returns a list of strings directly
            if isinstance(result, list):
                return result
            else:
                self.logger.warning("Unexpected autocomplete response format",
                                  response=result)
                return []
                
        except Exception as e:
            self.logger.error("Failed to get command names for autocomplete",
                            partial_name=partial_name,
                            error=e)
            # Return empty list on error to not break Discord autocomplete
            return []
    
    # === Creator Management ===
    
    async def get_or_create_creator(
        self,
        discord_id: int,
        username: str,
        display_name: Optional[str] = None
    ) -> CustomCommandCreator:
        """Get existing creator or create a new one."""
        try:
            creator = await self.get_creator_by_discord_id(discord_id)
            # Update username if it changed
            if creator.username != username or creator.display_name != display_name:
                await self._update_creator_info(creator.id, username, display_name)
                creator = await self.get_creator_by_discord_id(discord_id)
            return creator
        except BotException:
            # Creator doesn't exist, create new one
            pass
        
        # Create new creator
        creator_data = {
            'discord_id': discord_id,
            'username': username,
            'display_name': display_name,
            'created_at': datetime.now().isoformat(),
            'total_commands': 0,
            'active_commands': 0
        }
        
        result = await self.create_item_in_table('custom_command_creators', creator_data)
        if not result:
            raise BotException("Failed to create command creator")
        
        return await self.get_creator_by_discord_id(discord_id)
    
    async def get_creator_by_discord_id(self, discord_id: int) -> CustomCommandCreator:
        """Get creator by Discord ID.
        
        Raises:
            BotException: If creator not found
        """
        try:
            client = await self.get_client()
            data = await client.get('custom_commands/creators', params=[('discord_id', discord_id)])
            
            if not data or not data.get('creators'):
                raise BotException(f"Creator with Discord ID {discord_id} not found")
            
            creators = data['creators']
            if not creators:
                raise BotException(f"Creator with Discord ID {discord_id} not found")
            
            return CustomCommandCreator(**creators[0])
            
        except Exception as e:
            if "not found" in str(e).lower():
                raise BotException(f"Creator with Discord ID {discord_id} not found")
            else:
                self.logger.error("Failed to get creator by Discord ID",
                                discord_id=discord_id,
                                error=e)
                raise BotException(f"Failed to retrieve creator: {e}")
    
    async def get_creator_by_id(self, creator_id: int) -> CustomCommandCreator:
        """Get creator by database ID.
        
        Raises:
            BotException: If creator not found
        """
        creators = await self.get_items_from_table_with_params(
            'custom_command_creators',
            [('id', creator_id)]
        )
        
        if not creators:
            raise BotException(f"Creator with ID {creator_id} not found")
        
        return CustomCommandCreator(**creators[0])
    
    # === Statistics and Analytics ===
    
    async def get_statistics(self) -> CustomCommandStats:
        """Get comprehensive statistics about custom commands."""
        # Get basic counts
        total_commands = await self._get_search_count([])
        active_commands = await self._get_search_count([('is_active', True)])
        total_creators = await self._get_creator_count()
        
        # Get total uses
        all_commands = await self.get_items_with_params([('is_active', True)])
        total_uses = sum(cmd.use_count for cmd in all_commands)
        
        # Get most popular command
        popular_commands = await self.get_popular_commands(limit=1)
        most_popular = popular_commands[0] if popular_commands else None
        
        # Get most active creator
        most_active_creator = await self._get_most_active_creator()
        
        # Get recent commands count
        week_ago = datetime.now() - timedelta(days=7)
        recent_count = await self._get_search_count([
            ('created_at__gte', week_ago.isoformat()),
            ('is_active', True)
        ])
        
        # Get cleanup statistics
        warning_count = await self._get_commands_needing_warning_count()
        deletion_count = await self._get_commands_eligible_for_deletion_count()
        
        return CustomCommandStats(
            total_commands=total_commands,
            active_commands=active_commands,
            total_creators=total_creators,
            total_uses=total_uses,
            most_popular_command=most_popular,
            most_active_creator=most_active_creator,
            recent_commands_count=recent_count,
            commands_needing_warning=warning_count,
            commands_eligible_for_deletion=deletion_count
        )
    
    # === Cleanup Operations ===
    
    async def get_commands_needing_warning(self) -> List[CustomCommand]:
        """Get commands that need deletion warning (60+ days unused)."""
        cutoff_date = datetime.now() - timedelta(days=60)

        params = [
            ('last_used__lt', cutoff_date.isoformat()),
            ('warning_sent', False),
            ('is_active', True)
        ]

        commands_data = await self.get_items_with_params(params)

        commands = []
        for cmd_data in commands_data:
            try:
                creator = await self.get_creator_by_id(cmd_data.creator_id)
                commands.append(CustomCommand(**cmd_data.model_dump(), creator=creator))
            except BotException as e:
                # Handle missing creator gracefully
                self.logger.warning("Skipping command with missing creator",
                                  command_id=cmd_data.id,
                                  command_name=cmd_data.name,
                                  creator_id=cmd_data.creator_id,
                                  error=str(e))
                continue

        return commands
    
    async def get_commands_eligible_for_deletion(self) -> List[CustomCommand]:
        """Get commands eligible for deletion (90+ days unused)."""
        cutoff_date = datetime.now() - timedelta(days=90)

        params = [
            ('last_used__lt', cutoff_date.isoformat()),
            ('is_active', True)
        ]

        commands_data = await self.get_items_with_params(params)

        commands = []
        for cmd_data in commands_data:
            try:
                creator = await self.get_creator_by_id(cmd_data.creator_id)
                commands.append(CustomCommand(**cmd_data.model_dump(), creator=creator))
            except BotException as e:
                # Handle missing creator gracefully
                self.logger.warning("Skipping command with missing creator",
                                  command_id=cmd_data.id,
                                  command_name=cmd_data.name,
                                  creator_id=cmd_data.creator_id,
                                  error=str(e))
                continue

        return commands
    
    async def mark_warning_sent(self, command_name: str) -> bool:
        """Mark that a deletion warning has been sent for a command."""
        result = await self.update_item_by_field(
            'name', 
            command_name, 
            {'warning_sent': True}
        )
        return bool(result)
    
    async def bulk_delete_commands(self, command_names: List[str]) -> int:
        """Delete multiple commands and return count of successfully deleted."""
        deleted_count = 0
        
        for name in command_names:
            try:
                await self.delete_item_by_field('name', name)
                deleted_count += 1
            except Exception as e:
                self.logger.error("Failed to delete command during bulk delete",
                                command_name=name,
                                error=e)
        
        return deleted_count
    
    # === Private Helper Methods ===
    
    async def _update_creator_stats(self, creator_id: int) -> None:
        """Update creator statistics."""
        # Count total and active commands
        total = await self._get_search_count([('creator_id', creator_id)])
        active = await self._get_search_count([('creator_id', creator_id), ('is_active', True)])
        
        # Update creator via API
        try:
            client = await self.get_client()
            await client.put('custom_command_creators', {
                'total_commands': total,
                'active_commands': active
            }, object_id=creator_id)
        except Exception as e:
            self.logger.error(f"Failed to update creator {creator_id} stats: {e}")
    
    async def _update_creator_info(
        self, 
        creator_id: int, 
        username: str, 
        display_name: Optional[str]
    ) -> None:
        """Update creator username and display name."""
        try:
            client = await self.get_client()
            await client.put('custom_command_creators', {
                'username': username,
                'display_name': display_name
            }, object_id=creator_id)
        except Exception as e:
            self.logger.error(f"Failed to update creator {creator_id} info: {e}")
    
    async def _get_search_count(self, params: List[Tuple[str, Any]]) -> int:
        """Get count of commands matching search parameters."""
        # Use the count method from BaseService
        return await self.count(params)
    
    async def _get_creator_count(self) -> int:
        """Get total number of creators."""
        creators = await self.get_items_from_table_with_params('custom_command_creators', [])
        return len(creators)
    
    async def _get_most_active_creator(self) -> Optional[CustomCommandCreator]:
        """Get creator with most active commands."""
        creators = await self.get_items_from_table_with_params(
            'custom_command_creators',
            [('sort', '-active_commands'), ('limit', 1)]
        )
        
        if not creators:
            return None
        
        return CustomCommandCreator(**creators[0])
    
    async def _get_commands_needing_warning_count(self) -> int:
        """Get count of commands needing warning."""
        cutoff_date = datetime.now() - timedelta(days=60)
        return await self._get_search_count([
            ('last_used__lt', cutoff_date.isoformat()),
            ('warning_sent', False),
            ('is_active', True)
        ])
    
    async def _get_commands_eligible_for_deletion_count(self) -> int:
        """Get count of commands eligible for deletion."""
        cutoff_date = datetime.now() - timedelta(days=90)
        return await self._get_search_count([
            ('last_used__lt', cutoff_date.isoformat()),
            ('is_active', True)
        ])


# Global service instance
custom_commands_service = CustomCommandsService()