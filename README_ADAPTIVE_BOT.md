# 🧠 Adaptive Trading Bot

An advanced algorithmic trading system that dynamically adapts its strategies, parameters, and behavior in real-time to optimize trading performance across changing market conditions.

## 🌟 What is the Adaptive Trading Bot?

The Adaptive Trading Bot is a next-generation trading system that goes beyond traditional algorithmic trading by incorporating machine learning, market regime detection, and continuous self-improvement. Unlike static trading bots that use fixed strategies, this system learns from market conditions and its own trading history to continuously evolve and optimize its approach.

### Key Differentiators

- **🧠 Machine Learning Integration**: Uses ensemble ML models to predict trade outcomes and adapt strategies
- **📊 Market Regime Detection**: Automatically identifies market conditions (trending, ranging, volatile) and adjusts accordingly  
- **⚙️ Dynamic Parameter Optimization**: Continuously optimizes strategy parameters based on performance feedback
- **🔄 Self-Improving**: Learns from every trade to become more profitable over time
- **🎯 Multi-Strategy Ensemble**: Combines multiple trading strategies with intelligent weighting
- **📈 Portfolio Optimization**: Manages multiple trading pairs with correlation analysis and risk balancing

## 🏗️ How It Works

### Core Architecture

```
Market Data → Regime Detection → Strategy Selection → ML Prediction → Trade Execution
     ↓              ↓                    ↓              ↓              ↓
Performance Analysis ← Adaptation Controller ← Parameter Optimizer ← Risk Manager
```

### 1. Market Regime Detection
The system continuously analyzes market conditions across multiple timeframes to identify:
- **Trending Bull/Bear**: Strong directional movements
- **Ranging**: Sideways price action within bounds  
- **High/Low Volatility**: Market volatility levels
- **Uncertain**: Mixed or unclear signals

### 2. Adaptive Strategy Engine
Manages a portfolio of trading strategies with dynamic weighting:
- **Enhanced Momentum**: Catches quick price moves with volume confirmation
- **Price Action**: Support/resistance breakout detection
- **Multi-Timeframe**: Cross-timeframe trend analysis
- **Volatility Adjusted**: Adapts to changing market volatility
- **Custom Strategies**: Easily add new strategies to the ensemble

### 3. Machine Learning Engine
Uses multiple ML models to predict trade success:
- **Random Forest**: For feature importance and robust predictions
- **Gradient Boosting**: For complex pattern recognition
- **Ensemble Methods**: Combines multiple models for better accuracy
- **Online Learning**: Updates models with new trade results

### 4. Dynamic Parameter Optimization
Continuously optimizes trading parameters:
- **Bayesian Optimization**: Efficient parameter space exploration
- **Walk-Forward Analysis**: Validates parameters on out-of-sample data
- **Regime-Specific Optimization**: Different parameters for different market conditions
- **Performance-Based Adjustment**: Adapts based on recent trading results

### 5. Portfolio Optimization
Manages multiple trading pairs intelligently:
- **Correlation Analysis**: Avoids over-concentration in correlated assets
- **Risk Balancing**: Distributes risk across the portfolio
- **Capital Allocation**: Dynamically allocates capital to best opportunities
- **Rebalancing**: Automatically rebalances based on performance

## 🚀 Getting Started

### Prerequisites
- **Python 3.8+** with pip
- **4GB RAM** minimum (8GB recommended)
- **Trading Account** (Kraken supported, paper trading available)
- **Stable Internet** connection

### Installation

```bash
# 1. Clone the repository
git clone <repository-url>
cd crypto-scalping-bot-kiro

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.template .env
# Edit .env with your API credentials (optional for paper trading)
```

### Quick Start - Paper Trading

```bash
# Start with paper trading (recommended)
python -c "
from bot.adaptive.adaptive_bot_main import AdaptiveBotMain, AdaptiveBotConfig
import asyncio

config = AdaptiveBotConfig(
    trading_pairs=['BTC/USD', 'ETH/USD'],
    paper_trading=True,
    initial_capital=10000.0,
    adaptation_enabled=True
)

async def main():
    bot = AdaptiveBotMain(config)
    if await bot.start():
        await bot.run_main_loop()

asyncio.run(main())
"
```

