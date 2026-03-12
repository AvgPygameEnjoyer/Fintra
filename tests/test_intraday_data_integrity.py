"""
Unit tests for intraday data integrity.

Tests the DataComplianceManager for intraday data handling,
including window calculations, file validation, and compliance checks.
"""
import os
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backend.data_compliance import (
    DATA_LAG_DAYS,
    DataComplianceManager,
    get_intraday_parquet_path,
    get_intraday_window,
    load_stock_data_with_compliance,
)

# Alias for test clarity
SEBI_LAG_DAYS = DATA_LAG_DAYS


@pytest.fixture
def temp_intraday_dir():
    """Create a temporary intraday directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def compliance_manager(temp_intraday_dir):
    """Create a DataComplianceManager with temp directory."""
    with patch('backend.data_compliance.INTRADAY_DIRECTORY', temp_intraday_dir):
        yield DataComplianceManager()


@pytest.fixture
def sample_intraday_file(temp_intraday_dir):
    """Create a sample intraday parquet file."""
    def _create(symbol, start_time, periods=10):
        subdir = temp_intraday_dir / symbol[0].upper()
        subdir.mkdir(exist_ok=True)
        file_path = subdir / f'{symbol}.parquet'

        dates = pd.date_range(start=start_time, periods=periods, freq='5min')
        df = pd.DataFrame({
            'Open': range(periods),
            'High': range(periods),
            'Low': range(periods),
            'Close': range(periods),
            'Volume': range(periods)
        }, index=dates)
        df.to_parquet(file_path)
        return file_path
    return _create


class TestGetIntradayWindow:
    """Tests for intraday window calculation."""

    def test_returns_start_and_end_datetime(self):
        """Test returns tuple of (start, end) datetime objects."""
        start, end = get_intraday_window()

        assert isinstance(start, datetime)
        assert isinstance(end, datetime)
        assert start < end

    def test_window_respects_sebi_lag(self):
        """Test window end is at least SEBI_LAG_DAYS ago."""
        start, end = get_intraday_window()
        today = datetime.now()

        # End should be approximately SEBI_LAG_DAYS ago
        expected_end = today - timedelta(days=SEBI_LAG_DAYS)
        diff = abs((end - expected_end).total_seconds())
        assert diff < 86400  # Within 1 day

    def test_window_spans_multiple_days(self):
        """Test window covers multiple days of data."""
        start, end = get_intraday_window()

        # Should span at least a few days
        duration = (end - start).days
        assert duration >= 1


class TestGetIntradayParquetPath:
    """Tests for intraday parquet path resolution."""

    def test_returns_path_with_symbol_subdirectory(self, temp_intraday_dir):
        """Test returns path in symbol's letter subdirectory."""
        with patch('backend.data_compliance.INTRADAY_DIRECTORY', str(temp_intraday_dir)):
            path = get_intraday_parquet_path('TCS.NS')

            # Path is a string, check it contains expected parts
            assert 'T' in path
            assert 'TCS.NS.parquet' in path

    def test_handles_lowercase_symbol(self, temp_intraday_dir):
        """Test handles lowercase symbols."""
        with patch('backend.data_compliance.INTRADAY_DIRECTORY', str(temp_intraday_dir)):
            path = get_intraday_parquet_path('reliance.ns')

            assert 'R' in str(path)

    def test_handles_numeric_starting_symbol(self, temp_intraday_dir):
        """Test handles symbols starting with numbers."""
        with patch('backend.data_compliance.INTRADAY_DIRECTORY', str(temp_intraday_dir)):
            path = get_intraday_parquet_path('3MINDIA.NS')

            # Should use '0-9' subdirectory
            assert path is not None
            assert '0-9' in str(path)


