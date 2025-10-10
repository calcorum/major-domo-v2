"""
Test Factories for Discord Bot v2.0

Provides factory functions to create test instances of models with sensible defaults.
This eliminates the need for ad-hoc fixture creation and makes tests resilient
to model changes.
"""
from typing import Optional, Dict, Any

from models.player import Player
from models.team import Team, RosterType
from models.transaction import Transaction
from models.game import Game
from models.current import Current


class PlayerFactory:
    """Factory for creating Player test instances."""

    @staticmethod
    def create(
        id: int = 1,
        name: str = "Test Player",
        wara: float = 2.0,
        season: int = 12,
        pos_1: str = "CF",
        team_id: Optional[int] = None,
        **kwargs
    ) -> Player:
        """Create a Player instance with sensible defaults."""
        defaults = {
            "id": id,
            "name": name,
            "wara": wara,
            "season": season,
            "pos_1": pos_1,
            "team_id": team_id,
        }
        defaults.update(kwargs)
        return Player(**defaults)

    @staticmethod
    def mike_trout(id: int = 12472, **kwargs) -> Player:
        """Create Mike Trout player for consistent testing."""
        defaults = {
            "id": id,
            "name": "Mike Trout",
            "wara": 2.5,
            "season": 12,
            "pos_1": "CF",
        }
        defaults.update(kwargs)
        return PlayerFactory.create(**defaults)

    @staticmethod
    def ronald_acuna(id: int = 12473, **kwargs) -> Player:
        """Create Ronald Acuna Jr. player for consistent testing."""
        defaults = {
            "id": id,
            "name": "Ronald Acuna Jr.",
            "wara": 2.0,
            "season": 12,
            "pos_1": "OF",
        }
        defaults.update(kwargs)
        return PlayerFactory.create(**defaults)

    @staticmethod
    def mookie_betts(id: int = 12474, **kwargs) -> Player:
        """Create Mookie Betts player for consistent testing."""
        defaults = {
            "id": id,
            "name": "Mookie Betts",
            "wara": 1.8,
            "season": 12,
            "pos_1": "RF",
        }
        defaults.update(kwargs)
        return PlayerFactory.create(**defaults)

    @staticmethod
    def pitcher(id: int = 2000, name: str = "Test Pitcher", **kwargs) -> Player:
        """Create a pitcher for testing."""
        defaults = {
            "id": id,
            "name": name,
            "wara": 1.5,
            "season": 12,
            "pos_1": "SP",
        }
        defaults.update(kwargs)
        return PlayerFactory.create(**defaults)


class TeamFactory:
    """Factory for creating Team test instances."""

    @staticmethod
    def create(
        id: int = 1,
        abbrev: str = "TST",
        sname: str = "Test Team",
        lname: str = "Test City Test Team",
        season: int = 12,
        **kwargs
    ) -> Team:
        """Create a Team instance with sensible defaults."""
        defaults = {
            "id": id,
            "abbrev": abbrev,
            "sname": sname,
            "lname": lname,
            "season": season,
        }
        defaults.update(kwargs)
        return Team(**defaults)

    @staticmethod
    def west_virginia(id: int = 499, **kwargs) -> Team:
        """Create West Virginia Black Bears team for consistent testing."""
        defaults = {
            "id": id,
            "abbrev": "WV",
            "sname": "Black Bears",
            "lname": "West Virginia Black Bears",
            "season": 12,
        }
        defaults.update(kwargs)
        return TeamFactory.create(**defaults)

    @staticmethod
    def new_york(id: int = 500, **kwargs) -> Team:
        """Create New York team for testing."""
        defaults = {
            "id": id,
            "abbrev": "NY",
            "sname": "Yankees",
            "lname": "New York Yankees",
            "season": 12,
        }
        defaults.update(kwargs)
        return TeamFactory.create(**defaults)


