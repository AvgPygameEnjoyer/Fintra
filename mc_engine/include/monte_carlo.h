#ifndef MONTE_CARLO_H
#define MONTE_CARLO_H

#include <vector>
#include <random>
#include <cstdint>

namespace mc {

struct SimulationConfig {
    uint32_t num_simulations = 1000;
    uint32_t seed = 0;
    double initial_capital = 100000.0;
    double risk_per_trade = 0.02;
    double atr_multiplier = 3.0;
    double tax_rate = 0.002;
    bool use_position_shuffle = true;
    bool use_return_permutation = true;
    bool use_bootstrap = true;
};

struct Trade {
    double entry_price;
    double exit_price;
    int days_held;
    double pnl_pct;
    bool is_win;
};

struct SimulationResult {
    double final_value;
    double total_return_pct;
    double max_drawdown_pct;
    int num_trades;
    double win_rate;
    double sharpe_ratio;
};

struct MonteCarloAnalysis {
    std::vector<SimulationResult> simulations;
    
    // Statistical metrics
    double p_value_strategy_vs_random;
    double p_value_strategy_vs_bootstrap;
    
    // Percentiles
    double percentile_5;
    double percentile_25;
    double percentile_50;
    double percentile_75;
    double percentile_95;
    
    // Confidence intervals
    double ci_lower_95;
    double ci_upper_95;
    
    // Original strategy metrics
    double original_return;
    double original_sharpe;
    double original_max_dd;
    
    // Distribution histogram (20 bins)
    std::vector<int> return_distribution;
    double distribution_min;
    double distribution_max;
    
    // Metadata
    uint32_t seed_used;
    uint32_t num_trials;
};

class MonteCarloEngine {
public:
    explicit MonteCarloEngine(uint32_t seed = 0);
    
    void setTrades(const std::vector<Trade>& trades);
    void setReturns(const std::vector<double>& returns);
    void setPrices(const std::vector<double>& prices);
    
    MonteCarloAnalysis runAnalysis(const SimulationConfig& config);
    
    // Individual simulation methods
    std::vector<SimulationResult> runPositionShuffle(int num_simulations);
    std::vector<SimulationResult> runReturnPermutation(int num_simulations);
    std::vector<SimulationResult> runBootstrap(int num_simulations);
    
private:
    std::mt19937_64 rng_;
    std::vector<Trade> original_trades_;
    std::vector<double> daily_returns_;
    std::vector<double> prices_;
    
    // Helper methods
    double calculateSharpeRatio(const std::vector<double>& equity_curve);
    double calculateMaxDrawdown(const std::vector<double>& equity_curve);
    std::vector<double> simulateEquityCurve(
        const std::vector<double>& trade_returns,
        double initial_capital,
        const SimulationConfig& config
    );
    void computePercentiles(std::vector<double>& values, MonteCarloAnalysis& result);
    double computePValue(double observed_value, const std::vector<double>& simulated_values);
};

} // namespace mc

#endif // MONTE_CARLO_H
