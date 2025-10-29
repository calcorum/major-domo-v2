#!/usr/bin/env python3
"""
Week 19 Transaction Recovery Script

Recovers lost Week 19 transactions that were posted to Discord but never
saved to the database due to the missing database POST bug in /dropadd.

Usage:
    python scripts/recover_week19_transactions.py --dry-run  # Test only
    python scripts/recover_week19_transactions.py            # Execute with confirmation
    python scripts/recover_week19_transactions.py --yes      # Execute without confirmation
"""
import argparse
import asyncio
import logging
import re
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Add parent directory to path for imports
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


# Team name to abbreviation mapping
TEAM_MAPPING = {
    "Zephyr": "DEN",
    "Cavalry": "CAN",
    "Whale Sharks": "WAI"
}


class TransactionMove:
    """Represents a single player move from the markdown file."""

    def __init__(self, player_name: str, swar: float, from_team: str, to_team: str):
        self.player_name = player_name
        self.swar = swar
        self.from_team = from_team
        self.to_team = to_team
        self.player: Optional[Player] = None
        self.from_team_obj: Optional[Team] = None
        self.to_team_obj: Optional[Team] = None

    def __repr__(self):
        return f"{self.player_name} ({self.swar}): {self.from_team} → {self.to_team}"


class TeamTransaction:
    """Represents all moves for a single team."""

    def __init__(self, team_name: str, team_abbrev: str):
        self.team_name = team_name
        self.team_abbrev = team_abbrev
        self.moves: List[TransactionMove] = []
        self.team_obj: Optional[Team] = None

    def add_move(self, move: TransactionMove):
        self.moves.append(move)

    def __repr__(self):
        return f"{self.team_abbrev} ({self.team_name}): {len(self.moves)} moves"


def parse_transaction_file(file_path: str) -> List[TeamTransaction]:
    """
    Parse the markdown file and extract all transactions.

    Args:
        file_path: Path to the markdown file

    Returns:
        List of TeamTransaction objects
    """
    logger.info(f"Parsing: {file_path}")

    with open(file_path, 'r') as f:
        content = f.read()

    transactions = []
    current_team = None

    # Pattern to match player moves: "PlayerName (sWAR) from OLDTEAM to NEWTEAM"
    move_pattern = re.compile(r'^(.+?)\s*\((\d+\.\d+)\)\s+from\s+(\w+)\s+to\s+(\w+)\s*$', re.MULTILINE)

    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        line = line.strip()

        # New transaction section
        if line.startswith('# Week 19 Transaction'):
            current_team = None
            continue

        # Team name line
        if line and current_team is None and line in TEAM_MAPPING:
            team_abbrev = TEAM_MAPPING[line]
            current_team = TeamTransaction(line, team_abbrev)
            transactions.append(current_team)
            logger.debug(f"Found team: {line} ({team_abbrev})")
            continue

        # Skip headers
        if line == 'Player Moves':
            continue

        # Parse player move
        if current_team and line:
            match = move_pattern.match(line)
            if match:
                player_name = match.group(1).strip()
                swar = float(match.group(2))
                from_team = match.group(3)
                to_team = match.group(4)

                move = TransactionMove(player_name, swar, from_team, to_team)
                current_team.add_move(move)
                logger.debug(f"  Parsed move: {move}")

    logger.info(f"Parsed {len(transactions)} teams with {sum(len(t.moves) for t in transactions)} total moves")
    return transactions


