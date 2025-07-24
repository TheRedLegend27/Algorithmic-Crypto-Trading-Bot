"""
Integration tests for crypto risk management functionality.
"""
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import os
import json
from datetime import datetime, timedelta

from bot.crypto_risk_manager import CryptoRiskManager, CryptoRiskSettings, AlertLevel
from bot.crypto_position_manager import CryptoPositionManager, CryptoBalance
from bot.coinbase_client import CoinbaseClient
from bot.coinbase_data_fetcher import CoinbaseDataFetcher
from bot.config import CoinbaseCredentials


class TestCryptoRiskManagementIntegration(unittest.TestCase):
    """Integration tests for crypto risk management."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures that are reused across tests."""
        # Create mock credentials
        cls.mock_credentials = CoinbaseCredentials(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_passphrase",
            sandbox=True
        )
    
    def setUp(self):
        """Set up test fixtures before each test."""
        # Create mocks with realistic behavior
        self.mock_client = MagicMock(spec=CoinbaseClient)
        self.mock_data_fetcher = MagicMock(spec=CoinbaseDataFetcher)
        
        # Set up mock account data
        mock_accounts = [
            {
                'id': '1',
                'currency': 'BTC',
                'balance': '0.5',
                'available': '0.5',
                'hold': '0.0',
                'profile_id': 'profile1',
                'trading_enabled': True
            },
            {
                'id': '2',
                'currency': 'ETH',
                'balance': '5.0',
                'available': '5.0',
                'hold': '0.0',
                'profile_id': 'profile1',
                'trading_enabled': True
            },
            {
                'id': '3',
                'currency': 'USD',
                'balance': '10000.0',
                'available': '10000.0',
                'hold': '0.0',
                'profile_id': 'profile1',
                'trading_enabled': True
            }
        ]
        self.mock_client.get_accounts.return_value = mock_accounts
        
        # Set up mock price data
        self.mock_data_fetcher.get_latest_price.side_effect = lambda symbol: {
            'BTC-USD': 40000.0,
            'ETH-USD': 2000.0
        }.get(symbol, 0.0)
        
        # Create mock OHLCV data for volatility calculation
        dates = pd.date_range(start='2023-01-01', periods=24, freq='H')
        btc_data = {
            'timestamp': dates,
            'open': [40000] * 24,
            'high': [41000] * 24,
            'low': [39000] * 24,
            'close': [40000 + (i * 100) for i in range(24)],  # Increasing by $100 each hour
            'volume': [100] * 24
        }
        eth_data = {
            'timestamp': dates,
            'open': [2000] * 24,
            'high': [2100] * 24,
            'low': [1900] * 24,
            'close': [2000 + (i * 10) for i in range(24)],  # Increasing by $10 each hour
            'volume': [1000] * 24
        }
        
        self.mock_data_fetcher.fetch_crypto_ohlcv.side_effect = lambda symbol, timeframe, limit: {
            'BTC-USD': pd.DataFrame(btc_data),
            'ETH-USD': pd.DataFrame(eth_data)
        }.get(symbol, pd.DataFrame())
        
        # Create real position manager with mock client
        self.position_manager = CryptoPositionManager(self.mock_client)
        
        # Override _refresh_balances to use our mock data
        def mock_refresh_balances():
            self.position_manager.balances = {
                'BTC': CryptoBalance(
                    currency='BTC',
                    balance=0.5,
                    available=0.5,
                    hold=0.0,
                    profile_id='profile1',
                    trading_enabled=True
                ),
                'ETH': CryptoBalance(
                    currency='ETH',
                    balance=5.0,
                    available=5.0,
                    hold=0.0,
                    profile_id='profile1',
                    trading_enabled=True
                ),
                'USD': CryptoBalance(
                    currency='USD',
                    balance=10000.0,
                    available=10000.0,
                    hold=0.0,
                    profile_id='profile1',
                    trading_enabled=True
                )
            }
            return True
        
        self.position_manager._refresh_balances = mock_refresh_balances
        self.position_manager._refresh_balances()
        
        # Create risk settings
        self.risk_settings = CryptoRiskSettings(
            max_position_size_usd=25000.0,  # Higher than our test positions
            max_position_size_pct=0.50,     # Higher than our test positions
            max_single_order_usd=5000.0,    # Higher than our test orders
            max_daily_loss_usd=1000.0,
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
            max_trade_frequency=0,  # No delay for testing
            enable_circuit_breakers=True,
            market_drop_circuit_breaker_pct=0.10,
            consecutive_losses_limit=3
        )
        
        # Create alert callback
        self.alerts = []
        def alert_callback(alert):
            self.alerts.append(alert)
        
        # Create risk manager
        self.risk_manager = CryptoRiskManager(
            position_manager=self.position_manager,
            data_fetcher=self.mock_data_fetcher,
            client=self.mock_client,
            risk_settings=self.risk_settings,
            alert_callback=alert_callback
        )
        
        # Override _get_portfolio_value to use our mock data
        self.risk_manager._get_portfolio_value = MagicMock(return_value=30000.0)
        self.risk_manager.starting_portfolio_value = 30000.0
        self.risk_manager.high_water_mark = 30000.0
    
    def test_end_to_end_risk_workflow(self):
        """Test end-to-end risk management workflow."""
        # 1. Validate a position size
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency="BTC", size=0.1, price=40000.0
        )
        self.assertTrue(is_valid)
        self.assertEqual(adjusted_size, 0.1)
        
        # 2. Track a trade result (profitable)
        self.risk_manager.track_trade_result(is_profitable=True)
        self.assertEqual(self.risk_manager.consecutive_losses, 0)
        self.assertEqual(self.risk_manager.daily_trades_count, 1)
        
        # 3. Track a trade result (loss)
        self.risk_manager.track_trade_result(is_profitable=False)
        self.assertEqual(self.risk_manager.consecutive_losses, 1)
        self.assertEqual(self.risk_manager.daily_trades_count, 2)
        
        # 4. Monitor position change
        self.risk_manager.monitor_position_change(
            currency="BTC", old_position=0.5, new_position=0.3, price=40000.0
        )
        # Should create an alert (40% decrease)
        self.assertEqual(len(self.alerts), 1)
        self.assertEqual(self.alerts[0].level, AlertLevel.WARNING)
        
        # 5. Calculate real-time P&L
        pnl_data = self.risk_manager.calculate_real_time_pnl("BTC", 40000.0)
        self.assertEqual(pnl_data["currency"], "BTC")
        self.assertIn("position_value_usd", pnl_data)
        self.assertIn("risk_level", pnl_data)
        
        # 6. Update portfolio metrics
        metrics = self.risk_manager.update_portfolio_metrics()
        self.assertIn("portfolio_value", metrics)
        self.assertIn("daily_pnl", metrics)
        
        # 7. Test drawdown circuit breaker
        self.risk_manager._get_portfolio_value = MagicMock(return_value=24000.0)  # 20% drop
        metrics = self.risk_manager.update_portfolio_metrics()
        self.assertTrue(metrics["trading_paused"])
        self.assertIn("Max drawdown exceeded", metrics["trading_pause_reason"])
        
        # 8. Resume trading
        self.risk_manager.resume_trading()
        self.assertFalse(self.risk_manager.trading_paused)
        
        # 9. Reset daily metrics
        self.risk_manager.reset_daily_metrics()
        self.assertEqual(self.risk_manager.daily_pnl, 0.0)
        self.assertEqual(self.risk_manager.daily_trades_count, 0)
        
        # 10. Export risk data
        with patch('builtins.open', unittest.mock.mock_open()) as mock_file:
            self.risk_manager.export_risk_data("test_export.json")
            mock_file.assert_called_once_with("test_export.json", 'w')
    
    def test_volatility_based_position_sizing(self):
        """Test volatility-based position sizing."""
        # 1. Set up high volatility for BTC
        def mock_volatility(symbol):
            return 0.06 if symbol == "BTC-USD" else 0.02
        
        self.risk_manager.get_market_volatility = MagicMock(side_effect=mock_volatility)
        
        # 2. Validate BTC position (should be reduced)
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency="BTC", size=0.1, price=40000.0
        )
        self.assertTrue(is_valid)
        self.assertEqual(adjusted_size, 0.05)  # Reduced by 50%
        
        # 3. Validate ETH position (should not be reduced)
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency="ETH", size=1.0, price=2000.0
        )
        self.assertTrue(is_valid)
        self.assertEqual(adjusted_size, 1.0)  # Not reduced
        
        # 4. Set up extreme volatility for BTC
        def mock_extreme_volatility(symbol):
            return 0.12 if symbol == "BTC-USD" else 0.02
        
        self.risk_manager.get_market_volatility = MagicMock(side_effect=mock_extreme_volatility)
        
        # 5. Validate BTC position (should be rejected)
        is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
            currency="BTC", size=0.1, price=40000.0
        )
        self.assertFalse(is_valid)
        self.assertEqual(adjusted_size, 0.0)
        self.assertIn("Extreme market volatility", reason)
    
    def test_consecutive_losses_circuit_breaker(self):
        """Test consecutive losses circuit breaker."""
        # 1. Track three consecutive losses
        self.risk_manager.track_trade_result(is_profitable=False)
        self.assertEqual(self.risk_manager.consecutive_losses, 1)
        self.assertFalse(self.risk_manager.trading_paused)
        
        self.risk_manager.track_trade_result(is_profitable=False)
        self.assertEqual(self.risk_manager.consecutive_losses, 2)
        self.assertFalse(self.risk_manager.trading_paused)
        
        self.risk_manager.track_trade_result(is_profitable=False)
        self.assertEqual(self.risk_manager.consecutive_losses, 3)
        self.assertTrue(self.risk_manager.trading_paused)
        self.assertIn("Consecutive losses limit", self.risk_manager.trading_pause_reason)
        
        # 2. Resume trading
        self.risk_manager.resume_trading()
        self.assertFalse(self.risk_manager.trading_paused)
        
        # 3. Track a profitable trade (should reset consecutive losses)
        self.risk_manager.track_trade_result(is_profitable=True)
        self.assertEqual(self.risk_manager.consecutive_losses, 0)
    
    def test_daily_loss_circuit_breaker(self):
        """Test daily loss circuit breaker."""
        # 1. Set up a daily loss
        self.risk_manager.starting_portfolio_value = 30000.0
        self.risk_manager._get_portfolio_value = MagicMock(return_value=28500.0)  # $1500 loss (5%)
        
        # 2. Update portfolio metrics
        metrics = self.risk_manager.update_portfolio_metrics()
        self.assertTrue(metrics["trading_paused"])
        self.assertIn("Max daily loss", metrics["trading_pause_reason"])
        
        # 3. Resume trading
        self.risk_manager.resume_trading()
        self.assertFalse(self.risk_manager.trading_paused)
        
        # 4. Reset daily metrics
        self.risk_manager.reset_daily_metrics()
        self.assertEqual(self.risk_manager.daily_pnl, 0.0)
        
        # 5. Set up a smaller loss (below threshold)
        self.risk_manager.starting_portfolio_value = 30000.0
        self.risk_manager._get_portfolio_value = MagicMock(return_value=29500.0)  # $500 loss
        
        # 6. Update portfolio metrics
        metrics = self.risk_manager.update_portfolio_metrics()
        self.assertFalse(metrics["trading_paused"])
    
    def test_risk_level_calculation(self):
        """Test risk level calculation."""
        # Test low risk
        risk_level = self.risk_manager._calculate_risk_level(
            position_pct=0.02,  # Small position
            pnl_pct=0.05,       # Profitable
            volatility=0.02     # Low volatility
        )
        self.assertEqual(risk_level, "low")
        
        # Test medium risk
        risk_level = self.risk_manager._calculate_risk_level(
            position_pct=0.10,  # Medium position
            pnl_pct=-0.03,      # Small loss
            volatility=0.04     # Medium volatility
        )
        self.assertEqual(risk_level, "medium")
        
        # Test high risk
        risk_level = self.risk_manager._calculate_risk_level(
            position_pct=0.20,  # Large position
            pnl_pct=-0.08,      # Significant loss
            volatility=0.06     # High volatility
        )
        self.assertEqual(risk_level, "high")
        
        # Test extreme risk
        risk_level = self.risk_manager._calculate_risk_level(
            position_pct=0.30,  # Very large position
            pnl_pct=-0.15,      # Large loss
            volatility=0.12     # Extreme volatility
        )
        self.assertEqual(risk_level, "extreme")


if __name__ == '__main__':
    unittest.main()