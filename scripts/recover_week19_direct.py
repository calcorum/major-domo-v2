#!/usr/bin/env python3
"""
Week 19 Transaction Recovery Script - Direct ID Version

Uses pre-known player IDs to bypass search, posting directly to production.
"""
import asyncio
import argparse
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.transaction import Transaction
from models.player import Player
from models.team import Team
from services.player_service import player_service
from services.team_service import team_service
from services.transaction_service import transaction_service
from config import get_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/recover_week19.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Week 19 transaction data with known player IDs
WEEK19_TRANSACTIONS = {
    "DEN": [
        {"player_id": 11782, "player_name": "Fernando Cruz", "swar": 0.22, "from": "DENMiL", "to": "DEN"},
        {"player_id": 11566, "player_name": "Brandon Pfaadt", "swar": 0.25, "from": "DEN", "to": "DENMiL"},
    ],
    "CAN": [
        {"player_id": 12127, "player_name": "Masataka Yoshida", "swar": 0.96, "from": "CANMiL", "to": "CAN"},
        {"player_id": 12317, "player_name": "Sam Hilliard", "swar": 0.92, "from": "CAN", "to": "CANMiL"},
        {"player_id": 11984, "player_name": "Jose Herrera", "swar": 0.0, "from": "CANMiL", "to": "CAN"},
        {"player_id": 11723, "player_name": "Dillon Tate", "swar": 0.0, "from": "CAN", "to": "CANMiL"},
    ],
    "WAI": [
        {"player_id": 11812, "player_name": "Giancarlo Stanton", "swar": 0.44, "from": "WAIMiL", "to": "WAI"},
        {"player_id": 12199, "player_name": "Nicholas Castellanos", "swar": 0.35, "from": "WAIMiL", "to": "WAI"},
        {"player_id": 11832, "player_name": "Hayden Birdsong", "swar": 0.21, "from": "WAI", "to": "WAIMiL"},
        {"player_id": 12067, "player_name": "Kyle Nicolas", "swar": 0.18, "from": "WAI", "to": "WAIMiL"},
    ]
}


