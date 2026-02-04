# Monte Carlo Quick Fix

## Problem Fixed
`Uncaught ReferenceError: runQuickMonteCarlo is not defined` and `runFullMonteCarlo is not defined`

## Root Cause
Old Monte Carlo code in `backtesting.js` had:
1. Inline onclick handlers referencing non-existent global functions
2. Duplicate function definitions that conflicted with the new implementation
3. Dynamic imports that were causing timing issues

## Changes Made

### 1. Removed from `backtesting.js`:
- Old Monte Carlo HTML section from `displayBacktestResults()` function (lines 272-289)
- Old `runQuickMonteCarlo()` function (lines 295-299)
- Old `runFullMonteCarlo()` function (lines 301-305)

### 2. Removed from `monte_carlo.js`:
- Auto-initialization code that was causing conflicts with `main.js` (lines 179-184)
- This code would run twice: once on DOMContentLoaded and once when main.js initialized it

### 3. Added to `main.js`:
- Import: `import { initializeMonteCarlo } from './monte_carlo.js';`
- Call: `initializeMonteCarlo();` in the initialization sequence

### 4. Fixed in `dashboard.html`:
- Added `type="button"` to prevent button from submitting forms
- Button IDs: `mc-quick-btn` and `mc-full-btn`

## Current Architecture

```
main.js (on DOMContentLoaded)
  ↓
initializeMonteCarlo() from monte_carlo.js
  ↓
Attaches event listeners to:
  - #mc-quick-btn → runMonteCarloAnalysis(1000)
  - #mc-full-btn → runMonteCarloAnalysis(10000)
```

## How It Works Now

1. User runs backtest
2. Backtest completes
3. Monte Carlo buttons appear (already in DOM, shown via CSS)
4. User clicks "Quick (1K sims)" or "Full (10K sims)"
5. Event listener triggers `runMonteCarloAnalysis()`
6. Monte Carlo analysis runs and results display

## Files Modified
- `backtesting.js` - Removed old MC code
- `monte_carlo.js` - Removed auto-initialization
- `main.js` - Added MC initialization
- `dashboard.html` - Added type="button" to buttons
