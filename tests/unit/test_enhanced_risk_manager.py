"""
Unit tests for the Enhanced Risk Manager.

Tests dynamic position sizing, portfolio-level exposure limits, correlation analysis,
drawdown protection, and emergency stop mechanisms.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from bot.enhanced_risk_manager import (
    EnhancedRiskManager, EnhancedRiskSettings, RiskLevel, EmergencyStopReason,
    RiskAssessment, PortfolioRisk, PositionSizeCalculation
)
from bot.crypto_risk_manager import CryptoRiskSettings
from bot.crypto_position_manager import CryptoBalance


class TestEnhancedRiskManager(unittest.TestCase):
    """Test cases for EnhancedRiskManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.mock_position_manager = Mock()
        self.mock_data_manager = Mock()
        self.mock_kraken_client = Mock()
        
        # Test trading pairs
        self.trading_pairs = ['BTC/USD', 'ETH/USD', 'ADA/USD']
        
        # Create enhanced risk settings
        self.risk_settings = EnhancedRiskSettings(
            base_risk_per_trade=0.02,
            max_risk_per_trade=0.05,
            max_portfolio_exposure=0.80,
            max_single_pair_exposure=0.25,
            correlation_threshold=0.7,
            max_portfolio_drawdown=0.15
        )
        
        # Create risk manager
        self.risk_manager = EnhancedRiskManager(
            position_manager=self.mock_position_manager,
            data_manager=self.mock_data_manager,
            kraken_client=self.mock_kraken_client,
            trading_pairs=self.trading_pairs,
            settings=self.risk_settings
        )
        
        # Mock portfolio value
        self.risk_manager.base_risk_manager._get_portfolio_value = Mock(return_value=10000.0)
    
    def test_initialization(self):
        """Test risk manager initialization."""
        self.assertEqual(len(self.risk_manager.trading_pairs), 3)
        self.assertEqual(self.risk_manager.settings.base_risk_per_trade, 0.02)
        self.assertFalse(any(self.risk_manager.emergency_stops.values()))
    
    def test_validate_trade_basic(self):
        """Test basic trade validation."""
        # Mock data
        self.mock_data_manager.get_latest_data.return_value = pd.DataFrame({
            'close': [50000.0]
        })
        
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.1, "Valid")
        )
        
        # Mock position calculation
        with patch.object(self.risk_manager, '_calculate_dynamic_position_size') as mock_calc:
            mock_calc.return_value = PositionSizeCalculation(
                base_size=0.1, volatility_adjusted_size=0.08,
                correlation_adjusted_size=0.07, final_size=0.07,
                risk_per_trade=0.02, confidence_multiplier=0.8,
                adjustments_applied=[]
            )
            
            # Mock other methods
            with patch.object(self.risk_manager, '_assess_portfolio_impact', return_value=0.1):
                with patch.object(self.risk_manager, '_calculate_correlation_impact', return_value=0.3):
                    with patch.object(self.risk_manager, '_determine_risk_level', return_value=RiskLevel.LOW):
                        
                        assessment = self.risk_manager.validate_trade(
                            pair='BTC/USD',
                            side='buy',
                            quantity=0.1,
                            price=50000.0,
                            signal_confidence=0.8
                        )
                        
                        self.assertTrue(assessment.is_valid)
                        self.assertEqual(assessment.risk_level, RiskLevel.LOW)
                        self.assertEqual(assessment.recommended_size, 0.07)
    
    def test_validate_trade_emergency_stop(self):
        """Test trade validation with emergency stop active."""
        # Activate emergency stop
        self.risk_manager.emergency_stops[EmergencyStopReason.MAX_DRAWDOWN] = True
        
        assessment = self.risk_manager.validate_trade(
            pair='BTC/USD',
            side='buy',
            quantity=0.1,
            price=50000.0,
            signal_confidence=0.8
        )
        
        self.assertFalse(assessment.is_valid)
        self.assertIn("emergency_stop_active", assessment.risk_factors)
    
    def test_validate_trade_low_confidence(self):
        """Test trade validation with low confidence signal."""
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.1, "Valid")
        )
        
        with patch.object(self.risk_manager, '_calculate_dynamic_position_size') as mock_calc:
            mock_calc.return_value = PositionSizeCalculation(
                base_size=0.1, volatility_adjusted_size=0.08,
                correlation_adjusted_size=0.07, final_size=0.07,
                risk_per_trade=0.02, confidence_multiplier=0.3,
                adjustments_applied=[]
            )
            
            with patch.object(self.risk_manager, '_assess_portfolio_impact', return_value=0.1):
                with patch.object(self.risk_manager, '_calculate_correlation_impact', return_value=0.3):
                    with patch.object(self.risk_manager, '_determine_risk_level', return_value=RiskLevel.MEDIUM):
                        
                        assessment = self.risk_manager.validate_trade(
                            pair='BTC/USD',
                            side='buy',
                            quantity=0.1,
                            price=50000.0,
                            signal_confidence=0.3  # Low confidence
                        )
                        
                        self.assertFalse(assessment.is_valid)  # Below confidence threshold
    
    def test_calculate_position_size(self):
        """Test dynamic position size calculation."""
        # Mock volatility
        with patch.object(self.risk_manager, '_get_pair_volatility', return_value=0.5):
            with patch.object(self.risk_manager, 'adjust_for_correlation', return_value=0.08):
                
                calc = self.risk_manager.calculate_position_size(
                    pair='BTC/USD',
                    signal_confidence=0.8,
                    current_price=50000.0,
                    account_balance=10000.0
                )
                
                self.assertGreater(calc.final_size, 0)
                self.assertLessEqual(calc.final_size, calc.base_size)
                self.assertEqual(calc.confidence_multiplier, 0.8 ** 2)  # Squared confidence
    
    def test_calculate_position_size_zero_portfolio(self):
        """Test position size calculation with zero portfolio value."""
        self.risk_manager.base_risk_manager._get_portfolio_value = Mock(return_value=0.0)
        
        calc = self.risk_manager.calculate_position_size(
            pair='BTC/USD',
            signal_confidence=0.8,
            current_price=50000.0,
            account_balance=10000.0
        )
        
        self.assertEqual(calc.final_size, 0.0)
        self.assertIn("zero_portfolio_value", calc.adjustments_applied)
    
    def test_check_portfolio_risk(self):
        """Test portfolio risk assessment."""
        # Mock current positions
        mock_positions = {
            'BTC/USD': {'quantity': 0.1, 'price': 50000.0, 'value_usd': 5000.0, 'currency': 'BTC'},
            'ETH/USD': {'quantity': 2.0, 'price': 2000.0, 'value_usd': 4000.0, 'currency': 'ETH'}
        }
        
        with patch.object(self.risk_manager, '_get_current_positions', return_value=mock_positions):
            with patch.object(self.risk_manager, '_update_correlation_matrix'):
                with patch.object(self.risk_manager, '_calculate_portfolio_beta', return_value=1.2):
                    with patch.object(self.risk_manager, '_calculate_portfolio_var', return_value=500.0):
                        with patch.object(self.risk_manager, '_calculate_expected_shortfall', return_value=650.0):
                            with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
                                with patch.object(self.risk_manager, '_calculate_portfolio_sharpe_ratio', return_value=1.5):
                                    
                                    portfolio_risk = self.risk_manager.check_portfolio_risk()
                                    
                                    self.assertEqual(portfolio_risk.total_exposure_usd, 9000.0)
                                    self.assertEqual(len(portfolio_risk.exposure_by_pair), 2)
                                    self.assertEqual(portfolio_risk.beta_to_market, 1.2)
                                    self.assertEqual(portfolio_risk.value_at_risk_95, 500.0)
    
    def test_should_emergency_stop_drawdown(self):
        """Test emergency stop trigger for max drawdown."""
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.20):
            should_stop, reason = self.risk_manager.should_emergency_stop()
            
            self.assertTrue(should_stop)
            self.assertEqual(reason, EmergencyStopReason.MAX_DRAWDOWN)
            self.assertTrue(self.risk_manager.emergency_stops[EmergencyStopReason.MAX_DRAWDOWN])
    
    def test_should_emergency_stop_volatility_spike(self):
        """Test emergency stop trigger for volatility spike."""
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
            with patch.object(self.risk_manager, '_check_volatility_spike', return_value=True):
                should_stop, reason = self.risk_manager.should_emergency_stop()
                
                self.assertTrue(should_stop)
                self.assertEqual(reason, EmergencyStopReason.VOLATILITY_SPIKE)
    
    def test_should_emergency_stop_correlation_spike(self):
        """Test emergency stop trigger for correlation spike."""
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
            with patch.object(self.risk_manager, '_check_volatility_spike', return_value=False):
                with patch.object(self.risk_manager, '_check_correlation_spike', return_value=True):
                    should_stop, reason = self.risk_manager.should_emergency_stop()
                    
                    self.assertTrue(should_stop)
                    self.assertEqual(reason, EmergencyStopReason.PORTFOLIO_CORRELATION)
    
    def test_should_emergency_stop_consecutive_losses(self):
        """Test emergency stop trigger for consecutive losses."""
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
            with patch.object(self.risk_manager, '_check_volatility_spike', return_value=False):
                with patch.object(self.risk_manager, '_check_correlation_spike', return_value=False):
                    # Set consecutive losses
                    self.risk_manager.base_risk_manager.consecutive_losses = 6
                    
                    should_stop, reason = self.risk_manager.should_emergency_stop()
                    
                    self.assertTrue(should_stop)
                    self.assertEqual(reason, EmergencyStopReason.CONSECUTIVE_LOSSES)
    
    def test_should_emergency_stop_disabled(self):
        """Test emergency stop when disabled."""
        self.risk_settings.enable_emergency_stops = False
        
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.25):
            should_stop, reason = self.risk_manager.should_emergency_stop()
            
            self.assertFalse(should_stop)
            self.assertIsNone(reason)
    
    def test_adjust_for_correlation_high(self):
        """Test position size adjustment for high correlation."""
        with patch.object(self.risk_manager, '_calculate_correlation_impact', return_value=0.8):
            adjusted_size = self.risk_manager.adjust_for_correlation(
                pair='BTC/USD',
                proposed_size=0.1,
                current_price=50000.0
            )
            
            self.assertLess(adjusted_size, 0.1)  # Should be reduced
    
    def test_adjust_for_correlation_low(self):
        """Test position size adjustment for low correlation."""
        with patch.object(self.risk_manager, '_calculate_correlation_impact', return_value=0.3):
            adjusted_size = self.risk_manager.adjust_for_correlation(
                pair='BTC/USD',
                proposed_size=0.1,
                current_price=50000.0
            )
            
            self.assertEqual(adjusted_size, 0.1)  # Should remain unchanged
    
    def test_get_pair_volatility_cached(self):
        """Test volatility calculation with cached value."""
        # Set cached volatility
        self.risk_manager.volatility_cache['BTC/USD'] = (0.6, datetime.now())
        
        volatility = self.risk_manager._get_pair_volatility('BTC/USD')
        
        self.assertEqual(volatility, 0.6)
    
    def test_get_pair_volatility_calculated(self):
        """Test volatility calculation from historical data."""
        # Mock historical data
        dates = pd.date_range(start='2023-01-01', periods=30, freq='D')
        prices = np.random.normal(50000, 2000, 30)  # Random prices with volatility
        historical_data = pd.DataFrame({
            'close': prices
        }, index=dates)
        
        self.mock_data_manager.get_historical_data.return_value = historical_data
        
        volatility = self.risk_manager._get_pair_volatility('BTC/USD')
        
        self.assertGreater(volatility, 0)
        self.assertLess(volatility, 5.0)  # Reasonable volatility range
    
    def test_get_current_positions(self):
        """Test getting current positions."""
        # Mock balances
        btc_balance = CryptoBalance(currency='BTC', balance=0.1, available=0.1, hold=0.0)
        eth_balance = CryptoBalance(currency='ETH', balance=2.0, available=2.0, hold=0.0)
        
        self.mock_position_manager.get_crypto_balance.side_effect = lambda currency: {
            'BTC': btc_balance,
            'ETH': eth_balance,
            'ADA': None
        }.get(currency)
        
        # Mock price data
        btc_data = pd.DataFrame({'close': [50000.0]})
        eth_data = pd.DataFrame({'close': [2000.0]})
        ada_data = pd.DataFrame()  # Empty for ADA
        
        self.mock_data_manager.get_latest_data.side_effect = lambda pair, limit: {
            'BTC/USD': btc_data,
            'ETH/USD': eth_data,
            'ADA/USD': ada_data
        }.get(pair, pd.DataFrame())
        
        positions = self.risk_manager._get_current_positions()
        
        self.assertEqual(len(positions), 2)
        self.assertIn('BTC/USD', positions)
        self.assertIn('ETH/USD', positions)
        self.assertEqual(positions['BTC/USD']['value_usd'], 5000.0)
        self.assertEqual(positions['ETH/USD']['value_usd'], 4000.0)
    
    def test_update_correlation_matrix(self):
        """Test correlation matrix update."""
        # Mock price data for correlation calculation
        dates = pd.date_range(start='2023-01-01', periods=30, freq='D')
        
        # Create correlated price series
        base_returns = np.random.normal(0, 0.02, 30)
        btc_returns = base_returns + np.random.normal(0, 0.01, 30)
        eth_returns = base_returns * 0.8 + np.random.normal(0, 0.015, 30)
        ada_returns = np.random.normal(0, 0.03, 30)  # Uncorrelated
        
        btc_data = pd.Series(btc_returns, index=dates)
        eth_data = pd.Series(eth_returns, index=dates)
        ada_data = pd.Series(ada_returns, index=dates)
        
        def mock_get_historical_data(pair, start_time, end_time):
            if pair == 'BTC/USD':
                return pd.DataFrame({'close': np.cumprod(1 + btc_data)})
            elif pair == 'ETH/USD':
                return pd.DataFrame({'close': np.cumprod(1 + eth_data)})
            elif pair == 'ADA/USD':
                return pd.DataFrame({'close': np.cumprod(1 + ada_data)})
            return pd.DataFrame()
        
        self.mock_data_manager.get_historical_data.side_effect = mock_get_historical_data
        
        self.risk_manager._update_correlation_matrix()
        
        # Check that correlations were calculated
        self.assertGreater(len(self.risk_manager.correlation_matrix), 0)
        
        # BTC and ETH should be positively correlated
        btc_eth_corr = self.risk_manager.correlation_matrix.get(('BTC/USD', 'ETH/USD'))
        if btc_eth_corr is not None:
            self.assertGreater(btc_eth_corr, 0)
    
    def test_calculate_correlation_impact(self):
        """Test correlation impact calculation."""
        # Set up correlation matrix
        self.risk_manager.correlation_matrix = {
            ('BTC/USD', 'ETH/USD'): 0.8,
            ('ETH/USD', 'BTC/USD'): 0.8,
            ('BTC/USD', 'ADA/USD'): 0.3,
            ('ADA/USD', 'BTC/USD'): 0.3
        }
        
        # Mock current positions
        mock_positions = {
            'ETH/USD': {'value_usd': 4000.0}
        }
        
        with patch.object(self.risk_manager, '_get_current_positions', return_value=mock_positions):
            correlation_impact = self.risk_manager._calculate_correlation_impact(
                pair='BTC/USD',
                quantity=0.1,
                price=50000.0
            )
            
            self.assertGreater(correlation_impact, 0)
            self.assertLess(correlation_impact, 1.0)
    
    def test_determine_risk_level(self):
        """Test risk level determination."""
        with patch.object(self.risk_manager, '_get_pair_volatility', return_value=0.4):
            with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
                
                # Low risk scenario
                risk_level = self.risk_manager._determine_risk_level(
                    pair='BTC/USD',
                    quantity=0.01,  # Small position
                    price=50000.0,
                    signal_confidence=0.9,  # High confidence
                    portfolio_impact=0.1,  # Low impact
                    correlation_impact=0.2  # Low correlation
                )
                
                self.assertEqual(risk_level, RiskLevel.LOW)
                
                # High risk scenario
                risk_level = self.risk_manager._determine_risk_level(
                    pair='BTC/USD',
                    quantity=0.5,  # Large position
                    price=50000.0,
                    signal_confidence=0.3,  # Low confidence
                    portfolio_impact=0.8,  # High impact
                    correlation_impact=0.9  # High correlation
                )
                
                self.assertIn(risk_level, [RiskLevel.HIGH, RiskLevel.EXTREME])
    
    def test_check_volatility_spike(self):
        """Test volatility spike detection."""
        with patch.object(self.risk_manager, '_get_pair_volatility', return_value=1.5):
            with patch.object(self.risk_manager, '_get_historical_volatility', return_value=0.4):
                
                spike_detected = self.risk_manager._check_volatility_spike()
                
                self.assertTrue(spike_detected)  # 1.5 / 0.4 = 3.75 > threshold (3.0)
    
    def test_check_correlation_spike(self):
        """Test correlation spike detection."""
        # Set up high correlations
        self.risk_manager.correlation_matrix = {
            ('BTC/USD', 'ETH/USD'): 0.95,
            ('ETH/USD', 'BTC/USD'): 0.95,
            ('BTC/USD', 'ADA/USD'): 0.92,
            ('ADA/USD', 'BTC/USD'): 0.92,
            ('ETH/USD', 'ADA/USD'): 0.94,
            ('ADA/USD', 'ETH/USD'): 0.94
        }
        
        # Mock positions for all pairs
        mock_positions = {
            'BTC/USD': {'value_usd': 3000.0},
            'ETH/USD': {'value_usd': 3000.0},
            'ADA/USD': {'value_usd': 3000.0}
        }
        
        with patch.object(self.risk_manager, '_get_current_positions', return_value=mock_positions):
            spike_detected = self.risk_manager._check_correlation_spike()
            
            self.assertTrue(spike_detected)
    
    def test_reset_emergency_stops(self):
        """Test emergency stops reset."""
        # Activate some emergency stops
        self.risk_manager.emergency_stops[EmergencyStopReason.MAX_DRAWDOWN] = True
        self.risk_manager.emergency_stops[EmergencyStopReason.VOLATILITY_SPIKE] = True
        
        self.risk_manager.reset_emergency_stops()
        
        self.assertFalse(any(self.risk_manager.emergency_stops.values()))
    
    def test_get_risk_summary(self):
        """Test risk summary generation."""
        with patch.object(self.risk_manager, 'check_portfolio_risk') as mock_portfolio_risk:
            with patch.object(self.risk_manager, 'should_emergency_stop', return_value=(False, None)):
                
                mock_portfolio_risk.return_value = PortfolioRisk(
                    total_exposure_usd=8000.0,
                    exposure_by_pair={'BTC/USD': 5000.0, 'ETH/USD': 3000.0},
                    correlation_matrix={},
                    concentration_risk=0.4,
                    beta_to_market=1.2,
                    value_at_risk_95=400.0,
                    expected_shortfall=520.0,
                    max_drawdown=0.08,
                    sharpe_ratio=1.3,
                    risk_level=RiskLevel.MEDIUM
                )
                
                summary = self.risk_manager.get_risk_summary()
                
                self.assertIn('timestamp', summary)
                self.assertIn('portfolio_risk', summary)
                self.assertFalse(summary['emergency_stop_active'])
                self.assertIsNone(summary['emergency_stop_reason'])
    
    def test_update_portfolio_metrics(self):
        """Test portfolio metrics update."""
        initial_history_length = len(self.risk_manager.portfolio_value_history)
        
        self.risk_manager.update_portfolio_metrics()
        
        # Should have added one entry
        self.assertEqual(len(self.risk_manager.portfolio_value_history), initial_history_length + 1)
        
        # Check that base risk manager was updated
        self.risk_manager.base_risk_manager.update_portfolio_metrics.assert_called_once()


if __name__ == '__main__':
    unittest.main()