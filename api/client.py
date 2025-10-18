"""
API client for Discord Bot v2.0

Modern aiohttp-based HTTP client for communicating with the database API.
Provides connection pooling, proper error handling, and session management.
"""
import aiohttp
import logging
from typing import Optional, List, Dict, Any, Union
from urllib.parse import urljoin
from contextlib import asynccontextmanager

from config import get_config
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.APIClient')


class APIClient:
    """
    Async HTTP client for SBA database API communication.
    
    Features:
    - Connection pooling with proper session management
    - Bearer token authentication
    - Standardized v3 API usage
    - Comprehensive error handling
    - Debug logging with response truncation
    """
    
    def __init__(self, base_url: Optional[str] = None, api_token: Optional[str] = None):
        """
        Initialize API client with configuration.
        
        Args:
            base_url: Override default database URL from config
            api_token: Override default API token from config
            
        Raises:
            ValueError: If required configuration is missing
        """
        config = get_config()
        self.base_url = base_url or config.db_url
        self.api_token = api_token or config.api_token
        self._session: Optional[aiohttp.ClientSession] = None
        
        if not self.base_url:
            raise ValueError("DB_URL must be configured")
        if not self.api_token:
            raise ValueError("API_TOKEN must be configured")
        
        logger.debug(f"APIClient initialized with base_url: {self.base_url}")
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get headers with authentication and content type."""
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'SBA-Discord-Bot-v2/1.0'
        }
    
    def _build_url(self, endpoint: str, api_version: int = 3, object_id: Optional[int] = None) -> str:
        """
        Build complete API URL from components.
        
        Args:
            endpoint: API endpoint path
            api_version: API version number (default: 3)
            object_id: Optional object ID to append
            
        Returns:
            Complete URL for API request
        """
        # Handle already complete URLs
        if endpoint.startswith(('http://', 'https://')) or '/api/' in endpoint:
            return endpoint
            
        path = f"v{api_version}/{endpoint}"
        if object_id is not None:
            path += f"/{object_id}"
            
        return urljoin(self.base_url.rstrip('/') + '/', path)
    
    def _add_params(self, url: str, params: Optional[List[tuple]] = None) -> str:
        """
        Add query parameters to URL.
        
        Args:
            url: Base URL
            params: List of (key, value) tuples
            
        Returns:
            URL with query parameters appended
        """
        if not params:
            return url
            
        param_str = "&".join(f"{key}={value}" for key, value in params)
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{param_str}"
    
    async def _ensure_session(self) -> None:
        """Ensure aiohttp session exists and is not closed."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,  # Total connection pool size
                limit_per_host=30,  # Connections per host
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True
            )
            
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            
            self._session = aiohttp.ClientSession(
                headers=self.headers,
                connector=connector,
                timeout=timeout
            )
            
            logger.debug("Created new aiohttp session with connection pooling")
    
    async def get(
        self, 
        endpoint: str, 
        object_id: Optional[int] = None, 
        params: Optional[List[tuple]] = None,
        api_version: int = 3,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make GET request to API.
        
        Args:
            endpoint: API endpoint
            object_id: Optional object ID
            params: Query parameters
            api_version: API version (default: 3)
            timeout: Request timeout override
            
        Returns:
            JSON response data or None for 404
            
        Raises:
            APIException: For HTTP errors or network issues
        """
        url = self._build_url(endpoint, api_version, object_id)
        url = self._add_params(url, params)
        
        await self._ensure_session()
        
        try:
            logger.debug(f"GET: {endpoint} id: {object_id} params: {params}")
            
            request_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None
            
            async with self._session.get(url, timeout=request_timeout) as response:
                if response.status == 404:
                    logger.warning(f"Resource not found: {url}")
                    return None
                elif response.status == 401:
                    logger.error(f"Authentication failed for: {url}")
                    raise APIException("Authentication failed - check API token")
                elif response.status == 403:
                    logger.error(f"Access forbidden for: {url}")
                    raise APIException("Access forbidden - insufficient permissions")
                elif response.status >= 400:
                    error_text = await response.text()
                    logger.error(f"API error {response.status}: {url} - {error_text}")
                    raise APIException(f"API request failed with status {response.status}: {error_text}")
                
                data = await response.json()
                
                # Truncate response for logging
                data_str = str(data)
                if len(data_str) > 1200:
                    log_data = data_str[:1200] + "..."
                else:
                    log_data = data_str
                logger.debug(f"Response: {log_data}")
                
                return data
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error for {url}: {e}")
            raise APIException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in GET {url}: {e}")
            raise APIException(f"API call failed: {e}")
    
    async def post(
        self, 
        endpoint: str, 
        data: Dict[str, Any],
        api_version: int = 3,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make POST request to API.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            api_version: API version (default: 3)
            timeout: Request timeout override
            
        Returns:
            JSON response data
            
        Raises:
            APIException: For HTTP errors or network issues
        """
        url = self._build_url(endpoint, api_version)
        
        await self._ensure_session()
        
        try:
            logger.debug(f"POST: {endpoint} data: {data}")
            
            request_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None
            
            async with self._session.post(url, json=data, timeout=request_timeout) as response:
                if response.status == 401:
                    logger.error(f"Authentication failed for POST: {url}")
                    raise APIException("Authentication failed - check API token")
                elif response.status == 403:
                    logger.error(f"Access forbidden for POST: {url}")
                    raise APIException("Access forbidden - insufficient permissions")
                elif response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error(f"POST error {response.status}: {url} - {error_text}")
                    raise APIException(f"POST request failed with status {response.status}: {error_text}")
                
                result = await response.json()
                
                # Truncate response for logging
                result_str = str(result)
                if len(result_str) > 1200:
                    log_result = result_str[:1200] + "..."
                else:
                    log_result = result_str
                logger.debug(f"POST Response: {log_result}")
                
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error for POST {url}: {e}")
            raise APIException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in POST {url}: {e}")
            raise APIException(f"POST failed: {e}")
    
    async def put(
        self, 
        endpoint: str, 
        data: Dict[str, Any],
        object_id: Optional[int] = None,
        api_version: int = 3,
        timeout: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make PUT request to API.
        
        Args:
            endpoint: API endpoint
            data: Request payload
            object_id: Optional object ID
            api_version: API version (default: 3)
            timeout: Request timeout override
            
        Returns:
            JSON response data
            
        Raises:
            APIException: For HTTP errors or network issues
        """
        url = self._build_url(endpoint, api_version, object_id)
        
        await self._ensure_session()
        
        try:
            logger.debug(f"PUT: {endpoint} id: {object_id} data: {data}")
            
            request_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None
            
            async with self._session.put(url, json=data, timeout=request_timeout) as response:
                if response.status == 401:
                    logger.error(f"Authentication failed for PUT: {url}")
                    raise APIException("Authentication failed - check API token")
                elif response.status == 403:
                    logger.error(f"Access forbidden for PUT: {url}")
                    raise APIException("Access forbidden - insufficient permissions")
                elif response.status == 404:
                    logger.warning(f"Resource not found for PUT: {url}")
                    return None
                elif response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error(f"PUT error {response.status}: {url} - {error_text}")
                    raise APIException(f"PUT request failed with status {response.status}: {error_text}")
                
                result = await response.json()
                logger.debug(f"PUT Response: {str(result)[:1200]}{'...' if len(str(result)) > 1200 else ''}")
                return result
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error for PUT {url}: {e}")
            raise APIException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in PUT {url}: {e}")
            raise APIException(f"PUT failed: {e}")
    
    async def patch(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        object_id: Optional[int] = None,
        api_version: int = 3,
        timeout: Optional[int] = None,
        use_query_params: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Make PATCH request to API.

        Args:
            endpoint: API endpoint
            data: Request payload (optional for some PATCH operations)
            object_id: Optional object ID
            api_version: API version (default: 3)
            timeout: Request timeout override
            use_query_params: If True, send data as query parameters instead of JSON body (default: False)

        Returns:
            JSON response data

        Raises:
            APIException: For HTTP errors or network issues
        """
        url = self._build_url(endpoint, api_version, object_id)

        # Add data as query parameters if requested
        if use_query_params and data:
            # Handle None values by converting to empty string
            # The database API's PATCH endpoint treats empty strings as NULL for nullable fields
            # Example: {'il_return': None} → ?il_return= → Database sets il_return to NULL
            params = [(k, '' if v is None else str(v)) for k, v in data.items()]
            url = self._add_params(url, params)

        await self._ensure_session()

        try:
            logger.debug(f"PATCH: {endpoint} id: {object_id} data: {data} use_query_params: {use_query_params}")

            request_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None

            # Use json=data if data is provided and not using query params
            kwargs = {}
            if data is not None and not use_query_params:
                kwargs['json'] = data

            async with self._session.patch(url, timeout=request_timeout, **kwargs) as response:
                if response.status == 401:
                    logger.error(f"Authentication failed for PATCH: {url}")
                    raise APIException("Authentication failed - check API token")
                elif response.status == 403:
                    logger.error(f"Access forbidden for PATCH: {url}")
                    raise APIException("Access forbidden - insufficient permissions")
                elif response.status == 404:
                    logger.warning(f"Resource not found for PATCH: {url}")
                    return None
                elif response.status not in [200, 201]:
                    error_text = await response.text()
                    logger.error(f"PATCH error {response.status}: {url} - {error_text}")
                    raise APIException(f"PATCH request failed with status {response.status}: {error_text}")

                result = await response.json()
                logger.debug(f"PATCH Response: {str(result)[:1200]}{'...' if len(str(result)) > 1200 else ''}")
                return result

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error for PATCH {url}: {e}")
            raise APIException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in PATCH {url}: {e}")
            raise APIException(f"PATCH failed: {e}")
    
    async def delete(
        self, 
        endpoint: str, 
        object_id: Optional[int] = None,
        api_version: int = 3,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Make DELETE request to API.
        
        Args:
            endpoint: API endpoint
            object_id: Optional object ID
            api_version: API version (default: 3)
            timeout: Request timeout override
            
        Returns:
            True if deletion successful, False if resource not found
            
        Raises:
            APIException: For HTTP errors or network issues
        """
        url = self._build_url(endpoint, api_version, object_id)
        
        await self._ensure_session()
        
        try:
            logger.debug(f"DELETE: {endpoint} id: {object_id}")
            
            request_timeout = aiohttp.ClientTimeout(total=timeout) if timeout else None
            
            async with self._session.delete(url, timeout=request_timeout) as response:
                if response.status == 401:
                    logger.error(f"Authentication failed for DELETE: {url}")
                    raise APIException("Authentication failed - check API token")
                elif response.status == 403:
                    logger.error(f"Access forbidden for DELETE: {url}")
                    raise APIException("Access forbidden - insufficient permissions")
                elif response.status == 404:
                    logger.warning(f"Resource not found for DELETE: {url}")
                    return False
                elif response.status not in [200, 204]:
                    error_text = await response.text()
                    logger.error(f"DELETE error {response.status}: {url} - {error_text}")
                    raise APIException(f"DELETE request failed with status {response.status}: {error_text}")
                
                logger.debug(f"DELETE successful: {url}")
                return True
                
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error for DELETE {url}: {e}")
            raise APIException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in DELETE {url}: {e}")
            raise APIException(f"DELETE failed: {e}")
    
    async def close(self) -> None:
        """Close the HTTP session and clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Closed aiohttp session")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.close()


@asynccontextmanager
async def get_api_client() -> APIClient:
    """
    Get API client as async context manager.
    
    Usage:
        async with get_api_client() as client:
            data = await client.get('players')
    """
    client = APIClient()
    try:
        yield client
    finally:
        await client.close()


# Global API client instance for reuse
_global_client: Optional[APIClient] = None


async def get_global_client() -> APIClient:
    """
    Get global API client instance with automatic session management.
    
    Returns:
        Shared APIClient instance
    """
    global _global_client
    if _global_client is None:
        _global_client = APIClient()
    
    await _global_client._ensure_session()
    return _global_client


async def cleanup_global_client() -> None:
    """Clean up global API client. Call during bot shutdown."""
    global _global_client
    if _global_client:
        await _global_client.close()
        _global_client = None