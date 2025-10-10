"""
Help Commands Service for Discord Bot v2.0

Modern async service layer for managing help commands with full type safety.
Allows admins and help editors to create custom help topics for league documentation,
resources, FAQs, links, and guides.
"""
import math
from typing import Optional, List
from utils.logging import get_contextual_logger

from models.help_command import (
    HelpCommand,
    HelpCommandSearchFilters,
    HelpCommandSearchResult,
    HelpCommandStats
)
from services.base_service import BaseService
from exceptions import BotException


class HelpCommandNotFoundError(BotException):
    """Raised when a help command is not found."""
    pass


class HelpCommandExistsError(BotException):
    """Raised when trying to create a help command that already exists."""
    pass


class HelpCommandPermissionError(BotException):
    """Raised when user lacks permission for help command operation."""
    pass


class HelpCommandsService(BaseService[HelpCommand]):
    """Service for managing help commands."""

    def __init__(self):
        super().__init__(HelpCommand, 'help_commands')
        self.logger = get_contextual_logger(f'{__name__}.HelpCommandsService')
        self.logger.info("HelpCommandsService initialized")

    # === Command CRUD Operations ===

    async def create_help(
        self,
        name: str,
        title: str,
        content: str,
        creator_discord_id: str,
        category: Optional[str] = None,
        display_order: int = 0
    ) -> HelpCommand:
        """
        Create a new help command.

        Args:
            name: Help topic name (will be validated and normalized)
            title: Display title
            content: Help content (markdown supported)
            creator_discord_id: Discord ID of the creator
            category: Optional category for organization
            display_order: Sort order for display (default: 0)

        Returns:
            The created HelpCommand

        Raises:
            HelpCommandExistsError: If help topic name already exists
            ValidationError: If name, title, or content fails validation
        """
        # Check if help topic already exists
        try:
            await self.get_help_by_name(name)
            raise HelpCommandExistsError(f"Help topic '{name}' already exists")
        except HelpCommandNotFoundError:
            # Help topic doesn't exist, which is what we want
            pass

        # Create help command data
        help_data = {
            'name': name.lower().strip(),
            'title': title.strip(),
            'content': content.strip(),
            'category': category.lower().strip() if category else None,
            'created_by_discord_id': str(creator_discord_id),  # Convert to string for safe storage
            'display_order': display_order,
            'is_active': True,
            'view_count': 0
        }

        # Create via API
        result = await self.create(help_data)
        if not result:
            raise BotException("Failed to create help command")

        self.logger.info("Help command created",
                        help_name=name,
                        creator_id=creator_discord_id,
                        category=category)

        # Return full help command
        return await self.get_help_by_name(name)

    async def get_help_by_name(
        self,
        name: str,
        include_inactive: bool = False
    ) -> HelpCommand:
        """
        Get a help command by name.

        Args:
            name: Help topic name to search for
            include_inactive: Whether to include soft-deleted topics

        Returns:
            HelpCommand if found

        Raises:
            HelpCommandNotFoundError: If help command not found
        """
        normalized_name = name.lower().strip()

        try:
            # Use the dedicated by_name endpoint for exact lookup
            client = await self.get_client()
            params = [('include_inactive', include_inactive)] if include_inactive else []
            data = await client.get(f'help_commands/by_name/{normalized_name}', params=params)

            if not data:
                raise HelpCommandNotFoundError(f"Help topic '{name}' not found")

            # Convert API data to HelpCommand
            return self.model_class.from_api_data(data)

        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise HelpCommandNotFoundError(f"Help topic '{name}' not found")
            else:
                self.logger.error("Failed to get help command by name",
                                help_name=name,
                                error=e)
                raise BotException(f"Failed to retrieve help topic '{name}': {e}")

    async def update_help(
        self,
        name: str,
        new_title: Optional[str] = None,
        new_content: Optional[str] = None,
        updater_discord_id: Optional[str] = None,
        new_category: Optional[str] = None,
        new_display_order: Optional[int] = None
    ) -> HelpCommand:
        """
        Update an existing help command.

        Args:
            name: Help topic name to update
            new_title: New title (optional)
            new_content: New content (optional)
            updater_discord_id: Discord ID of user making the update
            new_category: New category (optional)
            new_display_order: New display order (optional)

        Returns:
            Updated HelpCommand

        Raises:
            HelpCommandNotFoundError: If help command doesn't exist
        """
        help_cmd = await self.get_help_by_name(name)

        # Prepare update data
        update_data = {}

        if new_title is not None:
            update_data['title'] = new_title.strip()

        if new_content is not None:
            update_data['content'] = new_content.strip()

        if new_category is not None:
            update_data['category'] = new_category.lower().strip() if new_category else None

        if new_display_order is not None:
            update_data['display_order'] = new_display_order

        if updater_discord_id is not None:
            update_data['last_modified_by'] = str(updater_discord_id)  # Convert to string for safe storage

        if not update_data:
            raise BotException("No fields to update")

        # Update via API
        client = await self.get_client()
        result = await client.put(f'help_commands/{help_cmd.id}', update_data)
        if not result:
            raise BotException("Failed to update help command")

        self.logger.info("Help command updated",
                        help_name=name,
                        updater_id=updater_discord_id,
                        fields_updated=list(update_data.keys()))

        return await self.get_help_by_name(name)

    async def delete_help(self, name: str) -> bool:
        """
        Soft delete a help command (sets is_active = FALSE).

        Args:
            name: Help topic name to delete

        Returns:
            True if successfully deleted

        Raises:
            HelpCommandNotFoundError: If help command doesn't exist
        """
        help_cmd = await self.get_help_by_name(name)

        # Soft delete via API
        client = await self.get_client()
        await client.delete(f'help_commands/{help_cmd.id}')

        self.logger.info("Help command soft deleted",
                        help_name=name,
                        help_id=help_cmd.id)

        return True

    async def restore_help(self, name: str) -> HelpCommand:
        """
        Restore a soft-deleted help command.

        Args:
            name: Help topic name to restore

        Returns:
            Restored HelpCommand

        Raises:
            HelpCommandNotFoundError: If help command doesn't exist
        """
        # Get help command including inactive ones
        help_cmd = await self.get_help_by_name(name, include_inactive=True)

        if help_cmd.is_active:
            raise BotException(f"Help topic '{name}' is already active")

        # Restore via API
        client = await self.get_client()
        result = await client.patch(f'help_commands/{help_cmd.id}/restore')
        if not result:
            raise BotException("Failed to restore help command")

        self.logger.info("Help command restored",
                        help_name=name,
                        help_id=help_cmd.id)

        return self.model_class.from_api_data(result)

    async def increment_view_count(self, name: str) -> HelpCommand:
        """
        Increment view count for a help command.

        Args:
            name: Help topic name

        Returns:
            Updated HelpCommand

        Raises:
            HelpCommandNotFoundError: If help command doesn't exist
        """
        normalized_name = name.lower().strip()

        try:
            client = await self.get_client()
            await client.patch(f'help_commands/by_name/{normalized_name}/view')

            self.logger.debug("Help command view count incremented",
                            help_name=name)

            # Return updated command
            return await self.get_help_by_name(name)

        except Exception as e:
            if "404" in str(e) or "not found" in str(e).lower():
                raise HelpCommandNotFoundError(f"Help topic '{name}' not found")
            else:
                self.logger.error("Failed to increment view count",
                                help_name=name,
                                error=e)
                raise BotException(f"Failed to increment view count for '{name}': {e}")

    # === Search and Listing ===

    async def search_help_commands(
        self,
        filters: HelpCommandSearchFilters
    ) -> HelpCommandSearchResult:
        """
        Search for help commands with filtering and pagination.

        Args:
            filters: Search filters and pagination options

        Returns:
            HelpCommandSearchResult with matching commands
        """
        # Build search parameters
        params = []

        # Apply filters
        if filters.name_contains:
            params.append(('name', filters.name_contains))  # API will do ILIKE search

        if filters.category:
            params.append(('category', filters.category))

        params.append(('is_active', filters.is_active))

        # Add sorting
        params.append(('sort', filters.sort_by))

        # Add pagination
        params.append(('page', filters.page))
        params.append(('page_size', filters.page_size))

        # Execute search via API
        client = await self.get_client()
        data = await client.get('help_commands', params=params)

        if not data:
            return HelpCommandSearchResult(
                help_commands=[],
                total_count=0,
                page=filters.page,
                page_size=filters.page_size,
                total_pages=0,
                has_more=False
            )

        # Extract response data
        help_commands_data = data.get('help_commands', [])
        total_count = data.get('total_count', 0)
        total_pages = data.get('total_pages', 0)
        has_more = data.get('has_more', False)

        # Convert to HelpCommand objects
        help_commands = []
        for cmd_data in help_commands_data:
            try:
                help_commands.append(self.model_class.from_api_data(cmd_data))
            except Exception as e:
                self.logger.warning("Failed to create HelpCommand from API data",
                                  help_id=cmd_data.get('id'),
                                  error=e)
                continue

        self.logger.debug("Help commands search completed",
                         total_results=total_count,
                         page=filters.page,
                         filters_applied=len([p for p in params if p[0] not in ['sort', 'page', 'page_size']]))

        return HelpCommandSearchResult(
            help_commands=help_commands,
            total_count=total_count,
            page=filters.page,
            page_size=filters.page_size,
            total_pages=total_pages,
            has_more=has_more
        )

    async def get_all_help_topics(
        self,
        category: Optional[str] = None,
        include_inactive: bool = False
    ) -> List[HelpCommand]:
        """
        Get all help topics, optionally filtered by category.

        Args:
            category: Optional category filter
            include_inactive: Whether to include soft-deleted topics

        Returns:
            List of HelpCommand objects
        """
        params = []

        if category:
            params.append(('category', category))

        params.append(('is_active', not include_inactive))
        params.append(('sort', 'display_order'))
        params.append(('page_size', 100))  # Get all

        client = await self.get_client()
        data = await client.get('help_commands', params=params)

        if not data:
            return []

        help_commands_data = data.get('help_commands', [])

        help_commands = []
        for cmd_data in help_commands_data:
            try:
                help_commands.append(self.model_class.from_api_data(cmd_data))
            except Exception as e:
                self.logger.warning("Failed to create HelpCommand from API data",
                                  help_id=cmd_data.get('id'),
                                  error=e)
                continue

        return help_commands

    async def get_help_names_for_autocomplete(
        self,
        partial_name: str = "",
        limit: int = 25,
        include_inactive: bool = False
    ) -> List[str]:
        """
        Get help command names for Discord autocomplete.

        Args:
            partial_name: Partial help topic name to match
            limit: Maximum number of suggestions
            include_inactive: Whether to include soft-deleted topics

        Returns:
            List of help topic names matching the partial input
        """
        try:
            # Use the dedicated autocomplete endpoint
            client = await self.get_client()
            params = [('limit', limit)]

            if partial_name:
                params.append(('q', partial_name.lower()))

            result = await client.get('help_commands/autocomplete', params=params)

            # The autocomplete endpoint returns results with name, title, category
            if isinstance(result, dict) and 'results' in result:
                return [item['name'] for item in result['results']]
            else:
                self.logger.warning("Unexpected autocomplete response format",
                                  response=result)
                return []

        except Exception as e:
            self.logger.error("Failed to get help names for autocomplete",
                            partial_name=partial_name,
                            error=e)
            # Return empty list on error to not break Discord autocomplete
            return []

    # === Statistics ===

    async def get_statistics(self) -> HelpCommandStats:
        """Get comprehensive statistics about help commands."""
        try:
            client = await self.get_client()
            data = await client.get('help_commands/stats')

            if not data:
                return HelpCommandStats(
                    total_commands=0,
                    active_commands=0,
                    total_views=0,
                    most_viewed_command=None,
                    recent_commands_count=0
                )

            # Convert most_viewed_command if present
            most_viewed = None
            if data.get('most_viewed_command'):
                try:
                    most_viewed = self.model_class.from_api_data(data['most_viewed_command'])
                except Exception as e:
                    self.logger.warning("Failed to parse most viewed command", error=e)

            return HelpCommandStats(
                total_commands=data.get('total_commands', 0),
                active_commands=data.get('active_commands', 0),
                total_views=data.get('total_views', 0),
                most_viewed_command=most_viewed,
                recent_commands_count=data.get('recent_commands_count', 0)
            )

        except Exception as e:
            self.logger.error("Failed to get help command statistics", error=e)
            # Return empty stats on error
            return HelpCommandStats(
                total_commands=0,
                active_commands=0,
                total_views=0,
                most_viewed_command=None,
                recent_commands_count=0
            )


# Global service instance
help_commands_service = HelpCommandsService()
