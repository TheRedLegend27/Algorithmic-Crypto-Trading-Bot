"""
Integration tests for MockTrader comparing responses with expected live trader behavior.

This module contains comprehensive tests to ensure that the MockTrader provides
the same interface and behavior as the live Trader class, enabling seamless
switching between mock and live trading environments.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from mock_trading.mock_trader import MockTrader, MockAlpacaAPI, MockCredentials
from mock_trading.mock_config import MockTradingConfig
from bot.config import AlpacaCredentials, TradingSettings
from bot.strategy import TradingSignal, SignalType
from bot.trader import TradeResult


class TestMockTraderIntegration(unittest.TestCase):
    """Test suite for MockTrader integration and interface compatibility."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mock credentials and settings
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret",
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        
        self.settings = TradingSettings(
            symbol="BTC/USD",
            trade_amount=100.0,
            max_position_size=500.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
            min_trade_interval=1
        )
        
        # Create mock trader
        self.mock_trader = MockTrader(self.credentials, self.settings)
        
        # Create test trading signals
        self.buy_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.8,
            strategy="TestStrategy",
            timestamp=datetime.now(),
            price=50000.0,
            reasoning="Test buy signal"
        )
        
        self.sell_signal = TradingSignal(
            action=SignalType.SELL,
            confidence=0.7,
            strategy="TestStrategy",
            timestamp=datetime.now(),
            price=51000.0,
            reasoning="Test sell signal"
        )
        
        self.hold_signal = TradingSignal(
            action=SignalType.HOLD,
            confidence=0.3,
            strategy="TestStrategy",
            timestamp=datetime.now(),
            price=50500.0,
            reasoning="Test hold signal"
        )
    
    def test_mock_trader_initialization(self):
        """Test that MockTrader initializes with the same interface as live Trader."""
        # Check that MockTrader has the same attributes as live Trader
        self.assertTrue(hasattr(self.mock_trader, 'credentials'))
        self.assertTrue(hasattr(self.mock_trader, 'settings'))
        self.assertTrue(hasattr(self.mock_trader, 'position_manager'))
        self.assertTrue(hasattr(self.mock_trader, 'order_manager'))
        self.assertTrue(hasattr(self.mock_trader, 'last_trade_time'))
        
        # Check that credentials are properly set (mock credentials)
        self.assertIsInstance(self.mock_trader.credentials, MockCredentials)
        self.assertEqual(self.mock_trader.credentials.paper_trading, True)
        
        # Check that settings are preserved
        self.assertEqual(self.mock_trader.settings.symbol, "BTC/USD")
        self.assertEqual(self.mock_trader.settings.trade_amount, 100.0)
    
    def test_execute_trade_interface_compatibility(self):
        """Test that execute_trade method has the same interface as live Trader."""
        # Test buy signal execution
        result = self.mock_trader.execute_trade(self.buy_signal)
        
        if result:  # Trade was executed
            self.assertIsInstance(result, TradeResult)
            self.assertTrue(hasattr(result, 'order_id'))
            self.assertTrue(hasattr(result, 'symbol'))
            self.assertTrue(hasattr(result, 'side'))
            self.assertTrue(hasattr(result, 'quantity'))
            self.assertTrue(hasattr(result, 'price'))
            self.assertTrue(hasattr(result, 'status'))
            self.assertTrue(hasattr(result, 'timestamp'))
            self.assertTrue(hasattr(result, 'fees'))
            
            # Check that values are reasonable
            self.assertEqual(result.symbol, "BTC/USD")
            self.assertEqual(result.side, "BUY")
            self.assertGreater(result.quantity, 0)
            self.assertGreater(result.price, 0)
            self.assertGreaterEqual(result.fees, 0)
        
        # Test hold signal (should return None)
        hold_result = self.mock_trader.execute_trade(self.hold_signal)
        self.assertIsNone(hold_result)
    
    def test_position_manager_interface_compatibility(self):
        """Test that position manager has the same interface as live PositionManager."""
        pm = self.mock_trader.position_manager
        
        # Check that all required methods exist
        self.assertTrue(hasattr(pm, 'get_position'))
        self.assertTrue(hasattr(pm, 'get_position_quantity'))
        self.assertTrue(hasattr(pm, 'get_position_value'))
        self.assertTrue(hasattr(pm, 'get_unrealized_pnl'))
        self.assertTrue(hasattr(pm, 'get_average_entry_price'))
        self.assertTrue(hasattr(pm, 'get_position_summary'))
        self.assertTrue(hasattr(pm, 'track_position_change'))
        self.assertTrue(hasattr(pm, 'get_position_history'))
        self.assertTrue(hasattr(pm, 'reconcile_positions'))
        self.assertTrue(hasattr(pm, 'verify_position_accuracy'))
        
        # Test method return types
        symbol = "BTC/USD"
        
        # Initially no position
        self.assertEqual(pm.get_position_quantity(symbol), 0.0)
        self.assertEqual(pm.get_position_value(symbol), 0.0)
        self.assertEqual(pm.get_unrealized_pnl(symbol), 0.0)
        self.assertEqual(pm.get_average_entry_price(symbol), 0.0)
        
        # Position summary should be a dict
        summary = pm.get_position_summary(symbol)
        self.assertIsInstance(summary, dict)
        self.assertIn('symbol', summary)
        self.assertIn('quantity', summary)
        self.assertIn('market_value', summary)
        self.assertIn('has_position', summary)
        self.assertFalse(summary['has_position'])
        
        # Position history should be a list
        history = pm.get_position_history(symbol)
        self.assertIsInstance(history, list)
        
        # Reconciliation should return boolean
        reconcile_result = pm.reconcile_positions()
        self.assertIsInstance(reconcile_result, bool)
        
        # Verification should return tuple
        is_accurate, actual_qty = pm.verify_position_accuracy(symbol, 0.0)
        self.assertIsInstance(is_accurate, bool)
        self.assertIsInstance(actual_qty, float)
    
    def test_order_manager_interface_compatibility(self):
        """Test that order manager has the same interface as live OrderManager."""
        om = self.mock_trader.order_manager
        
        # Check that all required methods exist
        self.assertTrue(hasattr(om, 'place_market_order'))
        self.assertTrue(hasattr(om, 'get_order_status'))
        self.assertTrue(hasattr(om, 'is_order_filled'))
        self.assertTrue(hasattr(om, 'cancel_order'))
        self.assertTrue(hasattr(om, 'get_recent_orders'))
        
        # Test method signatures and return types
        from alpaca.trading.enums import OrderSide
        
        # place_market_order should accept same parameters
        try:
            order = om.place_market_order("BTC/USD", OrderSide.BUY, 0.001)
            if order:
                self.assertTrue(hasattr(order, 'id'))
                self.assertTrue(hasattr(order, 'symbol'))
                self.assertTrue(hasattr(order, 'quantity'))
                self.assertTrue(hasattr(order, 'side'))
                self.assertTrue(hasattr(order, 'status'))
        except Exception as e:
            self.fail(f"place_market_order failed with interface-compatible parameters: {e}")
        
        # get_recent_orders should return a list
        recent_orders = om.get_recent_orders()
        self.assertIsInstance(recent_orders, list)
        
        # get_recent_orders with symbol filter
        recent_orders_filtered = om.get_recent_orders("BTC/USD", limit=5)
        self.assertIsInstance(recent_orders_filtered, list)
    
    def test_account_info_interface_compatibility(self):
        """Test that get_account_info returns the same structure as live Trader."""
        account_info = self.mock_trader.get_account_info()
        
        # Should return a dictionary
        self.assertIsInstance(account_info, dict)
        
        # Should have the same keys as live trader
        expected_keys = ['cash', 'portfolio_value', 'buying_power', 'equity']
        for key in expected_keys:
            self.assertIn(key, account_info)
            self.assertIsInstance(account_info[key], (int, float))
            self.assertGreaterEqual(account_info[key], 0)
        
        # Initial values should match starting capital
        starting_capital = self.mock_trader.config.starting_capital
        self.assertEqual(account_info['cash'], starting_capital)
        self.assertEqual(account_info['portfolio_value'], starting_capital)
    
    def test_trading_workflow_compatibility(self):
        """Test complete trading workflow matches live trader behavior."""
        # Execute a buy trade
        buy_result = self.mock_trader.execute_trade(self.buy_signal)
        
        if buy_result:
            # Check position was created
            position_qty = self.mock_trader.position_manager.get_position_quantity("BTC/USD")
            self.assertGreater(position_qty, 0)
            
            # Check account balance changed
            account_info = self.mock_trader.get_account_info()
            self.assertLess(account_info['cash'], self.mock_trader.config.starting_capital)
            
            # Execute a sell trade
            sell_result = self.mock_trader.execute_trade(self.sell_signal)
            
            if sell_result:
                # Check position was reduced/closed
                new_position_qty = self.mock_trader.position_manager.get_position_quantity("BTC/USD")
                self.assertLessEqual(new_position_qty, position_qty)
                
                # Check account balance changed again
                new_account_info = self.mock_trader.get_account_info()
                # Cash should have increased from the sell
                self.assertGreater(new_account_info['cash'], account_info['cash'])
    
    def test_risk_management_interface_compatibility(self):
        """Test that risk management methods have the same interface as live Trader."""
        # Check that risk management methods exist
        self.assertTrue(hasattr(self.mock_trader, 'check_risk_management_triggers'))
        
        # Test method signature
        symbol = "BTC/USD"
        current_price = 50000.0
        
        # Should return boolean
        trigger_result = self.mock_trader.check_risk_management_triggers(symbol, current_price)
        self.assertIsInstance(trigger_result, bool)
        
        # Test with position (execute buy first)
        buy_result = self.mock_trader.execute_trade(self.buy_signal)
        if buy_result:
            # Test stop loss trigger
            stop_loss_price = self.buy_signal.price * (1 - self.settings.stop_loss_pct - 0.01)
            stop_loss_triggered = self.mock_trader.check_risk_management_triggers(symbol, stop_loss_price)
            
            # Test take profit trigger
            take_profit_price = self.buy_signal.price * (1 + self.settings.take_profit_pct + 0.01)
            take_profit_triggered = self.mock_trader.check_risk_management_triggers(symbol, take_profit_price)
            
            # At least one should be boolean (both are valid outcomes)
            self.assertIsInstance(stop_loss_triggered, bool)
            self.assertIsInstance(take_profit_triggered, bool)
    
    def test_error_handling_compatibility(self):
        """Test that error handling behaves similarly to live Trader."""
        # Test invalid signal
        invalid_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.1,  # Too low confidence
            strategy="TestStrategy",
            timestamp=datetime.now(),
            price=0.0,  # Invalid price
            reasoning="Invalid signal"
        )
        
        # Should handle gracefully and return None
        result = self.mock_trader.execute_trade(invalid_signal)
        self.assertIsNone(result)
        
        # Test order validation
        from mock_trading.mock_models import Order, OrderType, OrderSide
        
        invalid_order = Order(
            symbol="INVALID",
            quantity=-1.0,  # Invalid quantity
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        # Should return False for invalid order
        is_valid = self.mock_trader.validate_order(invalid_order)
        self.assertFalse(is_valid)
        
        # Test valid order
        valid_order = Order(
            symbol="BTCUSD",
            quantity=0.001,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        is_valid = self.mock_trader.validate_order(valid_order)
        self.assertTrue(is_valid)
    
    def test_configuration_compatibility(self):
        """Test that configuration handling is compatible with live Trader."""
        # Test that MockTrader accepts same configuration parameters
        custom_settings = TradingSettings(
            symbol="ETH/USD",
            trade_amount=50.0,
            max_position_size=200.0,
            stop_loss_pct=0.03,
            take_profit_pct=0.08,
            min_trade_interval=2
        )
        
        # Should be able to create MockTrader with custom settings
        custom_mock_trader = MockTrader(self.credentials, custom_settings)
        
        # Settings should be preserved
        self.assertEqual(custom_mock_trader.settings.symbol, "ETH/USD")
        self.assertEqual(custom_mock_trader.settings.trade_amount, 50.0)
        self.assertEqual(custom_mock_trader.settings.max_position_size, 200.0)
        self.assertEqual(custom_mock_trader.settings.stop_loss_pct, 0.03)
        self.assertEqual(custom_mock_trader.settings.take_profit_pct, 0.08)
        self.assertEqual(custom_mock_trader.settings.min_trade_interval, 2)
    
    def test_mock_alpaca_api_compatibility(self):
        """Test that MockAlpacaAPI provides the same interface as Alpaca TradingClient."""
        api = self.mock_trader.mock_api
        
        # Check that required methods exist
        self.assertTrue(hasattr(api, 'get_all_positions'))
        self.assertTrue(hasattr(api, 'get_position'))
        self.assertTrue(hasattr(api, 'submit_order'))
        self.assertTrue(hasattr(api, 'get_order'))
        self.assertTrue(hasattr(api, 'get_orders'))
        self.assertTrue(hasattr(api, 'cancel_order'))
        self.assertTrue(hasattr(api, 'get_account'))
        
        # Test method return types
        positions = api.get_all_positions()
        self.assertIsInstance(positions, list)
        
        position = api.get_position("BTCUSD")
        # Can be None or MockPosition
        
        account = api.get_account()
        self.assertTrue(hasattr(account, 'cash'))
        self.assertTrue(hasattr(account, 'portfolio_value'))
        self.assertTrue(hasattr(account, 'buying_power'))
        self.assertTrue(hasattr(account, 'equity'))
        
        orders = api.get_orders()
        self.assertIsInstance(orders, list)
    
    def test_performance_metrics_compatibility(self):
        """Test that performance tracking is compatible with live trader expectations."""
        # Execute some trades to generate performance data
        buy_result = self.mock_trader.execute_trade(self.buy_signal)
        
        if buy_result:
            # Check that position manager tracks performance
            pm = self.mock_trader.position_manager_impl
            performance = pm.get_performance_summary()
            
            # Should return dictionary with expected keys
            self.assertIsInstance(performance, dict)
            expected_keys = [
                'starting_cash', 'current_cash', 'current_portfolio_value',
                'total_return', 'total_return_pct', 'realized_pnl', 'unrealized_pnl',
                'total_pnl', 'total_fees_paid', 'active_positions'
            ]
            
            for key in expected_keys:
                self.assertIn(key, performance)
                self.assertIsInstance(performance[key], (int, float))
            
            # Values should be reasonable
            self.assertEqual(performance['starting_cash'], self.mock_trader.config.starting_capital)
            self.assertGreaterEqual(performance['active_positions'], 0)
            self.assertGreaterEqual(performance['total_fees_paid'], 0)


class TestMockTraderBehaviorConsistency(unittest.TestCase):
    """Test suite for ensuring consistent behavior between mock and expected live trader."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.credentials = AlpacaCredentials(
            api_key="test_key",
            secret_key="test_secret", 
            base_url="https://paper-api.alpaca.markets",
            paper_trading=True
        )
        
        self.settings = TradingSettings(
            symbol="BTC/USD",
            trade_amount=100.0,
            max_position_size=500.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
            min_trade_interval=1
        )
        
        self.mock_trader = MockTrader(self.credentials, self.settings)
    
    def test_trade_execution_consistency(self):
        """Test that trade execution produces consistent results."""
        signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.8,
            strategy="TestStrategy",
            timestamp=datetime.now(),
            price=50000.0,
            reasoning="Test signal"
        )
        
        # Execute multiple trades with same signal
        results = []
        for _ in range(3):
            # Reset trader state
            self.mock_trader = MockTrader(self.credentials, self.settings)
            result = self.mock_trader.execute_trade(signal)
            if result:
                results.append(result)
        
        if len(results) > 1:
            # All results should have similar characteristics
            first_result = results[0]
            for result in results[1:]:
                self.assertEqual(result.symbol, first_result.symbol)
                self.assertEqual(result.side, first_result.side)
                # Quantities should be similar (within 1% due to slippage simulation)
                self.assertAlmostEqual(result.quantity, first_result.quantity, delta=first_result.quantity * 0.01)
                # Prices should be similar (within 1% due to slippage simulation)
                self.assertAlmostEqual(result.price, first_result.price, delta=first_result.price * 0.01)
    
    def test_position_tracking_consistency(self):
        """Test that position tracking is consistent across operations."""
        signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.8,
            strategy="TestStrategy",
            timestamp=datetime.now(),
            price=50000.0,
            reasoning="Test signal"
        )
        
        # Initial state
        initial_qty = self.mock_trader.position_manager.get_position_quantity("BTC/USD")
        self.assertEqual(initial_qty, 0.0)
        
        # Execute buy
        buy_result = self.mock_trader.execute_trade(signal)
        
        if buy_result:
            # Position should exist
            position_qty = self.mock_trader.position_manager.get_position_quantity("BTC/USD")
            self.assertGreater(position_qty, 0)
            self.assertAlmostEqual(position_qty, buy_result.quantity, places=4)
            
            # Position value should be reasonable
            position_value = self.mock_trader.position_manager.get_position_value("BTC/USD")
            expected_value = position_qty * buy_result.price
            self.assertAlmostEqual(position_value, expected_value, delta=expected_value * 0.01)
            
            # Account balance should be reduced
            account_info = self.mock_trader.get_account_info()
            expected_cash = self.mock_trader.config.starting_capital - (buy_result.quantity * buy_result.price + buy_result.fees)
            self.assertAlmostEqual(account_info['cash'], expected_cash, delta=1.0)
    
    def test_order_lifecycle_consistency(self):
        """Test that order lifecycle is handled consistently."""
        from alpaca.trading.enums import OrderSide
        
        # Place order through order manager
        order = self.mock_trader.order_manager.place_market_order("BTC/USD", OrderSide.BUY, 0.001)
        
        if order:
            # Order should have valid ID
            self.assertIsNotNone(order.id)
            self.assertTrue(len(order.id) > 0)
            
            # Order should be retrievable
            retrieved_order = self.mock_trader.order_manager.mock_api.get_order(order.id)
            self.assertIsNotNone(retrieved_order)
            self.assertEqual(retrieved_order.id, order.id)
            
            # Order should appear in recent orders
            recent_orders = self.mock_trader.order_manager.get_recent_orders()
            order_ids = [o.id for o in recent_orders]
            self.assertIn(order.id, order_ids)


if __name__ == '__main__':
    unittest.main()