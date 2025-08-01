"""
Unit tests for paper trading integration.

Tests cover paper trading mode functionality, real-time simulation,
performance comparison, and gradual transition to live trading.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
import threading
import time

from bot.adaptive.paper_trading import (
    PaperTradingEngine, PaperTradingConfig, PaperPosition, PaperTrade,
    PaperTradingState, create_default_paper_trading_config
)
from bot.adaptive.data_models import AdaptiveSignal, PerformanceMetrics
from bot.adaptive.enums import RegimeType, SignalStrength
from bot.enhanced_data_manager import EnhancedDataManager


class TestPaperTradingConfig(unittest.TestCase):
    """Test PaperTradingConfig class."""
    
    def test_default_config_creation(self):
        """Test creating default paper trading configuration."""
        config = create_default_paper_trading_config()
        
        self.assertEqual(config.initial_capital, 10000.0)
        self.assertEqual(config.max_position_size_pct, 0.1)
        self.assertEqual(config.commission_rate, 0.001)
        self.assertEqual(config.slippage_rate, 0.0005)
        self.assertTrue(config.enable_partial_fills)
        self.assertFalse(config.transition_mode)
    
    def test_custom_config_creation(self):
        """Test creating custom paper trading configuration."""
        config = PaperTradingConfig(
            initial_capital=50000.0,
            max_position_size_pct=0.05,
            commission_rate=0.0005,
            transition_mode=True
        )
        
        self.assertEqual(config.initial_capital, 50000.0)
        self.assertEqual(config.max_position_size_pct, 0.05)
        self.assertEqual(config.commission_rate, 0.0005)
        self.assertTrue(config.transition_mode)


class TestPaperPosition(unittest.TestCase):
    """Test PaperPosition class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.position = PaperPosition(
            position_id="BTC_001",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            quantity=0.1,
            entry_time=datetime.now()
        )
    
    def test_position_creation(self):
        """Test position creation."""
        self.assertEqual(self.position.position_id, "BTC_001")
        self.assertEqual(self.position.pair, "BTC/USD")
        self.assertEqual(self.position.side, "buy")
        self.assertEqual(self.position.entry_price, 50000.0)
        self.assertEqual(self.position.quantity, 0.1)
    
    def test_update_current_price_buy(self):
        """Test updating current price for buy position."""
        # Price goes up - profit
        self.position.update_current_price(52000.0)
        self.assertEqual(self.position.current_price, 52000.0)
        self.assertEqual(self.position.unrealized_pnl, 200.0)  # 0.1 * (52000 - 50000)
        
        # Price goes down - loss
        self.position.update_current_price(48000.0)
        self.assertEqual(self.position.current_price, 48000.0)
        self.assertEqual(self.position.unrealized_pnl, -200.0)  # 0.1 * (48000 - 50000)
    
    def test_update_current_price_sell(self):
        """Test updating current price for sell position."""
        sell_position = PaperPosition(
            position_id="BTC_002",
            pair="BTC/USD",
            side="sell",
            entry_price=50000.0,
            quantity=0.1,
            entry_time=datetime.now()
        )
        
        # Price goes down - profit for short
        sell_position.update_current_price(48000.0)
        self.assertEqual(sell_position.unrealized_pnl, 200.0)  # 0.1 * (50000 - 48000)
        
        # Price goes up - loss for short
        sell_position.update_current_price(52000.0)
        self.assertEqual(sell_position.unrealized_pnl, -200.0)  # 0.1 * (50000 - 52000)


class TestPaperTrade(unittest.TestCase):
    """Test PaperTrade class."""
    
    def test_trade_creation(self):
        """Test trade creation."""
        trade = PaperTrade(
            trade_id="BTC_001_close",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            exit_price=52000.0,
            quantity=0.1,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now(),
            pnl=200.0,
            pnl_percentage=0.04,
            commission=5.0,
            slippage=2.5,
            exit_reason="take_profit"
        )
        
        self.assertEqual(trade.trade_id, "BTC_001_close")
        self.assertEqual(trade.pnl, 200.0)
        self.assertEqual(trade.pnl_percentage, 0.04)
        self.assertEqual(trade.exit_reason, "take_profit")


