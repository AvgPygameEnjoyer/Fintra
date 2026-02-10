# Implementation Plan: SEBI-Compliant Live Replay, Forward Testing & GitHub Actions Data Pipeline

## Executive Summary

This plan implements three major features:
1. **GitHub Actions Data Pipeline**: Automated daily checks to update Parquet files before they hit the SEBI deadline
2. **SEBI-Compliant Live Replay**: Simulate live trading using historical data with 31-day lag
3. **Forward Testing**: Test strategies on "future" data (walk-forward analysis)

---

## Phase 1: GitHub Actions Data Pipeline

### 1.1 Create `.github/workflows/data-update.yml`

**Schedule**: Run daily at 2 AM UTC (after market close, minimal API load)

**Logic Flow**:
```
Today = February 9, 2025
SEBI Deadline = Today - 31 days = January 9, 2025
Buffer = 7 days (configurable)
Update Threshold = January 9 + 7 = January 16, 2025

Check random sample of Parquet files (e.g., 50 stocks):
  If file.last_date >= January 16, 2025:
    → Data is fresh, skip
  Else:
    → Update file with data up to January 9, 2025 (SEBI limit)
```

**Why this works**:
- 31-day lag means we don't need daily updates
- Update when data is within 7 days of deadline
- Batch updates to reduce API calls and GitHub Actions minutes

### 1.2 Create `scripts/check_and_update_data.py`

**Features**:
- Sample 50-100 random stocks from data directory
- Check last date in each Parquet file
- Compare against `today - 31 days + buffer`
- If update needed:
  - Fetch from yfinance up to SEBI limit date
  - Update Parquet file
  - Log changes
- Generate report of updated files

**SEBI Compliance**:
- Never fetch data newer than `today - 31 days`
- Log all updates for audit trail
- Validate data integrity before writing

### 1.3 Create `.github/workflows/test.yml`

**Features**:
- Run on every push to main
- Run on every pull request
- Run pytest with coverage reporting
- Upload coverage to Codecov (optional)

**Professional touches**:
- Matrix testing (Python 3.9, 3.10, 3.11)
- Cache pip dependencies
- Parallel test execution
- Artifact uploads for failed tests

---

## Phase 2: SEBI-Compliant Live Replay

### 2.1 Concept

**What it is**: Users can "replay" any historical trading day as if it were live, with:
- Real-time OHLCV updates every 1-5 seconds
- Progressive disclosure (you only see data up to the current replay time)
- Paper trading capability (make buy/sell decisions during replay)
- SEBI compliant: Always 31 days behind real-time

**Use cases**:
- Practice trading without risk
- Test reactions to market events
- Educational demonstrations
- Strategy validation in realistic conditions

### 2.2 Create `live_replay.py`

**Core Classes**:

```python
class LiveReplayEngine:
    """
    Simulates live market data from historical Parquet files.
    SEBI compliant - always uses data older than 31 days.
    """
    
    def __init__(self, symbol: str, replay_date: datetime, speed: float = 1.0):
        """
        Initialize live replay for a specific historical date.
        
        Args:
            symbol: Stock symbol to replay
            replay_date: Historical date to replay (must be >= 31 days old)
            speed: Replay speed multiplier (1.0 = real-time, 5.0 = 5x speed)
        """
        pass
    
    def start_replay(self):
        """Start streaming data with progressive disclosure."""
        pass
    
    def get_current_candle(self) -> dict:
        """Get the current candle based on replay progress."""
        pass
    
    def pause(self):
        """Pause the replay."""
        pass
    
    def resume(self):
        """Resume the replay."""
        pass
    
    def execute_paper_trade(self, action: str, quantity: int):
        """Execute a paper trade during replay."""
        pass
```

**Implementation Details**:
- Load full day of data from Parquet
- Stream candles based on `speed` parameter
- Track virtual positions and P&L
- Save replay session for review

### 2.3 Create `forward_testing.py`

**What is Forward Testing?**
While backtesting tests on past data, forward testing validates on "future" data the model hasn't seen. With SEBI's 31-day lag, our "future" is actually historical data from 31 days ago.

**Implementation**:

```python
class ForwardTestEngine:
    """
    Walk-forward analysis for strategy validation.
    Tests strategy on out-of-sample data (31-day lagged data).
    """
    
    def run_forward_test(
        self,
        strategy: str,
        train_period_days: int = 252,  # 1 year
        test_period_days: int = 21,     # 1 month
        num_iterations: int = 12        # 12 months of testing
    ):
        """
        Run walk-forward optimization:
        1. Train on Year 1, test on Month 13
        2. Train on Year 1-2, test on Month 14
        3. Continue rolling forward
        """
        pass
```

**Key Metrics**:
- Out-of-sample vs in-sample performance
- Robustness score (consistency across periods)
- Overfitting detection
- Parameter stability

### 2.4 API Endpoints

**New Routes**:

