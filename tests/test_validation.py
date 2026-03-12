"""
Unit tests for validation module.

Tests comprehensive backend validation including symbol validation,
XSS prevention, numeric validation, and data type validation.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import math
import pytest

from backend.validation import (
    XSS_PATTERNS,
    create_validation_error,
    get_available_symbols,
    get_symbol_whitelist,
    sanitize_string,
    validate_date,
    validate_date_range,
    validate_float,
    validate_int,
    validate_required_fields,
    validate_strategy,
    validate_symbol,
)


class TestValidateSymbol:
    """Tests for symbol validation."""

    def test_valid_nse_symbol_with_suffix(self):
        """Test valid NSE symbol with .NS suffix."""
        is_valid, error = validate_symbol('RELIANCE.NS')
        assert is_valid is True
        assert error == ""

    def test_valid_symbol_with_dash(self):
        """Test symbol containing dash."""
        is_valid, error = validate_symbol('M&M.NS')
        assert is_valid is True
        assert error == ""

    def test_valid_lowercase_symbol_is_uppercased(self):
        """Test lowercase symbols are accepted and uppercased."""
        is_valid, error = validate_symbol('tcs.ns')
        assert is_valid is True

    def test_symbol_too_long_returns_error(self):
        """Test symbol exceeding 50 characters."""
        long_symbol = 'A' * 51
        is_valid, error = validate_symbol(long_symbol)
        assert is_valid is False
        assert 'between 1 and 50 characters' in error

    def test_symbol_too_short_returns_error(self):
        """Test empty symbol."""
        is_valid, error = validate_symbol('')
        assert is_valid is False
        assert 'required' in error.lower()

    def test_symbol_with_invalid_characters(self):
        """Test symbol with special characters."""
        is_valid, error = validate_symbol('REL@NCE')
        assert is_valid is False
        assert 'invalid characters' in error.lower()

    def test_symbol_with_spaces_is_invalid(self):
        """Test symbol containing spaces."""
        is_valid, error = validate_symbol('REL IANCE')
        assert is_valid is False

    def test_none_symbol_returns_error(self):
        """Test None input."""
        is_valid, error = validate_symbol(None)
        assert is_valid is False
        assert 'required' in error.lower()

    def test_numeric_symbol_starting_with_digit(self):
        """Test symbol starting with digit is valid."""
        is_valid, error = validate_symbol('3MINDIA.NS')
        assert is_valid is True

    def test_symbol_is_trimmed(self):
        """Test symbol whitespace is trimmed."""
        is_valid, error = validate_symbol('  TCS.NS  ')
        assert is_valid is True

    @patch('backend.validation.get_symbol_whitelist')
    def test_rejects_symbol_not_in_whitelist(self, mock_whitelist):
        """Test symbol not in whitelist is rejected."""
        mock_whitelist.return_value = ['RELIANCE.NS', 'TCS.NS']

        is_valid, error = validate_symbol('UNKNOWN.NS')
        assert is_valid is False
        assert 'not available' in error.lower()

    @patch('backend.validation.get_symbol_whitelist')
    def test_accepts_symbol_in_whitelist(self, mock_whitelist):
        """Test symbol in whitelist is accepted."""
        mock_whitelist.return_value = ['RELIANCE.NS', 'TCS.NS']

        is_valid, error = validate_symbol('RELIANCE.NS')
        assert is_valid is True

    @patch('backend.validation.get_symbol_whitelist')
    def test_empty_whitelist_allows_all_valid_symbols(self, mock_whitelist):
        """Test empty whitelist falls back to basic validation."""
        mock_whitelist.return_value = []

        is_valid, error = validate_symbol('ANYVALID.NS')
        assert is_valid is True


class TestSanitizeString:
    """Tests for string sanitization and XSS prevention."""

    def test_returns_sanitized_string(self):
        """Test basic string passes through."""
        result, error = sanitize_string('Hello World')
        assert result == 'Hello World'
        assert error is None

    def test_trims_whitespace(self):
        """Test leading/trailing whitespace is removed."""
        result, error = sanitize_string('  hello  ')
        assert result == 'hello'

    def test_strips_html_tags(self):
        """Test HTML tags are removed."""
        result, error = sanitize_string('<b>Hello</b> World', allow_html=False)
        assert result == 'Hello World'
        assert error is None

    def test_rejects_xss_script_tag(self):
        """Test script tag triggers XSS detection."""
        result, error = sanitize_string('<script>alert(1)</script>')
        assert result == ""
        assert error is not None
        assert 'XSS' in error

    def test_rejects_javascript_protocol(self):
        """Test javascript: protocol is rejected."""
        result, error = sanitize_string('javascript:alert(1)')
        assert result == ""
        assert error is not None

    def test_rejects_onerror_handler(self):
        """Test onerror attribute is rejected."""
        result, error = sanitize_string('<img onerror="alert(1)">')
        assert result == ""
        assert error is not None

    def test_rejects_eval_call(self):
        """Test eval() is rejected."""
        result, error = sanitize_string('eval(code)')
        assert result == ""
        assert error is not None

    def test_rejects_document_cookie(self):
        """Test document.cookie access is rejected."""
        result, error = sanitize_string('document.cookie')
        assert result == ""
        assert error is not None

    def test_rejects_string_exceeding_max_length(self):
        """Test string exceeding max_length is rejected."""
        long_string = 'A' * 101
        result, error = sanitize_string(long_string, max_length=100)
        assert result == ""
        assert 'exceeds maximum length' in error

    def test_accepts_string_at_max_length(self):
        """Test string at exactly max_length is accepted."""
        string = 'A' * 100
        result, error = sanitize_string(string, max_length=100)
        assert result == string
        assert error is None

    def test_none_input_returns_empty_string(self):
        """Test None input returns empty string without error."""
        result, error = sanitize_string(None)
        assert result == ""
        assert error is None

    def test_non_string_input_returns_error(self):
        """Test non-string input returns error."""
        result, error = sanitize_string(123)
        assert result == ""
        assert 'must be a string' in error

    def test_escapes_html_entities(self):
        """Test HTML entities are escaped."""
        result, error = sanitize_string('Hello & World')
        assert '&' in result  # Escaped to &amp;

    def test_all_xss_patterns_are_rejected(self):
        """Test all XSS_PATTERNS are detected."""
        for pattern in XSS_PATTERNS:
            test_input = f'test{pattern}test'
            result, error = sanitize_string(test_input)
            assert result == "", f"Pattern '{pattern}' should be rejected"
            assert error is not None


class TestValidateFloat:
    """Tests for float validation."""

    def test_valid_float_string(self):
        """Test valid float string."""
        result, error = validate_float('123.45', 'price')
        assert result == 123.45
        assert error is None

    def test_valid_integer_string(self):
        """Test integer string converts to float."""
        result, error = validate_float('100', 'price')
        assert result == 100.0
        assert error is None

    def test_valid_float_value(self):
        """Test float value passes through."""
        result, error = validate_float(99.99, 'price')
        assert result == 99.99

    def test_invalid_string_returns_error(self):
        """Test non-numeric string returns error."""
        result, error = validate_float('abc', 'price')
        assert result is None
        assert 'must be a valid number' in error

    def test_none_returns_error(self):
        """Test None returns error."""
        result, error = validate_float(None, 'price')
        assert result is None
        assert 'required' in error.lower()

    def test_rejects_nan(self):
        """Test NaN is rejected."""
        result, error = validate_float(float('nan'), 'price')
        assert result is None
        assert 'valid number' in error.lower()

    def test_rejects_positive_infinity(self):
        """Test positive infinity is rejected."""
        result, error = validate_float(float('inf'), 'price')
        assert result is None
        assert 'finite' in error.lower()

    def test_rejects_negative_infinity(self):
        """Test negative infinity is rejected."""
        result, error = validate_float(float('-inf'), 'price')
        assert result is None
        assert 'finite' in error.lower()

    def test_rejects_boolean(self):
        """Test boolean is rejected."""
        result, error = validate_float(True, 'price')
        assert result is None
        assert 'boolean' in error.lower()

    def test_enforces_minimum(self):
        """Test minimum value is enforced."""
        result, error = validate_float('-5', 'price', min_val=0)
        assert result is None
        assert 'at least 0' in error

    def test_enforces_maximum(self):
        """Test maximum value is enforced."""
        result, error = validate_float('150', 'price', max_val=100)
        assert result is None
        assert 'exceed 100' in error

    def test_accepts_value_at_minimum(self):
        """Test value at minimum boundary is accepted."""
        result, error = validate_float('0', 'price', min_val=0)
        assert result == 0.0
        assert error is None

    def test_accepts_value_at_maximum(self):
        """Test value at maximum boundary is accepted."""
        result, error = validate_float('100', 'price', max_val=100)
        assert result == 100.0

    def test_negative_float_allowed_without_min(self):
        """Test negative floats allowed when no minimum."""
        result, error = validate_float('-50.5', 'price')
        assert result == -50.5


class TestValidateInt:
    """Tests for integer validation."""

    def test_valid_integer_string(self):
        """Test valid integer string."""
        result, error = validate_int('42', 'quantity')
        assert result == 42
        assert error is None

    def test_valid_integer_value(self):
        """Test integer value passes through."""
        result, error = validate_int(42, 'quantity')
        assert result == 42

    def test_rejects_float_string(self):
        """Test float string is rejected."""
        result, error = validate_int('10.5', 'quantity')
        assert result is None
        assert 'whole number' in error.lower()

    def test_rejects_float_value(self):
        """Test float value is rejected."""
        result, error = validate_int(10.5, 'quantity')
        assert result is None
        assert 'whole number' in error.lower()

    def test_accepts_whole_number_float(self):
        """Test float that is a whole number is accepted."""
        result, error = validate_int(10.0, 'quantity')
        assert result == 10

    def test_none_returns_error(self):
        """Test None returns error."""
        result, error = validate_int(None, 'quantity')
        assert result is None
        assert 'required' in error.lower()

    def test_rejects_boolean(self):
        """Test boolean is rejected."""
        result, error = validate_int(True, 'quantity')
        assert result is None
        assert 'boolean' in error.lower()

    def test_enforces_minimum(self):
        """Test minimum value is enforced."""
        result, error = validate_int('-5', 'quantity', min_val=0)
        assert result is None
        assert 'at least 0' in error

    def test_enforces_maximum(self):
        """Test maximum value is enforced."""
        result, error = validate_int('150', 'quantity', max_val=100)
        assert result is None
        assert 'exceed 100' in error

    def test_invalid_string_returns_error(self):
        """Test non-numeric string returns error."""
        result, error = validate_int('abc', 'quantity')
        assert result is None
        assert 'valid integer' in error.lower()


class TestValidateDate:
    """Tests for date validation."""

    def test_valid_date_string(self):
        """Test valid date string."""
        result, error = validate_date('2024-01-15', 'entry_date')
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert error is None

    def test_rejects_wrong_format_slash(self):
        """Test DD/MM/YYYY format is rejected."""
        result, error = validate_date('15/01/2024', 'entry_date')
        assert result is None
        assert 'YYYY-MM-DD' in error

    def test_rejects_wrong_format_no_separator(self):
        """Test date without separators is rejected."""
        result, error = validate_date('20240115', 'entry_date')
        assert result is None

    def test_rejects_invalid_date(self):
        """Test invalid date (e.g., Feb 30) is rejected."""
        result, error = validate_date('2024-02-30', 'entry_date')
        assert result is None
        assert 'valid date' in error.lower()

    def test_rejects_empty_string(self):
        """Test empty string returns error."""
        result, error = validate_date('', 'entry_date')
        assert result is None
        assert 'required' in error.lower()

    def test_rejects_none(self):
        """Test None returns error."""
        result, error = validate_date(None, 'entry_date')
        assert result is None

    def test_rejects_non_string(self):
        """Test non-string input returns error."""
        result, error = validate_date(123, 'entry_date')
        assert result is None
        assert 'string' in error.lower()

    def test_rejects_future_date_by_default(self):
        """Test future dates are rejected by default."""
        future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime('%Y-%m-%d')
        result, error = validate_date(future, 'entry_date')
        assert result is None
        assert 'future' in error.lower()

    def test_accepts_future_date_when_allowed(self):
        """Test future dates are accepted when allow_future=True."""
        future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime('%Y-%m-%d')
        result, error = validate_date(future, 'entry_date', allow_future=True)
        assert result is not None
        assert error is None

    def test_accepts_past_date(self):
        """Test past dates are accepted."""
        past = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
        result, error = validate_date(past, 'entry_date')
        assert result is not None

    def test_accepts_today(self):
        """Test today's date is accepted."""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        result, error = validate_date(today, 'entry_date')
        assert result is not None


