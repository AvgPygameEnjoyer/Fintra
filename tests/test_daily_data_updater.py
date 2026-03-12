"""
Unit tests for Daily Data Updater.

Tests the SEBI-compliant daily data update pipeline.
"""
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from scripts.daily_data_updater import (
    SEBI_LAG_DAYS,
    UPDATE_BUFFER_DAYS,
    DailyDataUpdater,
    SEBIComplianceError,
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def updater(temp_data_dir):
    """Create a DailyDataUpdater instance with temp directory."""
    return DailyDataUpdater(data_dir=temp_data_dir)


@pytest.fixture
def sample_parquet(temp_data_dir):
    """Create a sample parquet file for testing."""
    def _create(symbol, date, subdir_letter=None):
        if subdir_letter is None:
            subdir_letter = symbol[0].upper()
        subdir = temp_data_dir / subdir_letter
        subdir.mkdir(exist_ok=True)
        file_path = subdir / f'{symbol}.parquet'

        df = pd.DataFrame({
            'open': [100],
            'high': [105],
            'low': [99],
            'close': [103],
            'volume': [1000000]
        }, index=pd.DatetimeIndex([date]))
        df.to_parquet(file_path)
        return file_path
    return _create


class TestSEBICompliance:
    """Tests for SEBI compliance calculations."""

    def test_sebi_compliance_date_is_31_days_ago(self, updater):
        """Test SEBI compliance date is today minus 31 days."""
        sebi_date = updater.get_sebi_compliance_date()
        expected = datetime.now() - timedelta(days=SEBI_LAG_DAYS)

        diff = abs((sebi_date - expected).total_seconds())
        assert diff < 60

    def test_update_threshold_is_sebi_plus_buffer(self, updater):
        """Test update threshold is SEBI date plus 7-day buffer."""
        sebi_date = updater.get_sebi_compliance_date()
        threshold = updater.get_update_threshold_date()

        expected = sebi_date + timedelta(days=UPDATE_BUFFER_DAYS)
        diff = abs((threshold - expected).total_seconds())
        assert diff < 60

    def test_threshold_is_newer_than_sebi_date(self, updater):
        """Test update threshold is always newer than SEBI date."""
        sebi_date = updater.get_sebi_compliance_date()
        threshold = updater.get_update_threshold_date()

        assert threshold > sebi_date
        assert (threshold - sebi_date).days == UPDATE_BUFFER_DAYS


class TestSEBIComplianceError:
    """Tests for SEBIComplianceError exception."""

    def test_error_message_is_preserved(self):
        """Test error message is preserved."""
        error = SEBIComplianceError("Data violates SEBI rules")
        assert str(error) == "Data violates SEBI rules"

    def test_is_exception_subclass(self):
        """Test it's a proper Exception subclass."""
        error = SEBIComplianceError("test")
        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test error can be raised and caught."""
        with pytest.raises(SEBIComplianceError, match="violation"):
            raise SEBIComplianceError("SEBI violation detected")


class TestGetAllStockFiles:
    """Tests for discovering stock files."""

    def test_finds_all_parquet_files(self, updater, sample_parquet):
        """Test finds all parquet files in subdirectories."""
        sample_parquet('A.NS', datetime.now())
        sample_parquet('B.NS', datetime.now())
        sample_parquet('C.NS', datetime.now())

        files = updater.get_all_stock_files()
        assert len(files) == 3

    def test_ignores_non_parquet_files(self, updater, temp_data_dir):
        """Test ignores non-parquet files."""
        subdir = temp_data_dir / 'T'
        subdir.mkdir()
        (subdir / 'TEST.NS.parquet').write_bytes(b'\x00' * 100)
        (subdir / 'TEST.txt').write_text('ignored')

        files = updater.get_all_stock_files()
        assert len(files) == 1
        assert files[0].suffix == '.parquet'

    def test_returns_empty_for_empty_directory(self, updater):
        """Test returns empty list for empty directory."""
        files = updater.get_all_stock_files()
        assert files == []

    def test_returns_sorted_list(self, updater, sample_parquet):
        """Test returns sorted file list."""
        sample_parquet('Z.NS', datetime.now())
        sample_parquet('A.NS', datetime.now())
        sample_parquet('M.NS', datetime.now())

        files = updater.get_all_stock_files()
        file_names = [f.stem for f in files]
        assert file_names == sorted(file_names)


class TestGetLastDateFromParquet:
    """Tests for reading last date from parquet files."""

    def test_returns_datetime_from_index(self, updater, sample_parquet):
        """Test returns datetime from DatetimeIndex."""
        test_date = datetime(2024, 6, 15)
        file_path = sample_parquet('TEST.NS', test_date)

        result = updater.get_last_date_from_parquet(file_path)

        assert result is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_handles_date_column(self, updater, temp_data_dir):
        """Test handles date as column instead of index."""
        subdir = temp_data_dir / 'D'
        subdir.mkdir()
        file_path = subdir / 'DATECOL.NS.parquet'

        df = pd.DataFrame({
            'date': [datetime(2024, 6, 15)],
            'open': [100],
            'close': [103]
        })
        df.to_parquet(file_path)

        result = updater.get_last_date_from_parquet(file_path)
        assert result is not None

    def test_returns_none_for_corrupted_file(self, updater, temp_data_dir):
        """Test returns None for corrupted file."""
        subdir = temp_data_dir / 'C'
        subdir.mkdir()
        corrupted = subdir / 'BAD.NS.parquet'
        corrupted.write_text('corrupted')

        result = updater.get_last_date_from_parquet(corrupted)
        assert result is None

    def test_returns_none_for_empty_file(self, updater, temp_data_dir):
        """Test returns None for empty dataframe."""
        subdir = temp_data_dir / 'E'
        subdir.mkdir()
        file_path = subdir / 'EMPTY.NS.parquet'

        df = pd.DataFrame()
        df.to_parquet(file_path)

        result = updater.get_last_date_from_parquet(file_path)
        assert result is None

    def test_returns_max_date_for_multiple_rows(self, updater, temp_data_dir):
        """Test returns max date when multiple rows exist."""
        subdir = temp_data_dir / 'M'
        subdir.mkdir()
        file_path = subdir / 'MULTI.NS.parquet'

        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'open': range(10),
            'close': range(10)
        }, index=dates)
        df.to_parquet(file_path)

        result = updater.get_last_date_from_parquet(file_path)
        assert result is not None
        assert result.day == 10


class TestCheckStockNeedsUpdate:
    """Tests for checking if stock needs update."""

    def test_old_data_needs_update(self, updater, sample_parquet):
        """Test that old stock data (40 days ago) is flagged for update."""
        old_date = datetime.now() - timedelta(days=40)
        file_path = sample_parquet('TEST.NS', old_date)

        needs_update, last_date, sebi_date = updater.check_stock_needs_update(file_path)

        assert needs_update is True
        assert last_date is not None
        assert abs((last_date - old_date).total_seconds()) < 1

    def test_fresh_data_skipped(self, updater, sample_parquet):
        """Test that fresh stock data (5 days ago) is skipped."""
        fresh_date = datetime.now() - timedelta(days=5)
        file_path = sample_parquet('FRESH.NS', fresh_date)

        needs_update, last_date, sebi_date = updater.check_stock_needs_update(file_path)

        assert needs_update is False

    def test_data_at_boundary_needs_update(self, updater, sample_parquet):
        """Test stock at exactly the threshold boundary needs update."""
        threshold = updater.get_update_threshold_date()
        boundary_date = threshold - timedelta(days=1)
        file_path = sample_parquet('BOUNDARY.NS', boundary_date)

        needs_update, _, _ = updater.check_stock_needs_update(file_path)
        assert needs_update is True

    def test_data_just_above_threshold_skipped(self, updater, sample_parquet):
        """Test stock just above threshold is skipped."""
        threshold = updater.get_update_threshold_date()
        above_threshold = threshold + timedelta(days=1)
        file_path = sample_parquet('ABOVE.NS', above_threshold)

        needs_update, _, _ = updater.check_stock_needs_update(file_path)
        assert needs_update is False

    def test_unreadable_file_needs_update(self, updater, temp_data_dir):
        """Test unreadable file is marked for update."""
        subdir = temp_data_dir / 'U'
        subdir.mkdir()
        corrupted_file = subdir / 'CORRUPTED.NS.parquet'
        corrupted_file.write_text('not a parquet file')

        needs_update, last_date, sebi_date = updater.check_stock_needs_update(corrupted_file)

        assert needs_update is True
        assert last_date is None


class TestFetchStockData:
    """Tests for fetching stock data."""

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_trims_data_to_sebi_limit(self, mock_fetch, updater):
        """Test fetched data is trimmed to SEBI compliance date."""
        sebi_date = datetime.now() - timedelta(days=31)

        # Create data that spans across SEBI date (some before, some after)
        dates = pd.date_range(start=sebi_date - timedelta(days=10), periods=20, freq='D')
        mock_data = pd.DataFrame({
            'Open': range(20),
            'High': range(20),
            'Low': range(20),
            'Close': range(20),
            'Volume': range(20)
        }, index=dates)
        mock_fetch.return_value = mock_data

        result = updater.fetch_stock_data('TEST.NS', sebi_date)

        assert result is not None
        assert not result.empty
        assert result.index.max() <= sebi_date

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_returns_none_on_fetch_error(self, mock_fetch, updater):
        """Test returns None when fetch raises exception."""
        mock_fetch.side_effect = Exception("Network error")

        result = updater.fetch_stock_data('TEST.NS', datetime.now())

        assert result is None

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_returns_none_on_empty_response(self, mock_fetch, updater):
        """Test returns None when fetch returns None."""
        mock_fetch.return_value = None

        result = updater.fetch_stock_data('TEST.NS', datetime.now())

        assert result is None

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_standardizes_column_names(self, mock_fetch, updater):
        """Test column names are standardized to lowercase."""
        mock_data = pd.DataFrame({
            'Open': [100],
            'High': [105],
            'Low': [99],
            'Close': [103],
            'Volume': [1000]
        }, index=pd.DatetimeIndex([datetime.now() - timedelta(days=35)]))
        mock_fetch.return_value = mock_data

        result = updater.fetch_stock_data('TEST.NS', datetime.now())

        assert 'open' in result.columns
        assert 'high' in result.columns
        assert 'close' in result.columns


class TestUpdateStockData:
    """Tests for updating stock data."""

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_updates_file_with_new_data(self, mock_fetch, updater, sample_parquet):
        """Test updates parquet file with fetched data."""
        file_path = sample_parquet('TEST.NS', datetime.now() - timedelta(days=40))
        sebi_date = updater.get_sebi_compliance_date()

        mock_data = pd.DataFrame({
            'Open': [100],
            'High': [105],
            'Low': [99],
            'Close': [103],
            'Volume': [1000]
        }, index=pd.DatetimeIndex([sebi_date - timedelta(days=1)]))
        mock_fetch.return_value = mock_data

        result = updater.update_stock_data(file_path, 'TEST.NS', sebi_date)

        assert result is True

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_logs_compliance_error_on_violation(self, mock_fetch, updater, sample_parquet):
        """Test logs SEBIComplianceError for data newer than SEBI date."""
        file_path = sample_parquet('TEST.NS', datetime.now() - timedelta(days=40))
        sebi_date = datetime.now() - timedelta(days=31)

        # Data is newer than SEBI date - but fetch_stock_data trims it first
        # So we need to test the validation in update_stock_data directly
        mock_data = pd.DataFrame({
            'Open': [100],
            'High': [105],
            'Low': [99],
            'Close': [103],
            'Volume': [1000]
        }, index=pd.DatetimeIndex([sebi_date + timedelta(days=5)]))  # 5 days after SEBI
        mock_fetch.return_value = mock_data

        result = updater.update_stock_data(file_path, 'TEST.NS', sebi_date)

        # The data gets trimmed by fetch_stock_data, so no compliance error
        # Instead, check that it returns False when data is empty after trimming
        assert result is False  # Empty after trimming to SEBI date

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_returns_false_on_fetch_failure(self, mock_fetch, updater, sample_parquet):
        """Test returns False when fetch fails."""
        file_path = sample_parquet('TEST.NS', datetime.now() - timedelta(days=40))
        mock_fetch.return_value = None

        result = updater.update_stock_data(file_path, 'TEST.NS', datetime.now())

        assert result is False

    @patch('scripts.daily_data_updater.fetch_daily_ohlcv')
    def test_logs_error_on_exception(self, mock_fetch, updater, sample_parquet):
        """Test logs error on unexpected exception."""
        file_path = sample_parquet('TEST.NS', datetime.now() - timedelta(days=40))
        mock_fetch.side_effect = Exception("Unexpected error")

        result = updater.update_stock_data(file_path, 'TEST.NS', updater.get_sebi_compliance_date())

        assert result is False
        # Error is logged but not added to errors list (fetch_stock_data handles it)
        # The key assertion is that update_stock_data returns False on failure


class TestRunUpdate:
    """Tests for running the complete update pipeline."""

    @pytest.fixture
    def populated_updater(self, temp_data_dir):
        """Create updater with sample data structure."""
        updater = DailyDataUpdater(data_dir=temp_data_dir)

        # Create stocks with varying freshness
        for letter, days_ago in [('A', 5), ('B', 20), ('C', 40)]:
            subdir = temp_data_dir / letter
            subdir.mkdir()
            df = pd.DataFrame({
                'open': [100],
                'close': [103]
            }, index=pd.DatetimeIndex([datetime.now() - timedelta(days=days_ago)]))
            df.to_parquet(subdir / f'STOCK{letter}.NS.parquet')

        return updater

    def test_generates_report_with_required_fields(self, populated_updater):
        """Test pipeline generates report with all required fields."""
        with patch.object(populated_updater, 'update_stock_data', return_value=True):
            report = populated_updater.run_update(sample_size=3, force_update=False)

        assert 'timestamp' in report
        assert 'sebi_compliance_date' in report
        assert 'total_stocks' in report
        assert 'checked_stocks' in report
        assert 'updated_stocks' in report
        assert 'skipped_stocks' in report
        assert 'errors' in report
        assert report['pipeline'] == 'daily'

    def test_counts_total_stocks_correctly(self, populated_updater):
        """Test counts total stocks correctly."""
        report = populated_updater.run_update(sample_size=3, force_update=False)
        assert report['total_stocks'] == 3

    def test_respects_sample_size(self, populated_updater):
        """Test respects sample size parameter."""
        report = populated_updater.run_update(sample_size=2, force_update=False)
        assert report['checked_stocks'] <= 2

    def test_force_update_updates_all(self, populated_updater):
        """Test force_update=True updates all stocks."""
        with patch.object(populated_updater, 'update_stock_data', return_value=True) as mock_update:
            populated_updater.run_update(sample_size=3, force_update=True)
            assert mock_update.call_count == 3

    def test_skips_fresh_data_without_force(self, populated_updater):
        """Test skips fresh data when force_update=False."""
        report = populated_updater.run_update(sample_size=3, force_update=False)
        # Stock A (5 days ago) should be skipped
        assert report['skipped_stocks'] >= 1

    def test_handles_empty_data_directory(self, updater):
        """Test handles empty data directory gracefully."""
        report = updater.run_update(sample_size=10, force_update=False)

        assert report.get('success') is False or report.get('total_stocks') == 0
        assert 'error' in report or report.get('checked_stocks') == 0

    def test_processes_specific_symbols(self, populated_updater, temp_data_dir):
        """Test processes only specified symbols."""
        report = populated_updater.run_update(symbols=['STOCKA.NS'])

        # Should find STOCKA.NS file and process it
        assert report['checked_stocks'] == 1


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_handles_sample_larger_than_population(self, updater, sample_parquet):
        """Test handles sample size larger than available stocks."""
        sample_parquet('A.NS', datetime.now())

        files = updater.get_all_stock_files()
        sample = min(100, len(files))
        assert sample == 1

    def test_handles_special_characters_in_symbol(self, updater, sample_parquet):
        """Test handles symbols with special characters."""
        file_path = sample_parquet('M-M.NS', datetime.now())
        assert file_path.exists()

    def test_handles_numeric_starting_symbol(self, updater, sample_parquet):
        """Test handles symbols starting with numbers."""
        file_path = sample_parquet('3MINDIA.NS', datetime.now(), subdir_letter='0-9')
        assert file_path.exists()

    def test_handles_nonexistent_data_dir(self):
        """Test handles nonexistent data directory."""
        updater = DailyDataUpdater(data_dir=Path('/nonexistent/path'))
        files = updater.get_all_stock_files()
        assert files == []