async def main():
    """Main script execution."""
    parser = argparse.ArgumentParser(description='Recover Week 19 transactions with direct IDs')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, do not post')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation')
    args = parser.parse_args()

    # Set production database
    import os
    os.environ['DB_URL'] = 'https://sba.manticorum.com/api'
    import config as config_module
    config_module._config = None
    config = get_config()

    logger.warning(f"⚠️  PRODUCTION MODE: Using {config.db_url}")
    print(f"\n{'='*70}")
    print(f"⚠️  PRODUCTION DATABASE MODE")
    print(f"Database: {config.db_url}")
    print(f"{'='*70}\n")

    season = 12
    week = 19
    timestamp_base = int(datetime.now(UTC).timestamp())

    print("Loading team and player data from production...\n")

    # Load all teams and players
    teams_cache = {}
    players_cache = {}

    for team_abbrev, moves in WEEK19_TRANSACTIONS.items():
        # Load main team
        try:
            team = await team_service.get_team_by_abbrev(team_abbrev, season)
            if not team:
                logger.error(f"❌ Team not found: {team_abbrev}")
                return 1
            teams_cache[team_abbrev] = team
        except Exception as e:
            logger.error(f"❌ Error loading team {team_abbrev}: {e}")
            return 1

        # Load all teams referenced in moves
        for move in moves:
            for team_key in [move["from"], move["to"]]:
                if team_key not in teams_cache:
                    try:
                        team_obj = await team_service.get_team_by_abbrev(team_key, season)
                        if not team_obj:
                            logger.error(f"❌ Team not found: {team_key}")
                            return 1
                        teams_cache[team_key] = team_obj
                    except Exception as e:
                        logger.error(f"❌ Error loading team {team_key}: {e}")
                        return 1

            # Load player by ID
            player_id = move["player_id"]
            if player_id not in players_cache:
                try:
                    player = await player_service.get_player(player_id)
                    if not player:
                        logger.error(f"❌ Player not found: {player_id} ({move['player_name']})")
                        return 1
                    players_cache[player_id] = player
                except Exception as e:
                    logger.error(f"❌ Error loading player {player_id}: {e}")
                    return 1

    # Show preview
    print("="*70)
    print(f"TRANSACTION RECOVERY PREVIEW - Season {season}, Week {week}")
    print("="*70)
    print(f"\nFound {len(WEEK19_TRANSACTIONS)} teams with {sum(len(moves) for moves in WEEK19_TRANSACTIONS.values())} total moves:\n")

    for idx, (team_abbrev, moves) in enumerate(WEEK19_TRANSACTIONS.items()):
        moveid = f"Season-{season:03d}-Week-{week:02d}-{timestamp_base + idx}"
        team = teams_cache[team_abbrev]

        print("="*70)
        print(f"Team: {team_abbrev} ({team.lname})")
        print(f"Move ID: {moveid}")
        print(f"Week: {week}, Frozen: False, Cancelled: False")
        print()

        for i, move in enumerate(moves, 1):
            player = players_cache[move["player_id"]]
            print(f"{i}. {player.name} ({move['swar']})")
            print(f"   From: {move['from']} → To: {move['to']}")
            print(f"   Player ID: {player.id}")
            print()

    print("="*70)
    print(f"Total: {sum(len(moves) for moves in WEEK19_TRANSACTIONS.values())} moves across {len(WEEK19_TRANSACTIONS)} teams")
    print(f"Status: PROCESSED (frozen=False)")
    print(f"Season: {season}, Week: {week}")
    print("="*70)

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes made to database")
        logger.info("Dry run completed successfully")
        return 0

    # Confirmation
    if not args.yes:
        print("\n🚨 PRODUCTION DATABASE - This will POST to LIVE DATA!")
        print(f"Database: {config.db_url}")
        response = input("Continue with database POST? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Cancelled by user")
            return 0

    # Create and post transactions
    print("\nPosting transactions to production database...")
    results = {}

    for idx, (team_abbrev, moves) in enumerate(WEEK19_TRANSACTIONS.items()):
        moveid = f"Season-{season:03d}-Week-{week:02d}-{timestamp_base + idx}"

        txn_objects = []
        for move in moves:
            player = players_cache[move["player_id"]]
            from_team = teams_cache[move["from"]]
            to_team = teams_cache[move["to"]]

            transaction = Transaction(
                id=0,
                week=week,
                season=season,
                moveid=moveid,
                player=player,
                oldteam=from_team,
                newteam=to_team,
                cancelled=False,
                frozen=False
            )
            txn_objects.append(transaction)

        try:
            logger.info(f"Posting {len(txn_objects)} moves for {team_abbrev}...")
            created = await transaction_service.create_transaction_batch(txn_objects)
            results[team_abbrev] = created
            logger.info(f"✅ Successfully posted {len(created)} moves for {team_abbrev}")
        except Exception as e:
            logger.error(f"❌ Error posting for {team_abbrev}: {e}")
            continue

    # Show results
    print("\n" + "="*70)
    print("✅ RECOVERY COMPLETE")
    print("="*70)

    total_moves = 0
    for team_abbrev, created_txns in results.items():
        print(f"\nTeam {team_abbrev}: {len(created_txns)} moves (moveid: {created_txns[0].moveid if created_txns else 'N/A'})")
        total_moves += len(created_txns)

    print(f"\nTotal: {total_moves} player moves recovered")
    print("\nThese transactions are now in PRODUCTION database with:")
    print(f"  - Week: {week}")
    print("  - Frozen: False (already processed)")
    print("  - Cancelled: False (active)")
    print("\nTeams can view their moves with /mymoves")
    print("="*70)

    logger.info(f"Recovery completed: {total_moves} moves posted to PRODUCTION")
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
