"""
Tests for SBA data models

Validates model creation, validation, and business logic.
"""
import pytest
from datetime import datetime

from models import Team, Player, Current, DraftPick, DraftData, DraftList


class TestSBABaseModel:
    """Test base model functionality."""
    
    def test_model_creation_with_api_data(self):
        """Test creating models from API data."""
        team_data = {
            'id': 1,
            'abbrev': 'NYY',
            'sname': 'Yankees',
            'lname': 'New York Yankees',
            'season': 12
        }
        
        team = Team.from_api_data(team_data)
        assert team.id == 1
        assert team.abbrev == 'NYY'
        assert team.lname == 'New York Yankees'
    
    def test_to_dict_functionality(self):
        """Test model to dictionary conversion."""
        team = Team(id=1, abbrev='LAA', sname='Angels', lname='Los Angeles Angels', season=12)
        
        team_dict = team.to_dict()
        assert 'abbrev' in team_dict
        assert team_dict['abbrev'] == 'LAA'
        assert team_dict['lname'] == 'Los Angeles Angels'
    
    def test_model_repr(self):
        """Test model string representation."""
        team = Team(id=2, abbrev='BOS', sname='Red Sox', lname='Boston Red Sox', season=12)
        repr_str = repr(team)
        assert 'Team(' in repr_str
        assert 'abbrev=BOS' in repr_str


class TestTeamModel:
    """Test Team model functionality."""
    
    def test_team_creation_minimal(self):
        """Test team creation with minimal required fields."""
        team = Team(
            id=4,
            abbrev='HOU',
            sname='Astros',
            lname='Houston Astros',
            season=12
        )
        
        assert team.abbrev == 'HOU'
        assert team.sname == 'Astros'
        assert team.lname == 'Houston Astros'
        assert team.season == 12
    
    def test_team_creation_with_optional_fields(self):
        """Test team creation with optional fields."""
        team = Team(
            id=5,
            abbrev='SF',
            sname='Giants',
            lname='San Francisco Giants',
            season=12,
            gmid=100,
            division_id=1,
            stadium='Oracle Park',
            color='FF8C00'
        )
        
        assert team.gmid == 100
        assert team.division_id == 1
        assert team.stadium == 'Oracle Park'
        assert team.color == 'FF8C00'
    
    def test_team_str_representation(self):
        """Test team string representation."""
        team = Team(id=3, abbrev='SD', sname='Padres', lname='San Diego Padres', season=12)
        assert str(team) == 'SD - San Diego Padres'

    def test_team_roster_type_major_league(self):
        """Test roster type detection for Major League teams."""
        from models.team import RosterType

        # 3 chars or less → Major League
        team = Team(id=1, abbrev='NYY', sname='Yankees', lname='New York Yankees', season=12)
        assert team.roster_type() == RosterType.MAJOR_LEAGUE

        team = Team(id=2, abbrev='BOS', sname='Red Sox', lname='Boston Red Sox', season=12)
        assert team.roster_type() == RosterType.MAJOR_LEAGUE

        # Even "BHM" (ends in M) should be Major League
        team = Team(id=3, abbrev='BHM', sname='Iron', lname='Birmingham Iron', season=12)
        assert team.roster_type() == RosterType.MAJOR_LEAGUE

    def test_team_roster_type_minor_league(self):
        """Test roster type detection for Minor League teams."""
        from models.team import RosterType

        # Standard Minor League: [Team] + "MIL"
        team = Team(id=4, abbrev='NYYMIL', sname='RailRiders', lname='Staten Island RailRiders', season=12)
        assert team.roster_type() == RosterType.MINOR_LEAGUE

        team = Team(id=5, abbrev='PORMIL', sname='Portland MiL', lname='Portland Minor League', season=12)
        assert team.roster_type() == RosterType.MINOR_LEAGUE

        # Case insensitive
        team = Team(id=6, abbrev='LAAmil', sname='Bees', lname='Salt Lake Bees', season=12)
        assert team.roster_type() == RosterType.MINOR_LEAGUE

    def test_team_roster_type_injured_list(self):
        """Test roster type detection for Injured List teams."""
        from models.team import RosterType

        # Standard Injured List: [Team] + "IL"
        team = Team(id=7, abbrev='NYYIL', sname='Yankees IL', lname='New York Yankees IL', season=12)
        assert team.roster_type() == RosterType.INJURED_LIST

        team = Team(id=8, abbrev='PORIL', sname='Loggers IL', lname='Portland Loggers IL', season=12)
        assert team.roster_type() == RosterType.INJURED_LIST

        # Case insensitive
        team = Team(id=9, abbrev='LAAil', sname='Angels IL', lname='Los Angeles Angels IL', season=12)
        assert team.roster_type() == RosterType.INJURED_LIST

    def test_team_roster_type_edge_case_bhmil(self):
        """
        Test critical edge case: "BHMIL" should be Injured List, not Minor League.

        This is BHM (Birmingham, ends in M) + IL (Injured List).
        NOT BH + MIL (Minor League).

        Bug history: Originally failed because "BHMIL" ends with "MIL", so it was
        incorrectly classified as Minor League.
        """
        from models.team import RosterType

        # "BHMIL" = "BHM" + "IL" → sname contains "IL" → INJURED_LIST
        team = Team(id=10, abbrev='BHMIL', sname='Iron IL', lname='Birmingham Iron IL', season=12)
        assert team.roster_type() == RosterType.INJURED_LIST

        # Compare with a real Minor League team that has "Island" in name
        # "NYYMIL" = "NYY" + "MIL", even though sname has "Island" → MINOR_LEAGUE
        team = Team(id=11, abbrev='NYYMIL', sname='Staten Island RailRiders', lname='Staten Island RailRiders', season=12)
        assert team.roster_type() == RosterType.MINOR_LEAGUE

        # Another IL edge case with sname containing "IL" at word boundary
        team = Team(id=12, abbrev='WVMIL', sname='WV IL', lname='West Virginia IL', season=12)
        assert team.roster_type() == RosterType.INJURED_LIST

    def test_team_roster_type_sname_disambiguation(self):
        """Test that sname is used correctly to disambiguate MIL vs IL."""
        from models.team import RosterType

        # MiL team - sname does NOT have "IL" as a word
        team = Team(id=13, abbrev='WVMIL', sname='Miners', lname='West Virginia Miners', season=12)
        assert team.roster_type() == RosterType.MINOR_LEAGUE

        # IL team - sname has "IL" at word boundary
        team = Team(id=14, abbrev='WVMIL', sname='Miners IL', lname='West Virginia Miners IL', season=12)
        assert team.roster_type() == RosterType.INJURED_LIST

        # MiL team - sname has "IL" but only in "Island" (substring, not word boundary)
        team = Team(id=15, abbrev='CHIMIL', sname='Island Hoppers', lname='Chicago Island Hoppers', season=12)
        assert team.roster_type() == RosterType.MINOR_LEAGUE


