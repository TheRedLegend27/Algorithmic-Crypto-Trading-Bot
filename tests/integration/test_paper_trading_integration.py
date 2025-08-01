"""
Integration tests for paper trading with adaptive bot components.

Tests the full integration of paper trading with adaptive strategy engine,
market regime detection, and performance analysis.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import threading

from bot.adaptive.paper_trading import (
    PaperTradingEngine, PaperTradingConfig, create_default_paper_trading_config
)
from bot.adaptive.data_models import AdaptiveSignal, PerformanceMetrics, MarketRegime
from bot.adaptive.enums import RegimeType, SignalStrength
from bot.enhanced_data_manager import EnhancedDataManager


class TestPaperTradingIntegration(unittest.TestCase):
    """Test paper trading integration with adaptive components."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = create_default_paper_trading_config()
        self.config.initial_capital = 10000.0
        self.config.max_position_size_pct = 0.1
        
        # Mock components
        self.data_manager = Mock(spec=EnhancedDataManager)
        self.strategy_engine = Mock()
        self.regime_detector = Mock()
        self.ml_engine = Mock()
        self.performance_analyzer = Mock()
        
        # Create paper trading engine
        self.engine = PaperTradingEngine(
            config=self.config,
            data_manager=self.data_manager,
            strategy_engine=self.strategy_engine,
            regime_detector=self.regime_detector,
            ml_engine=self.ml_engine,
            performance_analyzer=self.performance_analyzer
        )
        
        # Mock market data
        self.market_data = {
            'BTC/USD': 50000.0,
            'ETH/USD': 3000.0,
            'ADA/USD': 0.5
        }
        
        def mock_get_latest_data(pair):
            return {'close': self.market_data.get(pair, 1000.0)}
        
        self.data_manager.get_latest_data.side_effect = mock_get_latest_data
    
    def test_adaptive_signal_execution(self):
        """Test executing adaptive signals with full context."""
        # Create market regime
        regime = MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.15,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now(),
            supporting_indicators={'rsi': 65, 'macd': 0.5}
        )
        
        # Create adaptive signal
        signal = AdaptiveSignal(
            pair='BTC/USD',
            signal_type='buy',
            strength=SignalStrength.STRONG,
            confidence=0.85,
            price=50000.0,
            timestamp=datetime.now(),
            stop_loss=48000.0,
            take_profit=55000.0,
            regime_context=regime,
            strategy_weights={'momentum': 0.6, 'breakout': 0.4},
            ml_confidence=0.75,
            suggested_position_size=1000.0
        )
        
        # Execute signal
        success = self.engine.execute_signal(signal)
        
        self.assertTrue(success)
        self.assertEqual(len(self.engine.state.open_positions), 1)
        
        # Verify position details
        position = list(self.engine.state.open_positions.values())[0]
        self.assertEqual(position.pair, 'BTC/USD')
        self.assertEqual(position.side, 'buy')
        self.assertAlmostEqual(position.entry_price, 50000.0 * (1 + self.config.slippage_rate), places=2)
        self.assertEqual(position.stop_loss, 48000.0)
        self.assertEqual(position.take_profit, 55000.0)
        self.assertEqual(position.confidence, 0.85)
    
    def test_multi_pair_trading_simulation(self):
        """Test paper trading with multiple pairs simultaneously."""
        pairs = ['BTC/USD', 'ETH/USD', 'ADA/USD']
        
        # Create signals for different pairs
        signals = [
            AdaptiveSignal(
                pair='BTC/USD',
                signal_type='buy',
                strength=SignalStrength.STRONG,
                confidence=0.8,
                price=50000.0,
                timestamp=datetime.now(),
                stop_loss=48000.0,
                take_profit=55000.0,
                suggested_position_size=1000.0
            ),
            AdaptiveSignal(
                pair='ETH/USD',
                signal_type='buy',
                strength=SignalStrength.MEDIUM,
                confidence=0.7,
                price=3000.0,
                timestamp=datetime.now(),
                stop_loss=2800.0,
                take_profit=3300.0,
                suggested_position_size=800.0
            ),
            AdaptiveSignal(
                pair='ADA/USD',
                signal_type='sell',
                strength=SignalStrength.WEAK,
                confidence=0.6,
                price=0.5,
                timestamp=datetime.now(),
                stop_loss=0.55,
                take_profit=0.45,
                suggested_position_size=500.0
            )
        ]
        
        # Execute all signals
        for signal in signals:
            success = self.engine.execute_signal(signal)
            self.assertTrue(success)
        
        # Verify all positions are open
        self.assertEqual(len(self.engine.state.open_positions), 3)
        
        # Verify different pairs
        position_pairs = {pos.pair for pos in self.engine.state.open_positions.values()}
        self.assertEqual(position_pairs, {'BTC/USD', 'ETH/USD', 'ADA/USD'})
        
        # Verify different sides
        sides = {pos.side for pos in self.engine.state.open_positions.values()}
        self.assertIn('buy', sides)
        self.assertIn('sell', sides)
    
    def test_regime_based_trading_decisions(self):
        """Test trading decisions based on market regime."""
        # Test different regimes
        regimes = [
            (RegimeType.TRENDING_BULL, 'buy', 0.8),
            (RegimeType.TRENDING_BEAR, 'sell', 0.7),
            (RegimeType.RANGING, 'buy', 0.5),  # Lower confidence in ranging market
            (RegimeType.HIGH_VOLATILITY, 'sell', 0.6)
        ]
        
        for regime_type, signal_type, expected_confidence in regimes:
            # Create regime context
            regime = MarketRegime(
                regime_type=regime_type,
                confidence=0.8,
                volatility_level=0.2 if regime_type != RegimeType.HIGH_VOLATILITY else 0.4,
                trend_strength=0.7 if 'TRENDING' in regime_type.name else 0.3,
                momentum=0.6,
                detected_at=datetime.now(),
                supporting_indicators={}
            )
            
            # Create signal with regime context
            signal = AdaptiveSignal(
                pair=f'TEST_{regime_type.name}',
                signal_type=signal_type,
                strength=SignalStrength.MEDIUM,
                confidence=expected_confidence,
                price=1000.0,
                timestamp=datetime.now(),
                regime_context=regime,
                suggested_position_size=500.0
            )
            
            # Execute signal
            success = self.engine.execute_signal(signal)
            self.assertTrue(success)
        
        # Verify all regime-based positions were created
        self.assertEqual(len(self.engine.state.open_positions), 4)
    
    def test_ml_confidence_integration(self):
        """Test integration with ML confidence scores."""
        # Create signals with different ML confidence levels
        ml_confidences = [0.9, 0.7, 0.5, 0.3]
        
        for i, ml_conf in enumerate(ml_confidences):
            signal = AdaptiveSignal(
                pair=f'ML_TEST_{i}',
                signal_type='buy',
                strength=SignalStrength.MEDIUM,
                confidence=0.8,  # Base confidence
                price=1000.0,
                timestamp=datetime.now(),
                ml_confidence=ml_conf,
                suggested_position_size=500.0
            )
            
            success = self.engine.execute_signal(signal)
            
            # Higher ML confidence should lead to successful execution
            if ml_conf >= 0.5:
                self.assertTrue(success)
            # Note: In this test, all should succeed since we're not filtering by ML confidence
            # In a real implementation, you might want to filter low-confidence signals
    
    def test_performance_analysis_integration(self):
        """Test integration with performance analysis."""
        # Execute some trades to generate performance data
        signals = [
            # Profitable trade
            AdaptiveSignal(
                pair='PROFIT_TEST',
                signal_type='buy',
                strength=SignalStrength.STRONG,
                confidence=0.8,
                price=1000.0,
                timestamp=datetime.now(),
                stop_loss=950.0,
                take_profit=1100.0,
                suggested_position_size=1000.0
            ),
            # Loss trade
            AdaptiveSignal(
                pair='LOSS_TEST',
                signal_type='buy',
                strength=SignalStrength.WEAK,
                confidence=0.6,
                price=2000.0,
                timestamp=datetime.now(),
                stop_loss=1900.0,
                take_profit=2200.0,
                suggested_position_size=800.0
            )
        ]
        
        # Execute signals
        for signal in signals:
            success = self.engine.execute_signal(signal)
            self.assertTrue(success)
        
        # Simulate price movements and close positions
        positions = list(self.engine.state.open_positions.values())
        
        # Close first position with profit
        self.engine._close_position(positions[0], 1100.0, 'take_profit')
        
        # Close second position with loss
        self.engine._close_position(positions[1], 1900.0, 'stop_loss')
        
        # Verify trades were recorded
        self.assertEqual(len(self.engine.state.completed_trades), 2)
        
        # Check trade outcomes
        trades = self.engine.state.completed_trades
        profit_trade = next(t for t in trades if t.pair == 'PROFIT_TEST')
        loss_trade = next(t for t in trades if t.pair == 'LOSS_TEST')
        
        self.assertGreater(profit_trade.pnl, 0)
        self.assertLess(loss_trade.pnl, 0)
        self.assertEqual(profit_trade.exit_reason, 'take_profit')
        self.assertEqual(loss_trade.exit_reason, 'stop_loss')
        
        # Update and check performance metrics
        self.engine._update_performance_metrics()
        metrics = self.engine.get_performance_metrics()
        
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.trades_count, 2)
        self.assertEqual(metrics.win_rate, 0.5)  # 1 win, 1 loss
    
    def test_real_time_simulation(self):
        """Test real-time simulation capabilities."""
        # Start the engine (this starts the real-time update thread)
        pairs = ['BTC/USD', 'ETH/USD']
        
        # Mock the real-time update to avoid actual threading in tests
        with patch.object(self.engine, '_real_time_update_loop'):
            self.engine.start(pairs)
            
            # Create and execute a signal
            signal = AdaptiveSignal(
                pair='BTC/USD',
                signal_type='buy',
                strength=SignalStrength.MEDIUM,
                confidence=0.7,
                price=50000.0,
                timestamp=datetime.now(),
                suggested_position_size=1000.0
            )
            
            success = self.engine.execute_signal(signal)
            self.assertTrue(success)
            
            # Verify position was created
            self.assertEqual(len(self.engine.state.open_positions), 1)
            
            # Stop the engine
            self.engine.stop()
            
            # Verify all positions were closed
            self.assertEqual(len(self.engine.state.open_positions), 0)
    
    def test_transition_readiness_analysis(self):
        """Test transition readiness analysis."""
        # Create performance data that meets transition criteria
        self.engine.performance_metrics = PerformanceMetrics(
            total_return=0.20,
            annualized_return=0.20,
            excess_return=0.15,
            sharpe_ratio=1.5,  # Above minimum (1.0)
            sortino_ratio=1.8,
            calmar_ratio=1.2,
            max_drawdown=-0.05,  # Better than minimum (-0.1)
            volatility=0.12,
            downside_deviation=0.10,
            win_rate=0.60,  # Above minimum (0.55)
            profit_factor=2.2,
            avg_trade_duration=timedelta(hours=8),
            trades_count=60,  # Above minimum (50)
            avg_win=180.0,
            avg_loss=-85.0
        )
        
        # Check transition readiness
        readiness = self.engine.check_transition_readiness()
        
        self.assertTrue(readiness['ready'])
        self.assertTrue(all(readiness['criteria_met'].values()))
        self.assertIn('Ready for gradual transition', readiness['recommendations'][0])
        
        # Test with poor performance
        self.engine.performance_metrics.sharpe_ratio = 0.5  # Below minimum
        self.engine.performance_metrics.win_rate = 0.45  # Below minimum
        
        readiness = self.engine.check_transition_readiness()
        
        self.assertFalse(readiness['ready'])
        self.assertFalse(readiness['criteria_met']['sharpe_ratio'])
        self.assertFalse(readiness['criteria_met']['win_rate'])
        self.assertGreater(len(readiness['recommendations']), 1)
    
    def test_live_trading_comparison(self):
        """Test comparison with live trading performance."""
        # Set up paper trading performance
        paper_performance = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            excess_return=0.10,
            sharpe_ratio=1.3,
            sortino_ratio=1.5,
            calmar_ratio=1.1,
            max_drawdown=-0.08,
            volatility=0.11,
            downside_deviation=0.09,
            win_rate=0.58,
            profit_factor=1.9,
            avg_trade_duration=timedelta(hours=10),
            trades_count=45,
            avg_win=130.0,
            avg_loss=-75.0
        )
        
        self.engine.performance_metrics = paper_performance
        
        # Create hypothetical live trading performance
        live_performance = PerformanceMetrics(
            total_return=0.12,
            annualized_return=0.12,
            excess_return=0.08,
            sharpe_ratio=1.1,
            sortino_ratio=1.3,
            calmar_ratio=0.9,
            max_drawdown=-0.10,
            volatility=0.11,
            downside_deviation=0.09,
            win_rate=0.55,
            profit_factor=1.7,
            avg_trade_duration=timedelta(hours=12),
            trades_count=42,
            avg_win=120.0,
            avg_loss=-80.0
        )
        
        # Compare performances
        comparison = self.engine.compare_with_live_trading(live_performance)
        
        # Verify comparison structure
        self.assertIn('paper_vs_live', comparison)
        self.assertIn('paper_performance', comparison)
        self.assertIn('live_performance', comparison)
        self.assertIn('recommendation', comparison)
        
        # Paper trading should be better in this scenario
        self.assertGreater(comparison['paper_vs_live']['total_return_diff'], 0)
        self.assertGreater(comparison['paper_vs_live']['sharpe_ratio_diff'], 0)
        self.assertGreater(comparison['paper_vs_live']['win_rate_diff'], 0)
        
        # Check individual performance records
        self.assertEqual(comparison['paper_performance']['total_return'], 0.15)
        self.assertEqual(comparison['live_performance']['total_return'], 0.12)
    
    def test_risk_management_integration(self):
        """Test risk management integration."""
        # Test maximum position limit
        max_positions = self.config.max_open_positions
        
        # Try to create more positions than allowed
        for i in range(max_positions + 2):
            signal = AdaptiveSignal(
                pair=f'RISK_TEST_{i}',
                signal_type='buy',
                strength=SignalStrength.MEDIUM,
                confidence=0.7,
                price=1000.0,
                timestamp=datetime.now(),
                suggested_position_size=500.0
            )
            
            success = self.engine.execute_signal(signal)
            
            if i < max_positions:
                self.assertTrue(success)
            else:
                self.assertFalse(success)  # Should fail due to position limit
        
        # Verify we have exactly max_positions
        self.assertEqual(len(self.engine.state.open_positions), max_positions)
        
        # Test drawdown limit
        original_capital = self.engine.state.current_capital
        self.engine.state.max_capital = original_capital
        
        # Simulate large loss to trigger drawdown limit
        self.engine.state.current_capital = original_capital * 0.75  # 25% drawdown
        self.engine.state.current_drawdown = 0.25
        
        # This should trigger position closure
        self.engine._check_risk_limits()
        
        # All positions should be closed due to drawdown
        self.assertEqual(len(self.engine.state.open_positions), 0)
    
    def test_data_export_and_analysis(self):
        """Test data export functionality."""
        # Create some trading history
        self.engine.equity_history = [
            (datetime.now() - timedelta(hours=2), 10000.0),
            (datetime.now() - timedelta(hours=1), 10300.0),
            (datetime.now(), 10150.0)
        ]
        
        # Add completed trades
        from bot.adaptive.paper_trading import PaperTrade
        
        trade = PaperTrade(
            trade_id="export_test_trade",
            pair="BTC/USD",
            side="buy",
            entry_price=50000.0,
            exit_price=51500.0,
            quantity=0.1,
            entry_time=datetime.now() - timedelta(hours=1),
            exit_time=datetime.now(),
            pnl=150.0,
            pnl_percentage=0.03,
            commission=5.0,
            slippage=2.5,
            exit_reason="take_profit",
            strategy_name="test_strategy"
        )
        
        self.engine.state.completed_trades = [trade]
        
        # Test export functionality
        with patch('builtins.open', create=True) as mock_open:
            with patch('json.dump') as mock_json_dump:
                filepath = "test_export.json"
                self.engine.export_trading_data(filepath)
                
                # Verify export was called
                mock_open.assert_called_once_with(filepath, 'w')
                mock_json_dump.assert_called_once()
                
                # Check exported data structure
                exported_data = mock_json_dump.call_args[0][0]
                
                self.assertIn('config', exported_data)
                self.assertIn('final_state', exported_data)
                self.assertIn('trades', exported_data)
                self.assertIn('equity_history', exported_data)
                self.assertIn('performance_metrics', exported_data)
                
                # Verify trade data
                self.assertEqual(len(exported_data['trades']), 1)
                self.assertEqual(exported_data['trades'][0]['trade_id'], "export_test_trade")
                self.assertEqual(exported_data['trades'][0]['pnl'], 150.0)


