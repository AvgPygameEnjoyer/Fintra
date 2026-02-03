#include <emscripten/emscripten.h>
#include <emscripten/bind.h>
#include "../include/monte_carlo.h"
#include <vector>
#include <string>

using namespace emscripten;
using namespace mc;

// Wrapper class for JavaScript/Python binding
class MonteCarloSimulatorJS {
private:
    MonteCarloEngine engine_;
    
public:
    MonteCarloSimulatorJS(uint32_t seed = 0) : engine_(seed) {}
    
    void setTrades(const val& tradeArray) {
        std::vector<Trade> trades;
        unsigned int length = tradeArray["length"].as<unsigned int>();
        
        for (unsigned int i = 0; i < length; ++i) {
            val tradeObj = tradeArray[i];
            Trade t;
            t.entry_price = tradeObj["entry_price"].as<double>();
            t.exit_price = tradeObj["exit_price"].as<double>();
            t.days_held = tradeObj["days_held"].as<int>();
            t.pnl_pct = tradeObj["pnl_pct"].as<double>();
            t.is_win = tradeObj["is_win"].as<bool>();
            trades.push_back(t);
        }
        
        engine_.setTrades(trades);
    }
    
    void setReturns(const val& returnArray) {
        std::vector<double> returns;
        unsigned int length = returnArray["length"].as<unsigned int>();
        
        for (unsigned int i = 0; i < length; ++i) {
            returns.push_back(returnArray[i].as<double>());
        }
        
        engine_.setReturns(returns);
    }
    
    val runMonteCarlo(int num_simulations, uint32_t seed) {
        SimulationConfig config;
        config.num_simulations = num_simulations;
        config.seed = seed;
        
        MonteCarloAnalysis analysis = engine_.runAnalysis(config);
        
        // Build result object
        val result = val::object();
        
        // Add metadata
        result.set("seed_used", analysis.seed_used);
        result.set("num_trials", analysis.num_trials);
        
        // Add original strategy metrics
        result.set("original_return", analysis.original_return);
        result.set("original_sharpe", analysis.original_sharpe);
        result.set("original_max_dd", analysis.original_max_dd);
        
        // Add percentiles
        result.set("percentile_5", analysis.percentile_5);
        result.set("percentile_25", analysis.percentile_25);
        result.set("percentile_50", analysis.percentile_50);
        result.set("percentile_75", analysis.percentile_75);
        result.set("percentile_95", analysis.percentile_95);
        
        // Add confidence intervals
        result.set("ci_lower_95", analysis.ci_lower_95);
        result.set("ci_upper_95", analysis.ci_upper_95);
        
        // Add p-values
        result.set("p_value_strategy_vs_random", analysis.p_value_strategy_vs_random);
        result.set("p_value_strategy_vs_bootstrap", analysis.p_value_strategy_vs_bootstrap);
        
        // Add distribution histogram
        val histogram = val::array();
        for (size_t i = 0; i < analysis.return_distribution.size(); ++i) {
            histogram.call<void>("push", analysis.return_distribution[i]);
        }
        result.set("return_distribution", histogram);
        result.set("distribution_min", analysis.distribution_min);
        result.set("distribution_max", analysis.distribution_max);
        
        // Add individual simulation results (limited to first 100 for performance)
        val simulations = val::array();
        int sim_count = std::min(100, static_cast<int>(analysis.simulations.size()));
        for (int i = 0; i < sim_count; ++i) {
            const auto& sim = analysis.simulations[i];
            val simObj = val::object();
            simObj.set("final_value", sim.final_value);
            simObj.set("total_return_pct", sim.total_return_pct);
            simObj.set("max_drawdown_pct", sim.max_drawdown_pct);
            simObj.set("num_trades", sim.num_trades);
            simObj.set("win_rate", sim.win_rate);
            simObj.set("sharpe_ratio", sim.sharpe_ratio);
            simulations.call<void>("push", simObj);
        }
        result.set("sample_simulations", simulations);
        
        // Calculate summary statistics
        double mean_return = 0.0;
        double mean_sharpe = 0.0;
        double mean_drawdown = 0.0;
        
        for (const auto& sim : analysis.simulations) {
            mean_return += sim.total_return_pct;
            mean_sharpe += sim.sharpe_ratio;
            mean_drawdown += sim.max_drawdown_pct;
        }
        
        if (!analysis.simulations.empty()) {
            mean_return /= analysis.simulations.size();
            mean_sharpe /= analysis.simulations.size();
            mean_drawdown /= analysis.simulations.size();
        }
        
        result.set("mean_return", mean_return);
        result.set("mean_sharpe", mean_sharpe);
        result.set("mean_max_drawdown", mean_drawdown);
        
        // Interpretation
        std::string interpretation;
        if (analysis.original_return > analysis.percentile_95) {
            interpretation = "STRONG_SIGNAL: Strategy significantly outperforms random permutations (>95th percentile). Results are likely NOT due to luck.";
        } else if (analysis.original_return > analysis.percentile_75) {
            interpretation = "MODERATE_SIGNAL: Strategy performs better than 75% of random permutations. Results suggest skill over luck.";
        } else if (analysis.original_return > analysis.percentile_50) {
            interpretation = "WEAK_SIGNAL: Strategy performs above median but not exceptionally. Results may have some skill component.";
        } else {
            interpretation = "NO_SIGNAL: Strategy does not outperform random permutations. Results likely due to luck.";
        }
        result.set("interpretation", interpretation);
        
        return result;
    }
    
    val runQuickAnalysis(int num_simulations, uint32_t seed) {
        return runMonteCarlo(num_simulations, seed);
    }
};

// Binding definitions
EMSCRIPTEN_BINDINGS(monte_carlo_module) {
    class_<MonteCarloSimulatorJS>("MonteCarloSimulator")
        .constructor<uint32_t>()
        .function("setTrades", &MonteCarloSimulatorJS::setTrades)
        .function("setReturns", &MonteCarloSimulatorJS::setReturns)
        .function("runMonteCarlo", &MonteCarloSimulatorJS::runMonteCarlo)
        .function("runQuickAnalysis", &MonteCarloSimulatorJS::runQuickAnalysis);
}