class TestPlayerModel:
    """Test Player model functionality."""
    
    def test_player_creation(self):
        """Test player creation with required fields."""
        player = Player(
            id=101,
            name='Mike Trout',
            wara=8.5,
            season=12,
            team_id=1,
            image='trout.jpg',
            pos_1='CF'
        )
        
        assert player.name == 'Mike Trout'
        assert player.wara == 8.5
        assert player.team_id == 1
        assert player.pos_1 == 'CF'
    
    def test_player_positions_property(self):
        """Test player positions property."""
        player = Player(
            id=102,
            name='Shohei Ohtani',
            wara=9.0,
            season=12,
            team_id=1,
            image='ohtani.jpg',
            pos_1='SP',
            pos_2='DH',
            pos_3='RF'
        )
        
        positions = player.positions
        assert len(positions) == 3
        assert 'SP' in positions
        assert 'DH' in positions
        assert 'RF' in positions
    
    def test_player_primary_position(self):
        """Test primary position property."""
        player = Player(
            id=103,
            name='Mookie Betts',
            wara=7.2,
            season=12,
            team_id=1,
            image='betts.jpg',
            pos_1='RF',
            pos_2='2B'
        )
        
        assert player.primary_position == 'RF'
    
    def test_player_is_pitcher(self):
        """Test is_pitcher property."""
        pitcher = Player(
            id=104,
            name='Gerrit Cole',
            wara=6.8,
            season=12,
            team_id=1,
            image='cole.jpg',
            pos_1='SP'
        )
        
        position_player = Player(
            id=105,
            name='Aaron Judge',
            wara=8.1,
            season=12,
            team_id=1,
            image='judge.jpg',
            pos_1='RF'
        )
        
        assert pitcher.is_pitcher is True
        assert position_player.is_pitcher is False
    
    def test_player_str_representation(self):
        """Test player string representation."""
        player = Player(
            id=106,
            name='Ronald Acuna Jr.',
            wara=8.8,
            season=12,
            team_id=1,
            image='acuna.jpg',
            pos_1='OF'
        )
        
        assert str(player) == 'Ronald Acuna Jr. (OF)'


