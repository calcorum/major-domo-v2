"""
Tests for BaseService functionality
"""
import pytest
from unittest.mock import AsyncMock

from services.base_service import BaseService
from models.base import SBABaseModel
from exceptions import APIException


class MockModel(SBABaseModel):
    """Mock model for testing BaseService."""
    id: int
    name: str
    value: int = 100


class TestBaseService:
    """Test BaseService functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock API client."""
        client = AsyncMock()
        return client
    
    @pytest.fixture
    def base_service(self, mock_client):
        """Create BaseService instance for testing."""
        service = BaseService(MockModel, 'mocks', client=mock_client)
        return service
    
    @pytest.mark.asyncio
    async def test_init(self):
        """Test service initialization."""
        service = BaseService(MockModel, 'test_endpoint')
        assert service.model_class == MockModel
        assert service.endpoint == 'test_endpoint'
        assert service._client is None
    
    @pytest.mark.asyncio
    async def test_get_by_id_success(self, base_service, mock_client):
        """Test successful get_by_id."""
        mock_data = {'id': 1, 'name': 'Test', 'value': 200}
        mock_client.get.return_value = mock_data
        
        result = await base_service.get_by_id(1)
        
        assert isinstance(result, MockModel)
        assert result.id == 1
        assert result.name == 'Test'
        assert result.value == 200
        mock_client.get.assert_called_once_with('mocks', object_id=1)
    
    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, base_service, mock_client):
        """Test get_by_id when object not found."""
        mock_client.get.return_value = None
        
        result = await base_service.get_by_id(999)
        
        assert result is None
        mock_client.get.assert_called_once_with('mocks', object_id=999)
    
    @pytest.mark.asyncio
    async def test_get_all_with_count(self, base_service, mock_client):
        """Test get_all with count response format."""
        mock_data = {
            'count': 2,
            'mocks': [
                {'id': 1, 'name': 'Test1', 'value': 100},
                {'id': 2, 'name': 'Test2', 'value': 200}
            ]
        }
        mock_client.get.return_value = mock_data
        
        result, count = await base_service.get_all()
        
        assert len(result) == 2
        assert count == 2
        assert all(isinstance(item, MockModel) for item in result)
        mock_client.get.assert_called_once_with('mocks', params=None)
    
    @pytest.mark.asyncio
    async def test_get_all_items_convenience(self, base_service, mock_client):
        """Test get_all_items convenience method."""
        mock_data = {
            'count': 1,
            'mocks': [{'id': 1, 'name': 'Test', 'value': 100}]
        }
        mock_client.get.return_value = mock_data
        
        result = await base_service.get_all_items()
        
        assert len(result) == 1
        assert isinstance(result[0], MockModel)
    
    @pytest.mark.asyncio
    async def test_create_success(self, base_service, mock_client):
        """Test successful object creation."""
        input_data = {'name': 'New Item', 'value': 300}
        response_data = {'id': 3, 'name': 'New Item', 'value': 300}
        mock_client.post.return_value = response_data
        
        result = await base_service.create(input_data)
        
        assert isinstance(result, MockModel)
        assert result.id == 3
        assert result.name == 'New Item'
        mock_client.post.assert_called_once_with('mocks', input_data)
    
    @pytest.mark.asyncio
    async def test_update_success(self, base_service, mock_client):
        """Test successful object update."""
        update_data = {'name': 'Updated'}
        response_data = {'id': 1, 'name': 'Updated', 'value': 100}
        mock_client.put.return_value = response_data
        
        result = await base_service.update(1, update_data)
        
        assert isinstance(result, MockModel)
        assert result.name == 'Updated'
        mock_client.put.assert_called_once_with('mocks', update_data, object_id=1)
    
    @pytest.mark.asyncio
    async def test_delete_success(self, base_service, mock_client):
        """Test successful object deletion."""
        mock_client.delete.return_value = True
        
        result = await base_service.delete(1)
        
        assert result is True
        mock_client.delete.assert_called_once_with('mocks', object_id=1)
    
    
    @pytest.mark.asyncio
    async def test_get_by_field(self, base_service, mock_client):
        """Test get_by_field functionality."""
        mock_data = {
            'count': 1,
            'mocks': [{'id': 1, 'name': 'Test', 'value': 100}]
        }
        mock_client.get.return_value = mock_data
        
        result = await base_service.get_by_field('name', 'Test')
        
        assert len(result) == 1
        mock_client.get.assert_called_once_with('mocks', params=[('name', 'Test')])
    
    def test_extract_items_and_count_standard_format(self, base_service):
        """Test response parsing for standard format."""
        data = {
            'count': 3,
            'mocks': [
                {'id': 1, 'name': 'Test1'},
                {'id': 2, 'name': 'Test2'},
                {'id': 3, 'name': 'Test3'}
            ]
        }
        
        items, count = base_service._extract_items_and_count_from_response(data)
        
        assert len(items) == 3
        assert count == 3
        assert items[0]['name'] == 'Test1'
    
    def test_extract_items_and_count_single_object(self, base_service):
        """Test response parsing for single object."""
        data = {'id': 1, 'name': 'Single'}
        
        items, count = base_service._extract_items_and_count_from_response(data)
        
        assert len(items) == 1
        assert count == 1
        assert items[0] == data
    
    def test_extract_items_and_count_direct_list(self, base_service):
        """Test response parsing for direct list."""
        data = [
            {'id': 1, 'name': 'Test1'},
            {'id': 2, 'name': 'Test2'}
        ]
        
        items, count = base_service._extract_items_and_count_from_response(data)
        
        assert len(items) == 2
        assert count == 2


