"""
Tests for Transaction model

Validates transaction model creation, validation, and business logic.
"""
import pytest
import copy
from datetime import datetime

from models.transaction import Transaction, RosterValidation
from models.player import Player
from models.team import Team


class TestTransaction:
    """Test Transaction model functionality."""
    
    def test_transaction_creation_from_minimal_api_data(self):
        """Test creating transaction from minimal API data."""
        # Create minimal test data matching actual API structure
        player_data = {
            'id': 12472,
            'name': 'Test Player',
            'wara': 2.47,
            'season': 12,
            'pos_1': 'LF'
        }
        
        team_data = {
            'id': 508,
            'abbrev': 'NYD', 
            'sname': 'Diamonds',
            'lname': 'New York Diamonds',
            'season': 12
        }
        
        transaction_data = {
            'id': 27787,
            'week': 10,
            'season': 12,
            'moveid': 'Season-012-Week-10-19-13:04:41',
            'player': player_data,
            'oldteam': team_data.copy(),
            'newteam': {**team_data, 'id': 499, 'abbrev': 'WV', 'sname': 'Black Bears', 'lname': 'West Virginia Black Bears'},
            'cancelled': False,
            'frozen': False
        }
        
        transaction = Transaction.from_api_data(transaction_data)
        
        assert transaction.id == 27787
        assert transaction.week == 10
        assert transaction.season == 12
        assert transaction.moveid == 'Season-012-Week-10-19-13:04:41'
        assert transaction.player.name == 'Test Player'
        assert transaction.oldteam.abbrev == 'NYD'
        assert transaction.newteam.abbrev == 'WV'
        assert transaction.cancelled is False
        assert transaction.frozen is False
    
    def test_transaction_creation_from_complete_api_data(self):
        """Test creating transaction from complete API data structure."""
        complete_data = {
            'id': 27787,
            'week': 10,
            'player': {
                'id': 12472,
                'name': 'Yordan Alvarez',
                'wara': 2.47,
                'image': 'https://example.com/image.png',
                'image2': None,
                'team': {
                    'id': 508,
                    'abbrev': 'NYD',
                    'sname': 'Diamonds', 
                    'lname': 'New York Diamonds',
                    'season': 12
                },
                'season': 12,
                'pitcher_injury': None,
                'pos_1': 'LF',
                'pos_2': None,
                'last_game': None,
                'il_return': None,
                'demotion_week': 1,
                'headshot': None,
                'strat_code': 'Alvarez,Y',
                'bbref_id': 'alvaryo01',
                'injury_rating': '1p65'
            },
            'oldteam': {
                'id': 508,
                'abbrev': 'NYD',
                'sname': 'Diamonds',
                'lname': 'New York Diamonds',
                'season': 12
            },
            'newteam': {
                'id': 499,
                'abbrev': 'WV', 
                'sname': 'Black Bears',
                'lname': 'West Virginia Black Bears',
                'season': 12
            },
            'season': 12,
            'moveid': 'Season-012-Week-10-19-13:04:41',
            'cancelled': False,
            'frozen': False
        }
        
        transaction = Transaction.from_api_data(complete_data)
        
        assert transaction.id == 27787
        assert transaction.player.name == 'Yordan Alvarez'
        assert transaction.player.wara == 2.47
        assert transaction.player.bbref_id == 'alvaryo01'
        assert transaction.oldteam.lname == 'New York Diamonds'
        assert transaction.newteam.lname == 'West Virginia Black Bears'
    
    def test_transaction_status_properties(self):
        """Test transaction status property logic."""
        base_data = self._create_base_transaction_data()
        
        # Test pending transaction (not frozen, not cancelled)
        pending_data = {**base_data, 'cancelled': False, 'frozen': False}
        pending_transaction = Transaction.from_api_data(pending_data)
        
        assert pending_transaction.is_pending is True
        assert pending_transaction.is_frozen is False
        assert pending_transaction.is_cancelled is False
        assert pending_transaction.status_text == 'Pending'
        assert pending_transaction.status_emoji == '⏳'
        
        # Test frozen transaction
        frozen_data = {**base_data, 'cancelled': False, 'frozen': True}
        frozen_transaction = Transaction.from_api_data(frozen_data)
        
        assert frozen_transaction.is_pending is False
        assert frozen_transaction.is_frozen is True
        assert frozen_transaction.is_cancelled is False
        assert frozen_transaction.status_text == 'Frozen'
        assert frozen_transaction.status_emoji == '❄️'
        
        # Test cancelled transaction
        cancelled_data = {**base_data, 'cancelled': True, 'frozen': False}
        cancelled_transaction = Transaction.from_api_data(cancelled_data)
        
        assert cancelled_transaction.is_pending is False
        assert cancelled_transaction.is_frozen is False
        assert cancelled_transaction.is_cancelled is True
        assert cancelled_transaction.status_text == 'Cancelled'
        assert cancelled_transaction.status_emoji == '❌'
    
    def test_transaction_move_description(self):
        """Test move description generation."""
        transaction_data = self._create_base_transaction_data()
        transaction = Transaction.from_api_data(transaction_data)
        
        expected_description = 'Test Player: NYD → WV'
        assert transaction.move_description == expected_description
    
    def test_transaction_string_representation(self):
        """Test transaction string representation."""
        transaction_data = self._create_base_transaction_data()
        transaction = Transaction.from_api_data(transaction_data)
        
        expected_str = '📋 Week 10: Test Player: NYD → WV - ⏳ Pending'
        assert str(transaction) == expected_str
    
    def test_major_league_move_detection(self):
        """Test major league move detection logic."""
        base_data = self._create_base_transaction_data()
        
        # Test major league to major league (should be True)
        ml_to_ml_data = copy.deepcopy(base_data)
        ml_to_ml = Transaction.from_api_data(ml_to_ml_data)
        assert ml_to_ml.is_major_league_move is True
        
        # Test major league to minor league (should be True)
        ml_to_minor_data = copy.deepcopy(base_data)
        ml_to_minor_data['newteam']['abbrev'] = 'WVMiL'
        ml_to_minor = Transaction.from_api_data(ml_to_minor_data)
        assert ml_to_minor.is_major_league_move is True
        
        # Test minor league to major league (should be True)
        minor_to_ml_data = copy.deepcopy(base_data)
        minor_to_ml_data['oldteam']['abbrev'] = 'NYDMiL'
        minor_to_ml = Transaction.from_api_data(minor_to_ml_data)
        assert minor_to_ml.is_major_league_move is True
        
        # Test FA to major league (should be True)
        fa_to_ml_data = copy.deepcopy(base_data)
        fa_to_ml_data['oldteam']['abbrev'] = 'FA'
        fa_to_ml = Transaction.from_api_data(fa_to_ml_data)
        assert fa_to_ml.is_major_league_move is True
        
        # Test major league to FA (should be True)
        ml_to_fa_data = copy.deepcopy(base_data)
        ml_to_fa_data['newteam']['abbrev'] = 'FA'
        ml_to_fa = Transaction.from_api_data(ml_to_fa_data)
        assert ml_to_fa.is_major_league_move is True
        
        # Test minor league to minor league (should be False)
        minor_to_minor_data = copy.deepcopy(base_data)
        minor_to_minor_data['oldteam']['abbrev'] = 'NYDMiL'
        minor_to_minor_data['newteam']['abbrev'] = 'WVMiL'
        minor_to_minor = Transaction.from_api_data(minor_to_minor_data)
        assert minor_to_minor.is_major_league_move is False
        
        # Test FA to FA (should be False - shouldn't happen but test edge case)
        fa_to_fa_data = copy.deepcopy(base_data)
        fa_to_fa_data['oldteam']['abbrev'] = 'FA'
        fa_to_fa_data['newteam']['abbrev'] = 'FA'
        fa_to_fa = Transaction.from_api_data(fa_to_fa_data)
        assert fa_to_fa.is_major_league_move is False
    
    def test_transaction_validation_errors(self):
        """Test transaction model validation with invalid data."""
        # Test missing required fields
        with pytest.raises(Exception):  # Pydantic validation error
            Transaction.from_api_data({})
        
        with pytest.raises(Exception):  # Missing player
            Transaction.from_api_data({
                'id': 1,
                'week': 10,
                'season': 12,
                'moveid': 'test'
            })
    
    def _create_base_transaction_data(self):
        """Create base transaction data for testing."""
        return {
            'id': 27787,
            'week': 10,
            'season': 12,
            'moveid': 'Season-012-Week-10-19-13:04:41',
            'player': {
                'id': 12472,
                'name': 'Test Player',
                'wara': 2.47,
                'season': 12,
                'pos_1': 'LF'
            },
            'oldteam': {
                'id': 508,
                'abbrev': 'NYD',
                'sname': 'Diamonds',
                'lname': 'New York Diamonds', 
                'season': 12
            },
            'newteam': {
                'id': 499,
                'abbrev': 'WV',
                'sname': 'Black Bears',
                'lname': 'West Virginia Black Bears',
                'season': 12
            },
            'cancelled': False,
            'frozen': False
        }