class TestCurrentModel:
    """Test Current league state model."""
    
    def test_current_default_values(self):
        """Test current model with default values."""
        current = Current()
        
        assert current.week == 69
        assert current.season == 69
        assert current.freeze is True
        assert current.bet_week == 'sheets'
    
    def test_current_with_custom_values(self):
        """Test current model with custom values."""
        current = Current(
            week=15,
            season=12,
            freeze=False,
            trade_deadline=14,
            playoffs_begin=19
        )
        
        assert current.week == 15
        assert current.season == 12
        assert current.freeze is False
    
    def test_current_properties(self):
        """Test current model properties."""
        # Regular season
        current = Current(week=10, playoffs_begin=19)
        assert current.is_offseason is False
        assert current.is_playoffs is False
        
        # Playoffs
        current = Current(week=20, playoffs_begin=19)
        assert current.is_offseason is True
        assert current.is_playoffs is True
        
        # Pick trading
        current = Current(week=15, pick_trade_start=10, pick_trade_end=20)
        assert current.can_trade_picks is True


class TestDraftPickModel:
    """Test DraftPick model functionality."""
    
    def test_draft_pick_creation(self):
        """Test draft pick creation."""
        pick = DraftPick(
            season=12,
            overall=1,
            round=1,
            origowner_id=1,
            owner_id=1
        )
        
        assert pick.season == 12
        assert pick.overall == 1
        assert pick.origowner_id == 1
        assert pick.owner_id == 1
    
    def test_draft_pick_properties(self):
        """Test draft pick properties."""
        # Not traded, not selected
        pick = DraftPick(
            season=12,
            overall=5,
            round=1,
            origowner_id=1,
            owner_id=1
        )
        
        assert pick.is_traded is False
        assert pick.is_selected is False
        
        # Traded pick
        traded_pick = DraftPick(
            season=12,
            overall=10,
            round=1,
            origowner_id=1,
            owner_id=2
        )
        
        assert traded_pick.is_traded is True
        
        # Selected pick
        selected_pick = DraftPick(
            season=12,
            overall=15,
            round=1,
            origowner_id=1,
            owner_id=1,
            player_id=100
        )
        
        assert selected_pick.is_selected is True


class TestDraftDataModel:
    """Test DraftData model functionality."""
    
    def test_draft_data_creation(self):
        """Test draft data creation."""
        draft_data = DraftData(
            result_channel=123456789,
            ping_channel=987654321,
            pick_minutes=10
        )

        assert draft_data.result_channel == 123456789
        assert draft_data.ping_channel == 987654321
        assert draft_data.pick_minutes == 10

    def test_draft_data_properties(self):
        """Test draft data properties."""
        # Inactive draft
        draft_data = DraftData(
            result_channel=123,
            ping_channel=456,
            timer=False
        )

        assert draft_data.is_draft_active is False

        # Active draft
        active_draft = DraftData(
            result_channel=123,
            ping_channel=456,
            timer=True
        )

        assert active_draft.is_draft_active is True


