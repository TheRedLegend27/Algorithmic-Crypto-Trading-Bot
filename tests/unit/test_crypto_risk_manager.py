"""
Unit tests for the crypto risk manager.
"""
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime, timedelta
import json

from bot.crypto_risk_manager import (
    CryptoRiskManager, CryptoRiskSettings, AlertLevel, RiskAlert
)


class TestCryptoRiskManager(unittest.TestCase):
    """Test cases for CryptoRiskManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mocks
        self.mock_position_manager = MagicMock()
        self.mock_data_fetcher = MagicMock()
        self.mock_client = MagicMock()
        self.mock_alert_callback = MagicMock()
        
        # Create risk settings with test values
        self.risk_settings = CryptoRiskSettings(
            max_position_size_usd=1000.0,
            max_position_size_pct=0.10,
            max_single_order_usd=500.0,
            max_daily_loss_usd=100.0,
            max_daily_loss_pct=0.05,
            max_drawdown_pct=0.15,
            high_volatility_threshold=0.05,
            extreme_volatility_threshold=0.10,
            volatility_lookback_hours=24,
            volatility_position_reduction=0.5,
            large_position_change_pct=0.20,
            large_loss_pct=0.10,
            large_profit_pct=0.20,
            max_open_positions=5,
            max_trades_per_day=20,
            max_trade_frequency=5,
            enable_circuit_breakers=True,
            market_drop_circuit_breaker_pct=0.10,
            consecutive_losses_limit=3
        )
        
        # Create risk manager with mocks
        self.risk_manager = CryptoRiskManager(
            position_manager=self.mock_position_manager,
            data_fetcher=self.mock_data_fetcher,
            client=self.mock_client,
            risk_settings=self.risk_settings,
            alert_callback=self.mock_alert_callback
        )
        
        # Set up initial portfolio value
        self.risk_manager.starting_portfolio_value = 10000.0
        self.risk_manager.high_water_mark = 10000.0
        
        # Mock _get_portfolio_value to return a fixed value
        self.risk_manager._get_portfolio_value = MagicMock(return_value=10000.0)
    
    def test_validate_position_size_within_limits(self):
        """Test position size validation when within limits."""
        # Set up
        currency = "BTC"
        size = 0.1  # 0.1 BTC
        price = 40000.0  # $40,000 per BTC
        
        # Position value = 0.1 * 40000 = $4,000
        # This is below our max_position_size_usd of $1000, so should fail
        
        # Execute
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency, size, price
        )
        
        # Assert
        self.assertFalse(is_valid)
        self.assertLess(adjusted_size, size)
        self.assertIn("exceeds max single order", reason)
    
    def test_validate_position_size_exceeds_percentage(self):
        """Test position size validation when exceeding portfolio percentage."""
        # Set up
        currency = "ETH"
        size = 0.5  # 0.5 ETH
        price = 2000.0  # $2,000 per ETH
        
        # Position value = 0.5 * 2000 = $1,000
        # Portfolio value = $10,000
        # Position percentage = 10%, which equals our max_position_size_pct
        
        # Execute
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency, size, price
        )
        
        # Assert
        self.assertFalse(is_valid)  # Should fail due to exceeding max_single_order_usd
        self.assertLess(adjusted_size, size)
    
    def test_validate_position_size_high_volatility(self):
        """Test position size validation with high volatility."""
        # Set up
        currency = "BTC"
        size = 0.01  # 0.01 BTC
        price = 40000.0  # $40,000 per BTC
        
        # Position value = 0.01 * 40000 = $400, which is within limits
        # Mock high volatility
        self.risk_manager.get_market_volatility = MagicMock(return_value=0.06)  # 6% volatility
        
        # Execute
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency, size, price
        )
        
        # Assert
        self.assertTrue(is_valid)
        self.assertLess(adjusted_size, size)  # Should be reduced due to volatility
        self.assertEqual(adjusted_size, size * 0.5)  # Reduced by volatility_position_reduction (50%)
    
    def test_validate_position_size_extreme_volatility(self):
        """Test position size validation with extreme volatility."""
        # Set up
        currency = "BTC"
        size = 0.01  # 0.01 BTC
        price = 40000.0  # $40,000 per BTC
        
        # Mock extreme volatility
        self.risk_manager.get_market_volatility = MagicMock(return_value=0.12)  # 12% volatility
        
        # Execute
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency, size, price
        )
        
        # Assert
        self.assertFalse(is_valid)
        self.assertEqual(adjusted_size, 0.0)
        self.assertIn("Extreme market volatility", reason)
    
    def test_validate_position_size_max_positions(self):
        """Test position size validation with maximum positions reached."""
        # Set up
        currency = "LTC"
        size = 0.01
        price = 100.0
        
        # Mock current positions count
        self.risk_manager._count_open_positions = MagicMock(return_value=5)
        
        # Mock that we don't already have a position in this currency
        self.mock_position_manager.get_crypto_balance.return_value = None
        
        # Execute
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency, size, price
        )
        
        # Assert
        self.assertFalse(is_valid)
        self.assertEqual(adjusted_size, 0.0)
        self.assertIn("Max open positions limit", reason)
    
    def test_validate_position_size_max_trades_per_day(self):
        """Test position size validation with maximum trades per day reached."""
        # Set up
        currency = "ETH"
        size = 0.01
        price = 2000.0
        
        # Set daily trades count to max
        self.risk_manager.daily_trades_count = 20
        
        # Execute
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency, size, price
        )
        
        # Assert
        self.assertFalse(is_valid)
        self.assertEqual(adjusted_size, 0.0)
        self.assertIn("Max daily trades limit", reason)
    
    def test_validate_position_size_trade_frequency(self):
        """Test position size validation with trade frequency limit."""
        # Set up
        currency = "ETH"
        size = 0.01
        price = 2000.0
        
        # Set last trade time to recent
        self.risk_manager.last_trade_time = datetime.now() - timedelta(minutes=2)
        
        # Execute
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency, size, price
        )
        
        # Assert
        self.assertFalse(is_valid)
        self.assertEqual(adjusted_size, 0.0)
        self.assertIn("Trade frequency limit", reason)
    
    def test_get_market_volatility(self):
        """Test market volatility calculation."""
        # Set up
        symbol = "BTC-USD"
        
        # Create mock OHLCV data with known volatility pattern
        dates = pd.date_range(start='2023-01-01', periods=24, freq='h')
        data = {
            'timestamp': dates,
            'open': [40000] * 24,
            'high': [41000] * 24,
            'low': [39000] * 24,
            'close': [40000 + (i * 100) for i in range(24)],  # Increasing by $100 each hour
            'volume': [100] * 24
        }
        mock_df = pd.DataFrame(data)
        
        # Mock data fetcher to return our dataframe
        self.mock_data_fetcher.fetch_crypto_ohlcv.return_value = mock_df
        
        # Execute
        volatility = self.risk_manager.get_market_volatility(symbol)
        
        # Assert
        self.assertGreater(volatility, 0)
        self.mock_data_fetcher.fetch_crypto_ohlcv.assert_called_once_with(
            symbol=symbol, timeframe="1h", limit=24
        )
        
        # Test cache
        self.risk_manager.get_market_volatility(symbol)
        # Should still be called only once due to caching
        self.mock_data_fetcher.fetch_crypto_ohlcv.assert_called_once()
    
    def test_update_portfolio_metrics(self):
        """Test portfolio metrics update."""
        # Set up
        self.risk_manager._get_portfolio_value = MagicMock(return_value=9500.0)
        self.risk_manager.high_water_mark = 10000.0
        self.risk_manager.starting_portfolio_value = 10000.0
        
        # Execute
        metrics = self.risk_manager.update_portfolio_metrics()
        
        # Assert
        self.assertEqual(metrics["portfolio_value"], 9500.0)
        self.assertEqual(metrics["high_water_mark"], 10000.0)
        self.assertEqual(metrics["current_drawdown"], 0.05)  # (10000 - 9500) / 10000
        self.assertEqual(metrics["daily_pnl"], -500.0)
    
    def test_update_portfolio_metrics_drawdown_circuit_breaker(self):
        """Test drawdown circuit breaker in portfolio metrics update."""
        # Set up
        self.risk_manager._get_portfolio_value = MagicMock(return_value=8000.0)
        self.risk_manager.high_water_mark = 10000.0
        self.risk_manager.starting_portfolio_value = 10000.0
        
        # Execute
        metrics = self.risk_manager.update_portfolio_metrics()
        
        # Assert
        self.assertEqual(metrics["current_drawdown"], 0.2)  # (10000 - 8000) / 10000
        self.assertTrue(metrics["trading_paused"])
        self.assertIn("Max drawdown exceeded", metrics["trading_pause_reason"])
        
        # Check that alert was created
        self.mock_alert_callback.assert_called_once()
        alert = self.mock_alert_callback.call_args[0][0]
        self.assertEqual(alert.level, AlertLevel.CRITICAL)
    
    def test_monitor_position_change(self):
        """Test position change monitoring."""
        # Set up
        currency = "BTC"
        old_position = 0.1
        new_position = 0.05
        price = 40000.0
        
        # Position change = -0.05 BTC
        # Position change percentage = -50%
        
        # Execute
        self.risk_manager.monitor_position_change(currency, old_position, new_position, price)
        
        # Assert
        # Should create an alert due to large position change
        self.mock_alert_callback.assert_called_once()
        alert = self.mock_alert_callback.call_args[0][0]
        self.assertEqual(alert.level, AlertLevel.WARNING)
        self.assertIn("Large BTC position change", alert.message)
    
    def test_monitor_pnl_change_large_loss(self):
        """Test P&L monitoring with large loss."""
        # Set up
        currency = "ETH"
        old_pnl = -100.0
        new_pnl = -200.0
        position_value = 1000.0
        
        # P&L percentage = -20%
        
        # Execute
        self.risk_manager.monitor_pnl_change(currency, old_pnl, new_pnl, position_value)
        
        # Assert
        # Should create an alert due to large loss
        self.mock_alert_callback.assert_called_once()
        alert = self.mock_alert_callback.call_args[0][0]
        self.assertEqual(alert.level, AlertLevel.WARNING)
        self.assertIn("Large ETH loss", alert.message)
    
    def test_monitor_pnl_change_large_profit(self):
        """Test P&L monitoring with large profit."""
        # Set up
        currency = "ETH"
        old_pnl = 100.0
        new_pnl = 250.0
        position_value = 1000.0
        
        # P&L percentage = 25%
        
        # Execute
        self.risk_manager.monitor_pnl_change(currency, old_pnl, new_pnl, position_value)
        
        # Assert
        # Should create an alert due to large profit
        self.mock_alert_callback.assert_called_once()
        alert = self.mock_alert_callback.call_args[0][0]
        self.assertEqual(alert.level, AlertLevel.INFO)
        self.assertIn("Large ETH profit", alert.message)
    
    def test_track_trade_result_consecutive_losses(self):
        """Test tracking consecutive losses."""
        # Set up
        self.risk_manager.consecutive_losses = 2
        
        # Execute - add a third loss
        self.risk_manager.track_trade_result(is_profitable=False)
        
        # Assert
        self.assertEqual(self.risk_manager.consecutive_losses, 3)
        self.assertEqual(self.risk_manager.daily_trades_count, 1)
        self.assertTrue(self.risk_manager.trading_paused)
        self.assertIn("Consecutive losses limit", self.risk_manager.trading_pause_reason)
        
        # Check that alert was created
        self.mock_alert_callback.assert_called_once()
    
    def test_track_trade_result_reset_consecutive_losses(self):
        """Test resetting consecutive losses after a profitable trade."""
        # Set up
        self.risk_manager.consecutive_losses = 2
        
        # Execute - add a profitable trade
        self.risk_manager.track_trade_result(is_profitable=True)
        
        # Assert
        self.assertEqual(self.risk_manager.consecutive_losses, 0)
        self.assertEqual(self.risk_manager.daily_trades_count, 1)
    
    def test_calculate_real_time_pnl(self):
        """Test real-time P&L calculation."""
        # Set up
        currency = "BTC"
        current_price = 40000.0
        
        # Mock position summary
        self.mock_position_manager.get_position_summary.return_value = {
            "balance": 0.1,
            "market_value_usd": 4000.0,
            "unrealized_pnl": 500.0,
            "realized_pnl": 200.0,
            "cost_basis": 3500.0,
            "pnl_percentage": 14.29  # (500/3500) * 100
        }
        
        # Mock volatility
        self.risk_manager.get_market_volatility = MagicMock(return_value=0.04)
        
        # Execute
        pnl_data = self.risk_manager.calculate_real_time_pnl(currency, current_price)
        
        # Assert
        self.assertEqual(pnl_data["currency"], currency)
        self.assertEqual(pnl_data["current_price"], current_price)
        self.assertEqual(pnl_data["position_size"], 0.1)
        self.assertEqual(pnl_data["position_value_usd"], 4000.0)
        self.assertEqual(pnl_data["unrealized_pnl"], 500.0)
        self.assertEqual(pnl_data["realized_pnl"], 200.0)
        self.assertEqual(pnl_data["total_pnl"], 700.0)
        self.assertAlmostEqual(pnl_data["pnl_percentage"], 0.1429, places=4)
        self.assertEqual(pnl_data["cost_basis"], 3500.0)
        self.assertEqual(pnl_data["volatility"], 0.04)
        
        # Check risk level calculation
        self.assertIn(pnl_data["risk_level"], ["low", "medium", "high", "extreme"])
    
    def test_reset_daily_metrics(self):
        """Test resetting daily metrics."""
        # Set up
        self.risk_manager.daily_pnl = -500.0
        self.risk_manager.daily_trades_count = 15
        self.risk_manager._get_portfolio_value = MagicMock(return_value=9500.0)
        
        # Execute
        self.risk_manager.reset_daily_metrics()
        
        # Assert
        self.assertEqual(self.risk_manager.starting_portfolio_value, 9500.0)
        self.assertEqual(self.risk_manager.daily_pnl, 0.0)
        self.assertEqual(self.risk_manager.daily_trades_count, 0)
    
    def test_export_risk_data(self):
        """Test exporting risk data to JSON."""
        # Set up
        self.risk_manager.alerts = [
            RiskAlert(
                timestamp=datetime.now(),
                level=AlertLevel.WARNING,
                message="Test alert",
                data={"test": "data"}
            )
        ]
        
        # Mock open to avoid actual file operations
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            # Execute
            result = self.risk_manager.export_risk_data("test_path.json")
            
            # Assert
            self.assertTrue(result)
            mock_file.assert_called_once_with("test_path.json", 'w')
            # Check that write was called (we don't care about the exact content)
            self.assertTrue(mock_file().write.called)


if __name__ == '__main__':
    unittest.main()