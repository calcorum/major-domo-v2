"""
API client layer for Discord Bot v2.0

HTTP client for communicating with the database API.
"""
from .client import APIClient, get_api_client, get_global_client, cleanup_global_client

__all__ = ['APIClient', 'get_api_client', 'get_global_client', 'cleanup_global_client']