```python
# Live Replay Endpoints
@api.route('/replay/start', methods=['POST'])
def start_live_replay():
    """Start a live replay session."""
    pass

@api.route('/replay/status/<session_id>', methods=['GET'])
def get_replay_status(session_id):
    """Get current replay progress and virtual P&L."""
    pass

@api.route('/replay/trade', methods=['POST'])
def execute_paper_trade():
    """Execute paper trade during replay."""
    pass

@api.route('/replay/pause/<session_id>', methods=['POST'])
def pause_replay(session_id):
    """Pause replay."""
    pass

# Forward Testing Endpoints
@api.route('/forward-test/run', methods=['POST'])
def run_forward_test():
    """Run walk-forward analysis."""
    pass

@api.route('/forward-test/results/<test_id>', methods=['GET'])
def get_forward_test_results(test_id):
    """Get forward test results with robustness metrics."""
    pass
```

### 2.5 Frontend Components

**New UI Elements**:

1. **Replay Control Panel**:
   - Date picker (limited to SEBI-compliant dates)
   - Speed control (0.5x, 1x, 2x, 5x, 10x)
   - Play/Pause button
   - Current time display
   - Virtual P&L tracker

2. **Paper Trading Interface**:
   - Buy/Sell buttons with quantity input
   - Virtual balance display
   - Open positions list
   - Trade history

3. **Forward Testing Dashboard**:
   - Strategy selector
   - Train/Test period configuration
   - Progress bar for multi-period testing
   - Results visualization (equity curves, robustness heatmap)

---

## Phase 3: README Updates

### 3.1 Remove US Equities References

**Current mentions to update**:
- "Comprehensive coverage of Indian stocks, US equities, and ETFs" → "Comprehensive coverage of Indian stocks (NSE/BSE)"
- Any references to US market data
- Update architecture diagram if needed

### 3.2 Add New Features Section

**New section in README**:

```markdown
## 🎮 SEBI-Compliant Live Replay & Forward Testing

### Live Replay
Practice trading in realistic conditions using historical data:
- **Real-time Simulation**: Replay any trading day with 1x to 10x speed
- **Paper Trading**: Execute virtual trades during replay
- **Progressive Disclosure**: Only see data up to current replay time
- **SEBI Compliant**: Always 31 days behind real-time

### Forward Testing (Walk-Forward Analysis)
Validate strategies on out-of-sample data:
- **Rolling Window Testing**: Train on past, test on recent (31-day lagged) data
- **Robustness Metrics**: Measure consistency across multiple periods
- **Overfitting Detection**: Compare in-sample vs out-of-sample performance
- **Parameter Stability**: Track how optimal parameters change over time
```

### 3.3 Update GitHub Actions Documentation

**Add to README**:

```markdown
## 🔄 Automated Data Pipeline

GitHub Actions automatically maintains the historical database:
- **Daily Checks**: Verifies data freshness against SEBI 31-day lag requirement
- **Smart Updates**: Only updates when data approaches deadline (7-day buffer)
- **Batch Processing**: Efficiently updates 50-100 stocks per run
- **Audit Trail**: All updates logged for compliance
```

---

## Phase 4: Testing Strategy

### 4.1 Unit Tests

**Test Coverage**:

```python
# tests/test_live_replay.py

def test_replay_engine_initialization():
    """Test replay engine validates SEBI compliance."""
    pass

def test_replay_speed_control():
    """Test replay at different speeds."""
    pass

def test_paper_trade_execution():
    """Test virtual trade execution and P&L calculation."""
    pass

def test_progressive_disclosure():
    """Test that future data is not revealed early."""
    pass

# tests/test_forward_testing.py

def test_walk_forward_split():
    """Test train/test data splitting."""
    pass

def test_robustness_calculation():
    """Test robustness metrics calculation."""
    pass

def test_overfitting_detection():
    """Test overfitting detection logic."""
    pass
```

### 4.2 Integration Tests

```python
# tests/test_data_pipeline.py

def test_data_update_check():
    """Test data freshness checking logic."""
    pass

def test_sebi_compliance_validation():
    """Test that updates respect 31-day lag."""
    pass
```

### 4.3 GitHub Actions Test Integration

**In `.github/workflows/test.yml`**:

```yaml
- name: Run tests with pytest
  run: |
    pytest tests/ -v --cov=. --cov-report=xml --cov-report=html
    
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
    fail_ci_if_error: false
```

---

## Phase 5: File Structure

### New Files to Create

```
.github/
├── workflows/
│   ├── data-update.yml          # Daily data freshness check
│   ├── test.yml                 # Run tests on PR/push
│   └── deploy.yml               # Optional: auto-deploy

scripts/
├── check_and_update_data.py     # Data pipeline logic
├── validate_sebi_compliance.py  # Compliance checker
└── update_readme_stats.py       # Auto-update README metrics

backend/
├── live_replay.py               # Live replay engine
├── forward_testing.py           # Walk-forward analysis
├── paper_trading.py             # Virtual trading logic
└── replay_session_manager.py    # Session persistence

tests/
├── test_live_replay.py          # Replay engine tests
├── test_forward_testing.py      # Forward testing tests
├── test_data_pipeline.py        # Data update tests
└── test_paper_trading.py        # Paper trading tests

static/
├── replay.js                    # Replay UI controller
├── forward_test.js              # Forward testing UI
├── paper_trading.js             # Paper trading interface
└── replay_controls.js           # Replay control panel

templates/
├── replay.html                  # Replay page
└── forward_test.html            # Forward testing dashboard
```