### Configuration Options

```python
config = AdaptiveBotConfig(
    # Trading pairs to monitor
    trading_pairs=['BTC/USD', 'ETH/USD', 'ADA/USD'],
    
    # Paper trading (recommended for testing)
    paper_trading=True,
    initial_capital=10000.0,
    
    # Adaptive behavior
    adaptation_enabled=True,
    adaptation_frequency_minutes=60,
    min_adaptation_confidence=0.7,
    
    # Risk management
    max_risk_per_trade=0.02,  # 2% per trade
    max_portfolio_risk=0.1,   # 10% total portfolio
    max_drawdown_threshold=0.15,  # 15% max drawdown
    
    # Performance thresholds
    min_performance_threshold=-0.05,  # -5% minimum performance
    performance_evaluation_hours=24,
    
    # System settings
    monitoring_enabled=True,
    alerting_enabled=True
)
```

## 📊 Features in Detail

### Market Regime Detection
- **Multi-timeframe Analysis**: Analyzes 5m, 15m, 1h, and 4h timeframes
- **Technical Indicators**: Uses ADX, ATR, Bollinger Bands, RSI, MACD
- **Regime Classification**: Automatically classifies market conditions
- **Confidence Scoring**: Provides confidence levels for regime detection
- **Transition Smoothing**: Prevents rapid regime switching with hysteresis

### Strategy Adaptation
- **Performance Tracking**: Monitors each strategy's performance in real-time
- **Dynamic Weighting**: Adjusts strategy weights based on recent performance
- **Regime-Aware Selection**: Selects optimal strategies for current market conditions
- **Ensemble Signals**: Combines multiple strategy signals intelligently
- **Strategy Switching**: Switches strategies with hysteresis to prevent whipsaws

### Machine Learning
- **Feature Engineering**: Creates 50+ technical and market structure features
- **Model Training**: Trains multiple ML models on historical data
- **Ensemble Prediction**: Combines predictions from multiple models
- **Online Learning**: Updates models with new trade results
- **Drift Detection**: Detects when models need retraining

### Risk Management
- **Position Sizing**: Dynamic position sizing based on volatility and confidence
- **Portfolio Risk**: Monitors total portfolio exposure and correlation
- **Stop Loss/Take Profit**: Dynamic risk levels based on market conditions
- **Drawdown Protection**: Automatic position reduction during drawdowns
- **Emergency Stops**: Circuit breakers for extreme market conditions

### Performance Analytics
- **Real-time Metrics**: Live tracking of returns, Sharpe ratio, drawdown
- **Strategy Attribution**: Performance breakdown by strategy and regime
- **Trade Analysis**: Detailed analysis of winning and losing trades
- **Adaptation History**: Track of all adaptations and their effectiveness
- **Backtesting**: Historical simulation with walk-forward analysis

## 🎛️ Usage Examples

### Basic Paper Trading
```python
from bot.adaptive.adaptive_bot_main import AdaptiveBotMain, AdaptiveBotConfig
import asyncio

# Conservative setup for beginners
config = AdaptiveBotConfig(
    trading_pairs=['BTC/USD'],
    paper_trading=True,
    initial_capital=5000.0,
    max_risk_per_trade=0.01,  # 1% risk per trade
    adaptation_enabled=True
)

async def run_bot():
    bot = AdaptiveBotMain(config)
    await bot.start()
    await bot.run_main_loop()

asyncio.run(run_bot())
```

### Multi-Pair Aggressive Trading
```python
# Aggressive setup for experienced traders
config = AdaptiveBotConfig(
    trading_pairs=['BTC/USD', 'ETH/USD', 'ADA/USD', 'SOL/USD'],
    paper_trading=True,
    initial_capital=25000.0,
    max_risk_per_trade=0.03,  # 3% risk per trade
    max_portfolio_risk=0.15,  # 15% total portfolio risk
    adaptation_frequency_minutes=30,  # More frequent adaptations
    min_adaptation_confidence=0.6  # Lower confidence threshold
)
```