class TestPaperTradingState(unittest.TestCase):
    """Test PaperTradingState class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.state = PaperTradingState(
            current_capital=10000.0,
            available_capital=9000.0,
            total_position_value=1000.0,
            open_positions={},
            completed_trades=[],
            daily_pnl=0.0,
            max_capital=10000.0,
            current_drawdown=0.0,
            last_update=datetime.now()
        )
    
    def test_get_total_value(self):
        """Test total value calculation."""
        total_value = self.state.get_total_value()
        self.assertEqual(total_value, 11000.0)  # 10000 + 1000
    
    def test_state_updates(self):
        """Test state updates."""
        self.state.current_capital = 9500.0
        self.state.total_position_value = 1500.0
        
        total_value = self.state.get_total_value()
        self.assertEqual(total_value, 11000.0)  # 9500 + 1500


class TestPaperTradingEngine(unittest.TestCase):
    """Test PaperTradingEngine class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = create_default_paper_trading_config()
        self.data_manager = Mock(spec=EnhancedDataManager)
        self.strategy_engine = Mock()
        
        self.engine = PaperTradingEngine(
            config=self.config,
            data_manager=self.data_manager,
            strategy_engine=self.strategy_engine
        )
        
        # Mock data manager responses
        self.data_manager.get_latest_data.return_value = {'close': 50000.0}
    
    def test_engine_initialization(self):
        """Test engine initialization."""
        self.assertEqual(self.engine.config.initial_capital, 10000.0)
        self.assertEqual(self.engine.state.current_capital, 10000.0)
        self.assertEqual(self.engine.state.available_capital, 10000.0)
        self.assertEqual(len(self.engine.state.open_positions), 0)
        self.assertEqual(len(self.engine.state.completed_trades), 0)
    
    def test_calculate_position_size(self):
        """Test position size calculation."""
        signal = Mock()
        signal.confidence = 0.8
        signal.strength = SignalStrength.STRONG
        
        position_size = self.engine._calculate_position_size(signal)
        
        # Should be based on max_position_size_pct * confidence * strength
        expected_base = self.config.initial_capital * self.config.max_position_size_pct
        expected_size = expected_base * signal.confidence * signal.strength.value
        
        self.assertEqual(position_size, expected_size)
    
    def test_should_execute_signal_valid(self):
        """Test signal execution validation - valid signal."""
        signal = Mock()
        signal.pair = "BTC/USD"
        signal.confidence = 0.8
        
        should_execute = self.engine._should_execute_signal(signal)
        self.assertTrue(should_execute)
    
    def test_should_execute_signal_insufficient_capital(self):
        """Test signal execution validation - insufficient capital."""
        # Reduce available capital
        self.engine.state.available_capital = 5.0
        
        signal = Mock()
        signal.pair = "BTC/USD"
        signal.confidence = 0.8
        
        should_execute = self.engine._should_execute_signal(signal)
        self.assertFalse(should_execute)
    
    def test_should_execute_signal_max_positions(self):
        """Test signal execution validation - max positions reached."""
        # Fill up open positions
        for i in range(self.config.max_open_positions):
            position = PaperPosition(
                position_id=f"pos_{i}",
                pair=f"PAIR_{i}",
                side="buy",
                entry_price=50000.0,
                quantity=0.1,
                entry_time=datetime.now()
            )
            self.engine.state.open_positions[f"pos_{i}"] = position
        
        signal = Mock()
        signal.pair = "BTC/USD"
        signal.confidence = 0.8
        
        should_execute = self.engine._should_execute_signal(signal)
        self.assertFalse(should_execute)
    
    def test_execute_buy_signal(self):
        """Test executing a buy signal."""
        signal = Mock()
        signal.pair = "BTC/USD"
        signal.price = 50000.0
        signal.confidence = 0.8
        signal.stop_loss = 48000.0
        signal.take_profit = 55000.0
        
        position_size = 1000.0
        
        success = self.engine._execute_buy_signal(signal, position_size)
        
        self.assertTrue(success)
        self.assertEqual(len(self.engine.state.open_positions), 1)
        
        # Check position details
        position = list(self.engine.state.open_positions.values())[0]
        self.assertEqual(position.pair, "BTC/USD")
        self.assertEqual(position.side, "buy")
        self.assertAlmostEqual(position.entry_price, 50000.0 * (1 + self.config.slippage_rate), places=2)
        
        # Check capital reduction
        expected_capital_reduction = position_size + (position_size * self.config.commission_rate)
        expected_available = self.config.initial_capital - expected_capital_reduction
        self.assertAlmostEqual(self.engine.state.available_capital, expected_available, places=2)
    
    def test_execute_sell_signal(self):
        """Test executing a sell signal."""
        signal = Mock()
        signal.pair = "ETH/USD"
        signal.price = 3000.0
        signal.confidence = 0.7
        signal.stop_loss = 3200.0
        signal.take_profit = 2800.0
        
        position_size = 500.0
        
        success = self.engine._execute_sell_signal(signal, position_size)
        
        self.assertTrue(success)
        self.assertEqual(len(self.engine.state.open_positions), 1)
        
        # Check position details
        position = list(self.engine.state.open_positions.values())[0]
        self.assertEqual(position.pair, "ETH/USD")
        self.assertEqual(position.side, "sell")
        self.assertAlmostEqual(position.entry_price, 3000.0 * (1 - self.config.slippage_rate), places=2)
    
    def test_close_position_profit(self):
        """Test closing a position with profit."""
        # Create a buy position
        position = PaperPosition(
            position_id="BTC_001",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            quantity=0.1,
            entry_time=datetime.now() - timedelta(hours=1)
        )
        
        self.engine.state.open_positions["BTC_001"] = position
        initial_capital = self.engine.state.current_capital
        
        # Close at higher price (profit)
        exit_price = 52000.0
        self.engine._close_position(position, exit_price, "take_profit")
        
        # Check position is closed
        self.assertEqual(len(self.engine.state.open_positions), 0)
        
        # Check trade is recorded
        self.assertEqual(len(self.engine.state.completed_trades), 1)
        
        trade = self.engine.state.completed_trades[0]
        self.assertEqual(trade.exit_reason, "take_profit")
        self.assertGreater(trade.pnl, 0)  # Should be profitable
        
        # Check capital increased
        self.assertGreater(self.engine.state.current_capital, initial_capital)
    
    def test_close_position_loss(self):
        """Test closing a position with loss."""
        # Create a buy position
        position = PaperPosition(
            position_id="BTC_002",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            quantity=0.1,
            entry_time=datetime.now() - timedelta(hours=1)
        )
        
        self.engine.state.open_positions["BTC_002"] = position
        initial_capital = self.engine.state.current_capital
        
        # Close at lower price (loss)
        exit_price = 48000.0
        self.engine._close_position(position, exit_price, "stop_loss")
        
        # Check position is closed
        self.assertEqual(len(self.engine.state.open_positions), 0)
        
        # Check trade is recorded
        self.assertEqual(len(self.engine.state.completed_trades), 1)
        
        trade = self.engine.state.completed_trades[0]
        self.assertEqual(trade.exit_reason, "stop_loss")
        self.assertLess(trade.pnl, 0)  # Should be a loss
    
    def test_check_exit_conditions_stop_loss(self):
        """Test exit condition checking - stop loss."""
        # Create buy position with stop loss
        position = PaperPosition(
            position_id="BTC_003",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            quantity=0.1,
            entry_time=datetime.now(),
            stop_loss=48000.0
        )
        position.current_price = 47000.0  # Below stop loss
        
        self.engine.state.open_positions["BTC_003"] = position
        
        # Check exit conditions
        self.engine._check_exit_conditions()
        
        # Position should be closed
        self.assertEqual(len(self.engine.state.open_positions), 0)
        self.assertEqual(len(self.engine.state.completed_trades), 1)
        self.assertEqual(self.engine.state.completed_trades[0].exit_reason, "stop_loss")
    
    def test_check_exit_conditions_take_profit(self):
        """Test exit condition checking - take profit."""
        # Create buy position with take profit
        position = PaperPosition(
            position_id="BTC_004",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            quantity=0.1,
            entry_time=datetime.now(),
            take_profit=55000.0
        )
        position.current_price = 56000.0  # Above take profit
        
        self.engine.state.open_positions["BTC_004"] = position
        
        # Check exit conditions
        self.engine._check_exit_conditions()
        
        # Position should be closed
        self.assertEqual(len(self.engine.state.open_positions), 0)
        self.assertEqual(len(self.engine.state.completed_trades), 1)
        self.assertEqual(self.engine.state.completed_trades[0].exit_reason, "take_profit")
    
    def test_get_current_state(self):
        """Test getting current state."""
        state = self.engine.get_current_state()
        
        self.assertIsInstance(state, PaperTradingState)
        self.assertEqual(state.current_capital, self.config.initial_capital)
        self.assertEqual(state.available_capital, self.config.initial_capital)
    
    def test_get_equity_curve(self):
        """Test getting equity curve."""
        # Add some equity history
        self.engine.equity_history = [
            (datetime.now() - timedelta(hours=2), 10000.0),
            (datetime.now() - timedelta(hours=1), 10500.0),
            (datetime.now(), 10200.0)
        ]
        
        equity_curve = self.engine.get_equity_curve()
        
        self.assertIsInstance(equity_curve, pd.Series)
        self.assertEqual(len(equity_curve), 3)
        self.assertEqual(equity_curve.iloc[0], 10000.0)
        self.assertEqual(equity_curve.iloc[-1], 10200.0)
    
    def test_update_performance_metrics(self):
        """Test performance metrics update."""
        # Add some equity history and trades
        self.engine.equity_history = [
            (datetime.now() - timedelta(days=1), 10000.0),
            (datetime.now() - timedelta(hours=12), 10500.0),
            (datetime.now(), 10200.0)
        ]
        
        # Add completed trades
        trade1 = PaperTrade(
            trade_id="trade_1",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            exit_price=52000.0,
            quantity=0.1,
            entry_time=datetime.now() - timedelta(hours=2),
            exit_time=datetime.now() - timedelta(hours=1),
            pnl=200.0,
            pnl_percentage=0.04,
            commission=5.0,
            slippage=2.5,
            exit_reason="take_profit"
        )
        
        trade2 = PaperTrade(
            trade_id="trade_2",
            pair="ETH/USD",
            side="buy",
            entry_price=3000.0,
            exit_price=2900.0,
            quantity=0.5,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now(),
            pnl=-50.0,
            pnl_percentage=-0.033,
            commission=3.0,
            slippage=1.5,
            exit_reason="stop_loss"
        )
        
        self.engine.state.completed_trades = [trade1, trade2]
        
        # Update performance metrics
        self.engine._update_performance_metrics()
        
        metrics = self.engine.performance_metrics
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.trades_count, 2)
        self.assertEqual(metrics.win_rate, 0.5)  # 1 win out of 2 trades
        self.assertGreater(metrics.total_return, -1.0)  # Should be reasonable
    
    def test_check_transition_readiness_not_ready(self):
        """Test transition readiness check - not ready."""
        # Set up minimal performance data
        self.engine.equity_history = [(datetime.now(), 10000.0)]
        self.engine.state.completed_trades = []
        
        readiness = self.engine.check_transition_readiness()
        
        self.assertFalse(readiness['ready'])
        self.assertIn('Insufficient performance data', readiness['reason'])
    
    def test_check_transition_readiness_ready(self):
        """Test transition readiness check - ready."""
        # Create good performance metrics
        self.engine.performance_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            excess_return=0.10,
            sharpe_ratio=1.5,  # Above minimum
            sortino_ratio=1.8,
            calmar_ratio=1.2,
            max_drawdown=-0.05,  # Better than minimum
            volatility=0.10,
            downside_deviation=0.08,
            win_rate=0.60,  # Above minimum
            profit_factor=2.0,
            avg_trade_duration=timedelta(hours=12),
            trades_count=60,  # Above minimum
            avg_win=150.0,
            avg_loss=-80.0
        )
        
        readiness = self.engine.check_transition_readiness()
        
        self.assertTrue(readiness['ready'])
        self.assertTrue(all(readiness['criteria_met'].values()))
        self.assertIn('Ready for gradual transition', readiness['recommendations'][0])
    
    def test_compare_with_live_trading(self):
        """Test comparison with live trading performance."""
        # Set up paper trading performance
        self.engine.performance_metrics = PerformanceMetrics(
            total_return=0.12,
            annualized_return=0.12,
            excess_return=0.08,
            sharpe_ratio=1.2,
            sortino_ratio=1.4,
            calmar_ratio=1.0,
            max_drawdown=-0.08,
            volatility=0.10,
            downside_deviation=0.08,
            win_rate=0.58,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=12),
            trades_count=45,
            avg_win=120.0,
            avg_loss=-70.0
        )
        
        # Create live trading performance
        live_performance = PerformanceMetrics(
            total_return=0.10,
            annualized_return=0.10,
            excess_return=0.06,
            sharpe_ratio=1.0,
            sortino_ratio=1.2,
            calmar_ratio=0.8,
            max_drawdown=-0.10,
            volatility=0.10,
            downside_deviation=0.08,
            win_rate=0.55,
            profit_factor=1.6,
            avg_trade_duration=timedelta(hours=12),
            trades_count=40,
            avg_win=100.0,
            avg_loss=-65.0
        )
        
        comparison = self.engine.compare_with_live_trading(live_performance)
        
        self.assertIn('paper_vs_live', comparison)
        self.assertIn('paper_performance', comparison)
        self.assertIn('live_performance', comparison)
        self.assertIn('recommendation', comparison)
        
        # Paper should be better in this case
        self.assertGreater(comparison['paper_vs_live']['total_return_diff'], 0)
        self.assertGreater(comparison['paper_vs_live']['sharpe_ratio_diff'], 0)
    
    @patch('builtins.open', create=True)
    @patch('json.dump')
    def test_export_trading_data(self, mock_json_dump, mock_open):
        """Test exporting trading data."""
        # Add some test data
        self.engine.equity_history = [(datetime.now(), 10500.0)]
        self.engine.state.completed_trades = [
            PaperTrade(
                trade_id="test_trade",
                pair="BTC/USD",
                side="buy",
                entry_price=50000.0,
                exit_price=52000.0,
                quantity=0.1,
                entry_time=datetime.now() - timedelta(hours=1),
                exit_time=datetime.now(),
                pnl=200.0,
                pnl_percentage=0.04,
                commission=5.0,
                slippage=2.5,
                exit_reason="take_profit"
            )
        ]
        
        filepath = "test_export.json"
        self.engine.export_trading_data(filepath)
        
        # Verify file operations
        mock_open.assert_called_once_with(filepath, 'w')
        mock_json_dump.assert_called_once()
        
        # Check exported data structure
        exported_data = mock_json_dump.call_args[0][0]
        self.assertIn('config', exported_data)
        self.assertIn('final_state', exported_data)
        self.assertIn('trades', exported_data)
        self.assertIn('equity_history', exported_data)