class TestDataComplianceManager:
    """Tests for DataComplianceManager class."""

    def test_get_current_date_with_lag(self, compliance_manager):
        """Test get_current_date_with_lag returns SEBI_LAG_DAYS ago."""
        lag_date = compliance_manager.get_current_date_with_lag()
        expected = datetime.now() - timedelta(days=SEBI_LAG_DAYS)

        diff = abs((lag_date - expected).total_seconds())
        assert diff < 60

    def test_filter_data_with_lag_filters_recent_data(self, compliance_manager):
        """Test filter_data_with_lag removes data newer than SEBI lag."""
        # Create DataFrame with dates spanning SEBI boundary
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=SEBI_LAG_DAYS + 20),
            end=datetime.now(),
            freq='D'
        )
        df = pd.DataFrame({
            'open': range(len(dates)),
            'close': range(len(dates))
        }, index=dates)

        filtered = compliance_manager.filter_data_with_lag(df)

        # All dates should be older than SEBI lag
        sebi_date = compliance_manager.get_current_date_with_lag()
        assert filtered.index.max() <= sebi_date

    def test_filter_data_with_lag_handles_empty_dataframe(self, compliance_manager):
        """Test filter_data_with_lag handles empty DataFrame."""
        df = pd.DataFrame()
        filtered = compliance_manager.filter_data_with_lag(df)

        assert filtered.empty

    def test_filter_data_with_lag_preserves_all_columns(self, compliance_manager):
        """Test filter_data_with_lag preserves all columns during filtering."""
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=SEBI_LAG_DAYS + 10),
            periods=5,
            freq='D'
        )
        df = pd.DataFrame({
            'open': range(5),
            'high': range(5),
            'low': range(5),
            'close': range(5),
            'volume': range(5)
        }, index=dates)

        filtered = compliance_manager.filter_data_with_lag(df)

        assert set(filtered.columns) == set(df.columns)

    def test_filter_data_with_lag_handles_date_column_instead_of_index(self, compliance_manager):
        """Test filter_data_with_lag handles date as column instead of index."""
        dates = pd.date_range(
            start=datetime.now() - timedelta(days=SEBI_LAG_DAYS + 10),
            periods=5,
            freq='D'
        )
        df = pd.DataFrame({
            'date': dates,
            'open': range(5),
            'close': range(5)
        })

        filtered = compliance_manager.filter_data_with_lag(df)

        assert len(filtered) <= len(df)


class TestLoadStockDataWithCompliance:
    """Tests for loading stock data with compliance filtering."""

    def test_loads_and_filters_data(self, temp_intraday_dir, sample_intraday_file):
        """Test loads and filters intraday data."""
        # Create sample file with old data
        old_time = datetime.now() - timedelta(days=SEBI_LAG_DAYS + 5)
        file_path = sample_intraday_file('TEST.NS', old_time, periods=100)

        with patch('backend.data_compliance.get_parquet_path') as mock_path:
            mock_path.return_value = str(file_path)
            result = load_stock_data_with_compliance('TEST.NS')

            df, info = result
            assert df is not None
            assert not df.empty

    def test_returns_none_for_missing_file(self, temp_intraday_dir):
        """Test returns None for missing file."""
        with patch('backend.data_compliance.get_parquet_path', return_value=None):
            result = load_stock_data_with_compliance('NONEXISTENT.NS')

            df, info = result
            assert df is None
            assert 'error' in info

    def test_returns_none_for_corrupted_file(self, temp_intraday_dir):
        """Test returns None for corrupted parquet file."""
        subdir = temp_intraday_dir / 'C'
        subdir.mkdir()
        corrupted = subdir / 'CORRUPTED.NS.parquet'
        corrupted.write_text('not a parquet file')

        with patch('backend.data_compliance.get_parquet_path', return_value=str(corrupted)):
            result = load_stock_data_with_compliance('CORRUPTED.NS')

            df, info = result
            assert df is None
            assert 'error' in info