class TestRosterValidation:
    """Test RosterValidation model functionality."""
    
    def test_roster_validation_creation(self):
        """Test creating roster validation instance."""
        validation = RosterValidation(
            is_legal=True,
            total_players=25,
            active_players=25,
            il_players=0,
            total_sWAR=125.5
        )
        
        assert validation.is_legal is True
        assert validation.total_players == 25
        assert validation.active_players == 25
        assert validation.il_players == 0
        assert validation.total_sWAR == 125.5
        assert validation.has_issues is False
    
    def test_roster_validation_with_errors(self):
        """Test roster validation with errors."""
        validation = RosterValidation(
            is_legal=False,
            errors=['Too many players on roster', 'Invalid player position'],
            warnings=['Low WARA total'],
            total_players=30,
            active_players=28,
            il_players=2,
            total_sWAR=95.2
        )
        
        assert validation.is_legal is False
        assert len(validation.errors) == 2
        assert len(validation.warnings) == 1
        assert validation.has_issues is True
        assert validation.status_emoji == '❌'
    
    def test_roster_validation_with_warnings_only(self):
        """Test roster validation with warnings but no errors."""
        validation = RosterValidation(
            is_legal=True,
            warnings=['Roster could use more depth'],
            total_players=23,
            active_players=23,
            total_sWAR=110.0
        )
        
        assert validation.is_legal is True
        assert len(validation.errors) == 0
        assert len(validation.warnings) == 1
        assert validation.has_issues is True
        assert validation.status_emoji == '⚠️'
    
    def test_roster_validation_perfect(self):
        """Test perfectly valid roster."""
        validation = RosterValidation(
            is_legal=True,
            total_players=25,
            active_players=25,
            total_sWAR=130.0
        )
        
        assert validation.is_legal is True
        assert len(validation.errors) == 0
        assert len(validation.warnings) == 0
        assert validation.has_issues is False
        assert validation.status_emoji == '✅'
    
    def test_roster_validation_defaults(self):
        """Test roster validation with default values."""
        validation = RosterValidation(is_legal=True)
        
        assert validation.total_players == 0
        assert validation.active_players == 0
        assert validation.il_players == 0
        assert validation.minor_league_players == 0
        assert validation.total_sWAR == 0.0
        assert len(validation.errors) == 0
        assert len(validation.warnings) == 0