class TestPaperTradingPerformance(unittest.TestCase):
    """Test paper trading performance under various scenarios."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = create_default_paper_trading_config()
        self.data_manager = Mock(spec=EnhancedDataManager)
        
        self.engine = PaperTradingEngine(
            config=self.config,
            data_manager=self.data_manager
        )
        
        # Mock consistent price data
        self.data_manager.get_latest_data.return_value = {'close': 50000.0}
    
    def test_high_frequency_trading_simulation(self):
        """Test paper trading with high frequency signals."""
        # Generate many signals in short time
        signals = []
        base_time = datetime.now()
        
        for i in range(20):
            signal = AdaptiveSignal(
                pair=f'HFT_PAIR_{i % 3}',  # Rotate between 3 pairs
                signal_type='buy' if i % 2 == 0 else 'sell',
                strength=SignalStrength.MEDIUM,
                confidence=0.6 + (i % 3) * 0.1,
                price=50000.0 + (i * 100),
                timestamp=base_time + timedelta(seconds=i * 5),
                suggested_position_size=200.0
            )
            signals.append(signal)
        
        # Execute signals rapidly
        successful_executions = 0
        for signal in signals:
            if self.engine.execute_signal(signal):
                successful_executions += 1
        
        # Should have some successful executions but limited by risk management
        self.assertGreater(successful_executions, 0)
        self.assertLessEqual(successful_executions, self.config.max_open_positions)
        self.assertLessEqual(len(self.engine.state.open_positions), self.config.max_open_positions)
    
    def test_market_stress_scenarios(self):
        """Test paper trading under market stress conditions."""
        # Simulate volatile market conditions
        volatile_signals = [
            # Large price swings
            AdaptiveSignal(
                pair='VOLATILE_BTC',
                signal_type='buy',
                strength=SignalStrength.STRONG,
                confidence=0.9,
                price=50000.0,
                timestamp=datetime.now(),
                stop_loss=45000.0,  # Wide stop loss
                take_profit=60000.0,  # Wide take profit
                suggested_position_size=1500.0
            ),
            # Quick reversal
            AdaptiveSignal(
                pair='REVERSAL_ETH',
                signal_type='sell',
                strength=SignalStrength.MEDIUM,
                confidence=0.7,
                price=3000.0,
                timestamp=datetime.now(),
                stop_loss=3300.0,
                take_profit=2500.0,
                suggested_position_size=1000.0
            )
        ]
        
        # Execute stress signals
        for signal in volatile_signals:
            success = self.engine.execute_signal(signal)
            self.assertTrue(success)
        
        # Simulate extreme price movements
        positions = list(self.engine.state.open_positions.values())
        
        # Simulate stop loss trigger on first position
        btc_position = next(p for p in positions if p.pair == 'VOLATILE_BTC')
        btc_position.update_current_price(44000.0)  # Below stop loss
        
        # Simulate take profit trigger on second position
        eth_position = next(p for p in positions if p.pair == 'REVERSAL_ETH')
        eth_position.update_current_price(2400.0)  # Below take profit for sell
        
        # Check exit conditions
        self.engine._check_exit_conditions()
        
        # Both positions should be closed
        self.assertEqual(len(self.engine.state.open_positions), 0)
        self.assertEqual(len(self.engine.state.completed_trades), 2)
        
        # Verify exit reasons
        trades = self.engine.state.completed_trades
        exit_reasons = {trade.exit_reason for trade in trades}
        self.assertIn('stop_loss', exit_reasons)
        self.assertIn('take_profit', exit_reasons)


if __name__ == '__main__':
    unittest.main()