class TransactionFactory:
    """Factory for creating Transaction test instances."""

    @staticmethod
    def create(
        id: int = 1,
        transaction_type: str = "Drop/Add",
        player_id: int = 1,
        team_id: int = 1,
        season: int = 12,
        week: int = 1,
        **kwargs
    ) -> Transaction:
        """Create a Transaction instance with sensible defaults."""
        defaults = {
            "id": id,
            "transaction_type": transaction_type,
            "player_id": player_id,
            "team_id": team_id,
            "season": season,
            "week": week,
        }
        defaults.update(kwargs)
        return Transaction(**defaults)


class GameFactory:
    """Factory for creating Game test instances."""

    @staticmethod
    def create(
        id: int = 1,
        season: int = 12,
        week: int = 1,
        game_num: int = 1,
        season_type: str = "regular",
        away_team: Optional[Team] = None,
        home_team: Optional[Team] = None,
        away_score: Optional[int] = None,
        home_score: Optional[int] = None,
        **kwargs
    ) -> Game:
        """Create a Game instance with sensible defaults."""
        # Use default teams if none provided
        if away_team is None:
            away_team = TeamFactory.create(id=1, abbrev="AWY", sname="Away", lname="Away Team")
        if home_team is None:
            home_team = TeamFactory.create(id=2, abbrev="HOM", sname="Home", lname="Home Team")

        defaults = {
            "id": id,
            "season": season,
            "week": week,
            "game_num": game_num,
            "season_type": season_type,
            "away_team": away_team,
            "home_team": home_team,
            "away_score": away_score,
            "home_score": home_score,
        }
        defaults.update(kwargs)
        return Game(**defaults)

    @staticmethod
    def completed(
        id: int = 1,
        away_score: int = 5,
        home_score: int = 3,
        **kwargs
    ) -> Game:
        """Create a completed game with scores."""
        return GameFactory.create(
            id=id,
            away_score=away_score,
            home_score=home_score,
            **kwargs
        )

    @staticmethod
    def upcoming(id: int = 1, **kwargs) -> Game:
        """Create an upcoming game (no scores)."""
        return GameFactory.create(
            id=id,
            away_score=None,
            home_score=None,
            **kwargs
        )


class CurrentFactory:
    """Factory for creating Current league state instances."""

    @staticmethod
    def create(
        week: int = 10,
        season: int = 12,
        freeze: bool = False,
        trade_deadline: int = 14,
        playoffs_begin: int = 19,
        **kwargs
    ) -> Current:
        """Create a Current instance with sensible defaults."""
        defaults = {
            "week": week,
            "season": season,
            "freeze": freeze,
            "trade_deadline": trade_deadline,
            "playoffs_begin": playoffs_begin,
        }
        defaults.update(kwargs)
        return Current(**defaults)


# Convenience functions for common test scenarios
def create_player_list(count: int = 3, **kwargs) -> list[Player]:
    """Create a list of test players."""
    players = []
    for i in range(count):
        player_kwargs = {
            "id": i + 1,
            "name": f"Test Player {i + 1}",
            **kwargs
        }
        players.append(PlayerFactory.create(**player_kwargs))
    return players


def create_team_roster(team_id: int = 1, player_count: int = 25) -> list[Player]:
    """Create a full team roster for testing."""
    players = []
    positions = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "SP", "RP"]

    for i in range(player_count):
        pos = positions[i % len(positions)]
        player = PlayerFactory.create(
            id=i + 1,
            name=f"Player {i + 1}",
            team_id=team_id,
            pos_1=pos
        )
        players.append(player)

    return players


def create_pitcher_staff(team_id: int = 1) -> list[Player]:
    """Create a pitching staff for testing."""
    return [
        PlayerFactory.create(id=100, name="Starter 1", team_id=team_id, pos_1="SP"),
        PlayerFactory.create(id=101, name="Starter 2", team_id=team_id, pos_1="SP"),
        PlayerFactory.create(id=102, name="Reliever 1", team_id=team_id, pos_1="RP"),
        PlayerFactory.create(id=103, name="Reliever 2", team_id=team_id, pos_1="RP"),
    ]