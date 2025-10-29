#!/usr/bin/env python3
"""
Process Week 19 Transactions
Moves all players to their new teams for week 19 transactions.
"""
import os
import sys
import asyncio
import logging
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logging import get_contextual_logger
from services.api_client import APIClient

# Configure logging
logger = get_contextual_logger(f'{__name__}')

# API Configuration
API_BASE_URL = "https://api.sba.manticorum.com"
API_TOKEN = os.getenv("API_TOKEN", "")

# Transaction data (fetched from API)
TRANSACTIONS = [
    {"player_id": 11782, "player_name": "Fernando Cruz", "old_team_id": 504, "new_team_id": 502},
    {"player_id": 11566, "player_name": "Brandon Pfaadt", "old_team_id": 502, "new_team_id": 504},
    {"player_id": 12127, "player_name": "Masataka Yoshida", "old_team_id": 531, "new_team_id": 529},
    {"player_id": 12317, "player_name": "Sam Hilliard", "old_team_id": 529, "new_team_id": 531},
    {"player_id": 11984, "player_name": "Jose Herrera", "old_team_id": 531, "new_team_id": 529},
    {"player_id": 11723, "player_name": "Dillon Tate", "old_team_id": 529, "new_team_id": 531},
    {"player_id": 11812, "player_name": "Giancarlo Stanton", "old_team_id": 528, "new_team_id": 526},
    {"player_id": 12199, "player_name": "Nicholas Castellanos", "old_team_id": 528, "new_team_id": 526},
    {"player_id": 11832, "player_name": "Hayden Birdsong", "old_team_id": 526, "new_team_id": 528},
    {"player_id": 11890, "player_name": "Andrew McCutchen", "old_team_id": 526, "new_team_id": 528},
]


async def update_player_team(client: APIClient, player_id: int, new_team_id: int, player_name: str) -> bool:
    """
    Update a player's team via PATCH request.

    Args:
        client: API client instance
        player_id: Player ID to update
        new_team_id: New team ID
        player_name: Player name (for logging)

    Returns:
        True if successful, False otherwise
    """
    try:
        endpoint = f"/players/{player_id}"
        params = [("team_id", str(new_team_id))]

        logger.info(f"Updating {player_name} (ID: {player_id}) to team {new_team_id}")

        response = await client.patch(endpoint, params=params)

        logger.info(f"✓ Successfully updated {player_name}")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to update {player_name}: {e}")
        return False


async def process_all_transactions():
    """Process all week 19 transactions."""
    logger.info("=" * 70)
    logger.info("PROCESSING WEEK 19 TRANSACTIONS")
    logger.info("=" * 70)

    if not API_TOKEN:
        logger.error("API_TOKEN environment variable not set!")
        return False

    # Initialize API client
    client = APIClient(base_url=API_BASE_URL, token=API_TOKEN)

    success_count = 0
    failure_count = 0

    # Process each transaction
    for i, transaction in enumerate(TRANSACTIONS, 1):
        logger.info(f"\n[{i}/{len(TRANSACTIONS)}] Processing transaction:")
        logger.info(f"  Player: {transaction['player_name']}")
        logger.info(f"  Old Team ID: {transaction['old_team_id']}")
        logger.info(f"  New Team ID: {transaction['new_team_id']}")

        success = await update_player_team(
            client=client,
            player_id=transaction["player_id"],
            new_team_id=transaction["new_team_id"],
            player_name=transaction["player_name"]
        )

        if success:
            success_count += 1
        else:
            failure_count += 1

    # Close the client session
    await client.close()

    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("TRANSACTION PROCESSING COMPLETE")
    logger.info("=" * 70)
    logger.info(f"✓ Successful: {success_count}/{len(TRANSACTIONS)}")
    logger.info(f"✗ Failed: {failure_count}/{len(TRANSACTIONS)}")
    logger.info("=" * 70)

    return failure_count == 0


async def main():
    """Main entry point."""
    success = await process_all_transactions()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
