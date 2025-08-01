"""
Comprehensive backtesting framework for adaptive trading strategies.

This module provides historical simulation with realistic market conditions,
walk-forward analysis for parameter optimization validation, regime-specific
backtesting, and Monte Carlo simulation for robustness testing.
"""
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
import random
from copy import deepcopy

from .interfaces import (
    AdaptiveStrategyEngineInterface, MarketRegimeDetectorInterface,
    MLEngineInterface, ParameterOptimizerInterface, PerformanceAnalyzerInterface
)
from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, OptimizationResult,
    AdaptationEvent, StrategyAllocation
)
from .enums import RegimeType, SignalStrength, OptimizationMethod, ValidationMethod
from ..enhanced_data_manager import EnhancedDataManager
from ..utils import log_info, log_warning, log_error


logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting runs."""
    start_date: datetime
    end_date: datetime
    initial_capital: float = 10000.0
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.0005   # 0.05%
    
    # Realism settings
    use_realistic_execution: bool = True
    max_position_size_pct: float = 0.1  # Max 10% of capital per position
    min_trade_size: float = 10.0
    
    # Data settings
    data_frequency: str = '1h'  # Data frequency for backtesting
    warmup_period: int = 100    # Bars for indicator warmup
    
    # Strategy settings
    enable_regime_detection: bool = True
    enable_ml_predictions: bool = True
    enable_parameter_optimization: bool = True
    
    # Risk management
    max_drawdown_stop: float = 0.2  # Stop if drawdown exceeds 20%
    daily_loss_limit: float = 0.05  # Stop if daily loss exceeds 5%
    
    # Validation
    validation_method: ValidationMethod = ValidationMethod.WALK_FORWARD
    validation_split: float = 0.2  # 20% for validation
    
    def __post_init__(self):
        """Validate configuration."""
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < self.max_position_size_pct <= 1:
            raise ValueError("max_position_size_pct must be between 0 and 1")


@dataclass
class BacktestResult:
    """Results from a backtesting run."""
    config: BacktestConfig
    performance_metrics: PerformanceMetrics
    trades: List[Dict[str, Any]]
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    
    # Strategy-specific results
    strategy_performance: Dict[str, PerformanceMetrics] = field(default_factory=dict)
    regime_performance: Dict[RegimeType, PerformanceMetrics] = field(default_factory=dict)
    
    # Detailed analytics
    monthly_returns: pd.Series = field(default_factory=pd.Series)
    trade_analysis: Dict[str, Any] = field(default_factory=dict)
    risk_metrics: Dict[str, float] = field(default_factory=dict)
    
    # Execution details
    execution_time: timedelta = field(default=timedelta())
    total_bars_processed: int = 0
    adaptations_made: int = 0
    
    # Validation results
    validation_metrics: Optional[PerformanceMetrics] = None
    out_of_sample_performance: Optional[float] = None
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the backtest."""
        return {
            'total_return': self.performance_metrics.total_return,
            'annualized_return': self.performance_metrics.annualized_return,
            'sharpe_ratio': self.performance_metrics.sharpe_ratio,
            'max_drawdown': self.performance_metrics.max_drawdown,
            'win_rate': self.performance_metrics.win_rate,
            'profit_factor': self.performance_metrics.profit_factor,
            'total_trades': len(self.trades),
            'execution_time': self.execution_time.total_seconds(),
            'adaptations_made': self.adaptations_made
        }