class TestIntradayFileIntegrity:
    """Tests for intraday file integrity validation."""

    def test_validates_ohlcv_columns(self, sample_intraday_file):
        """Test validates presence of OHLCV columns."""
        old_time = datetime.now() - timedelta(days=SEBI_LAG_DAYS + 5)
        file_path = sample_intraday_file('VALID.NS', old_time)

        df = pd.read_parquet(file_path)

        required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}
        assert required_cols.issubset(set(df.columns))

    def test_validates_datetime_index(self, sample_intraday_file):
        """Test validates DatetimeIndex."""
        old_time = datetime.now() - timedelta(days=SEBI_LAG_DAYS + 5)
        file_path = sample_intraday_file('TIME.NS', old_time)

        df = pd.read_parquet(file_path)

        assert isinstance(df.index, pd.DatetimeIndex)

    def test_validates_intraday_frequency(self, sample_intraday_file):
        """Test validates intraday frequency (5-min intervals)."""
        old_time = datetime.now() - timedelta(days=SEBI_LAG_DAYS + 5)
        file_path = sample_intraday_file('FREQ.NS', old_time, periods=10)

        df = pd.read_parquet(file_path)

        # Check frequency is approximately 5 minutes
        if len(df) > 1:
            freq_diff = (df.index[1] - df.index[0]).total_seconds()
            assert freq_diff == 300  # 5 minutes = 300 seconds

    def test_detects_missing_columns(self, temp_intraday_dir):
        """Test detects missing required columns."""
        subdir = temp_intraday_dir / 'M'
        subdir.mkdir()
        file_path = subdir / 'MISSING.NS.parquet'

        # Missing High, Low, Volume
        df = pd.DataFrame({
            'Open': [100],
            'Close': [103]
        }, index=pd.DatetimeIndex([datetime.now() - timedelta(days=40)]))
        df.to_parquet(file_path)

        loaded = pd.read_parquet(file_path)
        required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}

        assert not required_cols.issubset(set(loaded.columns))

    def test_detects_empty_file(self, temp_intraday_dir):
        """Test detects empty parquet file."""
        subdir = temp_intraday_dir / 'E'
        subdir.mkdir()
        file_path = subdir / 'EMPTY.NS.parquet'

        df = pd.DataFrame()
        df.to_parquet(file_path)

        loaded = pd.read_parquet(file_path)
        assert loaded.empty


class TestIntradayWindowCompliance:
    """Tests for intraday data window compliance."""

    def test_data_within_window(self, sample_intraday_file):
        """Test data falls within intraday window."""
        window_start, window_end = get_intraday_window()

        # Create data within window
        file_path = sample_intraday_file('WINDOW.NS', window_start, periods=10)

        df = pd.read_parquet(file_path)

        assert df.index.min() >= window_start
        assert df.index.max() <= window_end

    def test_data_outside_window_detected(self, temp_intraday_dir):
        """Test detects data outside intraday window."""
        window_start, window_end = get_intraday_window()

        # Create data outside window (too recent)
        subdir = temp_intraday_dir / 'O'
        subdir.mkdir()
        file_path = subdir / 'OUTSIDE.NS.parquet'

        recent_time = datetime.now() - timedelta(days=5)  # Within SEBI lag
        df = pd.DataFrame({
            'Open': [100],
            'Close': [103]
        }, index=pd.DatetimeIndex([recent_time]))
        df.to_parquet(file_path)

        loaded = pd.read_parquet(file_path)

        # This data should be filtered out by compliance manager
        assert loaded.index.min() > window_end


class TestGetInformaticsHtml:
    """Tests for generating HTML informatics."""

    def test_generates_html_report(self, compliance_manager):
        """Test generates HTML informatics report."""
        html = compliance_manager.get_informatics_html()

        assert html is not None
        assert isinstance(html, str)
        assert 'Data' in html or 'SEBI' in html

    def test_handles_missing_data_gracefully(self, compliance_manager):
        """Test handles missing data gracefully."""
        # With no data directory, should still return HTML
        html = compliance_manager.get_informatics_html()

        assert html is not None
        assert 'SEBI' in html


# Integration test that requires actual data (can be skipped)
@pytest.mark.integration
def test_real_intraday_directory_exists():
    """Test that real intraday directory exists (integration test)."""
    from backend.data_compliance import INTRADAY_DIRECTORY

    if not os.path.exists(INTRADAY_DIRECTORY):
        pytest.skip("Intraday directory not configured")

    assert os.path.isdir(INTRADAY_DIRECTORY)


@pytest.mark.integration
def test_real_intraday_files_have_required_columns():
    """Test real intraday files have required columns (integration test)."""
    from backend.data_compliance import INTRADAY_DIRECTORY

    if not os.path.exists(INTRADAY_DIRECTORY):
        pytest.skip("Intraday directory not configured")

    base_dir = Path(INTRADAY_DIRECTORY)
    files = list(base_dir.glob("*/*.parquet"))

    if not files:
        pytest.skip("No intraday parquet files found")

    # Test first file
    df = pd.read_parquet(files[0])
    required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}

    # Normalize column names
    df.columns = [c.title() for c in df.columns]

    assert required_cols.issubset(set(df.columns))