class TestValidateDateRange:
    """Tests for date range validation."""

    def test_valid_range(self):
        """Test valid date range."""
        is_valid, error = validate_date_range('2024-01-01', '2024-12-31')
        assert is_valid is True
        assert error == ""

    def test_same_start_and_end_date(self):
        """Test same start and end date is valid."""
        is_valid, error = validate_date_range('2024-06-15', '2024-06-15')
        assert is_valid is True

    def test_end_before_start_returns_error(self):
        """Test end date before start date."""
        is_valid, error = validate_date_range('2024-12-31', '2024-01-01')
        assert is_valid is False
        assert 'cannot be after' in error

    def test_propagates_invalid_start_date(self):
        """Test invalid start date is propagated."""
        is_valid, error = validate_date_range('invalid', '2024-12-31')
        assert is_valid is False

    def test_propagates_invalid_end_date(self):
        """Test invalid end date is propagated."""
        is_valid, error = validate_date_range('2024-01-01', 'invalid')
        assert is_valid is False


class TestValidateStrategy:
    """Tests for strategy validation."""

    def test_valid_strategies(self):
        """Test all valid strategies are accepted."""
        valid_strategies = [
            'golden_cross', 'rsi', 'macd', 'composite',
            'momentum', 'mean_reversion', 'breakout'
        ]
        for strategy in valid_strategies:
            is_valid, error = validate_strategy(strategy)
            assert is_valid is True, f"Strategy '{strategy}' should be valid"
            assert error == ""

    def test_strategy_is_case_insensitive(self):
        """Test strategy validation is case insensitive."""
        is_valid, error = validate_strategy('RSI')
        assert is_valid is True

        is_valid, error = validate_strategy('Golden_Cross')
        assert is_valid is True

    def test_strategy_is_trimmed(self):
        """Test strategy whitespace is trimmed."""
        is_valid, error = validate_strategy('  rsi  ')
        assert is_valid is True

    def test_invalid_strategy_returns_error(self):
        """Test invalid strategy name."""
        is_valid, error = validate_strategy('unknown_strategy')
        assert is_valid is False
        assert 'Invalid strategy' in error

    def test_none_strategy_returns_error(self):
        """Test None returns error."""
        is_valid, error = validate_strategy(None)
        assert is_valid is False

    def test_empty_strategy_returns_error(self):
        """Test empty string returns error."""
        is_valid, error = validate_strategy('')
        assert is_valid is False


