"""
Redis caching utilities for Discord Bot v2.0

Provides optional Redis caching functionality for API responses.
"""
import logging
from typing import Optional
import json

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

from config import get_config

logger = logging.getLogger(f'{__name__}.CacheUtils')

# Global Redis client instance
_redis_client: Optional['redis.Redis'] = None


async def get_redis_client() -> Optional['redis.Redis']:
    """
    Get Redis client if configured and available.
    
    Returns:
        Redis client instance or None if Redis is not configured/available
    """
    global _redis_client
    
    if not REDIS_AVAILABLE:
        logger.debug("Redis library not available - caching disabled")
        return None
        
    if _redis_client is not None:
        return _redis_client
        
    config = get_config()
    
    if not config.redis_url:
        logger.debug("No Redis URL configured - caching disabled")
        return None
        
    try:
        logger.info(f"Connecting to Redis at {config.redis_url}")
        _redis_client = redis.from_url(config.redis_url)
        
        # Test connection
        await _redis_client.ping()
        logger.info("Redis connection established successfully")
        return _redis_client
        
    except Exception as e:
        logger.warning(f"Redis connection failed: {e} - caching disabled")
        _redis_client = None
        return None


async def close_redis_client() -> None:
    """Close the Redis client connection."""
    global _redis_client
    
    if _redis_client:
        try:
            await _redis_client.aclose()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")
        finally:
            _redis_client = None


class CacheManager:
    """
    Manager for Redis caching operations with fallback to no-cache behavior.
    """
    
    def __init__(self, redis_client: Optional['redis.Redis'] = None, ttl: int = 300):
        """
        Initialize cache manager.
        
        Args:
            redis_client: Optional Redis client (will auto-connect if None)
            ttl: Time-to-live for cached items in seconds
        """
        self.redis_client = redis_client
        self.ttl = ttl
        
    async def _get_client(self) -> Optional['redis.Redis']:
        """Get Redis client, initializing if needed."""
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client
        
    def cache_key(self, prefix: str, identifier: str) -> str:
        """
        Generate standardized cache key.
        
        Args:
            prefix: Cache key prefix (e.g., 'sba', 'player')  
            identifier: Unique identifier for this cache entry
            
        Returns:
            Formatted cache key
        """
        return f"{prefix}:{identifier}"
        
    async def get(self, key: str) -> Optional[dict]:
        """
        Get cached data.
        
        Args:
            key: Cache key
            
        Returns:
            Cached data as dict or None if not found/error
        """
        client = await self._get_client()
        if not client:
            return None
            
        try:
            cached = await client.get(key)
            if cached:
                data = json.loads(cached)
                logger.debug(f"Cache hit: {key}")
                return data
        except Exception as e:
            logger.warning(f"Cache read error for {key}: {e}")
            
        logger.debug(f"Cache miss: {key}")
        return None
        
    async def set(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """
        Set cached data.
        
        Args:
            key: Cache key
            data: Data to cache (must be JSON serializable)
            ttl: Time-to-live override (uses default if None)
        """
        client = await self._get_client()
        if not client:
            return
            
        try:
            cache_ttl = ttl or self.ttl
            serialized = json.dumps(data)
            await client.setex(key, cache_ttl, serialized)
            logger.debug(f"Cached: {key} (TTL: {cache_ttl}s)")
        except Exception as e:
            logger.warning(f"Cache write error for {key}: {e}")
            
    async def delete(self, key: str) -> None:
        """
        Delete cached data.
        
        Args:
            key: Cache key to delete
        """
        client = await self._get_client()
        if not client:
            return
            
        try:
            await client.delete(key)
            logger.debug(f"Cache deleted: {key}")
        except Exception as e:
            logger.warning(f"Cache delete error for {key}: {e}")
            
    async def clear_prefix(self, prefix: str) -> int:
        """
        Clear all cache keys with given prefix.
        
        Args:
            prefix: Cache key prefix to clear
            
        Returns:
            Number of keys deleted
        """
        client = await self._get_client()
        if not client:
            return 0
            
        try:
            pattern = f"{prefix}:*"
            keys = await client.keys(pattern)
            if keys:
                deleted = await client.delete(*keys)
                logger.info(f"Cleared {deleted} cache keys with prefix '{prefix}'")
                return deleted
        except Exception as e:
            logger.warning(f"Cache clear error for prefix {prefix}: {e}")
            
        return 0