---

## Phase 6: Implementation Timeline

### Week 1: GitHub Actions Foundation
- [ ] Create `.github/workflows/test.yml`
- [ ] Set up pytest in CI/CD
- [ ] Create `scripts/check_and_update_data.py`
- [ ] Test data pipeline locally
- [ ] Create `.github/workflows/data-update.yml`
- [ ] Update README with CI/CD badges

### Week 2: Live Replay Core
- [ ] Create `live_replay.py` with core engine
- [ ] Implement progressive disclosure logic
- [ ] Create paper trading system
- [ ] Add API endpoints for replay
- [ ] Create basic replay UI

### Week 3: Forward Testing
- [ ] Create `forward_testing.py` with walk-forward logic
- [ ] Implement robustness metrics
- [ ] Add forward testing API endpoints
- [ ] Create forward testing dashboard UI
- [ ] Add visualization components

### Week 4: Frontend Polish & Testing
- [ ] Complete replay control panel UI
- [ ] Add keyboard shortcuts for replay
- [ ] Create comprehensive test suite
- [ ] Update README with new features
- [ ] Performance optimization

### Week 5: Integration & Documentation
- [ ] End-to-end testing
- [ ] SEBI compliance audit
- [ ] Documentation updates
- [ ] GitHub Actions monitoring
- [ ] Production deployment

---

## SEBI Compliance Checklist

### Data Pipeline
- [ ] Never fetch data newer than `today - 31 days`
- [ ] Log all data updates with timestamps
- [ ] Validate data integrity before writing
- [ ] Maintain audit trail for 3+ years
- [ ] Document data sources

### Live Replay
- [ ] Validate replay date is >= 31 days old
- [ ] No real-time data used in replay
- [ ] Clear labeling: "Historical Replay - Educational Only"
- [ ] No forward-looking indicators
- [ ] Disclaimer on every replay session

### Forward Testing
- [ ] Use only 31-day lagged data for "future" periods
- [ ] Clear documentation of methodology
- [ ] No claims of future performance
- [ ] Label results as "historical simulation"

---

## Expected Outcomes

### Lines of Code Growth

| Component | New Lines | Description |
|-----------|-----------|-------------|
| **GitHub Actions** | 150 | 2 workflow files |
| **Data Pipeline Scripts** | 400 | Check, update, validation |
| **Live Replay Backend** | 800 | Engine, session manager |
| **Forward Testing** | 600 | Walk-forward analysis |
| **Paper Trading** | 500 | Virtual trading logic |
| **API Routes** | 300 | New endpoints |
| **Frontend (JS)** | 1,200 | Replay UI, controls, dashboard |
| **Tests** | 800 | Comprehensive test coverage |
| **Documentation** | 200 | README updates, comments |
| **TOTAL** | **~4,950** | **~35% codebase increase** |

### New Skills Demonstrated

- **DevOps/MLOps**: GitHub Actions, CI/CD pipelines, automated data pipelines
- **Real-time Systems**: WebSocket simulation, event-driven architecture
- **Quantitative Finance**: Walk-forward analysis, robustness testing, paper trading
- **Testing**: Comprehensive test suites, integration testing, coverage reporting
- **SEBI Compliance**: Regulatory adherence, audit trails, data governance

### Recruiter Impact

**For Quant/Trading Roles**:
- Forward testing shows understanding of overfitting
- Paper trading demonstrates trading mechanics
- SEBI compliance shows regulatory awareness

**For Full-Stack Roles**:
- GitHub Actions shows DevOps skills
- Real-time replay shows event-driven architecture
- Testing suite shows professional development practices

**For Data Engineering Roles**:
- Automated data pipeline
- Parquet file management
- Data freshness monitoring
- Batch processing optimization

---

## Questions for You

1. **Replay Speed**: What speed options do you want? (0.5x, 1x, 2x, 5x, 10x?)

2. **Data Update Frequency**: Should we check daily or only weekdays (market days)?

3. **Forward Test Periods**: Default to 12 months of walk-forward testing?

4. **Paper Trading Persistence**: Should paper trades persist across sessions or reset?

5. **WebSocket vs Polling**: For replay, should we use WebSocket (real-time feel) or polling (simpler)?

6. **Coverage Target**: What test coverage percentage? (80%, 90%, 100%?)

7. **Codecov Integration**: Want to add Codecov for coverage badges in README?

---

## Next Steps

Once you approve this plan, I can:
1. Start with Phase 1 (GitHub Actions + tests)
2. Create each component with full implementation
3. Update README incrementally
4. Ensure SEBI compliance at every step

Which phase would you like to start with?