### Custom Strategy Integration
```python
from bot.adaptive.adaptive_strategy_engine import AdaptiveStrategyEngine
from bot.strategy import BaseStrategy

class CustomStrategy(BaseStrategy):
    def calculate_signals(self, data):
        # Your custom strategy logic here
        pass

# Add to the engine
engine = AdaptiveStrategyEngine()
engine.add_strategy("custom_strategy", CustomStrategy(), {
    'base_weight': 0.2,
    'regime_preferences': [RegimeType.HIGH_VOLATILITY]
})
```

## 📈 Performance Monitoring

### Real-time Dashboard
The system provides comprehensive monitoring through:
- **Portfolio Overview**: Live P&L, positions, and allocation
- **Strategy Performance**: Individual strategy metrics and weights
- **Market Regime**: Current regime detection and confidence
- **Adaptation Activity**: Recent adaptations and their impacts
- **Risk Metrics**: Real-time risk assessment and exposure

### Key Metrics Tracked
- **Total Return**: Overall portfolio performance
- **Sharpe Ratio**: Risk-adjusted returns
- **Maximum Drawdown**: Largest peak-to-trough decline
- **Win Rate**: Percentage of profitable trades
- **Profit Factor**: Ratio of gross profit to gross loss
- **Strategy Attribution**: Performance by strategy and regime
- **Adaptation Effectiveness**: Success rate of adaptations

## 🔧 Advanced Configuration

### Machine Learning Settings
```python
ml_config = {
    'model_types': ['random_forest', 'gradient_boosting', 'ensemble'],
    'feature_engineering': {
        'technical_indicators': True,
        'market_structure': True,
        'cross_asset_correlations': True
    },
    'online_learning': {
        'enabled': True,
        'update_frequency': 'daily',
        'drift_detection': True
    }
}
```

### Regime Detection Settings
```python
regime_config = {
    'timeframes': ['5m', '15m', '1h', '4h'],
    'timeframe_weights': {'5m': 0.1, '15m': 0.2, '1h': 0.3, '4h': 0.4},
    'confidence_threshold': 0.6,
    'smoothing_factor': 0.3,
    'min_data_points': 100
}
```

### Adaptation Control
```python
adaptation_config = {
    'max_adaptations_per_day': 10,
    'min_adaptation_confidence': 0.7,
    'adaptation_frequency_minutes': 60,
    'rollback_enabled': True,
    'a_b_testing': True
}
```

## 🧪 Testing and Validation

### Backtesting
```python
from bot.adaptive.backtesting_framework import BacktestingFramework

backtester = BacktestingFramework()
results = backtester.run_backtest(
    start_date='2023-01-01',
    end_date='2024-01-01',
    initial_capital=10000,
    trading_pairs=['BTC/USD', 'ETH/USD']
)

print(f"Total Return: {results.total_return:.2%}")
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")
```

### Paper Trading Validation
```python
# Run extended paper trading test
config = AdaptiveBotConfig(
    paper_trading=True,
    initial_capital=10000.0,
    trading_pairs=['BTC/USD', 'ETH/USD'],
    adaptation_enabled=True
)

# Monitor for several days/weeks before live trading
```

### Performance Validation
```python
from bot.adaptive.performance_analyzer import PerformanceAnalyzer

analyzer = PerformanceAnalyzer()
metrics = analyzer.analyze_performance(
    trades=trade_history,
    timeframe='30d'
)

print(f"Win Rate: {metrics.win_rate:.1%}")
print(f"Profit Factor: {metrics.profit_factor:.2f}")
print(f"Average Trade Duration: {metrics.avg_trade_duration}")
```

## ⚠️ Risk Warnings

### Important Disclaimers

**CRYPTOCURRENCY TRADING INVOLVES SUBSTANTIAL RISK OF LOSS**

- **Market Risk**: Crypto markets are extremely volatile and unpredictable
- **Model Risk**: ML models may fail or produce incorrect predictions
- **Technical Risk**: Software bugs or system failures can cause losses
- **Adaptation Risk**: Incorrect adaptations may worsen performance
- **Overfitting Risk**: Models may overfit to historical data

