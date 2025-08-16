#!/usr/bin/env python3
"""
Real Data Testing Script

Safely test services with real cloud database data (READ-ONLY operations only).
Uses structured logging to demonstrate contextual information with real data.
"""
import asyncio
import os
import sys
from pathlib import Path

# Load testing environment
os.environ.setdefault('BOT_TOKEN', 'dummy_token')
os.environ.setdefault('GUILD_ID', '123456789')
os.environ.setdefault('API_TOKEN', 'Tp3aO3jhYve5NJF1IqOmJTmk')
os.environ.setdefault('DB_URL', 'https://sbadev.manticorum.com/api')
os.environ.setdefault('LOG_LEVEL', 'DEBUG')
os.environ.setdefault('ENVIRONMENT', 'testing')
os.environ.setdefault('TESTING', 'true')

from services.player_service import player_service
from utils.logging import get_contextual_logger, set_discord_context
from api.client import cleanup_global_client
from constants import SBA_CURRENT_SEASON

logger = get_contextual_logger('test_real_data')


class MockInteraction:
    """Mock Discord interaction for testing context."""
    def __init__(self, user_id="999888777", guild_id="111222333"):
        self.user = MockUser(user_id)
        self.guild = MockGuild(guild_id)
        self.channel = MockChannel()

class MockUser:
    def __init__(self, user_id):
        self.id = int(user_id)

class MockGuild:
    def __init__(self, guild_id):
        self.id = int(guild_id)
        self.name = "SBA Test Guild"

class MockChannel:
    def __init__(self):
        self.id = 444555666


import pytest

@pytest.mark.asyncio
async def test_player_search():
    """Test player search with real data."""
    print("🔍 Testing Player Search...")
    
    # Set up logging context
    mock_interaction = MockInteraction()
    set_discord_context(
        interaction=mock_interaction,
        command="/player",
        test_type="player_search"
    )
    
    trace_id = logger.start_operation("real_data_test_player_search")
    
    try:
        # Test 1: Search for a common name (should find multiple)
        logger.info("Testing search for common player name")
        players = await player_service.get_players_by_name("Smith", SBA_CURRENT_SEASON)
        logger.info("Common name search completed", 
                   search_term="Smith", 
                   results_found=len(players))
        
        if players:
            print(f"  ✅ Found {len(players)} players with 'Smith' in name")
            for i, player in enumerate(players[:3]):  # Show first 3
                print(f"     {i+1}. {player.name} ({player.primary_position}) - Season {player.season}")
        else:
            print("  ⚠️  No players found with 'Smith' - unusual for baseball!")
        
        # Test 2: Search for specific player (exact match)
        logger.info("Testing search for specific player")
        players = await player_service.get_players_by_name("Mike Trout", SBA_CURRENT_SEASON)
        logger.info("Specific player search completed",
                   search_term="Mike Trout",
                   results_found=len(players))
        
        if players:
            player = players[0]
            print(f"  ✅ Found Mike Trout: {player.name} (WARA: {player.wara})")
            
            # Get with team info
            logger.debug("Testing get_player_with_team", player_id=player.id)
            player_with_team = await player_service.get_player_with_team(player.id)
            if player_with_team and hasattr(player_with_team, 'team') and player_with_team.team:
                print(f"     Team: {player_with_team.team.abbrev} - {player_with_team.team.sname}")
                logger.info("Player with team retrieved successfully",
                           player_name=player_with_team.name,
                           team_abbrev=player_with_team.team.abbrev)
            else:
                print("     Team: Not found or no team association")
                logger.warning("Player team information not available")
        else:
            print("  ❌ Mike Trout not found - checking if database has current players")
        
        # Test 3: Get player by ID (if we found any players)
        if players:
            test_player = players[0]
            logger.info("Testing get_by_id", player_id=test_player.id)
            player_by_id = await player_service.get_by_id(test_player.id)
            
            if player_by_id:
                print(f"  ✅ Retrieved by ID: {player_by_id.name} (ID: {player_by_id.id})")
                logger.info("Get by ID successful", 
                           player_id=player_by_id.id,
                           player_name=player_by_id.name)
            else:
                print(f"  ❌ Failed to retrieve player ID {test_player.id}")
                logger.error("Get by ID failed", player_id=test_player.id)
        
        return True
        
    except Exception as e:
        logger.error("Player search test failed", error=e)
        print(f"  ❌ Error: {e}")
        return False


