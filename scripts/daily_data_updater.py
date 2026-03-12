#!/usr/bin/env python3
"""
SEBI-Compliant Daily Data Updater

Updates daily OHLCV parquet files for NSE stocks while maintaining
SEBI compliance (31-day lag).

Logic:
- SEBI requires 31-day lag on all market data
- We maintain a 7-day buffer before the deadline
- Data is updated when: last_date < (today - 31 days + 7 days)
- Updates fetch from last_date to SEBI compliance date

Example:
    Today = February 9, 2025
    SEBI Compliance Date = January 9, 2025 (today - 31)
    Update Threshold = January 16, 2025 (SEBI date + 7)
    
    If stock.last_date = January 20, 2025:
        → Data is fresh, skip
    
    If stock.last_date = January 10, 2025:
        → Fetch from Jan 10 to Jan 9 (SEBI limit)
"""

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.data_providers import fetch_daily_ohlcv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('daily_update.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
DATA_DIR = Path(__file__).parent.parent / 'data'
SEBI_LAG_DAYS = 31
UPDATE_BUFFER_DAYS = 7
REPORT_FILE = 'daily_update_report.json'


class SEBIComplianceError(Exception):
    """Raised when data violates SEBI compliance rules."""
    pass


class DailyDataUpdater:
    """
    Manages SEBI-compliant daily data updates for NSE stock data.
    """
    
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.updated_stocks: List[Dict] = []
        self.skipped_stocks: List[Dict] = []
        self.errors: List[Dict] = []
        
    def get_sebi_compliance_date(self) -> datetime:
        """
        Calculate the SEBI compliance date (today - 31 days).
        No data newer than this date should be stored.
        """
        return datetime.now() - timedelta(days=SEBI_LAG_DAYS)
    
    def get_update_threshold_date(self) -> datetime:
        """
        Calculate the update threshold date.
        Stocks with data older than this need updating.
        """
        return self.get_sebi_compliance_date() + timedelta(days=UPDATE_BUFFER_DAYS)
    
    def get_all_stock_files(self) -> List[Path]:
        """
        Get all parquet files in the data directory.
        Returns sorted list of file paths.
        """
        parquet_files = []
        
        if not self.data_dir.exists():
            logger.warning(f"Data directory does not exist: {self.data_dir}")
            return parquet_files
        
        # Data is organized in subdirectories (0-9, A, B, C, etc.)
        for subdir in sorted(self.data_dir.iterdir()):
            if subdir.is_dir():
                for parquet_file in sorted(subdir.glob('*.parquet')):
                    parquet_files.append(parquet_file)
        
        return parquet_files
    
    def get_last_date_from_parquet(self, file_path: Path) -> Optional[datetime]:
        """
        Read the last (most recent) date from a parquet file.
        Returns None if file is corrupted or empty.
        """
        try:
            df = pd.read_parquet(file_path)
            
            if df.empty:
                return None
            
            # Handle DatetimeIndex
            if isinstance(df.index, pd.DatetimeIndex):
                last_date = df.index.max()
                return last_date.to_pydatetime() if hasattr(last_date, 'to_pydatetime') else last_date
            
            # Handle date column
            date_col = next((c for c in df.columns if c.lower() == 'date'), None)
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col])
                return df[date_col].max().to_pydatetime()
            
            # Try to parse index as datetime
            df.index = pd.to_datetime(df.index)
            last_date = df.index.max()
            return last_date.to_pydatetime() if hasattr(last_date, 'to_pydatetime') else last_date
            
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None
    
    def check_stock_needs_update(self, file_path: Path) -> Tuple[bool, Optional[datetime], datetime]:
        """
        Check if a stock needs data update.
        
        Returns:
            Tuple of (needs_update, last_date, sebi_compliance_date)
        """
        last_date = self.get_last_date_from_parquet(file_path)
        sebi_date = self.get_sebi_compliance_date()
        
        if last_date is None:
            logger.warning(f"Could not read {file_path}, marking for update")
            return True, None, sebi_date
        
        update_threshold = self.get_update_threshold_date()
        needs_update = last_date < update_threshold
        
        return needs_update, last_date, sebi_date
    
    def fetch_stock_data(self, symbol: str, up_to_date: datetime) -> Optional[pd.DataFrame]:
        """
        Fetch stock data from data providers up to the SEBI compliance date.
        
        Args:
            symbol: Stock symbol (e.g., 'RELIANCE.NS')
            up_to_date: Maximum date to fetch (SEBI compliance date)
            
        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        try:
            logger.info(f"Fetching {symbol} up to {up_to_date.date()}")
            
            # Fetch using data providers fallback chain
            df = fetch_daily_ohlcv(symbol, period="2y")
            
            if df is None or df.empty:
                logger.warning(f"No data returned for {symbol}")
                return None
            
            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                date_col = next((c for c in df.columns if c.lower() == 'date'), None)
                if date_col:
                    df[date_col] = pd.to_datetime(df[date_col])
                    df.set_index(date_col, inplace=True)
            
            # Remove timezone info if present
            if hasattr(df.index, 'tz') and df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            # Trim to SEBI compliance date
            if df.index.max() > up_to_date:
                logger.warning(f"Trimming {symbol} to SEBI limit {up_to_date.date()}")
                df = df[df.index <= up_to_date]
            
            # Standardize column names
            df.columns = [col.lower().replace(' ', '_') for col in df.columns]
            
            logger.info(f"Successfully fetched {len(df)} rows for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            return None
    
    def update_stock_data(self, file_path: Path, symbol: str, up_to_date: datetime) -> bool:
        """
        Update a single stock's parquet file with fresh data.
        
        Returns:
            True if update successful, False otherwise
        """
        try:
            # Fetch new data
            new_data = self.fetch_stock_data(symbol, up_to_date)
            
            if new_data is None or new_data.empty:
                logger.warning(f"No new data available for {symbol}")
                return False
            
            # Validate SEBI compliance
            max_date = new_data.index.max()
            if max_date > up_to_date:
                raise SEBIComplianceError(
                    f"Data violation: {symbol} has data from {max_date} "
                    f"which is newer than SEBI compliance date {up_to_date}"
                )
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save to parquet
            new_data.to_parquet(file_path, compression='snappy')
            
            logger.info(f"✅ Updated {symbol}: {len(new_data)} rows, up to {max_date.date()}")
            return True
            
        except SEBIComplianceError as e:
            logger.error(f"SEBI Compliance Error for {symbol}: {e}")
            self.errors.append({'symbol': symbol, 'error': str(e), 'type': 'compliance'})
            return False
        except Exception as e:
            logger.error(f"Error updating {symbol}: {e}")
            self.errors.append({'symbol': symbol, 'error': str(e), 'type': 'update'})
            return False
    
    def run_update(self, sample_size: int = None, force_update: bool = False,
                   symbols: List[str] = None) -> Dict:
        """
        Run the daily data update pipeline.
        
        Args:
            sample_size: Number of random stocks to check (None = all)
            force_update: If True, update all stocks regardless of date
            symbols: Specific symbols to update (overrides sample_size)
            
        Returns:
            Dictionary with update statistics
        """
        logger.info("=" * 60)
        logger.info("Starting Daily Data Update Pipeline")
        logger.info("=" * 60)
        
        # Calculate key dates
        today = datetime.now()
        sebi_date = self.get_sebi_compliance_date()
        threshold_date = self.get_update_threshold_date()
        
        logger.info(f"Current date: {today.date()}")
        logger.info(f"SEBI compliance date: {sebi_date.date()}")
        logger.info(f"Update threshold: {threshold_date.date()}")
        logger.info(f"Force update: {force_update}")
        logger.info("-" * 60)
        
        # Get stock files to process
        all_files = self.get_all_stock_files()
        logger.info(f"Total stocks in database: {len(all_files)}")
        
        if len(all_files) == 0:
            logger.error("No stock files found!")
            return {'success': False, 'error': 'No stock files found'}
        
        # Determine which files to process
        if symbols:
            # Filter to specific symbols
            files_to_process = [f for f in all_files if f.stem in symbols]
            logger.info(f"Processing {len(files_to_process)} specified symbols")
        elif sample_size:
            # Random sample
            files_to_process = random.sample(all_files, min(sample_size, len(all_files)))
            logger.info(f"Checking {len(files_to_process)} random stocks")
        else:
            # Process all
            files_to_process = all_files
            logger.info(f"Processing all {len(files_to_process)} stocks")
        
        # Process each stock
        for i, file_path in enumerate(files_to_process, 1):
            symbol = file_path.stem
            
            logger.info(f"\n[{i}/{len(files_to_process)}] Processing {symbol}...")
            
            # Check if update needed
            needs_update, last_date, sebi_compliance = self.check_stock_needs_update(file_path)
            
            if last_date:
                logger.info(f"  Last date: {last_date.date()}")
            
            if not needs_update and not force_update:
                logger.info(f"  ⏭️  Skipping (data is fresh)")
                self.skipped_stocks.append({
                    'symbol': symbol,
                    'last_date': last_date.isoformat() if last_date else None
                })
                continue
            
            # Update the stock
            logger.info(f"  🔄 Updating...")
            success = self.update_stock_data(file_path, symbol, sebi_compliance)
            
            if success:
                self.updated_stocks.append({
                    'symbol': symbol,
                    'previous_date': last_date.isoformat() if last_date else None,
                    'new_date': sebi_compliance.isoformat()
                })
        
        # Generate report
        report = {
            'timestamp': datetime.now().isoformat(),
            'pipeline': 'daily',
            'sebi_compliance_date': sebi_date.isoformat(),
            'update_threshold': threshold_date.isoformat(),
            'total_stocks': len(all_files),
            'checked_stocks': len(files_to_process),
            'updated_stocks': len(self.updated_stocks),
            'skipped_stocks': len(self.skipped_stocks),
            'errors': len(self.errors),
            'updated': self.updated_stocks,
            'skipped': self.skipped_stocks,
            'error_details': self.errors
        }
        
        # Save report
        with open(REPORT_FILE, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Daily Update Complete")
        logger.info("=" * 60)
        logger.info(f"Total checked: {len(files_to_process)}")
        logger.info(f"Updated: {len(self.updated_stocks)}")
        logger.info(f"Skipped (fresh): {len(self.skipped_stocks)}")
        logger.info(f"Errors: {len(self.errors)}")
        logger.info(f"Report saved to: {REPORT_FILE}")
        
        return report


def main():
    parser = argparse.ArgumentParser(
        description='SEBI-Compliant Daily Data Updater for NSE Stocks'
    )
    parser.add_argument(
        '--sample-size',
        type=int,
        default=None,
        help='Number of random stocks to check (default: all)'
    )
    parser.add_argument(
        '--force-update',
        action='store_true',
        help='Force update all stocks regardless of date'
    )
    parser.add_argument(
        '--symbols',
        type=str,
        nargs='+',
        help='Specific symbols to update'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        default=None,
        help='Override data directory'
    )
    
    args = parser.parse_args()
    
    # Create updater
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    updater = DailyDataUpdater(data_dir=data_dir)
    
    # Run update
    report = updater.run_update(
        sample_size=args.sample_size,
        force_update=args.force_update,
        symbols=args.symbols
    )
    
    # Exit with error code if there were failures
    if report.get('errors', 0) > 0:
        logger.warning(f"Pipeline completed with {report['errors']} errors")
        sys.exit(1)
    
    sys.exit(0)


if __name__ == '__main__':
    main()