class BacktestingFramework:
    """
    Comprehensive backtesting framework for adaptive strategies.
    
    Features:
    - Historical simulation with realistic market conditions
    - Walk-forward analysis for parameter optimization validation
    - Regime-specific backtesting and performance analysis
    - Monte Carlo simulation for robustness testing
    - Multi-threaded execution for performance
    """
    
    def __init__(self, 
                 data_manager: EnhancedDataManager,
                 strategy_engine: Optional[AdaptiveStrategyEngineInterface] = None,
                 regime_detector: Optional[MarketRegimeDetectorInterface] = None,
                 ml_engine: Optional[MLEngineInterface] = None,
                 parameter_optimizer: Optional[ParameterOptimizerInterface] = None,
                 performance_analyzer: Optional[PerformanceAnalyzerInterface] = None):
        """
        Initialize the backtesting framework.
        
        Args:
            data_manager: Enhanced data manager for market data
            strategy_engine: Adaptive strategy engine
            regime_detector: Market regime detector
            ml_engine: Machine learning engine
            parameter_optimizer: Parameter optimizer
            performance_analyzer: Performance analyzer
        """
        self.data_manager = data_manager
        self.strategy_engine = strategy_engine
        self.regime_detector = regime_detector
        self.ml_engine = ml_engine
        self.parameter_optimizer = parameter_optimizer
        self.performance_analyzer = performance_analyzer
        
        # Internal state
        self._current_positions: Dict[str, Dict[str, Any]] = {}
        self._trade_history: List[Dict[str, Any]] = []
        self._equity_history: List[Tuple[datetime, float]] = []
        self._adaptation_history: List[AdaptationEvent] = []
        
        logger.info("Backtesting framework initialized")
    
    def run_backtest(self, 
                    config: BacktestConfig,
                    pairs: List[str],
                    strategies: Optional[List[str]] = None) -> BacktestResult:
        """
        Run a comprehensive backtest with the given configuration.
        
        Args:
            config: Backtesting configuration
            pairs: Trading pairs to backtest
            strategies: Specific strategies to test (None for all)
            
        Returns:
            BacktestResult with comprehensive results
        """
        start_time = datetime.now()
        logger.info(f"Starting backtest from {config.start_date} to {config.end_date}")
        
        try:
            # Initialize backtest state
            self._initialize_backtest(config, pairs)
            
            # Get historical data
            historical_data = self._prepare_historical_data(config, pairs)
            
            # Run simulation
            result = self._run_simulation(config, historical_data, pairs, strategies)
            
            # Calculate final metrics
            result.execution_time = datetime.now() - start_time
            result.total_bars_processed = len(historical_data)
            result.adaptations_made = len(self._adaptation_history)
            
            logger.info(f"Backtest completed in {result.execution_time}")
            return result
            
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}")
            raise
    
    def walk_forward_analysis(self,
                            config: BacktestConfig,
                            pairs: List[str],
                            optimization_window: int = 252,  # 1 year
                            validation_window: int = 63,     # 3 months
                            step_size: int = 21) -> List[BacktestResult]:
        """
        Perform walk-forward analysis for parameter optimization validation.
        
        Args:
            config: Base backtesting configuration
            pairs: Trading pairs to analyze
            optimization_window: Bars for optimization
            validation_window: Bars for validation
            step_size: Step size between windows
            
        Returns:
            List of BacktestResult for each window
        """
        logger.info("Starting walk-forward analysis")
        
        results = []
        current_date = config.start_date
        
        while current_date + timedelta(days=optimization_window + validation_window) <= config.end_date:
            # Define optimization and validation periods
            opt_start = current_date
            opt_end = current_date + timedelta(days=optimization_window)
            val_start = opt_end
            val_end = val_start + timedelta(days=validation_window)
            
            logger.info(f"Walk-forward window: opt={opt_start} to {opt_end}, val={val_start} to {val_end}")
            
            try:
                # Optimization phase
                opt_config = deepcopy(config)
                opt_config.start_date = opt_start
                opt_config.end_date = opt_end
                
                if self.parameter_optimizer:
                    # Run parameter optimization on this window
                    historical_data = self._prepare_historical_data(opt_config, pairs)
                    self._optimize_parameters_for_window(historical_data, pairs)
                
                # Validation phase
                val_config = deepcopy(config)
                val_config.start_date = val_start
                val_config.end_date = val_end
                
                result = self.run_backtest(val_config, pairs)
                result.validation_metrics = result.performance_metrics
                results.append(result)
                
            except Exception as e:
                logger.warning(f"Walk-forward window failed: {str(e)}")
                continue
            
            # Move to next window
            current_date += timedelta(days=step_size)
        
        logger.info(f"Walk-forward analysis completed with {len(results)} windows")
        return results
    
    def regime_specific_backtest(self,
                               config: BacktestConfig,
                               pairs: List[str],
                               target_regime: RegimeType) -> BacktestResult:
        """
        Run backtest focusing on specific market regime periods.
        
        Args:
            config: Backtesting configuration
            pairs: Trading pairs to test
            target_regime: Specific regime to focus on
            
        Returns:
            BacktestResult for the specific regime
        """
        logger.info(f"Running regime-specific backtest for {target_regime}")
        
        if not self.regime_detector:
            raise ValueError("Regime detector required for regime-specific backtesting")
        
        # Get historical data
        historical_data = self._prepare_historical_data(config, pairs)
        
        # Filter data for target regime periods
        regime_data = self._filter_data_by_regime(historical_data, pairs, target_regime)
        
        if regime_data.empty:
            logger.warning(f"No data found for regime {target_regime}")
            return self._create_empty_result(config)
        
        # Run simulation on filtered data
        result = self._run_simulation(config, regime_data, pairs)
        result.regime_performance[target_regime] = result.performance_metrics
        
        logger.info(f"Regime-specific backtest completed for {target_regime}")
        return result
    
    def monte_carlo_simulation(self,
                             config: BacktestConfig,
                             pairs: List[str],
                             num_simulations: int = 1000,
                             randomization_methods: List[str] = None) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation for robustness testing.
        
        Args:
            config: Base backtesting configuration
            pairs: Trading pairs to test
            num_simulations: Number of Monte Carlo runs
            randomization_methods: Methods for randomization
            
        Returns:
            Dictionary with Monte Carlo results and statistics
        """
        logger.info(f"Starting Monte Carlo simulation with {num_simulations} runs")
        
        if randomization_methods is None:
            randomization_methods = ['bootstrap', 'parameter_noise', 'data_shuffle']
        
        results = []
        
        # Run simulations in parallel
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            
            for i in range(num_simulations):
                future = executor.submit(
                    self._run_monte_carlo_iteration,
                    config, pairs, i, randomization_methods
                )
                futures.append(future)
            
            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.warning(f"Monte Carlo iteration failed: {str(e)}")
        
        # Analyze Monte Carlo results
        mc_analysis = self._analyze_monte_carlo_results(results)
        
        logger.info(f"Monte Carlo simulation completed with {len(results)} successful runs")
        return mc_analysis
    
    def stress_test(self,
                   config: BacktestConfig,
                   pairs: List[str],
                   stress_scenarios: List[Dict[str, Any]]) -> Dict[str, BacktestResult]:
        """
        Run stress tests under various market scenarios.
        
        Args:
            config: Base backtesting configuration
            pairs: Trading pairs to test
            stress_scenarios: List of stress scenario configurations
            
        Returns:
            Dictionary mapping scenario names to results
        """
        logger.info(f"Running stress tests with {len(stress_scenarios)} scenarios")
        
        results = {}
        
        for scenario in stress_scenarios:
            scenario_name = scenario.get('name', 'unnamed_scenario')
            logger.info(f"Running stress test: {scenario_name}")
            
            try:
                # Modify data according to stress scenario
                stressed_config = self._apply_stress_scenario(config, scenario)
                result = self.run_backtest(stressed_config, pairs)
                results[scenario_name] = result
                
            except Exception as e:
                logger.error(f"Stress test {scenario_name} failed: {str(e)}")
                continue
        
        logger.info(f"Stress testing completed with {len(results)} scenarios")
        return results
    
    def _initialize_backtest(self, config: BacktestConfig, pairs: List[str]) -> None:
        """Initialize backtest state."""
        self._current_positions = {pair: {} for pair in pairs}
        self._trade_history = []
        self._equity_history = [(config.start_date, config.initial_capital)]
        self._adaptation_history = []
        
        logger.debug("Backtest state initialized")
    
    def _prepare_historical_data(self, config: BacktestConfig, pairs: List[str]) -> pd.DataFrame:
        """Prepare historical data for backtesting."""
        logger.info("Preparing historical data")
        
        all_data = {}
        
        for pair in pairs:
            try:
                # Get historical data from data manager
                data = self.data_manager.get_historical_data(
                    pair=pair,
                    timeframe=config.data_frequency,
                    start_time=config.start_date - timedelta(days=config.warmup_period),
                    end_time=config.end_date
                )
                
                if data is not None and not data.empty:
                    all_data[pair] = data
                else:
                    logger.warning(f"No data available for {pair}")
                    
            except Exception as e:
                logger.error(f"Failed to get data for {pair}: {str(e)}")
                continue
        
        if not all_data:
            raise ValueError("No historical data available for backtesting")
        
        # Combine data from all pairs
        combined_data = pd.concat(all_data, axis=1)
        combined_data = combined_data.fillna(method='ffill').dropna()
        
        logger.info(f"Prepared data: {len(combined_data)} bars, {len(pairs)} pairs")
        return combined_data    

    def _run_simulation(self, 
                       config: BacktestConfig, 
                       data: pd.DataFrame, 
                       pairs: List[str],
                       strategies: Optional[List[str]] = None) -> BacktestResult:
        """Run the main simulation loop."""
        logger.info("Running simulation")
        
        current_capital = config.initial_capital
        max_capital = config.initial_capital
        current_drawdown = 0.0
        daily_pnl = 0.0
        last_date = None
        
        # Skip warmup period
        simulation_data = data.iloc[config.warmup_period:]
        
        for timestamp, row in simulation_data.iterrows():
            try:
                # Check for new day (reset daily P&L)
                current_date = timestamp.date()
                if last_date and current_date != last_date:
                    daily_pnl = 0.0
                last_date = current_date
                
                # Update current positions
                current_capital = self._update_positions(timestamp, row, pairs, current_capital)
                
                # Check risk limits
                current_drawdown = (max_capital - current_capital) / max_capital
                if current_drawdown > config.max_drawdown_stop:
                    logger.warning(f"Max drawdown exceeded: {current_drawdown:.2%}")
                    break
                
                if daily_pnl / current_capital < -config.daily_loss_limit:
                    logger.warning(f"Daily loss limit exceeded: {daily_pnl/current_capital:.2%}")
                    continue
                
                # Generate signals for each pair
                for pair in pairs:
                    if self._should_generate_signal(pair, timestamp):
                        signal = self._generate_adaptive_signal(pair, timestamp, row, data)
                        if signal:
                            self._execute_signal(signal, timestamp, current_capital, config)
                
                # Update equity curve
                self._equity_history.append((timestamp, current_capital))
                max_capital = max(max_capital, current_capital)
                
                # Perform adaptations if enabled
                if config.enable_parameter_optimization and self._should_adapt(timestamp):
                    self._perform_adaptation(timestamp, data, pairs)
                
            except Exception as e:
                logger.error(f"Simulation error at {timestamp}: {str(e)}")
                continue
        
        # Calculate final performance metrics
        performance_metrics = self._calculate_performance_metrics(config, current_capital)
        
        # Create result
        result = BacktestResult(
            config=config,
            performance_metrics=performance_metrics,
            trades=self._trade_history,
            equity_curve=self._create_equity_curve(),
            drawdown_curve=self._create_drawdown_curve()
        )
        
        # Add detailed analytics
        result.trade_analysis = self._analyze_trades()
        result.risk_metrics = self._calculate_risk_metrics()
        result.monthly_returns = self._calculate_monthly_returns()
        
        return result
    
    def _generate_adaptive_signal(self, 
                                pair: str, 
                                timestamp: datetime, 
                                current_row: pd.Series,
                                historical_data: pd.DataFrame) -> Optional[AdaptiveSignal]:
        """Generate adaptive signal for a trading pair."""
        try:
            if not self.strategy_engine:
                return None
            
            # Get recent data for signal generation
            end_idx = historical_data.index.get_loc(timestamp)
            start_idx = max(0, end_idx - 100)  # Last 100 bars
            recent_data = historical_data.iloc[start_idx:end_idx + 1]
            
            # Detect market regime if enabled
            regime = None
            if self.regime_detector:
                try:
                    regime = self.regime_detector.detect_regime(recent_data, pair)
                except Exception as e:
                    logger.warning(f"Regime detection failed for {pair}: {str(e)}")
            
            # Generate signal using strategy engine
            signal = self.strategy_engine.execute_adaptive_signal(pair, recent_data)
            
            if signal and regime:
                signal.regime_context = regime
            
            return signal
            
        except Exception as e:
            logger.error(f"Signal generation failed for {pair}: {str(e)}")
            return None
    
    def _execute_signal(self, 
                       signal: AdaptiveSignal, 
                       timestamp: datetime,
                       current_capital: float,
                       config: BacktestConfig) -> None:
        """Execute a trading signal with realistic constraints."""
        try:
            pair = signal.pair
            
            # Calculate position size
            position_size = self._calculate_position_size(signal, current_capital, config)
            
            if position_size < config.min_trade_size:
                return
            
            # Apply slippage and commission
            execution_price = self._apply_execution_costs(signal.price, signal.signal_type, config)
            
            # Create trade record
            trade = {
                'trade_id': f"{pair}_{timestamp.strftime('%Y%m%d_%H%M%S')}",
                'pair': pair,
                'signal_type': signal.signal_type,
                'timestamp': timestamp,
                'price': execution_price,
                'size': position_size,
                'signal_strength': signal.strength.value,
                'confidence': signal.confidence,
                'regime': signal.regime_context.regime_type.value if signal.regime_context else None,
                'strategy_weights': signal.strategy_weights.copy(),
                'stop_loss': signal.stop_loss,
                'take_profit': signal.take_profit
            }
            
            # Update positions
            if signal.signal_type in ['buy', 'sell']:
                self._update_position(pair, trade)
                self._trade_history.append(trade)
                
                logger.debug(f"Executed {signal.signal_type} signal for {pair} at {execution_price}")
            
        except Exception as e:
            logger.error(f"Signal execution failed: {str(e)}")
    
    def _calculate_position_size(self, 
                               signal: AdaptiveSignal, 
                               current_capital: float,
                               config: BacktestConfig) -> float:
        """Calculate appropriate position size for the signal."""
        # Base position size from signal
        if signal.suggested_position_size:
            base_size = signal.suggested_position_size
        else:
            # Default to percentage of capital based on confidence
            base_size = current_capital * config.max_position_size_pct * signal.confidence
        
        # Adjust for signal strength
        strength_multiplier = signal.strength.value
        adjusted_size = base_size * strength_multiplier
        
        # Apply maximum position size limit
        max_size = current_capital * config.max_position_size_pct
        final_size = min(adjusted_size, max_size)
        
        return final_size
    
    def _apply_execution_costs(self, 
                             price: float, 
                             signal_type: str, 
                             config: BacktestConfig) -> float:
        """Apply slippage and return execution price."""
        if signal_type == 'buy':
            # Buy at higher price (positive slippage)
            return price * (1 + config.slippage_rate)
        elif signal_type == 'sell':
            # Sell at lower price (negative slippage)
            return price * (1 - config.slippage_rate)
        return price
    
    def _update_position(self, pair: str, trade: Dict[str, Any]) -> None:
        """Update position tracking."""
        if pair not in self._current_positions:
            self._current_positions[pair] = {}
        
        position = self._current_positions[pair]
        
        if trade['signal_type'] == 'buy':
            if 'quantity' not in position:
                position['quantity'] = 0
                position['avg_price'] = 0
            
            # Add to position
            old_quantity = position['quantity']
            old_avg_price = position['avg_price']
            new_quantity = trade['size'] / trade['price']
            
            if old_quantity == 0:
                position['avg_price'] = trade['price']
            else:
                total_cost = (old_quantity * old_avg_price) + (new_quantity * trade['price'])
                position['avg_price'] = total_cost / (old_quantity + new_quantity)
            
            position['quantity'] += new_quantity
            position['last_update'] = trade['timestamp']
            
        elif trade['signal_type'] == 'sell' and pair in self._current_positions:
            position = self._current_positions[pair]
            if 'quantity' in position and position['quantity'] > 0:
                # Close position (simplified - assume full close)
                sell_quantity = min(position['quantity'], trade['size'] / trade['price'])
                
                # Calculate P&L
                pnl = sell_quantity * (trade['price'] - position['avg_price'])
                trade['pnl'] = pnl
                trade['pnl_percentage'] = pnl / (sell_quantity * position['avg_price'])
                
                # Update position
                position['quantity'] -= sell_quantity
                if position['quantity'] <= 0:
                    position.clear()
    
    def _update_positions(self, 
                         timestamp: datetime, 
                         row: pd.Series, 
                         pairs: List[str],
                         current_capital: float) -> float:
        """Update position values and calculate current capital."""
        total_position_value = 0.0
        
        for pair in pairs:
            if pair in self._current_positions and self._current_positions[pair]:
                position = self._current_positions[pair]
                if 'quantity' in position and position['quantity'] > 0:
                    # Get current price for the pair
                    current_price = self._get_current_price(pair, row)
                    if current_price:
                        position_value = position['quantity'] * current_price
                        total_position_value += position_value
                        
                        # Check stop loss and take profit
                        self._check_exit_conditions(pair, position, current_price, timestamp)
        
        # Calculate current capital (cash + position values)
        return current_capital + total_position_value
    
    def _get_current_price(self, pair: str, row: pd.Series) -> Optional[float]:
        """Get current price for a pair from the data row."""
        try:
            # Try different column naming conventions
            possible_columns = [
                f"{pair}_close",
                f"{pair}_Close", 
                f"close_{pair}",
                f"Close_{pair}",
                pair
            ]
            
            for col in possible_columns:
                if col in row.index and pd.notna(row[col]):
                    return float(row[col])
            
            return None
            
        except Exception as e:
            logger.warning(f"Could not get price for {pair}: {str(e)}")
            return None
    
    def _check_exit_conditions(self, 
                             pair: str, 
                             position: Dict[str, Any], 
                             current_price: float,
                             timestamp: datetime) -> None:
        """Check if position should be closed due to stop loss or take profit."""
        if 'avg_price' not in position or 'quantity' not in position:
            return
        
        avg_price = position['avg_price']
        quantity = position['quantity']
        
        # Check stop loss
        if 'stop_loss' in position and position['stop_loss']:
            if current_price <= position['stop_loss']:
                self._close_position(pair, current_price, timestamp, 'stop_loss')
                return
        
        # Check take profit
        if 'take_profit' in position and position['take_profit']:
            if current_price >= position['take_profit']:
                self._close_position(pair, current_price, timestamp, 'take_profit')
                return
    
    def _close_position(self, 
                       pair: str, 
                       exit_price: float, 
                       timestamp: datetime,
                       exit_reason: str) -> None:
        """Close a position and record the trade."""
        if pair not in self._current_positions or not self._current_positions[pair]:
            return
        
        position = self._current_positions[pair]
        quantity = position.get('quantity', 0)
        avg_price = position.get('avg_price', 0)
        
        if quantity <= 0:
            return
        
        # Calculate P&L
        pnl = quantity * (exit_price - avg_price)
        pnl_percentage = pnl / (quantity * avg_price)
        
        # Create exit trade record
        exit_trade = {
            'trade_id': f"{pair}_{timestamp.strftime('%Y%m%d_%H%M%S')}_exit",
            'pair': pair,
            'signal_type': 'sell',
            'timestamp': timestamp,
            'price': exit_price,
            'size': quantity * exit_price,
            'quantity': quantity,
            'pnl': pnl,
            'pnl_percentage': pnl_percentage,
            'exit_reason': exit_reason,
            'entry_price': avg_price
        }
        
        self._trade_history.append(exit_trade)
        
        # Clear position
        self._current_positions[pair].clear()
        
        logger.debug(f"Closed {pair} position: {exit_reason}, P&L: {pnl:.2f}")
    
    def _should_generate_signal(self, pair: str, timestamp: datetime) -> bool:
        """Determine if we should generate a signal for this pair at this time."""
        # Simple logic - can be enhanced with more sophisticated rules
        return True
    
    def _should_adapt(self, timestamp: datetime) -> bool:
        """Determine if adaptation should be performed."""
        # Adapt every 24 hours (simplified)
        if not self._adaptation_history:
            return True
        
        last_adaptation = self._adaptation_history[-1].timestamp
        return timestamp - last_adaptation >= timedelta(hours=24)
    
    def _perform_adaptation(self, 
                          timestamp: datetime, 
                          data: pd.DataFrame, 
                          pairs: List[str]) -> None:
        """Perform system adaptation."""
        try:
            if not self.parameter_optimizer:
                return
            
            # Simple adaptation - optimize parameters for best performing strategy
            recent_performance = self._calculate_recent_performance()
            
            if recent_performance:
                best_strategy = max(recent_performance.items(), key=lambda x: x[1])[0]
                
                # Create adaptation event
                adaptation = AdaptationEvent(
                    event_id=f"adapt_{timestamp.strftime('%Y%m%d_%H%M%S')}",
                    event_type=AdaptationType.PARAMETER_OPTIMIZATION,
                    trigger_reason="Scheduled optimization",
                    changes_made={"optimized_strategy": best_strategy},
                    expected_impact=0.05,  # 5% improvement expected
                    timestamp=timestamp
                )
                
                self._adaptation_history.append(adaptation)
                logger.debug(f"Performed adaptation: {best_strategy}")
                
        except Exception as e:
            logger.error(f"Adaptation failed: {str(e)}")
    
    def _calculate_recent_performance(self) -> Dict[str, float]:
        """Calculate recent performance by strategy."""
        if not self._trade_history:
            return {}
        
        # Get trades from last 24 hours
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_trades = [t for t in self._trade_history 
                        if t.get('timestamp', datetime.min) > cutoff_time]
        
        strategy_performance = defaultdict(list)
        
        for trade in recent_trades:
            if 'pnl' in trade and 'strategy_weights' in trade:
                for strategy, weight in trade['strategy_weights'].items():
                    strategy_performance[strategy].append(trade['pnl'] * weight)
        
        # Calculate average performance
        return {strategy: np.mean(pnls) 
                for strategy, pnls in strategy_performance.items() 
                if pnls}
    
    def _calculate_performance_metrics(self, 
                                     config: BacktestConfig, 
                                     final_capital: float) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        if not self._equity_history:
            return self._create_empty_performance_metrics()
        
        # Calculate basic returns
        total_return = (final_capital - config.initial_capital) / config.initial_capital
        
        # Calculate time-based metrics
        start_date = config.start_date
        end_date = config.end_date
        days = (end_date - start_date).days
        years = days / 365.25
        
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Calculate equity curve for further analysis
        equity_series = pd.Series([eq[1] for eq in self._equity_history],
                                 index=[eq[0] for eq in self._equity_history])
        
        # Calculate returns series
        returns = equity_series.pct_change().dropna()
        
        # Risk metrics
        volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else 0
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0
        
        # Drawdown calculation
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Downside deviation for Sortino ratio
        negative_returns = returns[returns < 0]
        downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
        sortino_ratio = (annualized_return / downside_deviation) if downside_deviation > 0 else 0
        
        # Trade statistics
        completed_trades = [t for t in self._trade_history if 'pnl' in t]
        
        if completed_trades:
            pnls = [t['pnl'] for t in completed_trades]
            winning_trades = [p for p in pnls if p > 0]
            losing_trades = [p for p in pnls if p < 0]
            
            win_rate = len(winning_trades) / len(pnls) if pnls else 0
            avg_win = np.mean(winning_trades) if winning_trades else 0
            avg_loss = np.mean(losing_trades) if losing_trades else 0
            profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf')
            
            # Calculate average trade duration
            durations = []
            for trade in completed_trades:
                if 'entry_time' in trade and 'timestamp' in trade:
                    duration = trade['timestamp'] - trade.get('entry_time', trade['timestamp'])
                    durations.append(duration)
            
            avg_trade_duration = np.mean(durations) if durations else timedelta()
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
            avg_trade_duration = timedelta()
        
        # Calmar ratio
        calmar_ratio = (annualized_return / abs(max_drawdown)) if max_drawdown < 0 else 0
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            excess_return=annualized_return,  # Simplified - no benchmark
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            max_drawdown=max_drawdown,
            volatility=volatility,
            downside_deviation=downside_deviation,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_trade_duration=avg_trade_duration,
            trades_count=len(completed_trades),
            avg_win=avg_win,
            avg_loss=avg_loss
        )
    
    def _create_equity_curve(self) -> pd.Series:
        """Create equity curve series."""
        if not self._equity_history:
            return pd.Series()
        
        return pd.Series([eq[1] for eq in self._equity_history],
                        index=[eq[0] for eq in self._equity_history])
    
    def _create_drawdown_curve(self) -> pd.Series:
        """Create drawdown curve series."""
        equity_curve = self._create_equity_curve()
        if equity_curve.empty:
            return pd.Series()
        
        running_max = equity_curve.expanding().max()
        drawdown = (equity_curve - running_max) / running_max
        return drawdown
    
    def _analyze_trades(self) -> Dict[str, Any]:
        """Analyze trade statistics."""
        if not self._trade_history:
            return {}
        
        completed_trades = [t for t in self._trade_history if 'pnl' in t]
        
        if not completed_trades:
            return {}
        
        pnls = [t['pnl'] for t in completed_trades]
        
        return {
            'total_trades': len(completed_trades),
            'winning_trades': len([p for p in pnls if p > 0]),
            'losing_trades': len([p for p in pnls if p < 0]),
            'largest_win': max(pnls) if pnls else 0,
            'largest_loss': min(pnls) if pnls else 0,
            'average_trade': np.mean(pnls) if pnls else 0,
            'trade_pnl_std': np.std(pnls) if len(pnls) > 1 else 0
        }
    
    def _calculate_risk_metrics(self) -> Dict[str, float]:
        """Calculate additional risk metrics."""
        equity_curve = self._create_equity_curve()
        if equity_curve.empty:
            return {}
        
        returns = equity_curve.pct_change().dropna()
        
        if len(returns) < 2:
            return {}
        
        # Value at Risk (95% confidence)
        var_95 = np.percentile(returns, 5)
        
        # Expected Shortfall (Conditional VaR)
        es_95 = returns[returns <= var_95].mean()
        
        # Maximum consecutive losses
        consecutive_losses = 0
        max_consecutive_losses = 0
        
        for ret in returns:
            if ret < 0:
                consecutive_losses += 1
                max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
            else:
                consecutive_losses = 0
        
        return {
            'var_95': var_95,
            'expected_shortfall_95': es_95,
            'max_consecutive_losses': max_consecutive_losses,
            'return_skewness': returns.skew(),
            'return_kurtosis': returns.kurtosis()
        }
    
    def _calculate_monthly_returns(self) -> pd.Series:
        """Calculate monthly returns."""
        equity_curve = self._create_equity_curve()
        if equity_curve.empty:
            return pd.Series()
        
        monthly_equity = equity_curve.resample('M').last()
        monthly_returns = monthly_equity.pct_change().dropna()
        
        return monthly_returns
    
    def _create_empty_performance_metrics(self) -> PerformanceMetrics:
        """Create empty performance metrics for failed backtests."""
        return PerformanceMetrics(
            total_return=0.0,
            annualized_return=0.0,
            excess_return=0.0,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            calmar_ratio=0.0,
            max_drawdown=0.0,
            volatility=0.0,
            downside_deviation=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            avg_trade_duration=timedelta(),
            trades_count=0,
            avg_win=0.0,
            avg_loss=0.0
        )
    
    def _create_empty_result(self, config: BacktestConfig) -> BacktestResult:
        """Create empty backtest result."""
        return BacktestResult(
            config=config,
            performance_metrics=self._create_empty_performance_metrics(),
            trades=[],
            equity_curve=pd.Series(),
            drawdown_curve=pd.Series()
        ) 
   
    def _filter_data_by_regime(self, 
                              data: pd.DataFrame, 
                              pairs: List[str], 
                              target_regime: RegimeType) -> pd.DataFrame:
        """Filter historical data to include only periods of target regime."""
        if not self.regime_detector:
            return pd.DataFrame()
        
        regime_mask = pd.Series(False, index=data.index)
        
        for timestamp, row in data.iterrows():
            try:
                # Check regime for each pair
                regime_matches = []
                for pair in pairs:
                    recent_data = data.loc[:timestamp].tail(50)  # Last 50 bars
                    regime = self.regime_detector.detect_regime(recent_data, pair)
                    regime_matches.append(regime.regime_type == target_regime)
                
                # Include timestamp if any pair matches target regime
                regime_mask[timestamp] = any(regime_matches)
                
            except Exception as e:
                logger.warning(f"Regime filtering failed at {timestamp}: {str(e)}")
                continue
        
        return data[regime_mask]
    
    def _optimize_parameters_for_window(self, 
                                      data: pd.DataFrame, 
                                      pairs: List[str]) -> None:
        """Optimize parameters for a specific time window."""
        if not self.parameter_optimizer:
            return
        
        try:
            # Get current strategy allocations
            if self.strategy_engine:
                allocations = self.strategy_engine.get_strategy_allocation()
                
                for strategy_name, allocation in allocations.items():
                    if allocation.is_active:
                        # Define parameter space (simplified)
                        parameter_space = {
                            'stop_loss_pct': (0.01, 0.1),
                            'take_profit_pct': (0.02, 0.2),
                            'position_size_multiplier': (0.5, 2.0)
                        }
                        
                        # Run optimization
                        result = self.parameter_optimizer.optimize_parameters(
                            strategy_name=strategy_name,
                            parameter_space=parameter_space,
                            historical_data=data,
                            optimization_type=OptimizationMethod.BAYESIAN
                        )
                        
                        logger.debug(f"Optimized {strategy_name}: {result.performance_improvement:.2%} improvement")
                        
        except Exception as e:
            logger.error(f"Parameter optimization failed: {str(e)}")
    
    def _run_monte_carlo_iteration(self, 
                                 config: BacktestConfig, 
                                 pairs: List[str],
                                 iteration: int,
                                 randomization_methods: List[str]) -> Optional[BacktestResult]:
        """Run a single Monte Carlo iteration."""
        try:
            # Create modified config for this iteration
            mc_config = deepcopy(config)
            
            # Apply randomization
            for method in randomization_methods:
                mc_config = self._apply_randomization(mc_config, method, iteration)
            
            # Run backtest
            result = self.run_backtest(mc_config, pairs)
            return result
            
        except Exception as e:
            logger.warning(f"Monte Carlo iteration {iteration} failed: {str(e)}")
            return None
    
    def _apply_randomization(self, 
                           config: BacktestConfig, 
                           method: str, 
                           seed: int) -> BacktestConfig:
        """Apply randomization method to config."""
        random.seed(seed)
        np.random.seed(seed)
        
        if method == 'bootstrap':
            # Bootstrap sampling of time periods
            total_days = (config.end_date - config.start_date).days
            sample_days = int(total_days * 0.8)  # 80% sample
            
            start_offset = random.randint(0, total_days - sample_days)
            config.start_date = config.start_date + timedelta(days=start_offset)
            config.end_date = config.start_date + timedelta(days=sample_days)
            
        elif method == 'parameter_noise':
            # Add noise to configuration parameters
            config.commission_rate *= (1 + random.uniform(-0.2, 0.2))
            config.slippage_rate *= (1 + random.uniform(-0.2, 0.2))
            config.max_position_size_pct *= (1 + random.uniform(-0.1, 0.1))
            
        elif method == 'data_shuffle':
            # Shuffle data blocks (preserve local structure)
            # This would require modifying the data loading process
            pass
        
        return config
    
    def _analyze_monte_carlo_results(self, results: List[BacktestResult]) -> Dict[str, Any]:
        """Analyze Monte Carlo simulation results."""
        if not results:
            return {}
        
        # Extract key metrics
        returns = [r.performance_metrics.total_return for r in results]
        sharpe_ratios = [r.performance_metrics.sharpe_ratio for r in results]
        max_drawdowns = [r.performance_metrics.max_drawdown for r in results]
        win_rates = [r.performance_metrics.win_rate for r in results]
        
        # Calculate statistics
        analysis = {
            'num_simulations': len(results),
            'return_stats': {
                'mean': np.mean(returns),
                'std': np.std(returns),
                'min': np.min(returns),
                'max': np.max(returns),
                'percentile_5': np.percentile(returns, 5),
                'percentile_95': np.percentile(returns, 95),
                'positive_returns_pct': len([r for r in returns if r > 0]) / len(returns)
            },
            'sharpe_stats': {
                'mean': np.mean(sharpe_ratios),
                'std': np.std(sharpe_ratios),
                'min': np.min(sharpe_ratios),
                'max': np.max(sharpe_ratios)
            },
            'drawdown_stats': {
                'mean': np.mean(max_drawdowns),
                'std': np.std(max_drawdowns),
                'worst': np.min(max_drawdowns),
                'best': np.max(max_drawdowns)
            },
            'win_rate_stats': {
                'mean': np.mean(win_rates),
                'std': np.std(win_rates),
                'min': np.min(win_rates),
                'max': np.max(win_rates)
            }
        }
        
        # Risk metrics
        analysis['risk_metrics'] = {
            'probability_of_loss': len([r for r in returns if r < 0]) / len(returns),
            'expected_shortfall_5': np.mean([r for r in returns if r <= np.percentile(returns, 5)]),
            'return_to_risk_ratio': analysis['return_stats']['mean'] / analysis['return_stats']['std'] if analysis['return_stats']['std'] > 0 else 0
        }
        
        return analysis
    
    def _apply_stress_scenario(self, 
                             config: BacktestConfig, 
                             scenario: Dict[str, Any]) -> BacktestConfig:
        """Apply stress scenario modifications to config."""
        stressed_config = deepcopy(config)
        
        # Apply scenario modifications
        if 'commission_multiplier' in scenario:
            stressed_config.commission_rate *= scenario['commission_multiplier']
        
        if 'slippage_multiplier' in scenario:
            stressed_config.slippage_rate *= scenario['slippage_multiplier']
        
        if 'volatility_multiplier' in scenario:
            # This would require modifying the actual data
            # For now, adjust risk parameters
            stressed_config.max_position_size_pct *= (1 / scenario['volatility_multiplier'])
        
        if 'max_drawdown_limit' in scenario:
            stressed_config.max_drawdown_stop = scenario['max_drawdown_limit']
        
        return stressed_config


class BacktestValidator:
    """Validator for backtesting results and methodology."""
    
    def __init__(self):
        self.validation_rules = [
            self._check_data_quality,
            self._check_trade_realism,
            self._check_performance_consistency,
            self._check_risk_metrics
        ]
    
    def validate_backtest(self, result: BacktestResult) -> Dict[str, Any]:
        """Validate backtest result for accuracy and realism."""
        validation_results = {
            'is_valid': True,
            'warnings': [],
            'errors': [],
            'quality_score': 0.0
        }
        
        for rule in self.validation_rules:
            try:
                rule_result = rule(result)
                validation_results['warnings'].extend(rule_result.get('warnings', []))
                validation_results['errors'].extend(rule_result.get('errors', []))
                
                if rule_result.get('errors'):
                    validation_results['is_valid'] = False
                    
            except Exception as e:
                validation_results['errors'].append(f"Validation rule failed: {str(e)}")
                validation_results['is_valid'] = False
        
        # Calculate quality score
        validation_results['quality_score'] = self._calculate_quality_score(validation_results)
        
        return validation_results
    
    def _check_data_quality(self, result: BacktestResult) -> Dict[str, Any]:
        """Check data quality issues."""
        warnings = []
        errors = []
        
        # Check for sufficient data
        if result.total_bars_processed < 1000:
            warnings.append("Insufficient data for reliable backtesting (< 1000 bars)")
        
        # Check for reasonable number of trades
        if len(result.trades) < 10:
            warnings.append("Very few trades generated (< 10)")
        elif len(result.trades) > result.total_bars_processed * 0.1:
            warnings.append("Unusually high trade frequency (> 10% of bars)")
        
        return {'warnings': warnings, 'errors': errors}
    
    def _check_trade_realism(self, result: BacktestResult) -> Dict[str, Any]:
        """Check trade realism."""
        warnings = []
        errors = []
        
        if not result.trades:
            return {'warnings': warnings, 'errors': errors}
        
        # Check for unrealistic win rates
        completed_trades = [t for t in result.trades if 'pnl' in t]
        if completed_trades:
            win_rate = len([t for t in completed_trades if t['pnl'] > 0]) / len(completed_trades)
            
            if win_rate > 0.9:
                warnings.append(f"Unrealistically high win rate: {win_rate:.1%}")
            elif win_rate < 0.1:
                warnings.append(f"Unrealistically low win rate: {win_rate:.1%}")
        
        # Check for unrealistic returns
        if result.performance_metrics.total_return > 10.0:  # 1000% return
            warnings.append(f"Unrealistically high return: {result.performance_metrics.total_return:.1%}")
        
        return {'warnings': warnings, 'errors': errors}
    
    def _check_performance_consistency(self, result: BacktestResult) -> Dict[str, Any]:
        """Check performance metric consistency."""
        warnings = []
        errors = []
        
        metrics = result.performance_metrics
        
        # Check Sharpe ratio consistency
        if metrics.volatility > 0:
            expected_sharpe = metrics.annualized_return / metrics.volatility
            if abs(metrics.sharpe_ratio - expected_sharpe) > 0.1:
                warnings.append("Sharpe ratio calculation inconsistency")
        
        # Check drawdown consistency
        if not result.equity_curve.empty:
            running_max = result.equity_curve.expanding().max()
            drawdown = (result.equity_curve - running_max) / running_max
            calculated_max_dd = drawdown.min()
            
            if abs(metrics.max_drawdown - calculated_max_dd) > 0.01:
                warnings.append("Max drawdown calculation inconsistency")
        
        return {'warnings': warnings, 'errors': errors}
    
    def _check_risk_metrics(self, result: BacktestResult) -> Dict[str, Any]:
        """Check risk metrics for reasonableness."""
        warnings = []
        errors = []
        
        metrics = result.performance_metrics
        
        # Check for negative Sharpe with positive returns
        if metrics.total_return > 0 and metrics.sharpe_ratio < 0:
            warnings.append("Positive returns but negative Sharpe ratio")
        
        # Check for zero volatility
        if metrics.volatility == 0 and len(result.trades) > 1:
            warnings.append("Zero volatility with multiple trades")
        
        return {'warnings': warnings, 'errors': errors}
    
    def _calculate_quality_score(self, validation_results: Dict[str, Any]) -> float:
        """Calculate overall quality score for the backtest."""
        base_score = 100.0
        
        # Deduct points for warnings and errors
        base_score -= len(validation_results['warnings']) * 5
        base_score -= len(validation_results['errors']) * 20
        
        return max(0.0, min(100.0, base_score))


# Utility functions for backtesting
def create_default_backtest_config(start_date: datetime, 
                                 end_date: datetime,
                                 initial_capital: float = 10000.0) -> BacktestConfig:
    """Create a default backtesting configuration."""
    return BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        commission_rate=0.001,
        slippage_rate=0.0005,
        use_realistic_execution=True,
        max_position_size_pct=0.1,
        min_trade_size=10.0,
        data_frequency='1h',
        warmup_period=100,
        enable_regime_detection=True,
        enable_ml_predictions=True,
        enable_parameter_optimization=True,
        max_drawdown_stop=0.2,
        daily_loss_limit=0.05,
        validation_method=ValidationMethod.WALK_FORWARD,
        validation_split=0.2
    )


def compare_backtest_results(results: List[BacktestResult]) -> pd.DataFrame:
    """Compare multiple backtest results."""
    if not results:
        return pd.DataFrame()
    
    comparison_data = []
    
    for i, result in enumerate(results):
        metrics = result.performance_metrics
        comparison_data.append({
            'backtest_id': i,
            'total_return': metrics.total_return,
            'annualized_return': metrics.annualized_return,
            'sharpe_ratio': metrics.sharpe_ratio,
            'sortino_ratio': metrics.sortino_ratio,
            'max_drawdown': metrics.max_drawdown,
            'win_rate': metrics.win_rate,
            'profit_factor': metrics.profit_factor,
            'total_trades': metrics.trades_count,
            'execution_time': result.execution_time.total_seconds()
        })
    
    return pd.DataFrame(comparison_data)