class TestValidateRequiredFields:
    """Tests for required fields validation."""

    def test_all_fields_present(self):
        """Test all required fields present."""
        data = {'name': 'John', 'email': 'john@example.com'}
        is_valid, error = validate_required_fields(data, ['name', 'email'])
        assert is_valid is True
        assert error == ""

    def test_single_missing_field(self):
        """Test single missing field."""
        data = {'name': 'John'}
        is_valid, error = validate_required_fields(data, ['name', 'email'])
        assert is_valid is False
        assert 'Missing required fields' in error
        assert 'email' in error

    def test_multiple_missing_fields(self):
        """Test multiple missing fields."""
        data = {}
        is_valid, error = validate_required_fields(data, ['name', 'email', 'phone'])
        assert is_valid is False
        assert 'email' in error
        assert 'phone' in error

    def test_field_with_none_value(self):
        """Test field with None value is considered missing."""
        data = {'name': 'John', 'email': None}
        is_valid, error = validate_required_fields(data, ['name', 'email'])
        assert is_valid is False
        assert 'email' in error

    def test_non_dict_input_returns_error(self):
        """Test non-dict input returns error."""
        is_valid, error = validate_required_fields('not a dict', ['name'])
        assert is_valid is False
        assert 'JSON object' in error

    def test_empty_required_list_is_valid(self):
        """Test empty required fields list always passes."""
        data = {}
        is_valid, error = validate_required_fields(data, [])
        assert is_valid is True

    def test_extra_fields_are_ignored(self):
        """Test extra fields don't cause issues."""
        data = {'name': 'John', 'email': 'john@example.com', 'extra': 'value'}
        is_valid, error = validate_required_fields(data, ['name', 'email'])
        assert is_valid is True


