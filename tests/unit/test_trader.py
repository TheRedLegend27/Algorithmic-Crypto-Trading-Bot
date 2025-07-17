"""
Unit tests for the trader module.
Tests the Trader, PositionManager, and OrderManager classes.
"""
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

import pytest
from alpaca.trading.enums import OrderSide, OrderStatus
from alpaca.trading.models import Order, Position

from bot.trader import Trader, PositionManager, OrderManager, TradeResult
from bot.config import AlpacaCredentials, TradingSettings
from bot.strategy import TradingSignal, SignalType


class TestPositionManager:
    """Test cases for the PositionManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_client = MagicMock()
        self.position_manager = PositionManager(self.mock_trading_client)
        
        # Create mock positions
        mock_btc_position = MagicMock(spec=Position)
        mock_btc_position.symbol = "BTCUSD"
        mock_btc_position.qty = "0.5"
        mock_btc_position.market_value = "10000.0"
        mock_btc_position.unrealized_pl = "500.0"
        mock_btc_position.avg_entry_price = "19000.0"
        
        mock_eth_position = MagicMock(spec=Position)
        mock_eth_position.symbol = "ETHUSD"
        mock_eth_position.qty = "2.0"
        mock_eth_position.market_value = "4000.0"
        mock_eth_position.unrealized_pl = "200.0"
        mock_eth_position.avg_entry_price = "1800.0"
        
        # Set up mock return value for get_all_positions
        self.mock_trading_client.get_all_positions.return_value = [
            mock_btc_position, mock_eth_position
        ]
        
        # Force update positions
        self.position_manager._update_positions()
    
    def test_get_position(self):
        """Test getting a position by symbol."""
        # Test getting existing position
        position = self.position_manager.get_position("BTC/USD")
        assert position is not None
        assert position.symbol == "BTCUSD"
        assert position.qty == "0.5"
        
        # Test getting non-existent position
        position = self.position_manager.get_position("XRP/USD")
        assert position is None
    
    def test_get_position_quantity(self):
        """Test getting position quantity."""
        # Test existing position
        qty = self.position_manager.get_position_quantity("BTC/USD")
        assert qty == 0.5
        
        # Test non-existent position
        qty = self.position_manager.get_position_quantity("XRP/USD")
        assert qty == 0.0
    
    def test_get_position_value(self):
        """Test getting position market value."""
        # Test existing position
        value = self.position_manager.get_position_value("BTC/USD")
        assert value == 10000.0
        
        # Test non-existent position
        value = self.position_manager.get_position_value("XRP/USD")
        assert value == 0.0
    
    def test_get_unrealized_pnl(self):
        """Test getting unrealized profit/loss."""
        # Test existing position
        pnl = self.position_manager.get_unrealized_pnl("BTC/USD")
        assert pnl == 500.0
        
        # Test non-existent position
        pnl = self.position_manager.get_unrealized_pnl("XRP/USD")
        assert pnl == 0.0
        
    def test_get_average_entry_price(self):
        """Test getting average entry price."""
        # Test existing position
        avg_price = self.position_manager.get_average_entry_price("BTC/USD")
        assert avg_price == 19000.0
        
        # Test non-existent position
        avg_price = self.position_manager.get_average_entry_price("XRP/USD")
        assert avg_price == 0.0
    
    def test_get_position_summary(self):
        """Test getting position summary."""
        # Test existing position
        summary = self.position_manager.get_position_summary("BTC/USD")
        assert summary["symbol"] == "BTCUSD"
        assert summary["quantity"] == 0.5
        assert summary["market_value"] == 10000.0
        assert summary["unrealized_pnl"] == 500.0
        assert summary["avg_entry_price"] == 19000.0
        assert summary["has_position"] is True
        
        # Test non-existent position
        summary = self.position_manager.get_position_summary("XRP/USD")
        assert summary["symbol"] == "XRPUSD"
        assert summary["quantity"] == 0.0
        assert summary["has_position"] is False
    
    def test_track_position_change(self):
        """Test tracking position changes."""
        # Track a position change
        self.position_manager.track_position_change("BTC/USD", 20000.0)
        
        # Get position history
        history = self.position_manager.get_position_history("BTC/USD")
        
        # Verify history entry
        assert len(history) == 1
        assert history[0]["quantity"] == 0.5
        assert history[0]["market_value"] == 10000.0
        assert history[0]["unrealized_pnl"] == 500.0
        assert history[0]["avg_entry_price"] == 19000.0
        assert history[0]["current_price"] == 20000.0
        
        # Track another change
        self.position_manager.track_position_change("BTC/USD", 21000.0)
        
        # Verify history has two entries
        history = self.position_manager.get_position_history("BTC/USD")
        assert len(history) == 2
        assert history[1]["current_price"] == 21000.0
    
    def test_reconcile_positions(self):
        """Test position reconciliation."""
        # Test successful reconciliation
        result = self.position_manager.reconcile_positions()
        assert result is True
        
        # Test failed reconciliation
        self.mock_trading_client.get_all_positions.side_effect = Exception("API error")
        result = self.position_manager.reconcile_positions()
        assert result is False
        
    def test_verify_position_accuracy(self):
        """Test verifying position accuracy."""
        # Reset side effect from previous test
        self.mock_trading_client.get_all_positions.side_effect = None
        
        # Test accurate position
        is_accurate, actual_qty = self.position_manager.verify_position_accuracy("BTC/USD", 0.5)
        assert is_accurate is True
        assert actual_qty == 0.5
        
        # Test inaccurate position
        is_accurate, actual_qty = self.position_manager.verify_position_accuracy("BTC/USD", 0.6)
        assert is_accurate is False
        assert actual_qty == 0.5


class TestOrderManager:
    """Test cases for the OrderManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_trading_client = MagicMock()
        self.order_manager = OrderManager(self.mock_trading_client)
        
        # Create mock order
        self.mock_order = MagicMock(spec=Order)
        self.mock_order.id = "test-order-id"
        self.mock_order.status = OrderStatus.FILLED
        
        # Set up mock return values
        self.mock_trading_client.submit_order.return_value = self.mock_order
        self.mock_trading_client.get_order.return_value = self.mock_order
    
    def test_place_market_order(self):
        """Test placing a market order."""
        # Test successful order placement
        order = self.order_manager.place_market_order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            qty=0.1
        )
        assert order is not None
        assert order.id == "test-order-id"
        
        # Test order with invalid quantity
        order = self.order_manager.place_market_order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            qty=0.00001  # Too small
        )
        assert order is None
        
        # Test order with API error
        self.mock_trading_client.submit_order.side_effect = Exception("API error")
        order = self.order_manager.place_market_order(
            symbol="BTC/USD",
            side=OrderSide.BUY,
            qty=0.1
        )
        assert order is None
    
    def test_get_order_status(self):
        """Test getting order status."""
        # Test successful status retrieval
        status = self.order_manager.get_order_status("test-order-id")
        assert status == OrderStatus.FILLED
        
        # Test with API error
        self.mock_trading_client.get_order.side_effect = Exception("API error")
        status = self.order_manager.get_order_status("test-order-id")
        assert status is None
    
    def test_cancel_order(self):
        """Test cancelling an order."""
        # Test successful cancellation
        result = self.order_manager.cancel_order("test-order-id")
        assert result is True
        
        # Test with API error
        self.mock_trading_client.cancel_order.side_effect = Exception("API error")
        result = self.order_manager.cancel_order("test-order-id")
        assert result is False
    
    def test_get_recent_orders(self):
        """Test getting recent orders."""
        # Set up mock return value
        self.mock_trading_client.get_orders.return_value = [self.mock_order]
        
        # Test successful retrieval
        orders = self.order_manager.get_recent_orders(symbol="BTC/USD", limit=5)
        assert len(orders) == 1
        assert orders[0].id == "test-order-id"
        
        # Test with API error
        self.mock_trading_client.get_orders.side_effect = Exception("API error")
        orders = self.order_manager.get_recent_orders()
        assert len(orders) == 0