class TestDraftListModel:
    """Test DraftList model functionality.

    Note: DraftList model requires nested Team and Player objects,
    not just IDs. The API returns these objects populated.
    """

    def _create_mock_team(self, team_id: int = 1) -> 'Team':
        """Create a mock team for testing."""
        return Team(
            id=team_id,
            abbrev="TST",
            sname="Test",
            lname="Test Team",
            season=12
        )

    def _create_mock_player(self, player_id: int = 100) -> 'Player':
        """Create a mock player for testing."""
        return Player(
            id=player_id,
            name="Test Player",
            fname="Test",
            lname="Player",
            pos_1="1B",
            team_id=1,
            season=12,
            wara=2.5,
            image="https://example.com/test.jpg"
        )

    def test_draft_list_creation(self):
        """Test draft list creation with nested objects."""
        mock_team = self._create_mock_team(team_id=1)
        mock_player = self._create_mock_player(player_id=100)

        draft_entry = DraftList(
            season=12,
            team=mock_team,
            rank=1,
            player=mock_player
        )

        assert draft_entry.season == 12
        assert draft_entry.team_id == 1
        assert draft_entry.rank == 1
        assert draft_entry.player_id == 100

    def test_draft_list_top_ranked_property(self):
        """Test top ranked property."""
        mock_team = self._create_mock_team(team_id=1)
        mock_player_top = self._create_mock_player(player_id=100)
        mock_player_lower = self._create_mock_player(player_id=200)

        top_pick = DraftList(
            season=12,
            team=mock_team,
            rank=1,
            player=mock_player_top
        )

        lower_pick = DraftList(
            season=12,
            team=mock_team,
            rank=5,
            player=mock_player_lower
        )

        assert top_pick.is_top_ranked is True
        assert lower_pick.is_top_ranked is False

    def test_draft_list_from_api_data_extracts_player_team_id(self):
        """
        Test that DraftList.from_api_data() properly extracts player.team_id from nested team object.

        This is critical for auto-draft functionality. The API returns player data with a nested
        team object (not a flat team_id). Without the custom from_api_data(), Pydantic's default
        construction doesn't call Player.from_api_data(), leaving player.team_id as None.

        Bug fixed: Auto-draft was failing because player.team_id was None, causing all players
        to be incorrectly marked as "not available" (None != 547 always True).
        """
        # Simulate API response format - nested objects, NOT flat IDs
        api_response = {
            'id': 303,
            'season': 13,
            'rank': 1,
            'team': {
                'id': 548,
                'abbrev': 'WV',
                'sname': 'Black Bears',
                'lname': 'West Virginia Black Bears',
                'season': 13
            },
            'player': {
                'id': 12843,
                'name': 'George Springer',
                'wara': 0.31,
                'image': 'https://example.com/springer.png',
                'season': 13,
                'pos_1': 'CF',
                # Note: NO flat team_id here - it's nested in 'team' below
                'team': {
                    'id': 547,  # Free Agent team
                    'abbrev': 'FA',
                    'sname': 'Free Agents',
                    'lname': 'Free Agents',
                    'season': 13
                }
            }
        }

        # Create DraftList using from_api_data (what BaseService calls)
        draft_entry = DraftList.from_api_data(api_response)

        # Verify nested objects are created
        assert draft_entry.team is not None
        assert draft_entry.player is not None

        # CRITICAL: player.team_id must be extracted from nested team object
        assert draft_entry.player.team_id == 547, \
            f"player.team_id should be 547 (FA), got {draft_entry.player.team_id}"

        # Verify the nested team object is also populated
        assert draft_entry.player.team is not None
        assert draft_entry.player.team.id == 547
        assert draft_entry.player.team.abbrev == 'FA'

        # Verify DraftList's own team data
        assert draft_entry.team.id == 548
        assert draft_entry.team.abbrev == 'WV'
        assert draft_entry.team_id == 548  # Property from nested team


class TestModelCoverageExtras:
    """Additional model coverage tests."""
    
    def test_base_model_from_api_data_validation(self):
        """Test from_api_data with various edge cases."""
        from models.base import SBABaseModel
        
        # Test with empty data raises ValueError
        with pytest.raises(ValueError, match="Cannot create SBABaseModel from empty data"):
            SBABaseModel.from_api_data({})
        
        # Test with None raises ValueError
        with pytest.raises(ValueError, match="Cannot create SBABaseModel from empty data"):
            SBABaseModel.from_api_data(None)
    
    def test_player_positions_comprehensive(self):
        """Test player positions property with all position variations."""
        player_data = {
            'id': 201,
            'name': 'Multi-Position Player',
            'wara': 3.0,
            'season': 12,
            'team_id': 5,
            'image': 'https://example.com/player.jpg',
            'pos_1': 'C',
            'pos_2': '1B',
            'pos_3': '3B',
            'pos_4': None,  # Test None handling
            'pos_5': 'DH',
            'pos_6': 'OF',
            'pos_7': None,  # Another None
            'pos_8': 'SS'
        }
        player = Player.from_api_data(player_data)
        
        positions = player.positions
        assert 'C' in positions
        assert '1B' in positions
        assert '3B' in positions
        assert 'DH' in positions
        assert 'OF' in positions
        assert 'SS' in positions
        assert len(positions) == 6  # Should exclude None values
        assert None not in positions
    
    def test_player_is_pitcher_variations(self):
        """Test is_pitcher property with different positions."""
        test_cases = [
            ('SP', True),   # Starting pitcher
            ('RP', True),   # Relief pitcher
            ('P', True),    # Generic pitcher
            ('C', False),   # Catcher
            ('1B', False),  # First base
            ('OF', False),  # Outfield
            ('DH', False),  # Designated hitter
        ]
        
        for position, expected in test_cases:
            player_data = {
                'id': 300 + ord(position[0]),  # Generate unique IDs based on position
                'name': f'Test {position}',
                'wara': 2.0,
                'season': 12,
                'team_id': 5,
                'image': 'https://example.com/player.jpg',
                'pos_1': position,
            }
            player = Player.from_api_data(player_data)
            assert player.is_pitcher == expected, f"Position {position} should return {expected}"
            assert player.primary_position == position