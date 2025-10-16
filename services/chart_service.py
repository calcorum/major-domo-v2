"""
Chart Service for managing gameplay charts and infographics.

This service handles loading, saving, and managing chart definitions
from the JSON configuration file.
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from exceptions import BotException

logger = logging.getLogger(__name__)


@dataclass
class Chart:
    """Represents a gameplay chart or infographic."""
    key: str
    name: str
    category: str
    description: str
    urls: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert chart to dictionary (excluding key)."""
        return {
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'urls': self.urls
        }


class ChartService:
    """Service for managing gameplay charts and infographics."""

    CHARTS_FILE = Path(__file__).parent.parent / 'data' / 'charts.json'

    def __init__(self):
        """Initialize the chart service."""
        self._charts: Dict[str, Chart] = {}
        self._categories: Dict[str, str] = {}
        self._load_charts()

    def _load_charts(self) -> None:
        """Load charts from JSON file."""
        try:
            if not self.CHARTS_FILE.exists():
                logger.warning(f"Charts file not found: {self.CHARTS_FILE}")
                self._charts = {}
                self._categories = {}
                return

            with open(self.CHARTS_FILE, 'r') as f:
                data = json.load(f)

            # Load categories
            self._categories = data.get('categories', {})

            # Load charts
            charts_data = data.get('charts', {})
            for key, chart_data in charts_data.items():
                self._charts[key] = Chart(
                    key=key,
                    name=chart_data['name'],
                    category=chart_data['category'],
                    description=chart_data.get('description', ''),
                    urls=chart_data.get('urls', [])
                )

            logger.info(f"Loaded {len(self._charts)} charts from {self.CHARTS_FILE}")

        except Exception as e:
            logger.error(f"Failed to load charts: {e}", exc_info=True)
            self._charts = {}
            self._categories = {}

    def _save_charts(self) -> None:
        """Save charts to JSON file."""
        try:
            # Ensure data directory exists
            self.CHARTS_FILE.parent.mkdir(parents=True, exist_ok=True)

            # Build data structure
            data = {
                'charts': {
                    key: chart.to_dict()
                    for key, chart in self._charts.items()
                },
                'categories': self._categories
            }

            # Write to file
            with open(self.CHARTS_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"Saved {len(self._charts)} charts to {self.CHARTS_FILE}")

        except Exception as e:
            logger.error(f"Failed to save charts: {e}", exc_info=True)
            raise BotException(f"Failed to save charts: {str(e)}")

    def get_chart(self, chart_key: str) -> Optional[Chart]:
        """
        Get a chart by its key.

        Args:
            chart_key: The chart key/identifier

        Returns:
            Chart object if found, None otherwise
        """
        return self._charts.get(chart_key)

    def get_all_charts(self) -> List[Chart]:
        """
        Get all available charts.

        Returns:
            List of all Chart objects
        """
        return list(self._charts.values())

    def get_charts_by_category(self, category: str) -> List[Chart]:
        """
        Get all charts in a specific category.

        Args:
            category: The category to filter by

        Returns:
            List of charts in the specified category
        """
        return [
            chart for chart in self._charts.values()
            if chart.category == category
        ]

    def get_chart_keys(self) -> List[str]:
        """
        Get all chart keys for autocomplete.

        Returns:
            Sorted list of chart keys
        """
        return sorted(self._charts.keys())

    def get_categories(self) -> Dict[str, str]:
        """
        Get all categories.

        Returns:
            Dictionary mapping category keys to display names
        """
        return self._categories.copy()

    def add_chart(self, key: str, name: str, category: str,
                  urls: List[str], description: str = "") -> None:
        """
        Add a new chart.

        Args:
            key: Unique identifier for the chart
            name: Display name for the chart
            category: Category the chart belongs to
            urls: List of image URLs for the chart
            description: Optional description of the chart

        Raises:
            BotException: If chart key already exists
        """
        if key in self._charts:
            raise BotException(f"Chart '{key}' already exists")

        self._charts[key] = Chart(
            key=key,
            name=name,
            category=category,
            description=description,
            urls=urls
        )
        self._save_charts()
        logger.info(f"Added chart: {key}")

    def update_chart(self, key: str, name: Optional[str] = None,
                    category: Optional[str] = None, urls: Optional[List[str]] = None,
                    description: Optional[str] = None) -> None:
        """
        Update an existing chart.

        Args:
            key: Chart key to update
            name: New name (optional)
            category: New category (optional)
            urls: New URLs (optional)
            description: New description (optional)

        Raises:
            BotException: If chart doesn't exist
        """
        if key not in self._charts:
            raise BotException(f"Chart '{key}' not found")

        chart = self._charts[key]

        if name is not None:
            chart.name = name
        if category is not None:
            chart.category = category
        if urls is not None:
            chart.urls = urls
        if description is not None:
            chart.description = description

        self._save_charts()
        logger.info(f"Updated chart: {key}")

    def remove_chart(self, key: str) -> None:
        """
        Remove a chart.

        Args:
            key: Chart key to remove

        Raises:
            BotException: If chart doesn't exist
        """
        if key not in self._charts:
            raise BotException(f"Chart '{key}' not found")

        del self._charts[key]
        self._save_charts()
        logger.info(f"Removed chart: {key}")

    def add_category(self, key: str, display_name: str) -> None:
        """
        Add a new category.

        Args:
            key: Unique identifier for the category (e.g., 'gameplay')
            display_name: Display name for the category (e.g., 'Gameplay Charts')

        Raises:
            BotException: If category key already exists
        """
        if key in self._categories:
            raise BotException(f"Category '{key}' already exists")

        self._categories[key] = display_name
        self._save_charts()
        logger.info(f"Added category: {key} - {display_name}")

    def remove_category(self, key: str) -> None:
        """
        Remove a category.

        Args:
            key: Category key to remove

        Raises:
            BotException: If category doesn't exist or charts are using it
        """
        if key not in self._categories:
            raise BotException(f"Category '{key}' not found")

        # Check if any charts use this category
        charts_using = [c for c in self._charts.values() if c.category == key]
        if charts_using:
            chart_names = ", ".join([c.name for c in charts_using])
            raise BotException(
                f"Cannot remove category '{key}' - used by {len(charts_using)} chart(s): {chart_names}"
            )

        del self._categories[key]
        self._save_charts()
        logger.info(f"Removed category: {key}")

    def update_category(self, key: str, display_name: str) -> None:
        """
        Update category display name.

        Args:
            key: Category key to update
            display_name: New display name

        Raises:
            BotException: If category doesn't exist
        """
        if key not in self._categories:
            raise BotException(f"Category '{key}' not found")

        old_name = self._categories[key]
        self._categories[key] = display_name
        self._save_charts()
        logger.info(f"Updated category: {key} from '{old_name}' to '{display_name}'")

    def reload_charts(self) -> None:
        """Reload charts from the JSON file."""
        self._load_charts()


# Global chart service instance
_chart_service: Optional[ChartService] = None


def get_chart_service() -> ChartService:
    """
    Get the global chart service instance.

    Returns:
        ChartService instance
    """
    global _chart_service
    if _chart_service is None:
        _chart_service = ChartService()
    return _chart_service