async def lookup_players_and_teams(transactions: List[TeamTransaction], season: int) -> bool:
    """
    Lookup all players and teams via API services.

    Args:
        transactions: List of TeamTransaction objects
        season: Season number

    Returns:
        True if all lookups successful, False if any failures
    """
    logger.info("Looking up players and teams from database...")

    all_success = True

    for team_txn in transactions:
        # Lookup main team
        try:
            team_obj = await team_service.get_team_by_abbrev(team_txn.team_abbrev, season)
            if not team_obj:
                logger.error(f"❌ Team not found: {team_txn.team_abbrev}")
                all_success = False
                continue
            team_txn.team_obj = team_obj
            logger.debug(f"✓ Found team: {team_txn.team_abbrev} (ID: {team_obj.id})")
        except Exception as e:
            logger.error(f"❌ Error looking up team {team_txn.team_abbrev}: {e}")
            all_success = False
            continue

        # Lookup each player and their teams
        for move in team_txn.moves:
            # Lookup player
            try:
                players = await player_service.search_players(move.player_name, limit=5, season=season)
                if not players:
                    logger.warning(f"⚠️  Player not found: {move.player_name}")
                    all_success = False
                    continue

                # Try exact match first
                player = None
                for p in players:
                    if p.name.lower() == move.player_name.lower():
                        player = p
                        break

                if not player:
                    player = players[0]  # Use first match
                    logger.warning(f"⚠️  Using fuzzy match for '{move.player_name}': {player.name}")

                move.player = player
                logger.debug(f"  ✓ Found player: {player.name} (ID: {player.id})")

            except Exception as e:
                logger.error(f"❌ Error looking up player {move.player_name}: {e}")
                all_success = False
                continue

            # Lookup from team
            try:
                from_team = await team_service.get_team_by_abbrev(move.from_team, season)
                if not from_team:
                    logger.error(f"❌ From team not found: {move.from_team}")
                    all_success = False
                    continue
                move.from_team_obj = from_team
                logger.debug(f"    From: {from_team.abbrev} (ID: {from_team.id})")
            except Exception as e:
                logger.error(f"❌ Error looking up from team {move.from_team}: {e}")
                all_success = False
                continue

            # Lookup to team
            try:
                to_team = await team_service.get_team_by_abbrev(move.to_team, season)
                if not to_team:
                    logger.error(f"❌ To team not found: {move.to_team}")
                    all_success = False
                    continue
                move.to_team_obj = to_team
                logger.debug(f"    To: {to_team.abbrev} (ID: {to_team.id})")
            except Exception as e:
                logger.error(f"❌ Error looking up to team {move.to_team}: {e}")
                all_success = False
                continue

    return all_success


def show_preview(transactions: List[TeamTransaction], season: int, week: int):
    """
    Display a preview of all transactions that will be created.

    Args:
        transactions: List of TeamTransaction objects
        season: Season number
        week: Week number
    """
    print("\n" + "=" * 70)
    print(f"TRANSACTION RECOVERY PREVIEW - Season {season}, Week {week}")
    print("=" * 70)
    print(f"\nFound {len(transactions)} teams with {sum(len(t.moves) for t in transactions)} total moves:\n")

    timestamp_base = int(datetime.now(UTC).timestamp())

    for idx, team_txn in enumerate(transactions):
        moveid = f"Season-{season:03d}-Week-{week:02d}-{timestamp_base + idx}"

        print("=" * 70)
        print(f"Team: {team_txn.team_abbrev} ({team_txn.team_name})")
        print(f"Move ID: {moveid}")
        print(f"Week: {week}, Frozen: False, Cancelled: False")
        print()

        for i, move in enumerate(team_txn.moves, 1):
            print(f"{i}. {move.player_name} ({move.swar})")
            print(f"   From: {move.from_team} → To: {move.to_team}")
            if move.player:
                print(f"   Player ID: {move.player.id}")
            print()

    print("=" * 70)
    print(f"Total: {sum(len(t.moves) for t in transactions)} moves across {len(transactions)} teams")
    print(f"Status: PROCESSED (frozen=False)")
    print(f"Season: {season}, Week: {week}")
    print("=" * 70)


async def create_and_post_transactions(
    transactions: List[TeamTransaction],
    season: int,
    week: int
) -> Dict[str, List[Transaction]]:
    """
    Create Transaction objects and POST to database.

    Args:
        transactions: List of TeamTransaction objects
        season: Season number
        week: Week number

    Returns:
        Dictionary mapping team abbreviation to list of created Transaction objects
    """
    logger.info("Creating and posting transactions to database...")

    config = get_config()
    fa_team = Team(
        id=config.free_agent_team_id,
        abbrev="FA",
        sname="Free Agents",
        lname="Free Agency",
        season=season
    )

    results = {}
    timestamp_base = int(datetime.now(UTC).timestamp())

    for idx, team_txn in enumerate(transactions):
        moveid = f"Season-{season:03d}-Week-{week:02d}-{timestamp_base + idx}"

        # Create Transaction objects for this team
        txn_objects = []
        for move in team_txn.moves:
            if not move.player or not move.from_team_obj or not move.to_team_obj:
                logger.warning(f"Skipping move due to missing data: {move}")
                continue

            transaction = Transaction(
                id=0,  # Will be assigned by API
                week=week,
                season=season,
                moveid=moveid,
                player=move.player,
                oldteam=move.from_team_obj,
                newteam=move.to_team_obj,
                cancelled=False,
                frozen=False  # Already processed
            )
            txn_objects.append(transaction)

        if not txn_objects:
            logger.warning(f"No valid transactions for {team_txn.team_abbrev}, skipping")
            continue

        # POST to database
        try:
            logger.info(f"Posting {len(txn_objects)} moves for {team_txn.team_abbrev}...")
            created = await transaction_service.create_transaction_batch(txn_objects)
            results[team_txn.team_abbrev] = created
            logger.info(f"✅ Successfully posted {len(created)} moves for {team_txn.team_abbrev}")
        except Exception as e:
            logger.error(f"❌ Error posting transactions for {team_txn.team_abbrev}: {e}")
            continue

    return results


