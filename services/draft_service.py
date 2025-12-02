"""
Draft service for Discord Bot v2.0

Core draft business logic and state management. NO CACHING - draft state changes constantly.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from services.base_service import BaseService
from models.draft_data import DraftData
from exceptions import APIException

logger = logging.getLogger(f'{__name__}.DraftService')


class DraftService(BaseService[DraftData]):
    """
    Service for core draft operations and state management.

    IMPORTANT: This service does NOT use caching decorators because draft data
    changes every 2-12 minutes during an active draft. Always fetch fresh data.

    Features:
    - Get/update draft configuration
    - Timer management (start/stop)
    - Pick advancement
    - Draft state validation
    """

    def __init__(self):
        """Initialize draft service."""
        super().__init__(DraftData, 'draftdata')
        logger.debug("DraftService initialized")

    async def get_draft_data(self) -> Optional[DraftData]:
        """
        Get current draft configuration and state.

        NOT cached - draft state changes frequently during active draft.

        Returns:
            DraftData instance or None if not found
        """
        try:
            # Draft data endpoint typically returns single object
            items = await self.get_all_items()

            if items:
                draft_data = items[0]
                logger.debug(
                    f"Retrieved draft data: pick={draft_data.currentpick}, "
                    f"timer={draft_data.timer}, "
                    f"deadline={draft_data.pick_deadline}"
                )
                return draft_data

            logger.warning("No draft data found in database")
            return None

        except Exception as e:
            logger.error(f"Error getting draft data: {e}")
            return None

    async def update_draft_data(
        self,
        draft_id: int,
        updates: Dict[str, Any]
    ) -> Optional[DraftData]:
        """
        Update draft configuration.

        Args:
            draft_id: DraftData database ID (typically 1)
            updates: Dictionary of fields to update

        Returns:
            Updated DraftData instance or None if update failed
        """
        try:
            # Draft data API expects query parameters for PATCH requests
            updated = await self.patch(draft_id, updates, use_query_params=True)

            if updated:
                logger.info(f"Updated draft data: {updates}")
            else:
                logger.error(f"Failed to update draft data with {updates}")

            return updated

        except Exception as e:
            logger.error(f"Error updating draft data: {e}")
            return None

    async def set_timer(
        self,
        draft_id: int,
        active: bool,
        pick_minutes: Optional[int] = None
    ) -> Optional[DraftData]:
        """
        Enable or disable draft timer.

        Args:
            draft_id: DraftData database ID
            active: True to enable timer, False to disable
            pick_minutes: Minutes per pick (updates default if provided)

        Returns:
            Updated DraftData instance
        """
        try:
            updates = {'timer': active}

            if pick_minutes is not None:
                updates['pick_minutes'] = pick_minutes

            # Set deadline based on timer state
            if active:
                # Calculate new deadline
                if pick_minutes:
                    deadline = datetime.now() + timedelta(minutes=pick_minutes)
                else:
                    # Get current pick_minutes from existing data
                    current_data = await self.get_draft_data()
                    if current_data:
                        deadline = datetime.now() + timedelta(minutes=current_data.pick_minutes)
                    else:
                        deadline = datetime.now() + timedelta(minutes=2)  # Default fallback
                updates['pick_deadline'] = deadline
            else:
                # Set deadline far in future when timer inactive
                updates['pick_deadline'] = datetime.now() + timedelta(days=690)

            updated = await self.update_draft_data(draft_id, updates)

            if updated:
                status = "enabled" if active else "disabled"
                logger.info(f"Draft timer {status}")
            else:
                logger.error("Failed to update draft timer")

            return updated

        except Exception as e:
            logger.error(f"Error setting draft timer: {e}")
            return None

    async def advance_pick(
        self,
        draft_id: int,
        current_pick: int
    ) -> Optional[DraftData]:
        """
        Advance to next pick in draft.

        Automatically skips picks that have already been filled (player selected).
        Posts round announcement when entering new round.

        Args:
            draft_id: DraftData database ID
            current_pick: Current overall pick number

        Returns:
            Updated DraftData with new currentpick
        """
        try:
            from services.draft_pick_service import draft_pick_service
            from config import get_config

            config = get_config()
            season = config.sba_season
            total_picks = config.draft_total_picks

            # Start with next pick
            next_pick = current_pick + 1

            # Keep advancing until we find an unfilled pick or reach end
            while next_pick <= total_picks:
                pick = await draft_pick_service.get_pick(season, next_pick)

                if not pick:
                    logger.error(f"Pick #{next_pick} not found in database")
                    break

                # If pick has no player, this is the next pick to make
                if pick.player_id is None:
                    logger.info(f"Advanced to pick #{next_pick}")
                    break

                # Pick already filled, continue to next
                logger.debug(f"Pick #{next_pick} already filled, skipping")
                next_pick += 1

            # Check if draft is complete
            if next_pick > total_picks:
                logger.info("Draft is complete - all picks filled")
                # Disable timer
                await self.set_timer(draft_id, active=False)
                return await self.get_draft_data()

            # Update to next pick
            updates = {'currentpick': next_pick}

            # Reset deadline if timer is active
            current_data = await self.get_draft_data()
            if current_data and current_data.timer:
                updates['pick_deadline'] = datetime.now() + timedelta(minutes=current_data.pick_minutes)

            updated = await self.update_draft_data(draft_id, updates)

            if updated:
                logger.info(f"Draft advanced from pick #{current_pick} to #{next_pick}")
            else:
                logger.error(f"Failed to advance draft pick")

            return updated

        except Exception as e:
            logger.error(f"Error advancing draft pick: {e}")
            return None

    async def set_current_pick(
        self,
        draft_id: int,
        overall: int,
        reset_timer: bool = True
    ) -> Optional[DraftData]:
        """
        Manually set current pick (admin operation).

        Args:
            draft_id: DraftData database ID
            overall: Overall pick number to jump to
            reset_timer: Whether to reset the pick deadline

        Returns:
            Updated DraftData
        """
        try:
            updates = {'currentpick': overall}

            if reset_timer:
                current_data = await self.get_draft_data()
                if current_data and current_data.timer:
                    updates['pick_deadline'] = datetime.now() + timedelta(minutes=current_data.pick_minutes)

            updated = await self.update_draft_data(draft_id, updates)

            if updated:
                logger.info(f"Manually set current pick to #{overall}")
            else:
                logger.error(f"Failed to set current pick to #{overall}")

            return updated

        except Exception as e:
            logger.error(f"Error setting current pick: {e}")
            return None

    async def update_channels(
        self,
        draft_id: int,
        ping_channel_id: Optional[int] = None,
        result_channel_id: Optional[int] = None
    ) -> Optional[DraftData]:
        """
        Update draft Discord channel configuration.

        Args:
            draft_id: DraftData database ID
            ping_channel_id: Channel ID for "on the clock" pings
            result_channel_id: Channel ID for draft results

        Returns:
            Updated DraftData
        """
        try:
            updates = {}
            if ping_channel_id is not None:
                updates['ping_channel'] = ping_channel_id
            if result_channel_id is not None:
                updates['result_channel'] = result_channel_id

            if not updates:
                logger.warning("No channel updates provided")
                return await self.get_draft_data()

            updated = await self.update_draft_data(draft_id, updates)

            if updated:
                logger.info(f"Updated draft channels: {updates}")
            else:
                logger.error("Failed to update draft channels")

            return updated

        except Exception as e:
            logger.error(f"Error updating draft channels: {e}")
            return None

    async def reset_draft_deadline(
        self,
        draft_id: int,
        minutes: Optional[int] = None
    ) -> Optional[DraftData]:
        """
        Reset the current pick deadline.

        Args:
            draft_id: DraftData database ID
            minutes: Minutes to add (uses pick_minutes from config if not provided)

        Returns:
            Updated DraftData with new deadline
        """
        try:
            if minutes is None:
                current_data = await self.get_draft_data()
                if not current_data:
                    logger.error("Could not get current draft data")
                    return None
                minutes = current_data.pick_minutes

            new_deadline = datetime.now() + timedelta(minutes=minutes)
            updates = {'pick_deadline': new_deadline}

            updated = await self.update_draft_data(draft_id, updates)

            if updated:
                logger.info(f"Reset draft deadline to {new_deadline}")
            else:
                logger.error("Failed to reset draft deadline")

            return updated

        except Exception as e:
            logger.error(f"Error resetting draft deadline: {e}")
            return None


# Global service instance
draft_service = DraftService()
