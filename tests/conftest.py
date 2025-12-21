"""
Pytest configuration and fixtures for Discord Bot v2.0 tests.

This file provides test isolation and shared fixtures.
"""
import asyncio
import os
import pytest

# Ensure environment is set up before any imports happen
# This is critical for tests that check GUILD_ID
os.environ.setdefault("GUILD_ID", "669356687294988350")
os.environ.setdefault("TESTING", "true")


@pytest.fixture(autouse=True)
def reset_singleton_state():
    """
    Reset any singleton/global state between tests.

    This prevents test pollution from global state in services.
    """
    # Import after test function starts to ensure clean state
    yield  # Run test

    # Cleanup after test
    # Reset transaction builder caches
    try:
        from services.transaction_builder import _transaction_builders
        _transaction_builders.clear()
    except ImportError:
        pass

    try:
        from services.trade_builder import _trade_builders, _team_to_trade_key
        _trade_builders.clear()
        _team_to_trade_key.clear()
    except ImportError:
        pass

    # Reset config singleton to ensure clean state
    try:
        from config import _config
        import config as cfg
        cfg._config = None
    except (ImportError, AttributeError):
        pass


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    return asyncio.DefaultEventLoopPolicy()
