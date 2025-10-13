"""
Base service class for Discord Bot v2.0

Provides common CRUD operations and error handling for all data services.
"""
import logging
import hashlib
import json
from typing import Optional, Type, TypeVar, Generic, Dict, Any, List, Tuple

from api.client import get_global_client, APIClient
from models.base import SBABaseModel
from exceptions import APIException
from utils.cache import CacheManager

logger = logging.getLogger(f'{__name__}.BaseService')

T = TypeVar('T', bound=SBABaseModel)


class BaseService(Generic[T]):
    """
    Base service class providing common CRUD operations for SBA models.
    
    Features:
    - Generic type support for any SBABaseModel subclass
    - Automatic model validation and conversion
    - Standardized error handling
    - API response format handling (count + list format)
    - Connection management via global client
    """
    
    def __init__(self, 
                 model_class: Type[T], 
                 endpoint: str, 
                 client: Optional[APIClient] = None,
                 cache_manager: Optional[CacheManager] = None):
        """
        Initialize base service.
        
        Args:
            model_class: Pydantic model class for this service
            endpoint: API endpoint path (e.g., 'players', 'teams')
            client: Optional API client override (uses global client by default)
            cache_manager: Optional cache manager for Redis caching
        """
        self.model_class = model_class
        self.endpoint = endpoint
        self._client = client
        self._cached_client: Optional[APIClient] = None
        self.cache = cache_manager or CacheManager()
        
        logger.debug(f"Initialized {self.__class__.__name__} for {model_class.__name__} at endpoint '{endpoint}'")
    
    def _generate_cache_key(self, method: str, params: Optional[List[Tuple[str, Any]]] = None) -> str:
        """
        Generate consistent cache key for API calls.
        
        Args:
            method: API method name
            params: Query parameters as list of tuples
            
        Returns:
            SHA256-hashed cache key
        """
        key_parts = [self.endpoint, method]
        
        if params:
            # Sort parameters for consistent key generation
            sorted_params = sorted(params, key=lambda x: str(x[0]))
            param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
            key_parts.append(param_str)
        
        key_data = ":".join(key_parts)
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()[:16]  # First 16 chars
        
        return self.cache.cache_key("sba", f"{self.endpoint}_{key_hash}")
    
    async def _get_cached_items(self, cache_key: str) -> Optional[List[T]]:
        """
        Get cached list of model items.
        
        Args:
            cache_key: Cache key to lookup
            
        Returns:
            List of model instances or None if not cached
        """
        try:
            cached_data = await self.cache.get(cache_key)
            if cached_data and isinstance(cached_data, list):
                return [self.model_class.from_api_data(item) for item in cached_data]
        except Exception as e:
            logger.warning(f"Error deserializing cached data for {cache_key}: {e}")
        
        return None
    
    async def _cache_items(self, cache_key: str, items: List[T], ttl: Optional[int] = None) -> None:
        """
        Cache list of model items.
        
        Args:
            cache_key: Cache key to store under
            items: List of model instances to cache
            ttl: Optional TTL override
        """
        if not items:
            return
            
        try:
            # Convert to JSON-serializable format
            cache_data = [item.model_dump() for item in items]
            await self.cache.set(cache_key, cache_data, ttl)
        except Exception as e:
            logger.warning(f"Error caching items for {cache_key}: {e}")
    
    async def get_client(self) -> APIClient:
        """
        Get API client instance with caching to reduce async overhead.
        
        Returns:
            APIClient instance (cached after first access)
        """
        if self._client:
            return self._client
            
        # Cache the global client to avoid repeated async calls
        if self._cached_client is None:
            self._cached_client = await get_global_client()
        
        return self._cached_client
    
    async def get_by_id(self, object_id: int) -> Optional[T]:
        """
        Get single object by ID.
        
        Args:
            object_id: Unique identifier for the object
            
        Returns:
            Model instance or None if not found
            
        Raises:
            APIException: For API errors
            ValueError: For invalid data
        """
        try:
            client = await self.get_client()
            data = await client.get(self.endpoint, object_id=object_id)
            
            if not data:
                logger.debug(f"{self.model_class.__name__} {object_id} not found")
                return None
            
            model = self.model_class.from_api_data(data)
            logger.debug(f"Retrieved {self.model_class.__name__} {object_id}: {model}")
            return model
            
        except APIException:
            logger.error(f"API error retrieving {self.model_class.__name__} {object_id}")
            raise
        except Exception as e:
            logger.error(f"Error retrieving {self.model_class.__name__} {object_id}: {e}")
            raise APIException(f"Failed to retrieve {self.model_class.__name__}: {e}")
    
    async def get_all(self, params: Optional[List[tuple]] = None) -> Tuple[List[T], int]:
        """
        Get all objects with optional query parameters.
        
        Args:
            params: Query parameters as list of (key, value) tuples
            
        Returns:
            Tuple of (list of model instances, total count)
            
        Raises:
            APIException: For API errors
        """
        try:
            client = await self.get_client()
            data = await client.get(self.endpoint, params=params)
            
            if not data:
                logger.debug(f"No {self.model_class.__name__} objects found")
                return [], 0
            
            # Handle API response format: {'count': int, '<endpoint>': [...]}
            items, count = self._extract_items_and_count_from_response(data)
            
            models = [self.model_class.from_api_data(item) for item in items]
            logger.debug(f"Retrieved {len(models)} of {count} {self.model_class.__name__} objects")
            return models, count
            
        except APIException:
            logger.error(f"API error retrieving {self.model_class.__name__} list")
            raise
        except Exception as e:
            logger.error(f"Error retrieving {self.model_class.__name__} list: {e}")
            raise APIException(f"Failed to retrieve {self.model_class.__name__} list: {e}")
    
    async def get_all_items(self, params: Optional[List[tuple]] = None) -> List[T]:
        """
        Get all objects (convenience method that only returns the list).
        
        Args:
            params: Query parameters as list of (key, value) tuples
            
        Returns:
            List of model instances
        """
        items, _ = await self.get_all(params=params)
        return items
    
    async def create(self, model_data: Dict[str, Any]) -> Optional[T]:
        """
        Create new object from data dictionary.
        
        Args:
            model_data: Dictionary of model fields
            
        Returns:
            Created model instance or None
            
        Raises:
            APIException: For API errors
            ValueError: For invalid data
        """
        try:
            client = await self.get_client()
            response = await client.post(self.endpoint, model_data)
            
            if not response:
                logger.warning(f"No response from {self.model_class.__name__} creation")
                return None
            
            model = self.model_class.from_api_data(response)
            logger.debug(f"Created {self.model_class.__name__}: {model}")
            return model
            
        except APIException:
            logger.error(f"API error creating {self.model_class.__name__}")
            raise
        except Exception as e:
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            raise APIException(f"Failed to create {self.model_class.__name__}: {e}")
    
    async def create_from_model(self, model: T) -> Optional[T]:
        """
        Create new object from model instance.
        
        Args:
            model: Model instance to create
            
        Returns:
            Created model instance or None
        """
        return await self.create(model.to_dict(exclude_none=True))
    
    async def update(self, object_id: int, model_data: Dict[str, Any]) -> Optional[T]:
        """
        Update existing object.
        
        Args:
            object_id: ID of object to update
            model_data: Dictionary of fields to update
            
        Returns:
            Updated model instance or None if not found
            
        Raises:
            APIException: For API errors
        """
        try:
            client = await self.get_client()
            response = await client.put(self.endpoint, model_data, object_id=object_id)
            
            if not response:
                logger.debug(f"{self.model_class.__name__} {object_id} not found for update")
                return None
            
            model = self.model_class.from_api_data(response)
            logger.debug(f"Updated {self.model_class.__name__} {object_id}: {model}")
            return model
            
        except APIException:
            logger.error(f"API error updating {self.model_class.__name__} {object_id}")
            raise
        except Exception as e:
            logger.error(f"Error updating {self.model_class.__name__} {object_id}: {e}")
            raise APIException(f"Failed to update {self.model_class.__name__}: {e}")
    
    async def update_from_model(self, model: T) -> Optional[T]:
        """
        Update object from model instance.
        
        Args:
            model: Model instance to update (must have ID)
            
        Returns:
            Updated model instance or None
            
        Raises:
            ValueError: If model has no ID
        """
        if not model.id:
            raise ValueError(f"Cannot update {self.model_class.__name__} without ID")
        
        return await self.update(model.id, model.to_dict(exclude_none=True))
    
    async def patch(self, object_id: int, model_data: Dict[str, Any], use_query_params: bool = False) -> Optional[T]:
        """
        Update existing object with HTTP PATCH.

        Args:
            object_id: ID of object to update
            model_data: Dictionary of fields to update
            use_query_params: If True, send data as query parameters instead of JSON body

        Returns:
            Updated model instance or None if not found

        Raises:
            APIException: For API errors
        """
        try:
            client = await self.get_client()
            response = await client.patch(self.endpoint, model_data, object_id, use_query_params=use_query_params)

            if not response:
                logger.debug(f"{self.model_class.__name__} {object_id} not found for update")
                return None

            model = self.model_class.from_api_data(response)
            logger.debug(f"Updated {self.model_class.__name__} {object_id}: {model}")
            return model

        except APIException:
            logger.error(f"API error updating {self.model_class.__name__} {object_id}")
            raise
        except Exception as e:
            logger.error(f"Error updating {self.model_class.__name__} {object_id}: {e}")
            raise APIException(f"Failed to update {self.model_class.__name__}: {e}")

    
    async def delete(self, object_id: int) -> bool:
        """
        Delete object by ID.
        
        Args:
            object_id: ID of object to delete
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            APIException: For API errors
        """
        try:
            client = await self.get_client()
            success = await client.delete(self.endpoint, object_id=object_id)
            
            if success:
                logger.debug(f"Deleted {self.model_class.__name__} {object_id}")
            else:
                logger.debug(f"{self.model_class.__name__} {object_id} not found for deletion")
            
            return success
            
        except APIException:
            logger.error(f"API error deleting {self.model_class.__name__} {object_id}")
            raise
        except Exception as e:
            logger.error(f"Error deleting {self.model_class.__name__} {object_id}: {e}")
            raise APIException(f"Failed to delete {self.model_class.__name__}: {e}")
    
    
    async def get_by_field(self, field: str, value: Any) -> List[T]:
        """
        Get objects by specific field value.
        
        Args:
            field: Field name to search
            value: Field value to match
            
        Returns:
            List of matching model instances
        """
        params = [(field, str(value))]
        return await self.get_all_items(params=params)
    
    async def count(self, params: Optional[List[tuple]] = None) -> int:
        """
        Get count of objects matching parameters.
        
        Args:
            params: Query parameters
            
        Returns:
            Number of matching objects (from API count field)
        """
        _, count = await self.get_all(params=params)
        return count
    
    def _extract_items_and_count_from_response(self, data: Any) -> Tuple[List[Dict[str, Any]], int]:
        """
        Extract items list and count from API response with optimized parsing.
        
        Expected format: {'count': int, '<endpoint>': [...]}
        Single object format: {'id': 1, 'name': '...'}
        
        Args:
            data: API response data
            
        Returns:
            Tuple of (items list, total count)
        """
        if isinstance(data, list):
            return data, len(data)
        
        if not isinstance(data, dict):
            logger.warning(f"Unexpected response format for {self.model_class.__name__}: {type(data)}")
            return [], 0
        
        # Single pass through the response dict - get count first
        count = data.get('count', 0)
        
        # Priority order for finding items list (most common first)
        field_candidates = [self.endpoint, 'items', 'data', 'results']
        for field_name in field_candidates:
            if field_name in data and isinstance(data[field_name], list):
                return data[field_name], count or len(data[field_name])
        
        # Single object response (check for common identifying fields)
        if any(key in data for key in ['id', 'name', 'abbrev']):
            return [data], 1
        
        return [], count
    
    async def get_items_with_params(self, params: Optional[List[tuple]] = None) -> List[T]:
        """
        Get all items with parameters (alias for get_all_items for compatibility).
        
        Args:
            params: Query parameters as list of (key, value) tuples
            
        Returns:
            List of model instances
        """
        return await self.get_all_items(params=params)
    
    async def create_item(self, model_data: Dict[str, Any]) -> Optional[T]:
        """
        Create item (alias for create for compatibility).
        
        Args:
            model_data: Dictionary of model fields
            
        Returns:
            Created model instance or None
        """
        return await self.create(model_data)
    
    async def update_item_by_field(self, field: str, value: Any, update_data: Dict[str, Any]) -> Optional[T]:
        """
        Update item by field value.
        
        Args:
            field: Field name to search by
            value: Field value to match
            update_data: Data to update
            
        Returns:
            Updated model instance or None if not found
        """
        # First find the item by field
        items = await self.get_by_field(field, value)
        if not items:
            return None
        
        # Update the first matching item
        item = items[0]
        if not item.id:
            return None
            
        return await self.update(item.id, update_data)
    
    async def delete_item_by_field(self, field: str, value: Any) -> bool:
        """
        Delete item by field value.
        
        Args:
            field: Field name to search by
            value: Field value to match
            
        Returns:
            True if deleted, False if not found
        """
        # First find the item by field
        items = await self.get_by_field(field, value)
        if not items:
            return False
        
        # Delete the first matching item
        item = items[0]
        if not item.id:
            return False
            
        return await self.delete(item.id)
    
    async def create_item_in_table(self, table_name: str, item_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create item in a specific table (simplified for custom commands service).
        This is a placeholder - real implementation would need table-specific endpoints.
        
        Args:
            table_name: Name of the table
            item_data: Data to create
            
        Returns:
            Created item data or None
        """
        # For now, use the main endpoint - this would need proper implementation
        # for different tables like 'custom_command_creators'
        try:
            client = await self.get_client()
            # Use table name as endpoint for now
            response = await client.post(table_name, item_data)
            return response
        except Exception as e:
            logger.error(f"Error creating item in table {table_name}: {e}")
            return None
    
    async def get_items_from_table_with_params(self, table_name: str, params: List[tuple]) -> List[Dict[str, Any]]:
        """
        Get items from a specific table with parameters.
        
        Args:
            table_name: Name of the table
            params: Query parameters
            
        Returns:
            List of item dictionaries
        """
        try:
            client = await self.get_client()
            data = await client.get(table_name, params=params)
            
            if not data:
                return []
            
            # Handle response format
            items, _ = self._extract_items_and_count_from_response(data)
            return items
            
        except Exception as e:
            logger.error(f"Error getting items from table {table_name}: {e}")
            return []

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_class.__name__}, endpoint='{self.endpoint}')"