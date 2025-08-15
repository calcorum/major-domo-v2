"""
Base service class for Discord Bot v2.0

Provides common CRUD operations and error handling for all data services.
"""
import logging
from typing import Optional, Type, TypeVar, Generic, Dict, Any, List, Tuple

from api.client import get_global_client, APIClient
from models.base import SBABaseModel
from exceptions import APIException

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
                 client: Optional[APIClient] = None):
        """
        Initialize base service.
        
        Args:
            model_class: Pydantic model class for this service
            endpoint: API endpoint path (e.g., 'players', 'teams')
            client: Optional API client override (uses global client by default)
        """
        self.model_class = model_class
        self.endpoint = endpoint
        self._client = client
        self._cached_client: Optional[APIClient] = None
        
        logger.debug(f"Initialized {self.__class__.__name__} for {model_class.__name__} at endpoint '{endpoint}'")
    
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
    
    async def search(self, query: str, **kwargs) -> List[T]:
        """
        Search for objects by query string.
        
        Args:
            query: Search query
            **kwargs: Additional search parameters
            
        Returns:
            List of matching model instances
        """
        params = [('q', query)]
        params.extend(kwargs.items())
        
        return await self.get_all_items(params=params)
    
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
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.model_class.__name__}, endpoint='{self.endpoint}')"