# Testing Guide for Discord Bot v2.0

This document provides guidance on testing strategies, patterns, and lessons learned during the development of the Discord Bot v2.0 test suite.

## Test Structure Overview

```
tests/
├── README.md                           # This guide
├── __init__.py                        # Test package
├── fixtures/                          # Test data fixtures
├── test_config.py                     # Configuration tests
├── test_constants.py                  # Constants tests
├── test_exceptions.py                 # Exception handling tests
├── test_models.py                     # Pydantic model tests
├── test_services.py                   # Service layer tests (25 tests)
└── test_api_client_with_aioresponses.py   # API client HTTP tests (19 tests)
```

**Total Coverage**: 44 comprehensive tests covering all core functionality.

## Key Testing Patterns

### 1. HTTP Testing with aioresponses

**✅ Recommended Approach:**
```python
from aioresponses import aioresponses

@pytest.mark.asyncio
async def test_api_request(api_client):
    with aioresponses() as m:
        m.get(
            "https://api.example.com/v3/players/1",
            payload={"id": 1, "name": "Test Player"},
            status=200
        )
        
        result = await api_client.get("players", object_id=1)
        assert result["name"] == "Test Player"
```

**❌ Avoid Complex AsyncMock:**
We initially tried mocking aiohttp's async context managers manually with AsyncMock, which led to complex, brittle tests that failed due to coroutine protocol issues.

### 2. Service Layer Testing

**✅ Complete Model Data:**
Always provide complete model data that satisfies Pydantic validation:

```python
def create_player_data(self, player_id: int, name: str, **kwargs):
    """Create complete player data for testing."""
    base_data = {
        'id': player_id,
        'name': name,
        'wara': 2.5,                    # Required field
        'season': 12,                   # Required field
        'team_id': team_id,            # Required field
        'image': f'https://example.com/player{player_id}.jpg',  # Required field
        'pos_1': position,             # Required field
    }
    base_data.update(kwargs)
    return base_data
```

**❌ Partial Model Data:**
Providing incomplete data leads to Pydantic validation errors that are hard to debug.

### 3. API Response Format Testing

Our API returns responses in this format:
```json
{
  "count": 25,
  "players": [...]
}
```

**✅ Test Both Formats:**
```python
# Test the count + list format
mock_data = {
    "count": 2,
    "players": [player1_data, player2_data]
}

# Test single object format (for get_by_id)
mock_data = player1_data
```

## Lessons Learned

### 1. aiohttp Testing Complexity

**Problem**: Manually mocking aiohttp's async context managers is extremely complex and error-prone.

**Solution**: Use `aioresponses` library specifically designed for this purpose.

**Code Example**:
```bash
pip install aioresponses>=0.7.4
```

```python
# Clean, readable, reliable
with aioresponses() as m:
    m.get("https://api.example.com/endpoint", payload=expected_data)
    result = await client.get("endpoint")
```

### 2. Pydantic Model Validation in Tests

**Problem**: Our models have many required fields. Partial test data causes validation errors.

**Solution**: Create helper functions that generate complete, valid model data.

**Pattern**:
```python
def create_model_data(self, id: int, name: str, **overrides):
    """Create complete model data with all required fields."""
    base_data = {
        # All required fields with sensible defaults
        'id': id,
        'name': name,
        'required_field1': 'default_value',
        'required_field2': 42,
    }
    base_data.update(overrides)
    return base_data
```

### 3. Async Context Manager Mocking

**Problem**: This doesn't work reliably:
```python
# ❌ Brittle and complex
mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
mock_session.get.return_value.__aexit__ = AsyncMock(return_value=None)
```

**Solution**: Use specialized libraries or patch at higher levels:
```python
# ✅ Clean with aioresponses
with aioresponses() as m:
    m.get("url", payload=data)
    # Test the actual HTTP call
```

### 4. Service Layer Mocking Strategy

**✅ Mock at the Client Level:**
```python
@pytest.fixture
def player_service_instance(self, mock_client):
    service = PlayerService()
    service._client = mock_client  # Inject mock client
    return service
```

This allows testing service logic while controlling API responses.

### 5. Global Instance Testing

**Pattern for Singleton Services:**
```python
def test_global_service_independence():
    service1 = PlayerService()
    service2 = PlayerService()
    
    # Should be different instances
    assert service1 is not service2
    # But same configuration
    assert service1.endpoint == service2.endpoint
```

## Testing Anti-Patterns to Avoid

### 1. ❌ Incomplete Test Data
```python
# This will fail Pydantic validation
mock_data = {'id': 1, 'name': 'Test'}  # Missing required fields
```

### 2. ❌ Complex Manual Mocking
```python
# Avoid complex AsyncMock setups for HTTP clients
mock_response = AsyncMock()
mock_response.__aenter__ = AsyncMock(...)  # Too complex
```

### 3. ❌ Testing Implementation Details
```python
# Don't test internal method calls
assert mock_client.get.call_count == 2  # Brittle
# Instead test behavior
assert len(result) == 2  # What matters to users
```

### 4. ❌ Mixing Test Concerns
```python
# Don't test multiple unrelated things in one test
def test_everything():  # Too broad
    # Test HTTP client
    # Test service logic  
    # Test model validation
    # All in one test - hard to debug
```

## Best Practices Summary

### ✅ Do:
1. **Use aioresponses** for HTTP client testing
2. **Create complete model data** with helper functions
3. **Test behavior, not implementation** details
4. **Mock at appropriate levels** (client level for services)
5. **Use realistic data** that matches actual API responses
6. **Test error scenarios** as thoroughly as happy paths
7. **Keep tests focused** on single responsibilities

### ❌ Don't:
1. **Manually mock async context managers** - use specialized tools
2. **Use partial model data** - always provide complete valid data
3. **Test implementation details** - focus on behavior
4. **Mix multiple concerns** in single tests
5. **Ignore error paths** - test failure scenarios
6. **Skip integration scenarios** - test realistic workflows

## Running Tests

```bash
# Run all tests
pytest

# Run specific test files
pytest tests/test_services.py
pytest tests/test_api_client_with_aioresponses.py

# Run with coverage
pytest --cov=api --cov=services

# Run with verbose output
pytest -v

# Run specific test patterns
pytest -k "test_player" -v
```

## Adding New Tests

### For New API Endpoints:
1. Add aioresponses-based tests in `test_api_client_with_aioresponses.py`
2. Follow existing patterns for success/error scenarios

### For New Services:
1. Add service tests in `test_services.py`
2. Create helper functions for complete model data
3. Mock at the client level, not HTTP level

### For New Models:
1. Add model tests in `test_models.py`
2. Test validation, serialization, and edge cases
3. Use `from_api_data()` pattern for realistic data

## Dependencies

Core testing dependencies in `requirements.txt`:
```
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-mock>=3.10.0
aioresponses>=0.7.4        # Essential for HTTP testing
```

## Troubleshooting Common Issues

### "coroutine object does not support async context manager"
- **Cause**: Manually mocking aiohttp async context managers
- **Solution**: Use aioresponses instead of manual mocking

### "ValidationError: Field required"
- **Cause**: Incomplete test data for Pydantic models
- **Solution**: Use helper functions that provide all required fields

### "AssertionError: Regex pattern did not match"
- **Cause**: Exception message doesn't match expected pattern
- **Solution**: Check actual error message and adjust test expectations

### Tests hanging or timing out
- **Cause**: Unclosed aiohttp sessions or improper async handling
- **Solution**: Ensure proper session cleanup and use async context managers

This guide should help maintain high-quality, reliable tests as the project grows!