### Safety Guidelines

✅ **ALWAYS start with paper trading**  
✅ **Test thoroughly before using real money**  
✅ **Start with small amounts and gradually increase**  
✅ **Monitor the system actively, especially during volatile markets**  
✅ **Set strict risk limits and stick to them**  
✅ **Keep detailed logs and analyze performance regularly**  
✅ **Have a plan for when to stop or reduce trading**

### Responsible Usage

- **Understand the System**: Learn how the adaptive mechanisms work
- **Monitor Adaptations**: Review and validate system adaptations
- **Set Conservative Limits**: Use conservative risk parameters initially
- **Regular Review**: Regularly review performance and adjust settings
- **Emergency Procedures**: Have procedures for emergency shutdown

## 🔮 Future Enhancements

### Planned Features
- **Deep Learning Models**: Integration of neural networks and transformers
- **Alternative Data**: News sentiment, social media, and on-chain data
- **Multi-Exchange Support**: Trading across multiple exchanges
- **Advanced Portfolio Theory**: Modern portfolio theory integration
- **Reinforcement Learning**: RL-based strategy optimization
- **Real-time Optimization**: Intraday parameter optimization

### Research Areas
- **Quantum Computing**: Quantum algorithms for optimization
- **Federated Learning**: Collaborative learning across multiple bots
- **Explainable AI**: Better understanding of model decisions
- **Causal Inference**: Understanding causal relationships in markets
- **Meta-Learning**: Learning to learn new market patterns quickly

## 🤝 Contributing

We welcome contributions to improve the Adaptive Trading Bot!

### Development Setup
```bash
# Clone and setup development environment
git clone <repository-url>
cd crypto-scalping-bot-kiro
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Areas for Contribution
- **🧠 ML Models**: New machine learning algorithms and techniques
- **📊 Strategies**: Additional trading strategies and indicators  
- **🔧 Optimization**: Performance improvements and optimizations
- **📱 UI/UX**: Dashboard improvements and visualization
- **🧪 Testing**: Additional tests and validation frameworks
- **📚 Documentation**: Improved documentation and tutorials

## 📚 Documentation

### Core Components
- **[Adaptive Bot Main](bot/adaptive/adaptive_bot_main.py)**: Main application orchestrator
- **[Strategy Engine](bot/adaptive/adaptive_strategy_engine.py)**: Dynamic strategy management
- **[ML Engine](bot/adaptive/ml_engine.py)**: Machine learning infrastructure
- **[Regime Detector](bot/adaptive/market_regime_detector.py)**: Market condition analysis
- **[Parameter Optimizer](bot/adaptive/parameter_optimizer.py)**: Dynamic parameter optimization

### Configuration
- **[Adaptive Config](bot/adaptive/adaptive_config.py)**: Configuration management
- **[Data Models](bot/adaptive/data_models.py)**: Core data structures
- **[Interfaces](bot/adaptive/interfaces.py)**: Component interfaces

### Analysis Tools
- **[Performance Analyzer](bot/adaptive/performance_analyzer.py)**: Performance metrics and analysis
- **[Backtesting Framework](bot/adaptive/backtesting_framework.py)**: Historical simulation
- **[Diagnostic Tools](bot/adaptive/diagnostic_tools.py)**: System diagnostics

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🎯 Summary

The Adaptive Trading Bot represents the next evolution in algorithmic trading, combining:

- **🧠 Artificial Intelligence**: Machine learning models that learn and adapt
- **📊 Market Intelligence**: Advanced market regime detection and analysis  
- **⚙️ Dynamic Optimization**: Continuous parameter and strategy optimization
- **🛡️ Risk Management**: Sophisticated risk controls and portfolio management
- **📈 Performance Focus**: Relentless focus on improving trading performance

**Built for traders who want a system that evolves and improves over time, not just executes static strategies.**

Start with paper trading, learn the system, and gradually scale up as you gain confidence. The adaptive nature means the bot gets better over time, but it requires careful monitoring and responsible usage.

**Trade responsibly and never risk more than you can afford to lose!** 🚀