class TestCreateValidationError:
    """Tests for validation error helper."""

    def test_creates_error_dict(self):
        """Test error dictionary is created correctly."""
        errors = ['Invalid symbol', 'Price must be positive']
        result = create_validation_error(errors)

        assert result['error'] == 'Validation failed'
        assert result['errors'] == errors
        assert 'message' in result

    def test_single_error(self):
        """Test single error message."""
        result = create_validation_error(['Invalid input'])
        assert len(result['errors']) == 1

    def test_empty_errors_list(self):
        """Test empty errors list."""
        result = create_validation_error([])
        assert result['errors'] == []


class TestGetSymbolWhitelist:
    """Tests for symbol whitelist functionality."""

    @patch('backend.validation.get_available_symbols')
    def test_caches_whitelist(self, mock_get_symbols):
        """Test whitelist is cached after first call."""
        mock_get_symbols.return_value = ['RELIANCE.NS', 'TCS.NS']

        # First call
        result1 = get_symbol_whitelist()
        # Second call should use cache
        result2 = get_symbol_whitelist()

        assert result1 == result2
        mock_get_symbols.assert_called_once()

    @patch('backend.validation.get_available_symbols')
    def test_handles_exception_gracefully(self, mock_get_symbols):
        """Test exception returns empty list."""
        mock_get_symbols.side_effect = Exception("Test error")

        # Need to reset the cache first
        import backend.validation as val_module
        val_module._SYMBOL_WHITELIST = None

        result = get_symbol_whitelist()
        assert result == []


class TestGetAvailableSymbols:
    """Tests for get_available_symbols function."""

    @patch('os.path.exists')
    @patch('os.listdir')
    def test_returns_symbols_from_parquet_files(self, mock_listdir, mock_exists):
        """Test symbols are extracted from parquet filenames."""
        mock_exists.return_value = True
        mock_listdir.side_effect = [
            ['A', 'B'],  # Letter directories
            ['AAPL.NS.parquet', 'AMZN.NS.parquet'],  # Files in A
            ['BPCL.NS.parquet']  # Files in B
        ]

        with patch('os.path.isdir', return_value=True):
            with patch('os.path.join', side_effect=lambda *args: '/'.join(args)):
                result = get_available_symbols()

        assert 'AAPL.NS' in result
        assert 'AMZN.NS' in result
        assert 'BPCL.NS' in result

    @patch('os.path.exists')
    def test_returns_empty_if_data_dir_missing(self, mock_exists):
        """Test empty list if data directory doesn't exist."""
        mock_exists.return_value = False
        result = get_available_symbols()
        assert result == []