class TestTrader:
    """Test cases for the Trader class."""
    
    def setup_method(self):
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
            max_position_size=1000.0,
            stop_loss_pct=0.05,
            take_profit_pct=0.1,
            min_trade_interval=5
        )
        
        # Create mocks
        self.mock_trading_client = MagicMock()
        self.mock_position_manager = MagicMock()
        self.mock_order_manager = MagicMock()
        
        # Create mock order
        self.mock_order = MagicMock(spec=Order)
        self.mock_order.id = "test-order-id"
        self.mock_order.status = OrderStatus.FILLED
        
        # Set up mock return values
        self.mock_order_manager.place_market_order.return_value = self.mock_order
        
        # Create trader with mocks
        with patch('bot.trader.TradingClient', return_value=self.mock_trading_client):
            with patch('bot.trader.PositionManager', return_value=self.mock_position_manager):
                with patch('bot.trader.OrderManager', return_value=self.mock_order_manager):
                    self.trader = Trader(self.credentials, self.settings)
    
    def test_execute_trade_buy(self):
        """Test executing a buy trade."""
        # Create buy signal
        buy_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.8,
            strategy="Test Strategy",
            timestamp=datetime.now(),
            price=20000.0,
            reasoning="Test buy signal"
        )
        
        # Set up position manager mock
        self.mock_position_manager.get_position_value.return_value = 0.0
        
        # Execute trade
        result = self.trader.execute_trade(buy_signal)
        
        # Verify result
        assert result is not None
        assert result.side == "BUY"
        assert result.symbol == "BTC/USD"
        assert result.order_id == "test-order-id"
        
        # Verify order was placed
        self.mock_order_manager.place_market_order.assert_called_once()
    
    def test_execute_trade_sell(self):
        """Test executing a sell trade."""
        # Create sell signal
        sell_signal = TradingSignal(
            action=SignalType.SELL,
            confidence=0.8,
            strategy="Test Strategy",
            timestamp=datetime.now(),
            price=20000.0,
            reasoning="Test sell signal"
        )
        
        # Set up position manager mock
        self.mock_position_manager.get_position_quantity.return_value = 0.1
        
        # Execute trade
        result = self.trader.execute_trade(sell_signal)
        
        # Verify result
        assert result is not None
        assert result.side == "SELL"
        assert result.symbol == "BTC/USD"
        assert result.order_id == "test-order-id"
        
        # Verify order was placed
        self.mock_order_manager.place_market_order.assert_called_once()
    
    def test_execute_trade_hold(self):
        """Test executing a hold signal (no trade)."""
        # Create hold signal
        hold_signal = TradingSignal(
            action=SignalType.HOLD,
            confidence=0.0,
            strategy="Test Strategy",
            timestamp=datetime.now(),
            price=20000.0,
            reasoning="Test hold signal"
        )
        
        # Execute trade
        result = self.trader.execute_trade(hold_signal)
        
        # Verify no trade was executed
        assert result is None
        self.mock_order_manager.place_market_order.assert_not_called()
    
    def test_execute_trade_low_confidence(self):
        """Test executing a trade with low confidence (no trade)."""
        # Create low confidence buy signal
        low_confidence_signal = TradingSignal(
            action=SignalType.BUY,
            confidence=0.3,  # Below threshold
            strategy="Test Strategy",
            timestamp=datetime.now(),
            price=20000.0,
            reasoning="Test low confidence signal"
        )
        
        # Execute trade
        result = self.trader.execute_trade(low_confidence_signal)
        
        # Verify no trade was executed
        assert result is None
        self.mock_order_manager.place_market_order.assert_not_called()
    
    def test_calculate_buy_quantity(self):
        """Test calculation of buy quantity."""
        # Set up position manager mock
        self.mock_position_manager.get_position_value.return_value = 0.0
        
        # Test normal calculation
        qty = self.trader._calculate_buy_quantity("BTC/USD", 20000.0)
        assert qty == 0.005  # $100 / $20,000 = 0.005 BTC
        
        # Test with existing position near max size
        self.mock_position_manager.get_position_value.return_value = 950.0
        qty = self.trader._calculate_buy_quantity("BTC/USD", 20000.0)
        assert qty == 0.0025  # ($1000 - $950) / $20,000 = 0.0025 BTC
        
        # Test with position exceeding max size
        self.mock_position_manager.get_position_value.return_value = 1000.0
        qty = self.trader._calculate_buy_quantity("BTC/USD", 20000.0)
        assert qty == 0.0  # No more room to buy
    
    def test_validate_order(self):
        """Test order validation."""
        # Create valid order
        valid_order = MagicMock(spec=Order)
        valid_order.id = "valid-order"
        valid_order.status = OrderStatus.FILLED
        valid_order.qty = "0.1"
        
        # Create rejected order
        rejected_order = MagicMock(spec=Order)
        rejected_order.id = "rejected-order"
        rejected_order.status = OrderStatus.REJECTED
        rejected_order.qty = "0.1"
        
        # Create order with invalid quantity
        invalid_qty_order = MagicMock(spec=Order)
        invalid_qty_order.id = "invalid-qty-order"
        invalid_qty_order.status = OrderStatus.FILLED
        invalid_qty_order.qty = "0"
        
        # Test validation
        assert self.trader.validate_order(valid_order) is True
        assert self.trader.validate_order(rejected_order) is False
        assert self.trader.validate_order(invalid_qty_order) is False
        assert self.trader.validate_order(None) is False


