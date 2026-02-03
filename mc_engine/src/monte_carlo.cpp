#include "monte_carlo.h"
#include <algorithm>
#include <numeric>
#include <cmath>

namespace mc {

MonteCarloEngine::MonteCarloEngine(uint32_t seed) : rng_(seed == 0 ? std::random_device{}() : seed) {}

void MonteCarloEngine::setTrades(const std::vector<Trade>& trades) {
    original_trades_ = trades;
}

void MonteCarloEngine::setReturns(const std::vector<double>& returns) {
    daily_returns_ = returns;
}

void MonteCarloEngine::setPrices(const std::vector<double>& prices) {
    prices_ = prices;
}

MonteCarloAnalysis MonteCarloEngine::runAnalysis(const SimulationConfig& config) {
    MonteCarloAnalysis result;
    result.seed_used = config.seed;
    result.num_trials = config.num_simulations;
    
    // Run all three simulation types
    auto shuffle_results = runPositionShuffle(config.num_simulations / 3);
    auto perm_results = runReturnPermutation(config.num_simulations / 3);
    auto bootstrap_results = runBootstrap(config.num_simulations / 3);
    
    // Combine all results
    result.simulations.insert(result.simulations.end(), shuffle_results.begin(), shuffle_results.end());
    result.simulations.insert(result.simulations.end(), perm_results.begin(), perm_results.end());
    result.simulations.insert(result.simulations.end(), bootstrap_results.begin(), bootstrap_results.end());
    
    // Extract return values for statistical analysis
    std::vector<double> returns;
    returns.reserve(result.simulations.size());
    for (const auto& sim : result.simulations) {
        returns.push_back(sim.total_return_pct);
    }
    
    // Compute percentiles
    computePercentiles(returns, result);
    
    // Calculate confidence intervals (95%)
    result.ci_lower_95 = result.percentile_5;
    result.ci_upper_95 = result.percentile_95;
    
    // Build histogram (20 bins)
    result.return_distribution.resize(20, 0);
    if (!returns.empty()) {
        result.distribution_min = *std::min_element(returns.begin(), returns.end());
        result.distribution_max = *std::max_element(returns.begin(), returns.end());
        
        double bin_width = (result.distribution_max - result.distribution_min) / 20.0;
        if (bin_width > 0) {
            for (double ret : returns) {
                int bin = static_cast<int>((ret - result.distribution_min) / bin_width);
                if (bin >= 0 && bin < 20) {
                    result.return_distribution[bin]++;
                }
            }
        }
    }
    
    return result;
}

std::vector<SimulationResult> MonteCarloEngine::runPositionShuffle(int num_simulations) {
    std::vector<SimulationResult> results;
    results.reserve(num_simulations);
    
    if (original_trades_.empty()) {
        return results;
    }
    
    // Extract just the P&L percentages from trades
    std::vector<double> trade_pnls;
    trade_pnls.reserve(original_trades_.size());
    for (const auto& trade : original_trades_) {
        trade_pnls.push_back(trade.pnl_pct / 100.0); // Convert to decimal
    }
    
    for (int i = 0; i < num_simulations; ++i) {
        // Shuffle the trades
        std::vector<double> shuffled_pnls = trade_pnls;
        std::shuffle(shuffled_pnls.begin(), shuffled_pnls.end(), rng_);
        
        // Simulate equity curve
        double capital = 100000.0; // Initial capital
        std::vector<double> equity_curve;
        equity_curve.reserve(shuffled_pnls.size() + 1);
        equity_curve.push_back(capital);
        
        for (double pnl : shuffled_pnls) {
            capital *= (1.0 + pnl);
            equity_curve.push_back(capital);
        }
        
        SimulationResult sim;
        sim.final_value = capital;
        sim.total_return_pct = ((capital - 100000.0) / 100000.0) * 100.0;
        sim.max_drawdown_pct = calculateMaxDrawdown(equity_curve);
        sim.num_trades = static_cast<int>(shuffled_pnls.size());
        
        // Calculate win rate from shuffled trades
        int wins = 0;
        for (double pnl : shuffled_pnls) {
            if (pnl > 0) wins++;
        }
        sim.win_rate = shuffled_pnls.empty() ? 0.0 : (static_cast<double>(wins) / shuffled_pnls.size()) * 100.0;
        
        // Calculate Sharpe ratio (simplified)
        sim.sharpe_ratio = calculateSharpeRatio(equity_curve);
        
        results.push_back(sim);
    }
    
    return results;
}

std::vector<SimulationResult> MonteCarloEngine::runReturnPermutation(int num_simulations) {
    std::vector<SimulationResult> results;
    results.reserve(num_simulations);
    
    if (daily_returns_.empty()) {
        return results;
    }
    
    int num_days = static_cast<int>(daily_returns_.size());
    
    for (int i = 0; i < num_simulations; ++i) {
        // Create a permutation of daily returns
        std::vector<double> permuted_returns = daily_returns_;
        std::shuffle(permuted_returns.begin(), permuted_returns.end(), rng_);
        
        // Simulate equity curve with position sizing based on volatility
        double capital = 100000.0;
        std::vector<double> equity_curve;
        equity_curve.reserve(num_days + 1);
        equity_curve.push_back(capital);
        
        // Simple simulation: apply daily returns directly
        // In reality, you'd want to simulate entry/exit timing
        for (double daily_ret : permuted_returns) {
            // Apply the return (scaled to match trade frequency)
            capital *= (1.0 + daily_ret);
            equity_curve.push_back(capital);
        }
        
        SimulationResult sim;
        sim.final_value = capital;
        sim.total_return_pct = ((capital - 100000.0) / 100000.0) * 100.0;
        sim.max_drawdown_pct = calculateMaxDrawdown(equity_curve);
        sim.num_trades = num_days / 20; // Approximate number of trades (assuming ~20 days per trade)
        sim.win_rate = 50.0; // Random walk assumption
        sim.sharpe_ratio = calculateSharpeRatio(equity_curve);
        
        results.push_back(sim);
    }
    
    return results;
}

std::vector<SimulationResult> MonteCarloEngine::runBootstrap(int num_simulations) {
    std::vector<SimulationResult> results;
    results.reserve(num_simulations);
    
    if (original_trades_.empty()) {
        return results;
    }
    
    // Extract P&L percentages
    std::vector<double> trade_pnls;
    trade_pnls.reserve(original_trades_.size());
    for (const auto& trade : original_trades_) {
        trade_pnls.push_back(trade.pnl_pct / 100.0);
    }
    
    std::uniform_int_distribution<size_t> dist(0, trade_pnls.size() - 1);
    
    for (int i = 0; i < num_simulations; ++i) {
        // Bootstrap sample with replacement
        std::vector<double> bootstrapped_pnls;
        bootstrapped_pnls.reserve(trade_pnls.size());
        
        for (size_t j = 0; j < trade_pnls.size(); ++j) {
            size_t idx = dist(rng_);
            bootstrapped_pnls.push_back(trade_pnls[idx]);
        }
        
        // Simulate equity curve
        double capital = 100000.0;
        std::vector<double> equity_curve;
        equity_curve.reserve(bootstrapped_pnls.size() + 1);
        equity_curve.push_back(capital);
        
        for (double pnl : bootstrapped_pnls) {
            capital *= (1.0 + pnl);
            equity_curve.push_back(capital);
        }
        
        SimulationResult sim;
        sim.final_value = capital;
        sim.total_return_pct = ((capital - 100000.0) / 100000.0) * 100.0;
        sim.max_drawdown_pct = calculateMaxDrawdown(equity_curve);
        sim.num_trades = static_cast<int>(bootstrapped_pnls.size());
        
        int wins = 0;
        for (double pnl : bootstrapped_pnls) {
            if (pnl > 0) wins++;
        }
        sim.win_rate = bootstrapped_pnls.empty() ? 0.0 : (static_cast<double>(wins) / bootstrapped_pnls.size()) * 100.0;
        sim.sharpe_ratio = calculateSharpeRatio(equity_curve);
        
        results.push_back(sim);
    }
    
    return results;
}

double MonteCarloEngine::calculateSharpeRatio(const std::vector<double>& equity_curve) {
    if (equity_curve.size() < 2) return 0.0;
    
    // Calculate daily returns from equity curve
    std::vector<double> returns;
    returns.reserve(equity_curve.size() - 1);
    
    for (size_t i = 1; i < equity_curve.size(); ++i) {
        returns.push_back((equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]);
    }
    
    if (returns.empty()) return 0.0;
    
    // Calculate mean and std dev
    double sum = std::accumulate(returns.begin(), returns.end(), 0.0);
    double mean = sum / returns.size();
    
    double sq_sum = 0.0;
    for (double r : returns) {
        sq_sum += (r - mean) * (r - mean);
    }
    double std_dev = std::sqrt(sq_sum / returns.size());
    
    // Annualized Sharpe (assuming daily returns, 252 trading days)
    if (std_dev == 0) return 0.0;
    return (mean / std_dev) * std::sqrt(252.0);
}

double MonteCarloEngine::calculateMaxDrawdown(const std::vector<double>& equity_curve) {
    if (equity_curve.empty()) return 0.0;
    
    double max_dd = 0.0;
    double peak = equity_curve[0];
    
    for (double value : equity_curve) {
        if (value > peak) {
            peak = value;
        }
        double drawdown = (peak - value) / peak;
        if (drawdown > max_dd) {
            max_dd = drawdown;
        }
    }
    
    return max_dd * 100.0; // Return as percentage
}

void MonteCarloEngine::computePercentiles(std::vector<double>& values, MonteCarloAnalysis& result) {
    if (values.empty()) {
        result.percentile_5 = result.percentile_25 = result.percentile_50 = 
        result.percentile_75 = result.percentile_95 = 0.0;
        return;
    }
    
    std::sort(values.begin(), values.end());
    
    auto get_percentile = [&values](double p) -> double {
        if (values.empty()) return 0.0;
        size_t idx = static_cast<size_t>(p * (values.size() - 1) / 100.0);
        return values[idx];
    };
    
    result.percentile_5 = get_percentile(5);
    result.percentile_25 = get_percentile(25);
    result.percentile_50 = get_percentile(50);
    result.percentile_75 = get_percentile(75);
    result.percentile_95 = get_percentile(95);
}

double MonteCarloEngine::computePValue(double observed_value, const std::vector<double>& simulated_values) {
    if (simulated_values.empty()) return 1.0;
    
    int count_better = 0;
    for (double sim_val : simulated_values) {
        if (sim_val >= observed_value) {
            count_better++;
        }
    }
    
    return static_cast<double>(count_better) / simulated_values.size();
}

} // namespace mc