class TestPaperTradingIntegration(unittest.TestCase):
    """Test paper trading integration scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = create_default_paper_trading_config()
        self.data_manager = Mock(spec=EnhancedDataManager)
        self.strategy_engine = Mock()
        
        self.engine = PaperTradingEngine(
            config=self.config,
            data_manager=self.data_manager,
            strategy_engine=self.strategy_engine
        )
        
        # Mock data manager to return realistic prices
        self.current_prices = {
            'BTC/USD': 50000.0,
            'ETH/USD': 3000.0
        }
        
        def mock_get_latest_data(pair):
            return {'close': self.current_prices.get(pair, 50000.0)}
        
        self.data_manager.get_latest_data.side_effect = mock_get_latest_data
    
    def test_full_trading_cycle(self):
        """Test a complete trading cycle."""
        # Create and execute buy signal
        buy_signal = Mock()
        buy_signal.pair = "BTC/USD"
        buy_signal.signal_type = "buy"
        buy_signal.price = 50000.0
        buy_signal.confidence = 0.8
        buy_signal.strength = SignalStrength.STRONG
        buy_signal.stop_loss = 48000.0
        buy_signal.take_profit = 55000.0
        
        # Execute buy signal
        success = self.engine.execute_signal(buy_signal)
        self.assertTrue(success)
        self.assertEqual(len(self.engine.state.open_positions), 1)
        
        # Update price to trigger take profit
        self.current_prices['BTC/USD'] = 56000.0
        position = list(self.engine.state.open_positions.values())[0]
        position.update_current_price(56000.0)
        
        # Check exit conditions
        self.engine._check_exit_conditions()
        
        # Position should be closed with profit
        self.assertEqual(len(self.engine.state.open_positions), 0)
        self.assertEqual(len(self.engine.state.completed_trades), 1)
        
        trade = self.engine.state.completed_trades[0]
        self.assertEqual(trade.exit_reason, "take_profit")
        self.assertGreater(trade.pnl, 0)
    
    def test_risk_management_max_positions(self):
        """Test risk management - maximum positions limit."""
        # Fill up to max positions
        for i in range(self.config.max_open_positions):
            signal = Mock()
            signal.pair = f"PAIR_{i}"
            signal.signal_type = "buy"
            signal.price = 1000.0
            signal.confidence = 0.5
            signal.strength = SignalStrength.MODERATE
            signal.stop_loss = None
            signal.take_profit = None
            
            success = self.engine.execute_signal(signal)
            self.assertTrue(success)
        
        # Try to execute one more signal - should fail
        extra_signal = Mock()
        extra_signal.pair = "EXTRA_PAIR"
        extra_signal.signal_type = "buy"
        extra_signal.price = 1000.0
        extra_signal.confidence = 0.8
        extra_signal.strength = SignalStrength.STRONG
        extra_signal.stop_loss = None
        extra_signal.take_profit = None
        
        success = self.engine.execute_signal(extra_signal)
        self.assertFalse(success)
        self.assertEqual(len(self.engine.state.open_positions), self.config.max_open_positions)
    
    def test_risk_management_drawdown_limit(self):
        """Test risk management - drawdown limit."""
        # Simulate large losses to trigger drawdown limit
        self.engine.state.max_capital = 10000.0
        self.engine.state.current_capital = 7500.0  # 25% drawdown
        self.engine.state.current_drawdown = 0.25
        
        # Add some open positions
        position = PaperPosition(
            position_id="BTC_001",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            quantity=0.1,
            entry_time=datetime.now()
        )
        self.engine.state.open_positions["BTC_001"] = position
        
        # Check risk limits - should close all positions
        self.engine._check_risk_limits()
        
        # All positions should be closed due to drawdown limit
        self.assertEqual(len(self.engine.state.open_positions), 0)
    
    def test_performance_tracking(self):
        """Test performance tracking over time."""
        # Simulate trading activity over time
        start_time = datetime.now() - timedelta(days=1)
        
        # Add equity history
        self.engine.equity_history = [
            (start_time, 10000.0),
            (start_time + timedelta(hours=6), 10200.0),
            (start_time + timedelta(hours=12), 10100.0),
            (start_time + timedelta(hours=18), 10400.0),
            (datetime.now(), 10300.0)
        ]
        
        # Add some trades
        trades = [
            PaperTrade(
                trade_id="trade_1",
                pair="BTC/USD",
                side="buy",
                entry_price=50000.0,
                exit_price=51000.0,
                quantity=0.1,
                entry_time=start_time + timedelta(hours=1),
                exit_time=start_time + timedelta(hours=3),
                pnl=100.0,
                pnl_percentage=0.02,
                commission=5.0,
                slippage=2.5,
                exit_reason="take_profit"
            ),
            PaperTrade(
                trade_id="trade_2",
                pair="ETH/USD",
                side="buy",
                entry_price=3000.0,
                exit_price=2950.0,
                quantity=0.5,
                entry_time=start_time + timedelta(hours=8),
                exit_time=start_time + timedelta(hours=10),
                pnl=-25.0,
                pnl_percentage=-0.017,
                commission=3.0,
                slippage=1.5,
                exit_reason="stop_loss"
            )
        ]
        
        self.engine.state.completed_trades = trades
        
        # Update performance metrics
        self.engine._update_performance_metrics()
        
        metrics = self.engine.get_performance_metrics()
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.trades_count, 2)
        self.assertEqual(metrics.win_rate, 0.5)
        self.assertGreater(metrics.total_return, -0.1)  # Should be reasonable
        self.assertLess(metrics.max_drawdown, 0.0)  # Should have some drawdown


if __name__ == '__main__':
    unittest.main()