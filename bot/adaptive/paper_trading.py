"""
Paper trading integration for adaptive bot testing.

This module provides paper trading mode for adaptive bot testing with real-time
simulation using live market data, performance comparison between paper and live
trading, and gradual transition capabilities.
"""
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json
import threading
import time
from copy import deepcopy

from .interfaces import (
    AdaptiveStrategyEngineInterface, MarketRegimeDetectorInterface,
    MLEngineInterface, ParameterOptimizerInterface, PerformanceAnalyzerInterface
)
from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, OptimizationResult,
    AdaptationEvent, StrategyAllocation
)
from .enums import RegimeType, SignalStrength, AdaptationType
from ..enhanced_data_manager import EnhancedDataManager
from ..utils import log_info, log_warning, log_error


logger = logging.getLogger(__name__)


@dataclass
class PaperTradingConfig:
    """Configuration for paper trading."""
    initial_capital: float = 10000.0
    max_position_size_pct: float = 0.1  # Max 10% of capital per position
    commission_rate: float = 0.001      # 0.1% commission
    slippage_rate: float = 0.0005       # 0.05% slippage
    
    # Risk management
    max_drawdown_stop: float = 0.2      # Stop if drawdown exceeds 20%
    daily_loss_limit: float = 0.05      # Stop if daily loss exceeds 5%
    max_open_positions: int = 5         # Maximum concurrent positions
    
    # Execution settings
    min_trade_size: float = 10.0        # Minimum trade size in USD
    enable_partial_fills: bool = True   # Allow partial order fills
    order_timeout: int = 300            # Order timeout in seconds
    
    # Comparison settings
    enable_live_comparison: bool = False # Compare with live trading
    comparison_pairs: List[str] = field(default_factory=list)
    
    # Transition settings
    transition_mode: bool = False       # Gradual transition to live trading
    transition_allocation: float = 0.1  # Start with 10% live allocation
    transition_increment: float = 0.1   # Increase by 10% each step
    transition_criteria: Dict[str, float] = field(default_factory=lambda: {
        'min_sharpe_ratio': 1.0,
        'min_win_rate': 0.55,
        'max_drawdown': -0.1,
        'min_trades': 50
    })


@dataclass
class PaperPosition:
    """Represents a paper trading position."""
    position_id: str
    pair: str
    side: str  # 'buy' or 'sell'
    entry_price: float
    quantity: float
    entry_time: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    strategy_name: str = ""
    confidence: float = 0.0
    
    def update_current_price(self, price: float) -> None:
        """Update current price and unrealized P&L."""
        self.current_price = price
        if self.side == 'buy':
            self.unrealized_pnl = self.quantity * (price - self.entry_price)
        else:  # sell
            self.unrealized_pnl = self.quantity * (self.entry_price - price)


@dataclass
class PaperTrade:
    """Represents a completed paper trade."""
    trade_id: str
    pair: str
    side: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_percentage: float
    commission: float
    slippage: float
    exit_reason: str  # 'signal', 'stop_loss', 'take_profit', 'timeout'
    strategy_name: str = ""
    confidence: float = 0.0
    regime_context: Optional[RegimeType] = None


@dataclass
class PaperTradingState:
    """Current state of paper trading."""
    current_capital: float
    available_capital: float
    total_position_value: float
    open_positions: Dict[str, PaperPosition]
    completed_trades: List[PaperTrade]
    daily_pnl: float
    max_capital: float
    current_drawdown: float
    last_update: datetime
    
    def get_total_value(self) -> float:
        """Get total portfolio value."""
        return self.current_capital + self.total_position_value


