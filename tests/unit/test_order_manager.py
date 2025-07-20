"""
Unit tests for the order management and validation system.
Tests order validation, order book functionality, and order lifecycle management.
"""
import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from mock_trading.order_manager import (
    OrderManager, OrderValidator, OrderBook, Portfolio,
    OrderRejectionReason, ValidationError
)
from mock_trading.mock_models import (
    Order, OrderResult, OrderType, OrderSide, OrderStatus, TimeInForce,
    MockPosition, ExecutionResult
)
from mock_trading.mock_config import MockTradingConfig


class TestOrderValidator:
    """Test cases for OrderValidator class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = MockTradingConfig(
            starting_capital=15000.0,
            max_position_size=8000.0,
            max_daily_loss=1000.0
        )
        # Disable market hours enforcement for tests
        config.market.market_hours_enforcement = False
        return config
    
    @pytest.fixture
    def validator(self, config):
        """Create OrderValidator instance."""
        return OrderValidator(config)
    
    @pytest.fixture
    def portfolio(self):
        """Create test portfolio."""
        positions = {
            "BTCUSD": MockPosition(
                symbol="BTCUSD",
                quantity=0.1,
                market_value=5000.0,
                avg_entry_price=50000.0
            )
        }
        return Portfolio(
            cash_balance=8000.0,
            positions=positions,
            total_value=13000.0
        )
    
    @pytest.fixture
    def current_prices(self):
        """Create test current prices."""
        return {
            "BTCUSD": 50000.0,
            "ETHUSD": 3000.0
        }
    
    def test_validate_valid_buy_order(self, validator, portfolio, current_prices):
        """Test validation of a valid buy order."""
        order = Order(
            symbol="ETHUSD",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert is_valid
        assert error_msg is None
        assert rejection_reason is None
    
    def test_validate_valid_sell_order(self, validator, portfolio, current_prices):
        """Test validation of a valid sell order."""
        order = Order(
            symbol="BTCUSD",
            quantity=0.05,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert is_valid
        assert error_msg is None
        assert rejection_reason is None
    
    def test_validate_insufficient_funds(self, validator, portfolio, current_prices):
        """Test validation with insufficient funds."""
        order = Order(
            symbol="BTCUSD",
            quantity=1.0,  # Would cost ~$50,000, but only have $5,000 cash
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert not is_valid
        assert "Insufficient funds" in error_msg
        assert rejection_reason == OrderRejectionReason.INSUFFICIENT_FUNDS
    
    def test_validate_insufficient_position(self, validator, portfolio, current_prices):
        """Test validation with insufficient position to sell."""
        order = Order(
            symbol="BTCUSD",
            quantity=1.0,  # Trying to sell 1.0, but only have 0.1
            side=OrderSide.SELL,
            order_type=OrderType.MARKET
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert not is_valid
        assert "Insufficient position" in error_msg
        assert rejection_reason == OrderRejectionReason.INSUFFICIENT_FUNDS
    
    def test_validate_invalid_quantity(self, validator, portfolio, current_prices):
        """Test validation with invalid quantity."""
        order = Order(
            symbol="BTCUSD",
            quantity=0.0,  # Invalid quantity
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert not is_valid
        assert "Invalid quantity" in error_msg
        assert rejection_reason == OrderRejectionReason.SYSTEM_ERROR  # Basic validation error
    
    def test_validate_invalid_symbol(self, validator, portfolio, current_prices):
        """Test validation with invalid symbol."""
        order = Order(
            symbol="INVALID",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert not is_valid
        assert "No current price available" in error_msg
        assert rejection_reason == OrderRejectionReason.SYSTEM_ERROR
    
    def test_validate_limit_order_without_price(self, validator, portfolio, current_prices):
        """Test validation of limit order without price."""
        order = Order(
            symbol="BTCUSD",
            quantity=0.01,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=None
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert not is_valid
        assert "Invalid price for LIMIT order" in error_msg
        assert rejection_reason == OrderRejectionReason.SYSTEM_ERROR  # Basic validation error
    
    def test_validate_position_limit_exceeded(self, validator, portfolio, current_prices):
        """Test validation when position limit would be exceeded."""
        # Create large buy order that would exceed position limit
        order = Order(
            symbol="BTCUSD",
            quantity=0.1,  # Would add $5,000 to existing $5,000 position = $10,000 > $8,000 limit
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        is_valid, error_msg, rejection_reason = validator.validate_order(
            order, portfolio, current_prices
        )
        
        assert not is_valid
        assert "Position limit exceeded" in error_msg
        assert rejection_reason == OrderRejectionReason.POSITION_LIMIT_EXCEEDED
    
    def test_validate_market_hours_enforcement(self, validator, portfolio, current_prices):
        """Test market hours enforcement."""
        # Enable market hours enforcement
        validator.config.market.market_hours_enforcement = True
        validator.config.market.extended_hours_trading = False
        
        order = Order(
            symbol="BTCUSD",
            quantity=0.01,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        # Mock current time to be outside market hours
        with patch('mock_trading.order_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 8, 0)  # 8 AM (before market open)
            
            is_valid, error_msg, rejection_reason = validator.validate_order(
                order, portfolio, current_prices
            )
            
            assert not is_valid
            assert "Market is closed" in error_msg
            assert rejection_reason == OrderRejectionReason.MARKET_CLOSED


class TestOrderBook:
    """Test cases for OrderBook class."""
    
    @pytest.fixture
    def order_book(self):
        """Create OrderBook instance."""
        return OrderBook()
    
    @pytest.fixture
    def sample_order(self):
        """Create sample order."""
        return Order(
            symbol="BTCUSD",
            quantity=0.1,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
    
    def test_add_order(self, order_book, sample_order):
        """Test adding an order to the order book."""
        result = order_book.add_order(sample_order)
        
        assert result is True
        assert sample_order.id in order_book.pending_orders
        assert order_book.get_order_count() == 1
    
    def test_add_duplicate_order(self, order_book, sample_order):
        """Test adding duplicate order."""
        order_book.add_order(sample_order)
        result = order_book.add_order(sample_order)
        
        assert result is False
        assert order_book.get_order_count() == 1
    
    def test_remove_order(self, order_book, sample_order):
        """Test removing an order from the order book."""
        order_book.add_order(sample_order)
        removed_order = order_book.remove_order(sample_order.id)
        
        assert removed_order == sample_order
        assert sample_order.id not in order_book.pending_orders
        assert order_book.get_order_count() == 0
        assert len(order_book.order_history) == 1
    
    def test_get_pending_orders(self, order_book):
        """Test getting pending orders."""
        order1 = Order(symbol="BTCUSD", quantity=0.1, side=OrderSide.BUY, order_type=OrderType.MARKET)
        order2 = Order(symbol="ETHUSD", quantity=1.0, side=OrderSide.BUY, order_type=OrderType.MARKET)
        
        order_book.add_order(order1)
        order_book.add_order(order2)
        
        all_orders = order_book.get_pending_orders()
        btc_orders = order_book.get_pending_orders("BTCUSD")
        
        assert len(all_orders) == 2
        assert len(btc_orders) == 1
        assert btc_orders[0].symbol == "BTCUSD"
    
    def test_market_order_execution_queue(self, order_book):
        """Test that market orders are added to execution queue."""
        market_order = Order(
            symbol="BTCUSD",
            quantity=0.1,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        limit_order = Order(
            symbol="BTCUSD",
            quantity=0.1,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=50000.0
        )
        
        order_book.add_order(market_order)
        order_book.add_order(limit_order)
        
        execution_queue = order_book.get_orders_for_execution()
        
        assert market_order.id in execution_queue
        assert limit_order.id not in execution_queue
    
    def test_mark_order_for_execution(self, order_book):
        """Test marking an order for execution."""
        limit_order = Order(
            symbol="BTCUSD",
            quantity=0.1,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=50000.0
        )
        
        order_book.add_order(limit_order)
        order_book.mark_order_for_execution(limit_order.id)
        
        execution_queue = order_book.get_orders_for_execution()
        assert limit_order.id in execution_queue
    
    def test_cleanup_expired_orders(self, order_book):
        """Test cleanup of expired orders."""
        # Create DAY order
        day_order = Order(
            symbol="BTCUSD",
            quantity=0.1,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=50000.0,
            time_in_force=TimeInForce.DAY
        )
        
        order_book.add_order(day_order)
        
        # Mock current time to be after market close
        with patch('mock_trading.order_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 1, 1, 17, 0)  # 5 PM
            
            expired_orders = order_book.cleanup_expired_orders()
            
            assert len(expired_orders) == 1
            assert expired_orders[0].status == OrderStatus.EXPIRED
            assert order_book.get_order_count() == 0
    
    def test_get_orders_by_symbol(self, order_book):
        """Test getting orders by symbol."""
        btc_order = Order(symbol="BTCUSD", quantity=0.1, side=OrderSide.BUY, order_type=OrderType.MARKET)
        eth_order = Order(symbol="ETHUSD", quantity=1.0, side=OrderSide.BUY, order_type=OrderType.MARKET)
        
        order_book.add_order(btc_order)
        order_book.add_order(eth_order)
        
        btc_orders = order_book.get_orders_by_symbol("BTCUSD")
        
        assert len(btc_orders) == 1
        assert btc_orders[0].symbol == "BTCUSD"
    
    def test_get_orders_by_side(self, order_book):
        """Test getting orders by side."""
        buy_order = Order(symbol="BTCUSD", quantity=0.1, side=OrderSide.BUY, order_type=OrderType.MARKET)
        sell_order = Order(symbol="BTCUSD", quantity=0.1, side=OrderSide.SELL, order_type=OrderType.MARKET)
        
        order_book.add_order(buy_order)
        order_book.add_order(sell_order)
        
        buy_orders = order_book.get_orders_by_side(OrderSide.BUY)
        
        assert len(buy_orders) == 1
        assert buy_orders[0].side == OrderSide.BUY


class TestOrderManager:
    """Test cases for OrderManager class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = MockTradingConfig(
            starting_capital=15000.0,
            max_position_size=8000.0,
            max_daily_loss=1000.0
        )
        # Disable market hours enforcement for tests
        config.market.market_hours_enforcement = False
        return config
    
    @pytest.fixture
    def order_manager(self, config):
        """Create OrderManager instance."""
        return OrderManager(config)
    
    @pytest.fixture
    def portfolio(self):
        """Create test portfolio."""
        positions = {
            "BTCUSD": MockPosition(
                symbol="BTCUSD",
                quantity=0.1,
                market_value=5000.0,
                avg_entry_price=50000.0
            )
        }
        return Portfolio(
            cash_balance=8000.0,
            positions=positions,
            total_value=13000.0
        )
    
    @pytest.fixture
    def current_prices(self):
        """Create test current prices."""
        return {
            "BTCUSD": 50000.0,
            "ETHUSD": 3000.0
        }
    
    def test_submit_valid_order(self, order_manager, portfolio, current_prices):
        """Test submitting a valid order."""
        order = Order(
            symbol="ETHUSD",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        result = order_manager.submit_order(order, portfolio, current_prices)
        
        assert result.success
        assert result.error_message is None
        assert order.status == OrderStatus.ACCEPTED
        assert order_manager.order_stats["total_submitted"] == 1
        assert order_manager.order_book.get_order_count() == 1
    
    def test_submit_invalid_order(self, order_manager, portfolio, current_prices):
        """Test submitting an invalid order."""
        order = Order(
            symbol="BTCUSD",
            quantity=10.0,  # Too large, would exceed funds
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        result = order_manager.submit_order(order, portfolio, current_prices)
        
        assert not result.success
        assert result.error_message is not None
        assert "Insufficient funds" in result.error_message
        assert order.status == OrderStatus.REJECTED
        assert order_manager.order_stats["total_rejected"] == 1
        assert order_manager.order_book.get_order_count() == 0
    
    def test_cancel_order(self, order_manager, portfolio, current_prices):
        """Test cancelling an order."""
        order = Order(
            symbol="ETHUSD",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=2900.0
        )
        
        # Submit order
        result = order_manager.submit_order(order, portfolio, current_prices)
        assert result.success
        
        # Cancel order
        cancel_result = order_manager.cancel_order(order.id)
        
        assert cancel_result
        assert order.status == OrderStatus.CANCELED
        assert order_manager.order_stats["total_cancelled"] == 1
        assert order_manager.order_book.get_order_count() == 0
    
    def test_cancel_nonexistent_order(self, order_manager):
        """Test cancelling a non-existent order."""
        fake_order_id = str(uuid.uuid4())
        result = order_manager.cancel_order(fake_order_id)
        
        assert not result
    
    def test_modify_order(self, order_manager, portfolio, current_prices):
        """Test modifying an order."""
        order = Order(
            symbol="ETHUSD",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=2900.0
        )
        
        # Submit order
        result = order_manager.submit_order(order, portfolio, current_prices)
        assert result.success
        
        # Modify order
        modify_result = order_manager.modify_order(
            order.id,
            new_quantity=0.5,
            new_price=2800.0
        )
        
        assert modify_result
        assert order.quantity == 0.5
        assert order.price == 2800.0
    
    def test_process_market_update(self, order_manager, portfolio, current_prices):
        """Test processing market data updates."""
        # Submit limit buy order below current price
        order = Order(
            symbol="BTCUSD",
            quantity=0.01,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=49000.0
        )
        
        order_manager.submit_order(order, portfolio, current_prices)
        
        # Process market update with price drop
        price_data = {
            "last": 48500.0,
            "bid": 48400.0,
            "ask": 48600.0
        }
        
        order_manager.process_market_update("BTCUSD", price_data)
        
        # Order should be marked for execution
        execution_queue = order_manager.order_book.get_orders_for_execution()
        assert order.id in execution_queue
    
    def test_execute_pending_orders(self, order_manager, portfolio, current_prices):
        """Test getting orders ready for execution."""
        # Submit market order
        market_order = Order(
            symbol="BTCUSD",
            quantity=0.01,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        order_manager.submit_order(market_order, portfolio, current_prices)
        
        # Get pending orders for execution
        executable_orders = order_manager.execute_pending_orders(current_prices)
        
        assert market_order.id in executable_orders
    
    def test_record_execution(self, order_manager, portfolio, current_prices):
        """Test recording order execution."""
        order = Order(
            symbol="BTCUSD",
            quantity=0.01,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        order_manager.submit_order(order, portfolio, current_prices)
        
        # Create execution result
        execution_result = ExecutionResult(
            order_id=order.id,
            executed_quantity=0.01,
            execution_price=50000.0,
            slippage=0.0001,
            fees=0.5,
            execution_time=datetime.now()
        )
        
        # Record execution
        order_manager.record_execution(order.id, execution_result)
        
        assert order_manager.order_stats["total_executed"] == 1
        assert order.filled_quantity == 0.01
        assert order.status == OrderStatus.FILLED
        assert order_manager.order_book.get_order_count() == 0  # Fully filled order removed
    
    def test_execution_callback(self, order_manager, portfolio, current_prices):
        """Test execution callback functionality."""
        callback_called = False
        callback_order = None
        callback_result = None
        
        def test_callback(order, execution_result):
            nonlocal callback_called, callback_order, callback_result
            callback_called = True
            callback_order = order
            callback_result = execution_result
        
        order_manager.add_execution_callback(test_callback)
        
        order = Order(
            symbol="BTCUSD",
            quantity=0.01,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        order_manager.submit_order(order, portfolio, current_prices)
        
        execution_result = ExecutionResult(
            order_id=order.id,
            executed_quantity=0.01,
            execution_price=50000.0,
            slippage=0.0001,
            fees=0.5,
            execution_time=datetime.now()
        )
        
        order_manager.record_execution(order.id, execution_result)
        
        assert callback_called
        assert callback_order == order
        assert callback_result == execution_result
    
    def test_get_order_statistics(self, order_manager, portfolio, current_prices):
        """Test getting order statistics."""
        # Submit some orders
        order1 = Order(symbol="BTCUSD", quantity=0.01, side=OrderSide.BUY, order_type=OrderType.MARKET)
        order2 = Order(symbol="BTCUSD", quantity=10.0, side=OrderSide.BUY, order_type=OrderType.MARKET)  # Will be rejected
        
        order_manager.submit_order(order1, portfolio, current_prices)
        order_manager.submit_order(order2, portfolio, current_prices)
        
        stats = order_manager.get_order_statistics()
        
        assert stats["total_submitted"] == 2
        assert stats["total_rejected"] == 1
        assert stats["pending_orders"] == 1
    
    def test_duplicate_order_submission(self, order_manager, portfolio, current_prices):
        """Test submitting duplicate orders."""
        order = Order(
            id="test-order-123",
            symbol="BTCUSD",
            quantity=0.01,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
        
        # Submit first time
        result1 = order_manager.submit_order(order, portfolio, current_prices)
        assert result1.success
        
        # Submit same order again
        result2 = order_manager.submit_order(order, portfolio, current_prices)
        assert not result2.success
        assert result2.rejection_reason == OrderRejectionReason.DUPLICATE_ORDER.value


class TestPortfolio:
    """Test cases for Portfolio class."""
    
    def test_get_position_value(self):
        """Test getting position value."""
        position = MockPosition(
            symbol="BTCUSD",
            quantity=0.1,
            market_value=5000.0
        )
        
        portfolio = Portfolio(
            cash_balance=5000.0,
            positions={"BTCUSD": position},
            total_value=10000.0
        )
        
        assert portfolio.get_position_value("BTCUSD") == 5000.0
        assert portfolio.get_position_value("ETHUSD") == 0.0
    
    def test_get_available_cash(self):
        """Test getting available cash."""
        portfolio = Portfolio(
            cash_balance=5000.0,
            positions={},
            total_value=5000.0
        )
        
        assert portfolio.get_available_cash() == 5000.0
        
        # Test negative cash balance
        portfolio.cash_balance = -1000.0
        assert portfolio.get_available_cash() == 0.0


if __name__ == "__main__":
    pytest.main([__file__])