async def main():
    """Main script execution."""
    parser = argparse.ArgumentParser(description='Recover Week 19 transactions')
    parser.add_argument('--dry-run', action='store_true', help='Parse and validate only, do not post to database')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--prod', action='store_true', help='Send to PRODUCTION database (api.sba.manticorum.com)')
    parser.add_argument('--season', type=int, default=12, help='Season number (default: 12)')
    parser.add_argument('--week', type=int, default=19, help='Week number (default: 19)')
    args = parser.parse_args()

    # Get current database configuration
    config = get_config()
    current_db = config.db_url

    if args.prod:
        # Override to production database
        import os
        os.environ['DB_URL'] = 'https://api.sba.manticorum.com/'
        # Clear cached config and reload
        import config as config_module
        config_module._config = None
        config = get_config()
        logger.warning(f"⚠️  PRODUCTION MODE: Using {config.db_url}")
        print(f"\n{'='*70}")
        print(f"⚠️  PRODUCTION DATABASE MODE")
        print(f"Database: {config.db_url}")
        print(f"{'='*70}\n")
    else:
        logger.info(f"Using database: {current_db}")
        print(f"\nDatabase: {current_db}\n")

    # File path
    file_path = Path(__file__).parent.parent / '.claude' / 'week-19-transactions.md'

    if not file_path.exists():
        logger.error(f"❌ Input file not found: {file_path}")
        return 1

    # Parse the file
    try:
        transactions = parse_transaction_file(str(file_path))
    except Exception as e:
        logger.error(f"❌ Error parsing file: {e}")
        return 1

    if not transactions:
        logger.error("❌ No transactions found in file")
        return 1

    # Lookup players and teams
    try:
        success = await lookup_players_and_teams(transactions, args.season)
        if not success:
            logger.error("❌ Some lookups failed. Review errors above.")
            return 1
    except Exception as e:
        logger.error(f"❌ Error during lookups: {e}")
        return 1

    # Show preview
    show_preview(transactions, args.season, args.week)

    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes made to database")
        logger.info("Dry run completed successfully")
        return 0

    # Confirmation
    if not args.yes:
        if args.prod:
            print("\n🚨 PRODUCTION DATABASE - This will POST to LIVE DATA!")
            print(f"Database: {config.db_url}")
        else:
            print(f"\n⚠️  This will POST these transactions to: {config.db_url}")
        response = input("Continue with database POST? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Cancelled by user")
            logger.info("Cancelled by user")
            return 0

    # Create and post transactions
    try:
        results = await create_and_post_transactions(transactions, args.season, args.week)
    except Exception as e:
        logger.error(f"❌ Error posting transactions: {e}")
        return 1

    # Show results
    print("\n" + "=" * 70)
    print("✅ RECOVERY COMPLETE")
    print("=" * 70)

    total_moves = 0
    for team_abbrev, created_txns in results.items():
        print(f"\nTeam {team_abbrev}: {len(created_txns)} moves (moveid: {created_txns[0].moveid if created_txns else 'N/A'})")
        total_moves += len(created_txns)

    print(f"\nTotal: {total_moves} player moves recovered")
    print("\nThese transactions are now in the database with:")
    print(f"  - Week: {args.week}")
    print("  - Frozen: False (already processed)")
    print("  - Cancelled: False (active)")
    print("\nTeams can view their moves with /mymoves")
    print("=" * 70)

    logger.info(f"Recovery completed: {total_moves} moves posted to database")
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