class TestRiskManagement:
    """Test cases for risk management functionality."""
    
    def setup_method(self):
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
            max_position_size=1000.0,
            stop_loss_pct=0.05,  # 5% stop loss
            take_profit_pct=0.1,  # 10% take profit
            min_trade_interval=5
        )
        
        # Create mocks
        self.mock_trading_client = MagicMock()
        self.mock_position_manager = MagicMock()
        self.mock_order_manager = MagicMock()
        
        # Create mock order
        self.mock_order = MagicMock(spec=Order)
        self.mock_order.id = "test-order-id"
        self.mock_order.status = OrderStatus.FILLED
        
        # Set up mock return values
        self.mock_order_manager.place_market_order.return_value = self.mock_order
        
        # Create trader with mocks
        with patch('bot.trader.TradingClient', return_value=self.mock_trading_client):
            with patch('bot.trader.PositionManager', return_value=self.mock_position_manager):
                with patch('bot.trader.OrderManager', return_value=self.mock_order_manager):
                    self.trader = Trader(self.credentials, self.settings)
    
    def test_check_risk_management_triggers_stop_loss(self):
        """Test stop loss trigger."""
        # Create mock position
        mock_position = MagicMock()
        mock_position.qty = "0.1"
        mock_position.avg_entry_price = "20000.0"
        
        # Set up position manager mock
        self.mock_position_manager.get_position.return_value = mock_position
        
        # Test stop loss trigger (6% loss)
        current_price = 18800.0  # 6% below entry price
        result = self.trader.check_risk_management_triggers("BTC/USD", current_price)
        
        # Verify result
        assert result is True
        self.mock_order_manager.place_market_order.assert_called_once_with(
            symbol="BTC/USD",
            side=OrderSide.SELL,
            qty=0.1
        )
        
        # Verify position tracking was called
        self.mock_position_manager.track_position_change.assert_called_once_with(
            "BTC/USD", current_price
        )
    
    def test_check_risk_management_triggers_take_profit(self):
        """Test take profit trigger."""
        # Create mock position
        mock_position = MagicMock()
        mock_position.qty = "0.1"
        mock_position.avg_entry_price = "20000.0"
        
        # Set up position manager mock
        self.mock_position_manager.get_position.return_value = mock_position
        
        # Test take profit trigger (12% gain)
        current_price = 22400.0  # 12% above entry price
        result = self.trader.check_risk_management_triggers("BTC/USD", current_price)
        
        # Verify result
        assert result is True
        self.mock_order_manager.place_market_order.assert_called_once_with(
            symbol="BTC/USD",
            side=OrderSide.SELL,
            qty=0.1
        )
        
        # Verify position tracking was called
        self.mock_position_manager.track_position_change.assert_called_once_with(
            "BTC/USD", current_price
        )
    
    def test_check_risk_management_triggers_no_action(self):
        """Test no risk management action needed."""
        # Create mock position
        mock_position = MagicMock()
        mock_position.qty = "0.1"
        mock_position.avg_entry_price = "20000.0"
        
        # Set up position manager mock
        self.mock_position_manager.get_position.return_value = mock_position
        
        # Test price within thresholds (2% gain)
        current_price = 20400.0  # 2% above entry price
        result = self.trader.check_risk_management_triggers("BTC/USD", current_price)
        
        # Verify result
        assert result is False
        self.mock_order_manager.place_market_order.assert_not_called()
        
        # Verify position tracking was still called
        self.mock_position_manager.track_position_change.assert_called_once_with(
            "BTC/USD", current_price
        )
    
    def test_check_risk_management_triggers_no_position(self):
        """Test risk management with no position."""
        # Set up position manager mock to return None
        self.mock_position_manager.get_position.return_value = None
        
        # Test with any price
        result = self.trader.check_risk_management_triggers("BTC/USD", 20000.0)
        
        # Verify result
        assert result is False
        self.mock_order_manager.place_market_order.assert_not_called()
        
        # Verify position tracking was not called (no position)
        self.mock_position_manager.track_position_change.assert_not_called()
    
    def test_setup_risk_management(self):
        """Test setting up risk management for a position."""
        # Set up position manager mock
        self.mock_position_manager.get_position_quantity.return_value = 0.1
        
        # Test setting up risk management for a long position
        entry_price = 20000.0
        self.trader._setup_risk_management("BTC/USD", entry_price, OrderSide.BUY)
        
        # Verify position tracking was called
        self.mock_position_manager.track_position_change.assert_called_once_with(
            "BTC/USD", entry_price
        )
    
    def test_setup_risk_management_no_position(self):
        """Test setting up risk management with no position."""
        # Set up position manager mock to return 0 quantity
        self.mock_position_manager.get_position_quantity.return_value = 0.0
        
        # Test setting up risk management
        self.trader._setup_risk_management("BTC/USD", 20000.0, OrderSide.BUY)
        
        # Verify position tracking was not called (no position)
        self.mock_position_manager.track_position_change.assert_not_called()
    
    def test_get_risk_metrics(self):
        """Test getting risk metrics for a position."""
        # Create mock position summary
        mock_summary = {
            "has_position": True,
            "symbol": "BTCUSD",
            "quantity": 0.1,
            "market_value": 21000.0,
            "unrealized_pnl": 1000.0,
            "avg_entry_price": 20000.0,
            "pnl_percentage": 5.0
        }
        
        # Set up position manager mock
        self.mock_position_manager.get_position_summary.return_value = mock_summary
        
        # Get risk metrics
        metrics = self.trader.get_risk_metrics("BTC/USD")
        
        # Verify metrics
        assert metrics["has_position"] is True
        assert metrics["symbol"] == "BTCUSD"
        assert metrics["avg_entry_price"] == 20000.0
        assert metrics["stop_loss_level"] == 19000.0  # 5% below entry
        assert metrics["take_profit_level"] == 22000.0  # 10% above entry
        assert metrics["stop_loss_pct"] == 5.0
        assert metrics["take_profit_pct"] == 10.0
        assert metrics["risk_reward_ratio"] == 2.0  # $2000 gain / $1000 loss
        
    def test_get_risk_metrics_no_position(self):
        """Test getting risk metrics with no position."""
        # Create mock position summary with no position
        mock_summary = {
            "has_position": False,
            "symbol": "BTCUSD",
            "quantity": 0.0,
            "market_value": 0.0,
            "unrealized_pnl": 0.0,
            "avg_entry_price": 0.0,
            "pnl_percentage": 0.0
        }
        
        # Set up position manager mock
        self.mock_position_manager.get_position_summary.return_value = mock_summary
        
        # Get risk metrics
        metrics = self.trader.get_risk_metrics("BTC/USD")
        
        # Verify metrics
        assert metrics["has_position"] is False
        assert metrics["symbol"] == "BTCUSD"
        assert metrics["stop_loss_level"] == 0.0
        assert metrics["take_profit_level"] == 0.0
        assert metrics["risk_reward_ratio"] == 0.0


if __name__ == "__main__":
    pytest.main(["-xvs", "test_trader.py"])