@pytest.mark.asyncio
async def test_player_service_methods():
    """Test various player service methods."""
    print("🔧 Testing Player Service Methods...")
    
    set_discord_context(
        command="/test-service-methods",
        test_type="service_methods"
    )
    
    trace_id = logger.start_operation("test_service_methods")
    
    try:
        # Test get_all with limit (need to include season)
        from constants import SBA_CURRENT_SEASON
        logger.info("Testing get_all with limit")
        players, total_count = await player_service.get_all(params=[
            ('season', str(SBA_CURRENT_SEASON)),
            ('limit', '10')
        ])
        
        print(f"  ✅ Retrieved {len(players)} of {total_count} total players")
        logger.info("Get all players completed",
                   retrieved_count=len(players),
                   total_count=total_count,
                   limit=10,
                   season=SBA_CURRENT_SEASON)
        
        if players:
            print("     Sample players:")
            for i, player in enumerate(players[:3]):
                print(f"     {i+1}. {player.name} ({player.primary_position}) - WARA: {player.wara}")
        
        # Test search by position (if we have players)
        if players:
            test_position = players[0].primary_position
            logger.info("Testing position search", position=test_position)
            position_players = await player_service.get_players_by_position(test_position, SBA_CURRENT_SEASON)
            
            print(f"  ✅ Found {len(position_players)} players at position {test_position}")
            logger.info("Position search completed",
                       position=test_position,
                       players_found=len(position_players))
        
        return True
        
    except Exception as e:
        logger.error("Service methods test failed", error=e)
        print(f"  ❌ Error: {e}")
        return False


@pytest.mark.asyncio
async def test_api_connectivity():
    """Test basic API connectivity."""
    print("🌐 Testing API Connectivity...")
    
    set_discord_context(
        command="/test-api",
        test_type="connectivity"
    )
    
    trace_id = logger.start_operation("test_api_connectivity")
    
    try:
        from api.client import get_global_client
        
        logger.info("Testing basic API connection")
        client = await get_global_client()
        
        # Test current endpoint (usually lightweight)
        logger.debug("Making API call to current endpoint")
        current_data = await client.get('current')
        
        if current_data:
            print("  ✅ API connection successful")
            logger.info("API connectivity test passed", 
                       endpoint='current',
                       response_received=True)
            
            # Show some basic info about the league
            if isinstance(current_data, dict):
                season = current_data.get('season', 'Unknown')
                week = current_data.get('week', 'Unknown')
                print(f"     Current season: {season}, Week: {week}")
                logger.info("Current league info retrieved",
                           season=season,
                           week=week)
        else:
            print("  ⚠️  API connected but returned no data")
            logger.warning("API connection successful but no data returned")
        
        return True
        
    except Exception as e:
        logger.error("API connectivity test failed", error=e)
        print(f"  ❌ API Error: {e}")
        return False


async def main():
    """Run all real data tests."""
    print("🧪 Testing Discord Bot v2.0 with Real Cloud Database")
    print("=" * 60)
    print(f"🌐 API URL: https://sbadev.manticorum.com/api")
    print(f"📝 Logging: Check logs/discord_bot_v2.json for structured output")
    print()
    
    # Initialize logging
    import logging
    from logging.handlers import RotatingFileHandler
    from utils.logging import JSONFormatter
    
    os.makedirs('logs', exist_ok=True)
    
    # Set up logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # JSON file handler for structured logging
    json_handler = RotatingFileHandler('logs/discord_bot_v2.json', maxBytes=2*1024*1024, backupCount=3)
    json_handler.setFormatter(JSONFormatter())
    
    root_logger.addHandler(console_handler)
    root_logger.addHandler(json_handler)
    
    # Run tests
    tests = [
        ("API Connectivity", test_api_connectivity),
        ("Player Search", test_player_search),
        ("Player Service Methods", test_player_service_methods),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n📋 {test_name}")
            print("-" * 40)
            success = await test_func()
            if success:
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} CRASHED: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! Services work with real data!")
    else:
        print("⚠️  Some tests failed. Check logs for details.")
    
    print(f"\n📁 Structured logs available at: logs/discord_bot_v2.json")
    print("   Use jq to query: jq '.context.test_type' logs/discord_bot_v2.json")
    
    # Cleanup
    await cleanup_global_client()
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n🛑 Testing interrupted by user")
        sys.exit(1)