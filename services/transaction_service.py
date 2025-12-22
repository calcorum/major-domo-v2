"""
Transaction service for Discord Bot v2.0

Handles transaction CRUD operations and business logic.
"""
import logging
from typing import Optional, List, Tuple
from datetime import datetime, UTC

from services.base_service import BaseService
from models.transaction import Transaction, RosterValidation
from models.roster import TeamRoster
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.TransactionService')


class TransactionService(BaseService[Transaction]):
    """Service for transaction operations."""
    
    def __init__(self):
        """Initialize transaction service."""
        super().__init__(
            model_class=Transaction,
            endpoint='transactions'
        )
        logger.debug("TransactionService initialized")
    
    async def get_team_transactions(
        self, 
        team_abbrev: str, 
        season: int,
        cancelled: Optional[bool] = None,
        frozen: Optional[bool] = None,
        week_start: Optional[int] = None,
        week_end: Optional[int] = None
    ) -> List[Transaction]:
        """
        Get transactions for a specific team.
        
        Args:
            team_abbrev: Team abbreviation
            season: Season number
            cancelled: Filter by cancelled status
            frozen: Filter by frozen status
            week_start: Start week for filtering
            week_end: End week for filtering
            
        Returns:
            List of matching transactions
        """
        try:
            params = [
                ('season', str(season)),
                ('team_abbrev', team_abbrev)
            ]
            
            if cancelled is not None:
                params.append(('cancelled', str(cancelled).lower()))
            if frozen is not None:
                params.append(('frozen', str(frozen).lower()))
            if week_start is not None:
                params.append(('week_start', str(week_start)))
            if week_end is not None:
                params.append(('week_end', str(week_end)))
            
            transactions = await self.get_all_items(params=params)
            
            # Sort by week, then by moveid
            transactions.sort(key=lambda t: (t.week, t.moveid))
            
            logger.debug(f"Retrieved {len(transactions)} transactions for {team_abbrev}")
            return transactions
            
        except Exception as e:
            logger.error(f"Error getting transactions for team {team_abbrev}: {e}")
            raise APIException(f"Failed to retrieve transactions: {e}")
    
    async def get_pending_transactions(self, team_abbrev: str, season: int) -> List[Transaction]:
        """Get pending (future) transactions for a team."""
        try:
            # Get current week to filter future transactions
            current_data = await self.get_client()
            current_response = await current_data.get('current')
            current_week = current_response.get('week', 0) if current_response else 0

            # Get transactions from current week onward
            return await self.get_team_transactions(
                team_abbrev,
                season,
                cancelled=False,
                frozen=False,
                week_start=current_week
            )
        except Exception as e:
            logger.warning(f"Could not get current week, returning all non-cancelled/non-frozen transactions: {e}")
            # Fallback to all non-cancelled/non-frozen if we can't get current week
            return await self.get_team_transactions(
                team_abbrev,
                season,
                cancelled=False,
                frozen=False
            )
    
    async def get_frozen_transactions(self, team_abbrev: str, season: int) -> List[Transaction]:
        """Get frozen (scheduled for processing) transactions for a team."""
        return await self.get_team_transactions(
            team_abbrev,
            season, 
            frozen=True
        )
    
    async def get_processed_transactions(
        self, 
        team_abbrev: str, 
        season: int,
        recent_weeks: int = 4
    ) -> List[Transaction]:
        """Get recently processed transactions for a team."""
        # Get current week to limit search
        try:
            current_data = await self.get_client()
            current_response = await current_data.get('current')
            current_week = current_response.get('week', 0) if current_response else 0
            
            week_start = max(1, current_week - recent_weeks)
            
            # For processed transactions, we need to filter by completed/processed status
            # Since the API structure doesn't have a processed status, we'll get all non-pending/non-frozen
            all_transactions = await self.get_team_transactions(
                team_abbrev,
                season,
                week_start=week_start
            )
            # Filter for transactions that are neither pending nor frozen (i.e., processed)
            processed = [t for t in all_transactions if not t.is_pending and not t.is_frozen and not t.cancelled]
            return processed
        except Exception as e:
            logger.warning(f"Could not get current week, using basic query: {e}")
            all_transactions = await self.get_team_transactions(
                team_abbrev,
                season
            )
            # Filter for processed transactions
            processed = [t for t in all_transactions if not t.is_pending and not t.is_frozen and not t.cancelled]
            return processed
    
    async def validate_transaction(self, transaction: Transaction) -> RosterValidation:
        """
        Validate a transaction for legality.
        
        Args:
            transaction: Transaction to validate
            
        Returns:
            Validation results with any errors or warnings
        """
        try:
            validation = RosterValidation(is_legal=True)
            
            # Basic validation rules for single-move transactions
            if not transaction.player:
                validation.is_legal = False
                validation.errors.append("Transaction has no player")
            
            if not transaction.oldteam or not transaction.newteam:
                validation.is_legal = False
                validation.errors.append("Transaction missing team information")
            
            # Validate player eligibility (basic checks)
            if transaction.player and transaction.player.wara < 0:
                validation.warnings.append("Player has negative WARA")
            
            # Add more validation logic as needed
            # - Roster size limits
            # - Position requirements
            # - Contract constraints
            # - etc.
            
            logger.debug(f"Validated transaction {transaction.id}: legal={validation.is_legal}")
            return validation
            
        except Exception as e:
            logger.error(f"Error validating transaction {transaction.id}: {e}")
            # Return failed validation on error
            return RosterValidation(
                is_legal=False,
                errors=[f"Validation error: {str(e)}"]
            )

    async def create_transaction_batch(self, transactions: List[Transaction]) -> List[Transaction]:
        """
        Create multiple transactions via API POST (for immediate execution).

        This is used for real-time transactions (like IL moves) that need to be
        posted to the database immediately rather than scheduled for later processing.

        The API expects a TransactionList format:
        {
            "count": 2,
            "moves": [
                {
                    "week": 17,
                    "player_id": 123,
                    "oldteam_id": 10,
                    "newteam_id": 11,
                    "season": 12,
                    "moveid": "Season-012-Week-17-123456",
                    "cancelled": false,
                    "frozen": false
                },
                ...
            ]
        }

        Args:
            transactions: List of Transaction objects to create

        Returns:
            List of created Transaction objects with API-assigned IDs

        Raises:
            APIException: If transaction creation fails
        """
        try:
            # Convert Transaction objects to API format (simple ID references only)
            moves = []
            for transaction in transactions:
                move = {
                    "week": transaction.week,
                    "player_id": transaction.player.id,
                    "oldteam_id": transaction.oldteam.id,
                    "newteam_id": transaction.newteam.id,
                    "season": transaction.season,
                    "moveid": transaction.moveid,
                    "cancelled": transaction.cancelled or False,
                    "frozen": transaction.frozen or False
                }
                moves.append(move)

            # Create batch request payload
            batch_data = {
                "count": len(moves),
                "moves": moves
            }

            # POST batch to API
            client = await self.get_client()
            response = await client.post(self.endpoint, data=batch_data)

            # API returns a string like "2 transactions have been added"
            # We need to return the original Transaction objects (they won't have IDs assigned by API)
            if response and isinstance(response, str) and "transactions have been added" in response:
                logger.info(f"Successfully created batch: {response}")
                return transactions
            else:
                logger.error(f"Unexpected API response: {response}")
                raise APIException(f"Unexpected API response: {response}")

        except Exception as e:
            logger.error(f"Error creating transaction batch: {e}")
            raise APIException(f"Failed to create transactions: {e}")

    async def cancel_transaction(self, transaction_id: str) -> bool:
        """
        Cancel a pending transaction.

        Note: When using moveid, this updates ALL transactions with that moveid (bulk update).
        The API returns a message string like "Updated 4 transactions" instead of the transaction object.

        Args:
            transaction_id: Move ID of transaction to cancel (e.g., "Season-012-Week-17-08-18:57:21")

        Returns:
            True if cancelled successfully
        """
        try:
            # Update transaction status using direct API call to handle bulk updates
            update_data = {
                'cancelled': True,
                'cancelled_at': datetime.now(UTC).isoformat()
            }

            # Call API directly since bulk update returns a message string, not a Transaction object
            client = await self.get_client()
            response = await client.patch(
                self.endpoint,
                update_data,
                object_id=transaction_id,
                use_query_params=True
            )

            # Check if response indicates success
            # Response will be a string like "Updated 4 transactions" for bulk updates
            if response and (isinstance(response, str) and 'Updated' in response):
                logger.info(f"Cancelled transaction(s) {transaction_id}: {response}")
                return True
            elif response:
                # If we got a dict response, it's a single transaction update
                logger.info(f"Cancelled transaction {transaction_id}")
                return True
            else:
                logger.warning(f"Failed to cancel transaction {transaction_id}")
                return False

        except Exception as e:
            logger.error(f"Error cancelling transaction {transaction_id}: {e}")
            return False

    async def unfreeze_transaction(self, transaction_id: str) -> bool:
        """
        Unfreeze a frozen transaction, allowing it to be processed.

        Note: When using moveid, this updates ALL transactions with that moveid (bulk update).
        The API returns a message string like "Updated 4 transactions" instead of the transaction object.

        Args:
            transaction_id: Move ID of transaction to unfreeze (e.g., "Season-012-Week-17-08-18:57:21")

        Returns:
            True if unfrozen successfully
        """
        try:
            # Call API directly since bulk update returns a message string, not a Transaction object
            client = await self.get_client()
            response = await client.patch(
                self.endpoint,
                {'frozen': False},
                object_id=transaction_id,
                use_query_params=True
            )

            # Check if response indicates success
            # Response will be a string like "Updated 4 transactions" for bulk updates
            if response and (isinstance(response, str) and 'Updated' in response):
                logger.info(f"Unfroze transaction(s) {transaction_id}: {response}")
                return True
            elif response:
                # If we got a dict response, it's a single transaction update
                logger.info(f"Unfroze transaction {transaction_id}")
                return True
            else:
                logger.warning(f"Failed to unfreeze transaction {transaction_id}")
                return False

        except Exception as e:
            logger.error(f"Error unfreezing transaction {transaction_id}: {e}")
            return False

    async def get_frozen_transactions_by_week(
        self,
        season: int,
        week_start: int,
        week_end: int
    ) -> List[Transaction]:
        """
        Get all frozen transactions for a week range (all teams).

        This is used during freeze processing to get all contested transactions
        across the entire league.

        Args:
            season: Season number
            week_start: Starting week number
            week_end: Ending week number

        Returns:
            List of frozen transactions for the week range
        """
        try:
            params = [
                ('season', str(season)),
                ('week_start', str(week_start)),
                ('week_end', str(week_end)),
                ('frozen', 'true')
            ]

            transactions = await self.get_all_items(params=params)

            logger.debug(f"Retrieved {len(transactions)} frozen transactions for weeks {week_start}-{week_end}")
            return transactions

        except Exception as e:
            logger.error(f"Error getting frozen transactions for weeks {week_start}-{week_end}: {e}")
            return []

    async def get_regular_transactions_by_week(
        self,
        season: int,
        week: int
    ) -> List[Transaction]:
        """
        Get non-frozen, non-cancelled transactions for a specific week.

        This is used during freeze begin to process regular transactions
        that were submitted during the non-freeze period and should take
        effect immediately when the new week starts.

        Args:
            season: Season number
            week: Week number to get transactions for

        Returns:
            List of regular (non-frozen, non-cancelled) transactions for the week
        """
        try:
            params = [
                ('season', str(season)),
                ('week_start', str(week)),
                ('week_end', str(week)),
                ('frozen', 'false'),
                ('cancelled', 'false')
            ]

            transactions = await self.get_all_items(params=params)

            logger.debug(f"Retrieved {len(transactions)} regular transactions for week {week}")
            return transactions

        except Exception as e:
            logger.error(f"Error getting regular transactions for week {week}: {e}")
            return []

    async def get_contested_transactions(self, season: int, week: int) -> List[Transaction]:
        """
        Get transactions that may be contested (multiple teams want same player).
        
        Args:
            season: Season number
            week: Week number
            
        Returns:
            List of potentially contested transactions
        """
        try:
            # Get all pending transactions for the week
            params = [
                ('season', str(season)),
                ('week', str(week)),
                ('cancelled', 'false'),
                ('frozen', 'false')
            ]
            
            transactions = await self.get_all_items(params=params)
            
            # Group by players being targeted (simplified contest detection)
            player_target_map = {}
            contested = []
            
            for transaction in transactions:
                # In the new model, each transaction is a single player move
                # Contest occurs when multiple teams try to acquire the same player
                if transaction.newteam.abbrev != 'FA':  # Not dropping to free agency
                    player_name = transaction.player.name.lower()
                    if player_name not in player_target_map:
                        player_target_map[player_name] = []
                    player_target_map[player_name].append(transaction)
            
            # Find contested players (wanted by multiple teams)
            for player_name, player_transactions in player_target_map.items():
                if len(player_transactions) > 1:
                    contested.extend(player_transactions)
            
            # Remove duplicates while preserving order
            seen = set()
            result = []
            for transaction in contested:
                if transaction.id not in seen:
                    seen.add(transaction.id)
                    result.append(transaction)
            
            logger.debug(f"Found {len(result)} potentially contested transactions for week {week}")
            return result

        except Exception as e:
            logger.error(f"Error getting contested transactions: {e}")
            return []

    async def is_player_in_pending_transaction(
        self,
        player_id: int,
        week: int,
        season: int
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a player is already in a pending transaction for a specific week.

        This checks ALL teams' pending transactions (frozen=false, cancelled=false)
        to prevent duplicate claims on the same player.

        Args:
            player_id: Player ID to check
            week: Week number to check
            season: Season number

        Returns:
            Tuple of (is_in_pending_transaction, claiming_team_abbrev or None)
        """
        try:
            # Get all pending transactions for the week (all teams)
            # Use week_start to filter out keepers (week=0) and earlier transactions
            params = [
                ('season', str(season)),
                ('week_start', str(week)),
                ('cancelled', 'false'),
                ('frozen', 'false')
            ]

            transactions = await self.get_all_items(params=params)

            # Check if the player is in any of these transactions
            for transaction in transactions:
                if transaction.player and transaction.player.id == player_id:
                    # Found the player in a pending transaction
                    claiming_team = transaction.newteam.abbrev if transaction.newteam else "Unknown"
                    logger.info(
                        f"Player {player_id} already in pending transaction for week {week} "
                        f"(claimed by {claiming_team})"
                    )
                    return True, claiming_team

            return False, None

        except Exception as e:
            logger.error(f"Error checking pending transactions for player {player_id}: {e}")
            # On error, allow the transaction (fail open) but log the issue
            # The freeze task will still catch duplicates if they occur
            return False, None


# Global service instance
transaction_service = TransactionService()