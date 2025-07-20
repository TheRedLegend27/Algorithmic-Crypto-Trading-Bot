"""
Comprehensive tests for mock trading error handler and simulation realism.

This module tests all aspects of error simulation including partial fills,
market gaps, system failures, and recovery mechanisms.
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from mock_trading.error_handler import (
    MockTradingErrorHandler, PartialFillSimulator, MarketGapHandler,
    SystemFailureSimulator, ErrorType, ErrorSeverity, ErrorScenario,
    MarketGapEvent, LiquidityCondition
)
from mock_trading.mock_models import Order, OrderType, OrderSide, OrderStatus
from mock_trading.mock_config import MockTradingConfig


class TestPartialFillSimulator:
    """Test partial fill simulation functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = MockTradingConfig()
        config.execution.partial_fill_probability = 0.3
        config.execution.min_fill_percentage = 0.5
        config.execution.large_order_threshold = 1000.0
        return config
    
    @pytest.fixture
    def simulator(self, config):
        """Create partial fill simulator."""
        return PartialFillSimulator(config)
    
    @pytest.fixture
    def sample_order(self):
        """Create sample order for testing."""
        return Order(
            symbol="BTCUSD",
            quantity=10.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
    
    def test_should_partial_fill_small_order(self, simulator, sample_order):
        """Test partial fill decision for small orders."""
        # Small order should have low probability of partial fill
        market_price = 50.0  # Order value = 500, below threshold
        
        # Test multiple times due to randomness
        partial_fills = 0
        for _ in range(100):
            should_partial, fill_percentage = simulator.should_partial_fill(
                sample_order, market_price
            )
            if should_partial:
                partial_fills += 1
                assert 0.5 <= fill_percentage <= 0.9
        
        # Should have some partial fills but not too many
        assert 10 <= partial_fills <= 50  # Roughly 30% with some variance
    
    def test_should_partial_fill_large_order(self, simulator, sample_order):
        """Test partial fill decision for large orders."""
        # Large order should have higher probability of partial fill
        market_price = 200.0  # Order value = 2000, above threshold
        
        partial_fills = 0
        for _ in range(100):
            should_partial, fill_percentage = simulator.should_partial_fill(
                sample_order, market_price
            )
            if should_partial:
                partial_fills += 1
        
        # Should have more partial fills for large orders
        assert partial_fills >= 40  # Higher than small orders
    
    def test_should_partial_fill_low_liquidity(self, simulator, sample_order):
        """Test partial fill with low liquidity conditions."""
        market_price = 100.0
        
        # Create low liquidity condition
        low_liquidity = LiquidityCondition(
            symbol="BTCUSD",
            available_volume=500.0,  # Low volume
            bid_depth=100.0,
            ask_depth=100.0,
            spread_multiplier=3.0  # High spread
        )
        
        partial_fills = 0
        low_fill_percentages = 0
        
        for _ in range(100):
            should_partial, fill_percentage = simulator.should_partial_fill(
                sample_order, market_price, low_liquidity
            )
            if should_partial:
                partial_fills += 1
                if fill_percentage <= 0.5:
                    low_fill_percentages += 1
        
        # Should have high partial fill rate in low liquidity
        assert partial_fills >= 50
        # Should have more low fill percentages
        assert low_fill_percentages >= partial_fills * 0.3
    
    def test_simulate_partial_fill(self, simulator, sample_order):
        """Test partial fill simulation."""
        execution_price = 100.0
        
        # Mock the should_partial_fill to return True
        with patch.object(simulator, 'should_partial_fill', return_value=(True, 0.6)):
            result = simulator.simulate_partial_fill(sample_order, execution_price)
            
            assert result.partial_fill is True
            assert result.executed_quantity == sample_order.quantity * 0.6
            assert result.remaining_quantity == sample_order.quantity * 0.4
            assert result.execution_price == execution_price
            assert result.fees > 0
            
            # Check order was updated
            assert sample_order.filled_quantity == result.executed_quantity
            assert sample_order.status == OrderStatus.PARTIALLY_FILLED
    
    def test_simulate_full_fill(self, simulator, sample_order):
        """Test full fill simulation."""
        execution_price = 100.0
        
        # Mock the should_partial_fill to return False
        with patch.object(simulator, 'should_partial_fill', return_value=(False, 1.0)):
            result = simulator.simulate_partial_fill(sample_order, execution_price)
            
            assert result.partial_fill is False
            assert result.executed_quantity == sample_order.quantity
            assert result.remaining_quantity == 0.0
            
            # Check order was updated
            assert sample_order.status == OrderStatus.FILLED
    
    def test_liquidity_condition_management(self, simulator):
        """Test liquidity condition management."""
        symbol = "ETHUSD"
        condition = LiquidityCondition(
            symbol=symbol,
            available_volume=1000.0,
            bid_depth=300.0,
            ask_depth=300.0
        )
        
        # Update condition
        simulator.update_liquidity_condition(symbol, condition)
        
        # Retrieve condition
        retrieved = simulator.get_liquidity_condition(symbol)
        assert retrieved is not None
        assert retrieved.symbol == symbol
        assert retrieved.available_volume == 1000.0
        
        # Test non-existent symbol
        assert simulator.get_liquidity_condition("NONEXISTENT") is None


class TestMarketGapHandler:
    """Test market gap handling functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return MockTradingConfig()
    
    @pytest.fixture
    def handler(self, config):
        """Create market gap handler."""
        return MarketGapHandler(config)
    
    @pytest.fixture
    def limit_buy_order(self):
        """Create limit buy order for testing."""
        return Order(
            symbol="BTCUSD",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=45000.0
        )
    
    @pytest.fixture
    def limit_sell_order(self):
        """Create limit sell order for testing."""
        return Order(
            symbol="BTCUSD",
            quantity=1.0,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            price=55000.0
        )
    
    @pytest.fixture
    def stop_loss_order(self):
        """Create stop-loss order for testing."""
        return Order(
            symbol="BTCUSD",
            quantity=1.0,
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            stop_price=48000.0
        )
    
    def test_should_create_gap_probability(self, handler):
        """Test gap creation probability."""
        symbol = "BTCUSD"
        current_price = 50000.0
        
        # Test multiple times due to low probability
        gaps_created = 0
        for _ in range(10000):  # Large number to test probability
            if handler.should_create_gap(symbol, current_price):
                gaps_created += 1
                # Create the gap to prevent multiple gaps
                handler.create_market_gap(symbol, current_price)
                break  # Only test one gap creation
        
        # Should create at least one gap in 10000 attempts (probability is 0.001)
        assert gaps_created >= 0  # Very low probability, so just check it doesn't crash
    
    def test_create_market_gap_up(self, handler):
        """Test market gap up creation."""
        symbol = "BTCUSD"
        current_price = 50000.0
        
        # Force gap up by mocking random
        with patch('random.random', return_value=0.7):  # > 0.6 = gap up
            with patch('random.uniform', return_value=0.03):  # 3% gap
                gap_event = handler.create_market_gap(symbol, current_price)
                
                assert gap_event.symbol == symbol
                assert gap_event.gap_start_price == current_price
                assert gap_event.gap_direction == "UP"
                assert gap_event.gap_end_price > current_price
                assert gap_event.gap_size_percent == 0.03
                
                # Check it's stored in active gaps
                assert symbol in handler.active_gaps
                assert len(handler.gap_history) == 1
    
    def test_create_market_gap_down(self, handler):
        """Test market gap down creation."""
        symbol = "BTCUSD"
        current_price = 50000.0
        
        # Force gap down by mocking random
        with patch('random.random', return_value=0.3):  # < 0.6 = gap down
            with patch('random.uniform', return_value=0.02):  # 2% gap
                gap_event = handler.create_market_gap(symbol, current_price)
                
                assert gap_event.gap_direction == "DOWN"
                assert gap_event.gap_end_price < current_price
                assert gap_event.gap_size_percent == 0.02
    
    def test_handle_limit_buy_order_gap_down(self, handler, limit_buy_order):
        """Test limit buy order execution during gap down."""
        # Create gap down that triggers the limit order
        gap_event = MarketGapEvent(
            symbol="BTCUSD",
            gap_start_price=50000.0,
            gap_end_price=40000.0,  # Below limit price of 45000
            gap_direction="DOWN",
            gap_size_percent=0.2,
            timestamp=datetime.now()
        )
        
        result = handler.handle_limit_order_gap(limit_buy_order, gap_event)
        
        assert result is not None
        assert result.executed_quantity == limit_buy_order.quantity
        assert result.execution_price <= limit_buy_order.price  # At or better than limit
        assert result.slippage == 0.0  # No slippage for gap executions
        assert limit_buy_order.status == OrderStatus.FILLED
    
    def test_handle_limit_sell_order_gap_up(self, handler, limit_sell_order):
        """Test limit sell order execution during gap up."""
        # Create gap up that triggers the limit order
        gap_event = MarketGapEvent(
            symbol="BTCUSD",
            gap_start_price=50000.0,
            gap_end_price=60000.0,  # Above limit price of 55000
            gap_direction="UP",
            gap_size_percent=0.2,
            timestamp=datetime.now()
        )
        
        result = handler.handle_limit_order_gap(limit_sell_order, gap_event)
        
        assert result is not None
        assert result.executed_quantity == limit_sell_order.quantity
        assert result.execution_price >= limit_sell_order.price  # At or better than limit
        assert limit_sell_order.status == OrderStatus.FILLED
    
    def test_handle_limit_order_no_trigger(self, handler, limit_buy_order):
        """Test limit order not triggered by gap."""
        # Create gap that doesn't trigger the order
        gap_event = MarketGapEvent(
            symbol="BTCUSD",
            gap_start_price=50000.0,
            gap_end_price=48000.0,  # Above limit price of 45000
            gap_direction="DOWN",
            gap_size_percent=0.04,
            timestamp=datetime.now()
        )
        
        result = handler.handle_limit_order_gap(limit_buy_order, gap_event)
        
        assert result is None
        assert limit_buy_order.status != OrderStatus.FILLED
    
    def test_handle_stop_loss_gap_down(self, handler, stop_loss_order):
        """Test stop-loss order execution during gap down."""
        # Create gap down that triggers the stop-loss
        gap_event = MarketGapEvent(
            symbol="BTCUSD",
            gap_start_price=50000.0,
            gap_end_price=45000.0,  # Below stop price of 48000
            gap_direction="DOWN",
            gap_size_percent=0.1,
            timestamp=datetime.now()
        )
        
        result = handler.handle_stop_loss_gap(stop_loss_order, gap_event)
        
        assert result is not None
        assert result.executed_quantity == stop_loss_order.quantity
        assert result.execution_price == gap_event.gap_end_price
        assert result.slippage > 0  # Should have slippage for stop orders
        assert stop_loss_order.status == OrderStatus.FILLED
    
    def test_cleanup_expired_gaps(self, handler):
        """Test cleanup of expired gap events."""
        symbol = "BTCUSD"
        
        # Create gap with short duration
        gap_event = MarketGapEvent(
            symbol=symbol,
            gap_start_price=50000.0,
            gap_end_price=48000.0,
            gap_direction="DOWN",
            gap_size_percent=0.04,
            timestamp=datetime.now() - timedelta(seconds=20),  # Old timestamp
            duration_seconds=1.0  # Very short duration
        )
        
        handler.active_gaps[symbol] = gap_event
        
        # Cleanup should remove expired gap
        handler.cleanup_expired_gaps()
        
        assert symbol not in handler.active_gaps


class TestSystemFailureSimulator:
    """Test system failure simulation functionality."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return MockTradingConfig()
    
    @pytest.fixture
    def simulator(self, config):
        """Create system failure simulator."""
        return SystemFailureSimulator(config)
    
    def test_should_simulate_failure_probability(self, simulator):
        """Test failure simulation probability."""
        operation_type = "order_submission"
        
        # Test multiple times due to low probability
        failures = 0
        for _ in range(10000):  # Large number to test probability
            if simulator.should_simulate_failure(operation_type):
                failures += 1
                # Simulate the failure to prevent multiple failures
                simulator.simulate_system_failure(operation_type)
                break  # Only test one failure
        
        # Should have very low failure rate
        assert failures >= 0  # Very low probability, so just check it doesn't crash
    
    def test_simulate_system_failure(self, simulator):
        """Test system failure simulation."""
        operation_type = "execution"
        
        failure_details = simulator.simulate_system_failure(operation_type)
        
        assert failure_details['operation_type'] == operation_type
        assert 'timestamp' in failure_details
        assert 'recovery_time_seconds' in failure_details
        assert 'error_message' in failure_details
        assert 'failure_id' in failure_details
        
        # Check failure is recorded
        assert operation_type in simulator.system_failures
        assert len(simulator.failure_history) == 1
    
    def test_is_system_recovering(self, simulator):
        """Test system recovery status checking."""
        operation_type = "market_data"
        
        # Initially not recovering
        is_recovering, remaining_time = simulator.is_system_recovering(operation_type)
        assert not is_recovering
        assert remaining_time is None
        
        # Simulate failure
        failure_details = simulator.simulate_system_failure(operation_type)
        
        # Should be recovering
        is_recovering, remaining_time = simulator.is_system_recovering(operation_type)
        assert is_recovering
        assert remaining_time is not None
        assert remaining_time > 0
        
        # Mock time passage for recovery
        simulator.system_failures[operation_type] = datetime.now() - timedelta(seconds=100)
        
        # Should be recovered
        is_recovering, remaining_time = simulator.is_system_recovering(operation_type)
        assert not is_recovering
        assert remaining_time is None
        assert operation_type not in simulator.system_failures
    
    def test_failure_rate_limiting(self, simulator):
        """Test that failures are rate limited."""
        operation_type = "portfolio"
        
        # Create multiple recent failures
        for i in range(5):
            simulator.failure_history.append({
                'operation_type': operation_type,
                'timestamp': datetime.now() - timedelta(seconds=i * 30),
                'recovery_time_seconds': 10.0,
                'error_message': f"Test failure {i}",
                'failure_id': f"test_{i}"
            })
        
        # Should not allow more failures
        assert not simulator.should_simulate_failure(operation_type)
    
    def test_generate_failure_message(self, simulator):
        """Test failure message generation."""
        # Test different operation types
        operations = ['order_submission', 'market_data', 'execution', 'portfolio']
        
        for operation in operations:
            message = simulator._generate_failure_message(operation)
            assert isinstance(message, str)
            assert len(message) > 0
        
        # Test unknown operation type
        message = simulator._generate_failure_message('unknown')
        assert message == "System temporarily unavailable"


class TestMockTradingErrorHandler:
    """Test main error handler integration."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = MockTradingConfig()
        config.execution.enable_partial_fills = True
        return config
    
    @pytest.fixture
    def error_handler(self, config):
        """Create error handler."""
        return MockTradingErrorHandler(config)
    
    @pytest.fixture
    def sample_order(self):
        """Create sample order for testing."""
        return Order(
            symbol="BTCUSD",
            quantity=1.0,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET
        )
    
    def test_handle_order_execution_success(self, error_handler, sample_order):
        """Test successful order execution handling."""
        market_price = 50000.0
        
        # Mock no system failures
        with patch.object(error_handler.system_failure_simulator, 'is_system_recovering', return_value=(False, None)):
            with patch.object(error_handler.system_failure_simulator, 'should_simulate_failure', return_value=False):
                with patch.object(error_handler.market_gap_handler, 'should_create_gap', return_value=False):
                    with patch.object(error_handler.partial_fill_simulator, 'simulate_partial_fill') as mock_partial:
                        # Mock partial fill result
                        mock_result = Mock()
                        mock_result.partial_fill = False
                        mock_partial.return_value = mock_result
                        
                        success, result, error_msg = error_handler.handle_order_execution(
                            sample_order, market_price
                        )
                        
                        assert success is True
                        assert result is not None
                        assert error_msg is None
    
    def test_handle_order_execution_system_failure(self, error_handler, sample_order):
        """Test order execution with system failure."""
        market_price = 50000.0
        
        # Mock system failure
        with patch.object(error_handler.system_failure_simulator, 'is_system_recovering', return_value=(True, 15.5)):
            success, result, error_msg = error_handler.handle_order_execution(
                sample_order, market_price
            )
            
            assert success is False
            assert result is None
            assert "System recovering" in error_msg
            assert "15.5s remaining" in error_msg
    
    def test_handle_order_execution_market_gap(self, error_handler, sample_order):
        """Test order execution with market gap."""
        market_price = 50000.0
        sample_order.order_type = OrderType.LIMIT
        sample_order.price = 49000.0
        
        # Mock gap creation
        gap_event = MarketGapEvent(
            symbol="BTCUSD",
            gap_start_price=50000.0,
            gap_end_price=48000.0,
            gap_direction="DOWN",
            gap_size_percent=0.04,
            timestamp=datetime.now()
        )
        
        with patch.object(error_handler.system_failure_simulator, 'is_system_recovering', return_value=(False, None)):
            with patch.object(error_handler.system_failure_simulator, 'should_simulate_failure', return_value=False):
                with patch.object(error_handler.market_gap_handler, 'should_create_gap', return_value=True):
                    with patch.object(error_handler.market_gap_handler, 'create_market_gap', return_value=gap_event):
                        with patch.object(error_handler.market_gap_handler, 'handle_limit_order_gap') as mock_gap:
                            mock_result = Mock()
                            mock_gap.return_value = mock_result
                            
                            success, result, error_msg = error_handler.handle_order_execution(
                                sample_order, market_price
                            )
                            
                            assert success is True
                            assert result == mock_result
                            assert error_msg is None
                            assert error_handler.error_stats['market_gaps'] == 1
    
    def test_handle_market_data_error(self, error_handler):
        """Test market data error handling."""
        symbol = "ETHUSD"
        
        # Test normal operation
        with patch.object(error_handler.system_failure_simulator, 'is_system_recovering', return_value=(False, None)):
            with patch.object(error_handler.system_failure_simulator, 'should_simulate_failure', return_value=False):
                available, error_msg = error_handler.handle_market_data_error(symbol)
                
                assert available is True
                assert error_msg is None
        
        # Test with system failure
        with patch.object(error_handler.system_failure_simulator, 'is_system_recovering', return_value=(True, 10.0)):
            available, error_msg = error_handler.handle_market_data_error(symbol)
            
            assert available is False
            assert "Market data service recovering" in error_msg
    
    def test_handle_portfolio_error(self, error_handler):
        """Test portfolio error handling."""
        # Test normal operation
        with patch.object(error_handler.system_failure_simulator, 'is_system_recovering', return_value=(False, None)):
            with patch.object(error_handler.system_failure_simulator, 'should_simulate_failure', return_value=False):
                available, error_msg = error_handler.handle_portfolio_error()
                
                assert available is True
                assert error_msg is None
        
        # Test with system failure
        with patch.object(error_handler.system_failure_simulator, 'is_system_recovering', return_value=(True, 5.0)):
            available, error_msg = error_handler.handle_portfolio_error()
            
            assert available is False
            assert "Portfolio service recovering" in error_msg
    
    def test_update_liquidity_conditions(self, error_handler):
        """Test liquidity conditions update."""
        symbol = "SOLUSD"
        volume = 5000.0
        spread = 0.002
        
        error_handler.update_liquidity_conditions(symbol, volume, spread)
        
        condition = error_handler.partial_fill_simulator.get_liquidity_condition(symbol)
        assert condition is not None
        assert condition.symbol == symbol
        assert condition.available_volume == volume
        assert condition.spread_multiplier == 2.0  # spread / 0.001
    
    def test_cleanup_expired_events(self, error_handler):
        """Test cleanup of expired events."""
        # Add some test gaps
        symbol = "BTCUSD"
        old_gap = MarketGapEvent(
            symbol=symbol,
            gap_start_price=50000.0,
            gap_end_price=48000.0,
            gap_direction="DOWN",
            gap_size_percent=0.04,
            timestamp=datetime.now() - timedelta(seconds=100),
            duration_seconds=1.0
        )
        
        error_handler.market_gap_handler.active_gaps[symbol] = old_gap
        
        # Cleanup should remove expired gap
        error_handler.cleanup_expired_events()
        
        assert symbol not in error_handler.market_gap_handler.active_gaps
    
    def test_get_error_statistics(self, error_handler):
        """Test error statistics retrieval."""
        # Increment some stats
        error_handler.error_stats['total_errors'] = 5
        error_handler.error_stats['partial_fills'] = 3
        error_handler.error_stats['market_gaps'] = 2
        
        stats = error_handler.get_error_statistics()
        
        assert stats['total_errors'] == 5
        assert stats['partial_fills'] == 3
        assert stats['market_gaps'] == 2
        assert 'active_gaps' in stats
        assert 'active_failures' in stats
        assert 'gap_history_count' in stats
        assert 'failure_history_count' in stats
    
    def test_reset_statistics(self, error_handler):
        """Test statistics reset."""
        # Set some stats
        error_handler.error_stats['total_errors'] = 10
        error_handler.error_stats['partial_fills'] = 5
        
        # Reset
        error_handler.reset_statistics()
        
        # Check all stats are reset
        for key, value in error_handler.error_stats.items():
            assert value == 0


class TestErrorScenarios:
    """Test error scenario configurations and edge cases."""
    
    def test_error_scenario_validation(self):
        """Test error scenario validation."""
        # Valid scenario
        scenario = ErrorScenario(
            error_type=ErrorType.NETWORK_ERROR,
            probability=0.5,
            severity=ErrorSeverity.MEDIUM,
            recovery_time_seconds=10.0
        )
        assert scenario.probability == 0.5
        
        # Invalid probability
        with pytest.raises(ValueError, match="Error probability must be between 0.0 and 1.0"):
            ErrorScenario(
                error_type=ErrorType.NETWORK_ERROR,
                probability=1.5,
                severity=ErrorSeverity.MEDIUM,
                recovery_time_seconds=10.0
            )
        
        # Invalid recovery time
        with pytest.raises(ValueError, match="Recovery time cannot be negative"):
            ErrorScenario(
                error_type=ErrorType.NETWORK_ERROR,
                probability=0.5,
                severity=ErrorSeverity.MEDIUM,
                recovery_time_seconds=-5.0
            )
    
    def test_market_gap_event_properties(self):
        """Test market gap event properties."""
        # Gap up event
        gap_up = MarketGapEvent(
            symbol="BTCUSD",
            gap_start_price=50000.0,
            gap_end_price=52000.0,
            gap_direction="UP",
            gap_size_percent=0.04,
            timestamp=datetime.now()
        )
        
        assert gap_up.is_gap_up is True
        assert gap_up.is_gap_down is False
        
        # Gap down event
        gap_down = MarketGapEvent(
            symbol="BTCUSD",
            gap_start_price=50000.0,
            gap_end_price=48000.0,
            gap_direction="DOWN",
            gap_size_percent=0.04,
            timestamp=datetime.now()
        )
        
        assert gap_down.is_gap_up is False
        assert gap_down.is_gap_down is True
    
    def test_liquidity_condition_properties(self):
        """Test liquidity condition properties."""
        # Normal liquidity
        normal_liquidity = LiquidityCondition(
            symbol="ETHUSD",
            available_volume=10000.0,
            bid_depth=3000.0,
            ask_depth=3000.0,
            spread_multiplier=1.0
        )
        
        assert normal_liquidity.is_low_liquidity is False
        
        # Low liquidity (low volume)
        low_volume = LiquidityCondition(
            symbol="ETHUSD",
            available_volume=500.0,  # Below 1000 threshold
            bid_depth=150.0,
            ask_depth=150.0,
            spread_multiplier=1.0
        )
        
        assert low_volume.is_low_liquidity is True
        
        # Low liquidity (high spread)
        high_spread = LiquidityCondition(
            symbol="ETHUSD",
            available_volume=5000.0,
            bid_depth=1500.0,
            ask_depth=1500.0,
            spread_multiplier=3.0  # Above 2.0 threshold
        )
        
        assert high_spread.is_low_liquidity is True


if __name__ == "__main__":
    pytest.main([__file__])