"""
Unit tests for validation module
"""
import pytest
from validation import (
    validate_symbol, sanitize_string, validate_float, validate_int,
    validate_date, validate_date_range, validate_required_fields, validate_strategy,
    create_validation_error
)


class TestSymbolValidation:
    """Tests for symbol validation"""
    
    def test_valid_symbol(self):
        """Test valid symbol formats"""
        assert validate_symbol('RELIANCE.NS') == ('RELIANCE.NS', None)
        assert validate_symbol('TCS.NS') == ('TCS.NS', None)
        assert validate_symbol('INFY.NS') == ('INFY.NS', None)
    
    def test_invalid_symbol_too_long(self):
        """Test symbol too long"""
        symbol, error = validate_symbol('A' * 21)
        assert symbol is None
        assert 'exceeds maximum length' in error
    
    def test_invalid_symbol_chars(self):
        """Test invalid characters in symbol"""
        symbol, error = validate_symbol('REL@NCE')
        assert symbol is None
        assert 'Invalid characters' in error
    
    def test_empty_symbol(self):
        """Test empty symbol"""
        symbol, error = validate_symbol('')
        assert symbol is None
        assert 'Symbol is required' in error


class TestStringValidation:
    """Tests for string sanitization"""
    
    def test_sanitize_basic_string(self):
        """Test basic string sanitization"""
        result, error = sanitize_string('Hello World', max_length=20)
        assert result == 'Hello World'
        assert error is None
    
    def test_sanitize_with_html(self):
        """Test HTML removal"""
        result, error = sanitize_string('<script>alert("xss")</script>Hello', allow_html=False)
        assert '<script>' not in result
        assert error is None
    
    def test_sanitize_too_long(self):
        """Test string exceeding max length"""
        result, error = sanitize_string('A' * 101, max_length=100)
        assert result is None
        assert 'exceeds maximum length' in error
    
    def test_sanitize_xss_patterns(self):
        """Test XSS pattern detection"""
        result, error = sanitize_string('javascript:alert(1)')
        assert result is None
        assert 'potentially malicious content' in error


class TestNumericValidation:
    """Tests for numeric validation"""
    
    def test_validate_float_valid(self):
        """Test valid float validation"""
        assert validate_float('123.45', 'price') == (123.45, None)
        assert validate_float('0.01', 'price') == (0.01, None)
    
    def test_validate_float_invalid(self):
        """Test invalid float"""
        value, error = validate_float('abc', 'price')
        assert value is None
        assert 'must be a number' in error
    
    def test_validate_float_range(self):
        """Test float range validation"""
        value, error = validate_float('150', 'price', min_val=0, max_val=100)
        assert value is None
        assert 'must be between' in error
    
    def test_validate_int_valid(self):
        """Test valid integer"""
        assert validate_int('10', 'quantity') == (10, None)
    
    def test_validate_int_invalid(self):
        """Test invalid integer"""
        value, error = validate_int('10.5', 'quantity')
        assert value is None
        assert 'must be an integer' in error


class TestDateValidation:
    """Tests for date validation"""
    
    def test_validate_date_valid(self):
        """Test valid date"""
        result, error = validate_date('2024-01-15', 'entry_date')
        assert result == '2024-01-15'
        assert error is None
    
    def test_validate_date_invalid_format(self):
        """Test invalid date format"""
        result, error = validate_date('15/01/2024', 'entry_date')
        assert result is None
        assert 'Invalid date format' in error
    
    def test_validate_date_range_valid(self):
        """Test valid date range"""
        result, error = validate_date_range('2024-01-01', '2024-12-31')
        assert error is None
    
    def test_validate_date_range_invalid(self):
        """Test end date before start date"""
        result, error = validate_date_range('2024-12-31', '2024-01-01')
        assert result is None
        assert 'End date must be after start date' in error


class TestStrategyValidation:
    """Tests for strategy validation"""
    
    def test_valid_strategy(self):
        """Test valid strategy"""
        result, error = validate_strategy('rsi_macd')
        assert result == 'rsi_macd'
        assert error is None
    
    def test_invalid_strategy(self):
        """Test invalid strategy"""
        result, error = validate_strategy('invalid_strategy')
        assert result is None
        assert 'Invalid strategy' in error


class TestRequiredFields:
    """Tests for required fields validation"""
    
    def test_all_fields_present(self):
        """Test with all required fields"""
        data = {'name': 'John', 'email': 'john@example.com'}
        result, errors = validate_required_fields(data, ['name', 'email'])
        assert result is True
        assert errors == []
    
    def test_missing_fields(self):
        """Test with missing fields"""
        data = {'name': 'John'}
        result, errors = validate_required_fields(data, ['name', 'email'])
        assert result is False
        assert 'email' in errors


class TestValidationError:
    """Tests for validation error helper"""
    
    def test_create_validation_error(self):
        """Test error creation"""
        error = create_validation_error('symbol', 'Invalid symbol format')
        assert error['field'] == 'symbol'
        assert error['message'] == 'Invalid symbol format'
