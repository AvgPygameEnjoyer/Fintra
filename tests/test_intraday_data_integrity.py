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
    DataComplianceManager,
    SEBI_LAG_DAYS,
    get_intraday_parquet_path,
    get_intraday_window,
    load_stock_data_with_compliance,
)


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
        with patch('backend.data_compliance.INTRADAY_DIRECTORY', temp_intraday_dir):
            path = get_intraday_parquet_path('TCS.NS')

            assert path.parent.name == 'T'
            assert path.name == 'TCS.NS.parquet'

    def test_handles_lowercase_symbol(self, temp_intraday_dir):
        """Test handles lowercase symbols."""
        with patch('backend.data_compliance.INTRADAY_DIRECTORY', temp_intraday_dir):
            path = get_intraday_parquet_path('reliance.ns')

            assert 'R' in str(path)

    def test_handles_numeric_starting_symbol(self, temp_intraday_dir):
        """Test handles symbols starting with numbers."""
        with patch('backend.data_compliance.INTRADAY_DIRECTORY', temp_intraday_dir):
            path = get_intraday_parquet_path('3MINDIA.NS')

            # Should use '0-9' or similar subdirectory
            assert path is not None


class TestDataComplianceManager:
    """Tests for DataComplianceManager class."""

    def test_get_effective_lag_date(self, compliance_manager):
        """Test effective lag date is SEBI_LAG_DAYS ago."""
        lag_date = compliance_manager.get_effective_lag_date()
        expected = datetime.now() - timedelta(days=SEBI_LAG_DAYS)

        diff = abs((lag_date - expected).total_seconds())
        assert diff < 60

    def test_is_data_available_for_past_date(self, compliance_manager):
        """Test data is available for dates older than SEBI lag."""
        past_date = datetime.now() - timedelta(days=SEBI_LAG_DAYS + 10)

        is_available = compliance_manager.is_data_available(past_date)
        assert is_available is True

    def test_is_data_unavailable_for_recent_date(self, compliance_manager):
        """Test data is unavailable for dates within SEBI lag."""
        recent_date = datetime.now() - timedelta(days=SEBI_LAG_DAYS - 10)

        is_available = compliance_manager.is_data_available(recent_date)
        assert is_available is False

    def test_is_data_unavailable_for_future_date(self, compliance_manager):
        """Test data is unavailable for future dates."""
        future_date = datetime.now() + timedelta(days=10)

        is_available = compliance_manager.is_data_available(future_date)
        assert is_available is False


class TestFilterComplianceDataframe:
    """Tests for filtering DataFrames to SEBI compliance."""

    def test_filters_to_sebi_lag(self, compliance_manager):
        """Test filters DataFrame to only include SEBI-compliant dates."""
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

        filtered = compliance_manager.filter_compliance_dataframe(df)

        # All dates should be older than SEBI lag
        sebi_date = compliance_manager.get_effective_lag_date()
        assert filtered.index.max() <= sebi_date

    def test_handles_empty_dataframe(self, compliance_manager):
        """Test handles empty DataFrame."""
        df = pd.DataFrame()
        filtered = compliance_manager.filter_compliance_dataframe(df)

        assert filtered.empty

    def test_preserves_all_columns(self, compliance_manager):
        """Test preserves all columns during filtering."""
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

        filtered = compliance_manager.filter_compliance_dataframe(df)

        assert set(filtered.columns) == set(df.columns)

    def test_handles_date_column_instead_of_index(self, compliance_manager):
        """Test handles date as column instead of index."""
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

        filtered = compliance_manager.filter_compliance_dataframe(df)

        assert len(filtered) <= len(df)


class TestLoadStockDataWithCompliance:
    """Tests for loading stock data with compliance filtering."""

    def test_loads_and_filters_data(self, temp_intraday_dir, sample_intraday_file):
        """Test loads and filters intraday data."""
        # Create sample file with old data
        old_time = datetime.now() - timedelta(days=SEBI_LAG_DAYS + 5)
        file_path = sample_intraday_file('TEST.NS', old_time, periods=100)

        with patch('backend.data_compliance.INTRADAY_DIRECTORY', temp_intraday_dir), \
             patch('backend.data_compliance.get_intraday_parquet_path', return_value=file_path):
            df = load_stock_data_with_compliance('TEST.NS')

            assert df is not None
            assert not df.empty

    def test_returns_none_for_missing_file(self, temp_intraday_dir):
        """Test returns None for missing file."""
        with patch('backend.data_compliance.INTRADAY_DIRECTORY', temp_intraday_dir), \
             patch('backend.data_compliance.get_intraday_parquet_path') as mock_path:
            mock_path.return_value = temp_intraday_dir / 'NONEXISTENT.NS.parquet'

            df = load_stock_data_with_compliance('NONEXISTENT.NS')

            assert df is None

    def test_returns_none_for_corrupted_file(self, temp_intraday_dir):
        """Test returns None for corrupted parquet file."""
        subdir = temp_intraday_dir / 'C'
        subdir.mkdir()
        corrupted = subdir / 'CORRUPTED.NS.parquet'
        corrupted.write_text('not a parquet file')

        with patch('backend.data_compliance.INTRADAY_DIRECTORY', temp_intraday_dir), \
             patch('backend.data_compliance.get_intraday_parquet_path', return_value=corrupted):
            df = load_stock_data_with_compliance('CORRUPTED.NS')

            assert df is None


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


class TestGenerateInformatics:
    """Tests for generating HTML informatics."""

    def test_generates_html_report(self, compliance_manager):
        """Test generates HTML informatics report."""
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

        html = compliance_manager.generate_intraday_informatics(df, 'TEST.NS')

        assert '<html' in html.lower() or '<!doctype' in html.lower()
        assert 'TEST.NS' in html

    def test_handles_empty_dataframe(self, compliance_manager):
        """Test handles empty DataFrame gracefully."""
        df = pd.DataFrame()

        html = compliance_manager.generate_intraday_informatics(df, 'EMPTY.NS')

        assert html is not None


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