class TestBaseServiceExtras:
    """Additional coverage tests for BaseService edge cases."""
    
    @pytest.mark.asyncio
    async def test_base_service_additional_methods(self):
        """Test additional BaseService methods for coverage."""
        from services.base_service import BaseService
        from models.base import SBABaseModel
        
        class TestModel(SBABaseModel):
            name: str
            value: int = 100
        
        mock_client = AsyncMock()
        service = BaseService(TestModel, 'test', client=mock_client)
        
        
        # Test count method
        mock_client.reset_mock()
        mock_client.get.return_value = {'count': 42, 'test': []}
        count = await service.count(params=[('active', 'true')])
        assert count == 42
        
        # Test update_from_model with ID
        mock_client.reset_mock()
        model = TestModel(id=1, name="Updated", value=300)
        mock_client.put.return_value = {"id": 1, "name": "Updated", "value": 300}
        result = await service.update_from_model(model)
        assert result.name == "Updated"
        
        # Test update_from_model without ID
        model_no_id = TestModel(name="Test")
        with pytest.raises(ValueError, match="Cannot update TestModel without ID"):
            await service.update_from_model(model_no_id)
    
    def test_base_service_response_parsing_edge_cases(self):
        """Test edge cases in response parsing."""
        from services.base_service import BaseService
        from models.base import SBABaseModel
        
        class TestModel(SBABaseModel):
            name: str
        
        service = BaseService(TestModel, 'test')
        
        # Test with 'items' field
        data = {'count': 2, 'items': [{'name': 'Item1'}, {'name': 'Item2'}]}
        items, count = service._extract_items_and_count_from_response(data)
        assert len(items) == 2
        assert count == 2
        
        # Test with 'data' field
        data = {'count': 1, 'data': [{'name': 'DataItem'}]}
        items, count = service._extract_items_and_count_from_response(data)
        assert len(items) == 1
        assert count == 1
        
        # Test with count but no recognizable list field
        data = {'count': 5, 'unknown_field': [{'name': 'Item'}]}
        items, count = service._extract_items_and_count_from_response(data)
        assert len(items) == 0
        assert count == 5
        
        # Test with unexpected data type
        items, count = service._extract_items_and_count_from_response("unexpected")
        assert len(items) == 0
        assert count == 0