class PaperTradingEngine:
    """
    Paper trading engine for adaptive bot testing.
    
    Features:
    - Real-time simulation with live market data
    - Performance tracking and comparison
    - Risk management and position sizing
    - Gradual transition to live trading
    """
    
    def __init__(self,
                 config: PaperTradingConfig,
                 data_manager: EnhancedDataManager,
                 strategy_engine: Optional[AdaptiveStrategyEngineInterface] = None,
                 regime_detector: Optional[MarketRegimeDetectorInterface] = None,
                 ml_engine: Optional[MLEngineInterface] = None,
                 performance_analyzer: Optional[PerformanceAnalyzerInterface] = None):
        """
        Initialize paper trading engine.
        
        Args:
            config: Paper trading configuration
            data_manager: Enhanced data manager for market data
            strategy_engine: Adaptive strategy engine
            regime_detector: Market regime detector
            ml_engine: Machine learning engine
            performance_analyzer: Performance analyzer
        """
        self.config = config
        self.data_manager = data_manager
        self.strategy_engine = strategy_engine
        self.regime_detector = regime_detector
        self.ml_engine = ml_engine
        self.performance_analyzer = performance_analyzer
        
        # Initialize trading state
        self.state = PaperTradingState(
            current_capital=config.initial_capital,
            available_capital=config.initial_capital,
            total_position_value=0.0,
            open_positions={},
            completed_trades=[],
            daily_pnl=0.0,
            max_capital=config.initial_capital,
            current_drawdown=0.0,
            last_update=datetime.now()
        )
        
        # Performance tracking
        self.equity_history: List[Tuple[datetime, float]] = []
        self.performance_metrics: Optional[PerformanceMetrics] = None
        
        # Live comparison data
        self.live_comparison_data: Dict[str, Any] = {}
        
        # Threading for real-time updates
        self._running = False
        self._update_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        logger.info("Paper trading engine initialized")
    
    def start(self, pairs: List[str]) -> None:
        """Start paper trading engine."""
        logger.info(f"Starting paper trading for pairs: {pairs}")
        
        self._running = True
        self._update_thread = threading.Thread(
            target=self._real_time_update_loop,
            args=(pairs,),
            daemon=True
        )
        self._update_thread.start()
        
        # Initialize equity history
        self.equity_history.append((datetime.now(), self.state.get_total_value()))
    
    def stop(self) -> None:
        """Stop paper trading engine."""
        logger.info("Stopping paper trading engine")
        
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5.0)
        
        # Close all open positions
        self._close_all_positions("engine_stop")
        
        # Calculate final performance metrics
        self._update_performance_metrics()
    
    def execute_signal(self, signal: AdaptiveSignal) -> bool:
        """
        Execute a trading signal in paper trading mode.
        
        Args:
            signal: Adaptive signal to execute
            
        Returns:
            True if signal was executed successfully
        """
        with self._lock:
            try:
                # Check if we should execute this signal
                if not self._should_execute_signal(signal):
                    return False
                
                # Calculate position size
                position_size = self._calculate_position_size(signal)
                
                if position_size < self.config.min_trade_size:
                    logger.debug(f"Position size too small: ${position_size:.2f}")
                    return False
                
                # Execute the signal
                if signal.signal_type in ['buy', 'long']:
                    return self._execute_buy_signal(signal, position_size)
                elif signal.signal_type in ['sell', 'short']:
                    return self._execute_sell_signal(signal, position_size)
                elif signal.signal_type == 'close':
                    return self._execute_close_signal(signal)
                
                return False
                
            except Exception as e:
                logger.error(f"Signal execution failed: {str(e)}")
                return False
    
    def get_current_state(self) -> PaperTradingState:
        """Get current paper trading state."""
        with self._lock:
            return deepcopy(self.state)
    
    def get_performance_metrics(self) -> Optional[PerformanceMetrics]:
        """Get current performance metrics."""
        with self._lock:
            self._update_performance_metrics()
            return self.performance_metrics
    
    def get_open_positions(self) -> Dict[str, PaperPosition]:
        """Get current open positions."""
        with self._lock:
            return deepcopy(self.state.open_positions)
    
    def get_trade_history(self) -> List[PaperTrade]:
        """Get completed trade history."""
        with self._lock:
            return deepcopy(self.state.completed_trades)
    
    def get_equity_curve(self) -> pd.Series:
        """Get equity curve as pandas Series."""
        with self._lock:
            if not self.equity_history:
                return pd.Series()
            
            timestamps = [eq[0] for eq in self.equity_history]
            values = [eq[1] for eq in self.equity_history]
            
            return pd.Series(values, index=timestamps)
    
    def compare_with_live_trading(self, live_performance: PerformanceMetrics) -> Dict[str, Any]:
        """
        Compare paper trading performance with live trading.
        
        Args:
            live_performance: Live trading performance metrics
            
        Returns:
            Comparison analysis
        """
        paper_performance = self.get_performance_metrics()
        
        if not paper_performance:
            return {}
        
        comparison = {
            'paper_vs_live': {
                'total_return_diff': paper_performance.total_return - live_performance.total_return,
                'sharpe_ratio_diff': paper_performance.sharpe_ratio - live_performance.sharpe_ratio,
                'max_drawdown_diff': paper_performance.max_drawdown - live_performance.max_drawdown,
                'win_rate_diff': paper_performance.win_rate - live_performance.win_rate,
                'profit_factor_diff': paper_performance.profit_factor - live_performance.profit_factor
            },
            'paper_performance': {
                'total_return': paper_performance.total_return,
                'sharpe_ratio': paper_performance.sharpe_ratio,
                'max_drawdown': paper_performance.max_drawdown,
                'win_rate': paper_performance.win_rate,
                'total_trades': paper_performance.trades_count
            },
            'live_performance': {
                'total_return': live_performance.total_return,
                'sharpe_ratio': live_performance.sharpe_ratio,
                'max_drawdown': live_performance.max_drawdown,
                'win_rate': live_performance.win_rate,
                'total_trades': live_performance.trades_count
            },
            'recommendation': self._get_transition_recommendation(paper_performance)
        }
        
        return comparison
    
    def check_transition_readiness(self) -> Dict[str, Any]:
        """
        Check if paper trading is ready for transition to live trading.
        
        Returns:
            Transition readiness analysis
        """
        performance = self.get_performance_metrics()
        
        if not performance:
            return {
                'ready': False,
                'reason': 'Insufficient performance data',
                'criteria_met': {},
                'recommendations': ['Continue paper trading to gather more data']
            }
        
        criteria = self.config.transition_criteria
        criteria_met = {}
        
        # Check each criterion
        criteria_met['sharpe_ratio'] = performance.sharpe_ratio >= criteria['min_sharpe_ratio']
        criteria_met['win_rate'] = performance.win_rate >= criteria['min_win_rate']
        criteria_met['max_drawdown'] = performance.max_drawdown >= criteria['max_drawdown']
        criteria_met['min_trades'] = performance.trades_count >= criteria['min_trades']
        
        # Overall readiness
        ready = all(criteria_met.values())
        
        # Generate recommendations
        recommendations = []
        if not criteria_met['sharpe_ratio']:
            recommendations.append(f"Improve Sharpe ratio (current: {performance.sharpe_ratio:.2f}, required: {criteria['min_sharpe_ratio']:.2f})")
        if not criteria_met['win_rate']:
            recommendations.append(f"Improve win rate (current: {performance.win_rate:.2%}, required: {criteria['min_win_rate']:.2%})")
        if not criteria_met['max_drawdown']:
            recommendations.append(f"Reduce maximum drawdown (current: {performance.max_drawdown:.2%}, required: {criteria['max_drawdown']:.2%})")
        if not criteria_met['min_trades']:
            recommendations.append(f"Execute more trades (current: {performance.trades_count}, required: {criteria['min_trades']})")
        
        if ready:
            recommendations.append("Ready for gradual transition to live trading")
        
        return {
            'ready': ready,
            'criteria_met': criteria_met,
            'current_performance': {
                'sharpe_ratio': performance.sharpe_ratio,
                'win_rate': performance.win_rate,
                'max_drawdown': performance.max_drawdown,
                'total_trades': performance.trades_count
            },
            'required_criteria': criteria,
            'recommendations': recommendations
        }
    
    def export_trading_data(self, filepath: str) -> None:
        """Export paper trading data to file."""
        with self._lock:
            export_data = {
                'config': {
                    'initial_capital': self.config.initial_capital,
                    'commission_rate': self.config.commission_rate,
                    'slippage_rate': self.config.slippage_rate,
                    'max_position_size_pct': self.config.max_position_size_pct
                },
                'final_state': {
                    'current_capital': self.state.current_capital,
                    'total_value': self.state.get_total_value(),
                    'total_return': (self.state.get_total_value() - self.config.initial_capital) / self.config.initial_capital,
                    'max_drawdown': self.state.current_drawdown,
                    'open_positions_count': len(self.state.open_positions),
                    'completed_trades_count': len(self.state.completed_trades)
                },
                'trades': [
                    {
                        'trade_id': trade.trade_id,
                        'pair': trade.pair,
                        'side': trade.side,
                        'entry_price': trade.entry_price,
                        'exit_price': trade.exit_price,
                        'quantity': trade.quantity,
                        'entry_time': trade.entry_time.isoformat(),
                        'exit_time': trade.exit_time.isoformat(),
                        'pnl': trade.pnl,
                        'pnl_percentage': trade.pnl_percentage,
                        'exit_reason': trade.exit_reason,
                        'strategy_name': trade.strategy_name
                    }
                    for trade in self.state.completed_trades
                ],
                'equity_history': [
                    {
                        'timestamp': eq[0].isoformat(),
                        'value': eq[1]
                    }
                    for eq in self.equity_history
                ],
                'performance_metrics': self._serialize_performance_metrics()
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Paper trading data exported to {filepath}")
    
    def _real_time_update_loop(self, pairs: List[str]) -> None:
        """Real-time update loop for position values and market data."""
        logger.info("Starting real-time update loop")
        
        while self._running:
            try:
                with self._lock:
                    # Update position values
                    self._update_position_values(pairs)
                    
                    # Check exit conditions
                    self._check_exit_conditions()
                    
                    # Update equity history
                    current_time = datetime.now()
                    total_value = self.state.get_total_value()
                    self.equity_history.append((current_time, total_value))
                    
                    # Update drawdown
                    self.state.max_capital = max(self.state.max_capital, total_value)
                    self.state.current_drawdown = (self.state.max_capital - total_value) / self.state.max_capital
                    
                    # Check risk limits
                    self._check_risk_limits()
                    
                    self.state.last_update = current_time
                
                # Sleep for update interval
                time.sleep(1.0)  # Update every second
                
            except Exception as e:
                logger.error(f"Real-time update error: {str(e)}")
                time.sleep(5.0)  # Wait longer on error
    
    def _should_execute_signal(self, signal: AdaptiveSignal) -> bool:
        """Check if signal should be executed."""
        # Check if we have enough capital
        if self.state.available_capital < self.config.min_trade_size:
            return False
        
        # Check maximum open positions
        if len(self.state.open_positions) >= self.config.max_open_positions:
            return False
        
        # Check if we already have a position in this pair
        if signal.pair in self.state.open_positions:
            return False
        
        # Check daily loss limit
        if self.state.daily_pnl / self.state.current_capital < -self.config.daily_loss_limit:
            return False
        
        # Check maximum drawdown
        if self.state.current_drawdown > self.config.max_drawdown_stop:
            return False
        
        return True
    
    def _calculate_position_size(self, signal: AdaptiveSignal) -> float:
        """Calculate position size for the signal."""
        # Base position size from available capital
        base_size = self.state.available_capital * self.config.max_position_size_pct
        
        # Adjust for signal confidence
        confidence_adjusted = base_size * signal.confidence
        
        # Adjust for signal strength
        strength_multiplier = signal.strength.value if hasattr(signal, 'strength') else 1.0
        final_size = confidence_adjusted * strength_multiplier
        
        # Ensure we don't exceed available capital
        return min(final_size, self.state.available_capital * 0.95)
    
    def _execute_buy_signal(self, signal: AdaptiveSignal, position_size: float) -> bool:
        """Execute a buy signal."""
        try:
            # Apply slippage to execution price
            execution_price = signal.price * (1 + self.config.slippage_rate)
            
            # Calculate quantity
            quantity = position_size / execution_price
            
            # Calculate commission
            commission = position_size * self.config.commission_rate
            
            # Create position
            position_id = f"{signal.pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            position = PaperPosition(
                position_id=position_id,
                pair=signal.pair,
                side='buy',
                entry_price=execution_price,
                quantity=quantity,
                entry_time=datetime.now(),
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                current_price=execution_price,
                strategy_name=getattr(signal, 'strategy_name', ''),
                confidence=signal.confidence
            )
            
            # Update state
            self.state.open_positions[position_id] = position
            self.state.available_capital -= (position_size + commission)
            self.state.total_position_value += position_size
            
            logger.info(f"Executed buy signal: {signal.pair} @ ${execution_price:.2f}, size: ${position_size:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Buy signal execution failed: {str(e)}")
            return False
    
    def _execute_sell_signal(self, signal: AdaptiveSignal, position_size: float) -> bool:
        """Execute a sell signal (short position)."""
        try:
            # Apply slippage to execution price
            execution_price = signal.price * (1 - self.config.slippage_rate)
            
            # Calculate quantity
            quantity = position_size / execution_price
            
            # Calculate commission
            commission = position_size * self.config.commission_rate
            
            # Create position
            position_id = f"{signal.pair}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            position = PaperPosition(
                position_id=position_id,
                pair=signal.pair,
                side='sell',
                entry_price=execution_price,
                quantity=quantity,
                entry_time=datetime.now(),
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                current_price=execution_price,
                strategy_name=getattr(signal, 'strategy_name', ''),
                confidence=signal.confidence
            )
            
            # Update state
            self.state.open_positions[position_id] = position
            self.state.available_capital -= commission
            self.state.total_position_value += position_size
            
            logger.info(f"Executed sell signal: {signal.pair} @ ${execution_price:.2f}, size: ${position_size:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"Sell signal execution failed: {str(e)}")
            return False
    
    def _execute_close_signal(self, signal: AdaptiveSignal) -> bool:
        """Execute a close signal."""
        positions_to_close = [
            pos for pos in self.state.open_positions.values()
            if pos.pair == signal.pair
        ]
        
        if not positions_to_close:
            return False
        
        for position in positions_to_close:
            self._close_position(position, signal.price, "signal")
        
        return True
    
    def _update_position_values(self, pairs: List[str]) -> None:
        """Update current values of open positions."""
        for position in self.state.open_positions.values():
            if position.pair in pairs:
                try:
                    # Get current market price
                    current_price = self._get_current_price(position.pair)
                    if current_price:
                        position.update_current_price(current_price)
                except Exception as e:
                    logger.warning(f"Failed to update price for {position.pair}: {str(e)}")
        
        # Update total position value
        self.state.total_position_value = sum(
            pos.quantity * pos.current_price for pos in self.state.open_positions.values()
        )
    
    def _get_current_price(self, pair: str) -> Optional[float]:
        """Get current market price for a pair."""
        try:
            # Get latest data from data manager
            latest_data = self.data_manager.get_latest_data(pair)
            if latest_data and 'close' in latest_data:
                return float(latest_data['close'])
            return None
        except Exception as e:
            logger.warning(f"Could not get current price for {pair}: {str(e)}")
            return None
    
    def _check_exit_conditions(self) -> None:
        """Check exit conditions for open positions."""
        positions_to_close = []
        
        for position in self.state.open_positions.values():
            # Check stop loss
            if position.stop_loss:
                if position.side == 'buy' and position.current_price <= position.stop_loss:
                    positions_to_close.append((position, 'stop_loss'))
                elif position.side == 'sell' and position.current_price >= position.stop_loss:
                    positions_to_close.append((position, 'stop_loss'))
            
            # Check take profit
            if position.take_profit:
                if position.side == 'buy' and position.current_price >= position.take_profit:
                    positions_to_close.append((position, 'take_profit'))
                elif position.side == 'sell' and position.current_price <= position.take_profit:
                    positions_to_close.append((position, 'take_profit'))
        
        # Close positions
        for position, reason in positions_to_close:
            self._close_position(position, position.current_price, reason)
    
    def _close_position(self, position: PaperPosition, exit_price: float, exit_reason: str) -> None:
        """Close a position and create trade record."""
        try:
            # Calculate P&L
            if position.side == 'buy':
                pnl = position.quantity * (exit_price - position.entry_price)
            else:  # sell
                pnl = position.quantity * (position.entry_price - exit_price)
            
            # Calculate commission and slippage
            position_value = position.quantity * exit_price
            commission = position_value * self.config.commission_rate
            slippage_cost = position_value * self.config.slippage_rate
            
            # Net P&L after costs
            net_pnl = pnl - commission - slippage_cost
            pnl_percentage = net_pnl / (position.quantity * position.entry_price)
            
            # Create trade record
            trade = PaperTrade(
                trade_id=f"{position.position_id}_close",
                pair=position.pair,
                side=position.side,
                entry_price=position.entry_price,
                exit_price=exit_price,
                quantity=position.quantity,
                entry_time=position.entry_time,
                exit_time=datetime.now(),
                pnl=net_pnl,
                pnl_percentage=pnl_percentage,
                commission=commission,
                slippage=slippage_cost,
                exit_reason=exit_reason,
                strategy_name=position.strategy_name,
                confidence=position.confidence
            )
            
            # Update state
            self.state.completed_trades.append(trade)
            self.state.current_capital += position_value - commission
            self.state.available_capital += position_value - commission
            self.state.daily_pnl += net_pnl
            
            # Remove position
            del self.state.open_positions[position.position_id]
            
            logger.info(f"Closed position {position.pair}: P&L ${net_pnl:.2f} ({pnl_percentage:.2%})")
            
        except Exception as e:
            logger.error(f"Position close failed: {str(e)}")
    
    def _close_all_positions(self, reason: str) -> None:
        """Close all open positions."""
        positions_to_close = list(self.state.open_positions.values())
        
        for position in positions_to_close:
            current_price = self._get_current_price(position.pair)
            if current_price:
                self._close_position(position, current_price, reason)
    
    def _check_risk_limits(self) -> None:
        """Check risk limits and take action if necessary."""
        # Check maximum drawdown
        if self.state.current_drawdown > self.config.max_drawdown_stop:
            logger.warning(f"Maximum drawdown exceeded: {self.state.current_drawdown:.2%}")
            self._close_all_positions("max_drawdown")
        
        # Check daily loss limit
        if self.state.daily_pnl / self.state.current_capital < -self.config.daily_loss_limit:
            logger.warning(f"Daily loss limit exceeded: {self.state.daily_pnl/self.state.current_capital:.2%}")
            # Could implement position reduction or trading halt
    
    def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        if not self.equity_history or len(self.state.completed_trades) == 0:
            return
        
        # Calculate returns
        initial_capital = self.config.initial_capital
        current_value = self.state.get_total_value()
        total_return = (current_value - initial_capital) / initial_capital
        
        # Calculate time-based metrics
        start_time = self.equity_history[0][0]
        current_time = datetime.now()
        days = (current_time - start_time).days
        years = days / 365.25 if days > 0 else 1/365.25
        
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # Calculate equity curve
        equity_values = [eq[1] for eq in self.equity_history]
        equity_series = pd.Series(equity_values)
        
        # Calculate returns series
        returns = equity_series.pct_change().dropna()
        
        # Risk metrics
        volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else 0
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0
        
        # Drawdown
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Trade statistics
        completed_trades = self.state.completed_trades
        if completed_trades:
            pnls = [trade.pnl for trade in completed_trades]
            winning_trades = [p for p in pnls if p > 0]
            losing_trades = [p for p in pnls if p < 0]
            
            win_rate = len(winning_trades) / len(pnls) if pnls else 0
            avg_win = np.mean(winning_trades) if winning_trades else 0
            avg_loss = np.mean(losing_trades) if losing_trades else 0
            profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf')
            
            # Average trade duration
            durations = [(trade.exit_time - trade.entry_time) for trade in completed_trades]
            avg_trade_duration = np.mean(durations) if durations else timedelta()
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
            avg_trade_duration = timedelta()
        
        # Downside deviation for Sortino ratio
        negative_returns = returns[returns < 0]
        downside_deviation = negative_returns.std() * np.sqrt(252) if len(negative_returns) > 0 else 0
        sortino_ratio = (annualized_return / downside_deviation) if downside_deviation > 0 else 0
        
        # Calmar ratio
        calmar_ratio = (annualized_return / abs(max_drawdown)) if max_drawdown < 0 else 0
        
        self.performance_metrics = PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            excess_return=annualized_return,  # Simplified
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
    
    def _get_transition_recommendation(self, performance: PerformanceMetrics) -> str:
        """Get recommendation for transitioning to live trading."""
        criteria = self.config.transition_criteria
        
        if (performance.sharpe_ratio >= criteria['min_sharpe_ratio'] and
            performance.win_rate >= criteria['min_win_rate'] and
            performance.max_drawdown >= criteria['max_drawdown'] and
            performance.trades_count >= criteria['min_trades']):
            return "Ready for live trading transition"
        else:
            return "Continue paper trading to improve performance"
    
    def _serialize_performance_metrics(self) -> Optional[Dict[str, Any]]:
        """Serialize performance metrics for export."""
        if not self.performance_metrics:
            return None
        
        return {
            'total_return': self.performance_metrics.total_return,
            'annualized_return': self.performance_metrics.annualized_return,
            'sharpe_ratio': self.performance_metrics.sharpe_ratio,
            'sortino_ratio': self.performance_metrics.sortino_ratio,
            'max_drawdown': self.performance_metrics.max_drawdown,
            'win_rate': self.performance_metrics.win_rate,
            'profit_factor': self.performance_metrics.profit_factor,
            'total_trades': self.performance_metrics.trades_count,
            'avg_trade_duration_hours': self.performance_metrics.avg_trade_duration.total_seconds() / 3600
        }


def create_default_paper_trading_config() -> PaperTradingConfig:
    """Create default paper trading configuration."""
    return PaperTradingConfig(
        initial_capital=10000.0,
        max_position_size_pct=0.1,
        commission_rate=0.001,
        slippage_rate=0.0005,
        max_drawdown_stop=0.2,
        daily_loss_limit=0.05,
        max_open_positions=5,
        min_trade_size=10.0,
        enable_partial_fills=True,
        order_timeout=300,
        enable_live_comparison=False,
        transition_mode=False,
        transition_allocation=0.1,
        transition_increment=0.1,
        transition_criteria={
            'min_sharpe_ratio': 1.0,
            'min_win_rate': 0.55,
            'max_drawdown': -0.1,
            'min_trades': 50
        }
    )