"""
Integration tests for Enhanced Risk Management system.

Tests the integration between enhanced risk manager, data manager, position manager,
and Kraken client for comprehensive risk management scenarios.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import time

from bot.enhanced_risk_manager import (
    EnhancedRiskManager, EnhancedRiskSettings, RiskLevel, EmergencyStopReason
)
from bot.crypto_risk_manager import CryptoRiskSettings
from bot.crypto_position_manager import CryptoPositionManager, CryptoBalance
from bot.enhanced_data_manager import EnhancedDataManager
from bot.kraken_client import KrakenClient


class TestEnhancedRiskManagementIntegration(unittest.TestCase):
    """Integration tests for enhanced risk management system."""
    
    def setUp(self):
        """Set up integration test environment."""
        # Create mock dependencies
        self.mock_kraken_client = Mock(spec=KrakenClient)
        self.mock_position_manager = Mock(spec=CryptoPositionManager)
        self.mock_data_manager = Mock(spec=EnhancedDataManager)
        
        # Test configuration
        self.trading_pairs = ['BTC/USD', 'ETH/USD', 'ADA/USD', 'DOT/USD']
        
        # Enhanced risk settings for testing
        self.risk_settings = EnhancedRiskSettings(
            base_risk_per_trade=0.02,
            max_risk_per_trade=0.05,
            min_risk_per_trade=0.005,
            max_portfolio_exposure=0.80,
            max_single_pair_exposure=0.25,
            max_correlated_exposure=0.40,
            correlation_threshold=0.7,
            max_portfolio_drawdown=0.15,
            daily_drawdown_limit=0.08,
            enable_emergency_stops=True,
            volatility_spike_threshold=3.0,
            correlation_spike_threshold=0.9,
            consecutive_loss_limit=5,
            confidence_threshold=0.6
        )
        
        # Create enhanced risk manager
        self.risk_manager = EnhancedRiskManager(
            position_manager=self.mock_position_manager,
            data_manager=self.mock_data_manager,
            kraken_client=self.mock_kraken_client,
            trading_pairs=self.trading_pairs,
            settings=self.risk_settings
        )
        
        # Mock portfolio value
        self.portfolio_value = 50000.0
        self.risk_manager.base_risk_manager._get_portfolio_value = Mock(
            return_value=self.portfolio_value
        )
    
    def _setup_mock_market_data(self):
        """Set up mock market data for testing."""
        # Create realistic price data
        dates = pd.date_range(start='2023-01-01', periods=60, freq='D')
        
        # BTC price data (base asset)
        btc_base_price = 45000
        btc_returns = np.random.normal(0.001, 0.03, 60)  # 3% daily volatility
        btc_prices = btc_base_price * np.cumprod(1 + btc_returns)
        
        # ETH price data (correlated with BTC)
        eth_base_price = 2800
        eth_correlation = 0.75
        eth_returns = (btc_returns * eth_correlation + 
                      np.random.normal(0, 0.02, 60) * (1 - eth_correlation))
        eth_prices = eth_base_price * np.cumprod(1 + eth_returns)
        
        # ADA price data (moderately correlated)
        ada_base_price = 0.45
        ada_correlation = 0.5
        ada_returns = (btc_returns * ada_correlation + 
                      np.random.normal(0, 0.04, 60) * (1 - ada_correlation))
        ada_prices = ada_base_price * np.cumprod(1 + ada_returns)
        
        # DOT price data (less correlated)
        dot_base_price = 6.5
        dot_correlation = 0.3
        dot_returns = (btc_returns * dot_correlation + 
                      np.random.normal(0, 0.035, 60) * (1 - dot_correlation))
        dot_prices = dot_base_price * np.cumprod(1 + dot_returns)
        
        # Create DataFrames
        self.market_data = {
            'BTC/USD': pd.DataFrame({
                'close': btc_prices,
                'volume': np.random.uniform(1000, 5000, 60),
                'high': btc_prices * 1.02,
                'low': btc_prices * 0.98,
                'open': btc_prices
            }, index=dates),
            
            'ETH/USD': pd.DataFrame({
                'close': eth_prices,
                'volume': np.random.uniform(2000, 8000, 60),
                'high': eth_prices * 1.025,
                'low': eth_prices * 0.975,
                'open': eth_prices
            }, index=dates),
            
            'ADA/USD': pd.DataFrame({
                'close': ada_prices,
                'volume': np.random.uniform(5000, 15000, 60),
                'high': ada_prices * 1.03,
                'low': ada_prices * 0.97,
                'open': ada_prices
            }, index=dates),
            
            'DOT/USD': pd.DataFrame({
                'close': dot_prices,
                'volume': np.random.uniform(1500, 6000, 60),
                'high': dot_prices * 1.025,
                'low': dot_prices * 0.975,
                'open': dot_prices
            }, index=dates)
        }
        
        # Configure mock data manager
        def mock_get_historical_data(pair, start_time, end_time):
            if pair in self.market_data:
                data = self.market_data[pair]
                mask = (data.index >= start_time) & (data.index <= end_time)
                return data.loc[mask]
            return pd.DataFrame()
        
        def mock_get_latest_data(pair, periods=1):
            if pair in self.market_data:
                return self.market_data[pair].tail(periods)
            return pd.DataFrame()
        
        self.mock_data_manager.get_historical_data.side_effect = mock_get_historical_data
        self.mock_data_manager.get_latest_data.side_effect = mock_get_latest_data
    
    def _setup_mock_positions(self, positions_config):
        """Set up mock positions based on configuration."""
        def mock_get_crypto_balance(currency):
            if currency in positions_config:
                config = positions_config[currency]
                return CryptoBalance(
                    currency=currency,
                    balance=config['balance'],
                    available=config['balance'],
                    hold=0.0
                )
            return None
        
        self.mock_position_manager.get_crypto_balance.side_effect = mock_get_crypto_balance
    
    def test_comprehensive_risk_assessment_scenario(self):
        """Test comprehensive risk assessment in a realistic trading scenario."""
        self._setup_mock_market_data()
        
        # Set up existing positions
        positions_config = {
            'BTC': {'balance': 0.5},  # ~$22,500 position
            'ETH': {'balance': 4.0},  # ~$11,200 position
        }
        self._setup_mock_positions(positions_config)
        
        # Mock base risk manager validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.1, "Valid")
        )
        
        # Test trade validation for new ADA position
        assessment = self.risk_manager.validate_trade(
            pair='ADA/USD',
            side='buy',
            quantity=5000,  # $2,250 position
            price=0.45,
            signal_confidence=0.8
        )
        
        # Should be valid trade with reasonable risk
        self.assertTrue(assessment.is_valid)
        self.assertIn(assessment.risk_level, [RiskLevel.LOW, RiskLevel.MEDIUM])
        self.assertGreater(assessment.recommended_size, 0)
        self.assertLessEqual(assessment.recommended_size, 5000)
        
        # Check portfolio risk
        portfolio_risk = self.risk_manager.check_portfolio_risk()
        self.assertGreater(portfolio_risk.total_exposure_usd, 0)
        self.assertLess(portfolio_risk.total_exposure_usd, self.portfolio_value)
        self.assertIn(portfolio_risk.risk_level, [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH])
    
    def test_correlation_based_position_sizing(self):
        """Test position sizing adjustments based on correlation analysis."""
        self._setup_mock_market_data()
        
        # Set up highly correlated positions (BTC and ETH)
        positions_config = {
            'BTC': {'balance': 0.8},  # Large BTC position
            'ETH': {'balance': 6.0},  # Large ETH position
        }
        self._setup_mock_positions(positions_config)
        
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.2, "Valid")
        )
        
        # Test adding another correlated position (should be reduced)
        assessment = self.risk_manager.validate_trade(
            pair='ADA/USD',  # Moderately correlated with BTC/ETH
            side='buy',
            quantity=10000,
            price=0.45,
            signal_confidence=0.8
        )
        
        # Position should be adjusted down due to correlation
        self.assertLess(assessment.recommended_size, 10000)
        self.assertGreater(assessment.correlation_impact, 0.3)
        
        # Test with uncorrelated asset (DOT) - should have less adjustment
        assessment_dot = self.risk_manager.validate_trade(
            pair='DOT/USD',
            side='buy',
            quantity=500,
            price=6.5,
            signal_confidence=0.8
        )
        
        # Should have lower correlation impact
        self.assertLess(assessment_dot.correlation_impact, assessment.correlation_impact)
    
    def test_volatility_based_position_sizing(self):
        """Test position sizing adjustments based on volatility."""
        self._setup_mock_market_data()
        
        # Create high volatility scenario by modifying market data
        high_vol_returns = np.random.normal(0, 0.08, 30)  # 8% daily volatility
        high_vol_prices = 45000 * np.cumprod(1 + high_vol_returns)
        
        dates = pd.date_range(start='2023-02-01', periods=30, freq='D')
        high_vol_data = pd.DataFrame({
            'close': high_vol_prices,
            'volume': np.random.uniform(1000, 5000, 30),
            'high': high_vol_prices * 1.05,
            'low': high_vol_prices * 0.95,
            'open': high_vol_prices
        }, index=dates)
        
        # Replace recent BTC data with high volatility data
        self.market_data['BTC/USD'] = pd.concat([
            self.market_data['BTC/USD'].iloc[:-30],
            high_vol_data
        ])
        
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.1, "Valid")
        )
        
        # Test trade in high volatility environment
        assessment = self.risk_manager.validate_trade(
            pair='BTC/USD',
            side='buy',
            quantity=0.1,
            price=45000,
            signal_confidence=0.8
        )
        
        # Position should be reduced due to high volatility
        self.assertLess(assessment.volatility_adjustment, 0.8)
        self.assertLess(assessment.recommended_size, 0.1)
    
    def test_emergency_stop_scenarios(self):
        """Test various emergency stop scenarios."""
        self._setup_mock_market_data()
        
        # Test 1: Drawdown emergency stop
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.18):
            should_stop, reason = self.risk_manager.should_emergency_stop()
            self.assertTrue(should_stop)
            self.assertEqual(reason, EmergencyStopReason.MAX_DRAWDOWN)
        
        # Test 2: Volatility spike emergency stop
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
            # Create extreme volatility scenario
            extreme_vol_returns = np.random.normal(0, 0.15, 10)  # 15% daily volatility
            extreme_vol_prices = 45000 * np.cumprod(1 + extreme_vol_returns)
            
            # Mock volatility methods
            with patch.object(self.risk_manager, '_get_pair_volatility', return_value=2.5):
                with patch.object(self.risk_manager, '_get_historical_volatility', return_value=0.6):
                    should_stop, reason = self.risk_manager.should_emergency_stop()
                    self.assertTrue(should_stop)
                    self.assertEqual(reason, EmergencyStopReason.VOLATILITY_SPIKE)
        
        # Test 3: Correlation spike emergency stop
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
            with patch.object(self.risk_manager, '_check_volatility_spike', return_value=False):
                # Set up extreme correlations
                self.risk_manager.correlation_matrix = {
                    ('BTC/USD', 'ETH/USD'): 0.95,
                    ('ETH/USD', 'BTC/USD'): 0.95,
                    ('BTC/USD', 'ADA/USD'): 0.93,
                    ('ADA/USD', 'BTC/USD'): 0.93,
                    ('ETH/USD', 'ADA/USD'): 0.94,
                    ('ADA/USD', 'ETH/USD'): 0.94,
                    ('BTC/USD', 'DOT/USD'): 0.91,
                    ('DOT/USD', 'BTC/USD'): 0.91
                }
                
                # Mock positions for all pairs
                positions_config = {
                    'BTC': {'balance': 0.5},
                    'ETH': {'balance': 4.0},
                    'ADA': {'balance': 8000},
                    'DOT': {'balance': 500}
                }
                self._setup_mock_positions(positions_config)
                
                should_stop, reason = self.risk_manager.should_emergency_stop()
                self.assertTrue(should_stop)
                self.assertEqual(reason, EmergencyStopReason.PORTFOLIO_CORRELATION)
        
        # Test 4: Consecutive losses emergency stop
        with patch.object(self.risk_manager, '_calculate_current_drawdown', return_value=0.05):
            with patch.object(self.risk_manager, '_check_volatility_spike', return_value=False):
                with patch.object(self.risk_manager, '_check_correlation_spike', return_value=False):
                    # Set consecutive losses
                    self.risk_manager.base_risk_manager.consecutive_losses = 6
                    
                    should_stop, reason = self.risk_manager.should_emergency_stop()
                    self.assertTrue(should_stop)
                    self.assertEqual(reason, EmergencyStopReason.CONSECUTIVE_LOSSES)
    
    def test_portfolio_rebalancing_scenario(self):
        """Test portfolio rebalancing with risk constraints."""
        self._setup_mock_market_data()
        
        # Set up unbalanced portfolio (too much concentration in BTC)
        positions_config = {
            'BTC': {'balance': 1.2},  # ~$54,000 position (>50% of portfolio)
        }
        self._setup_mock_positions(positions_config)
        
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.1, "Valid")
        )
        
        # Test adding more BTC (should be restricted due to concentration)
        assessment_btc = self.risk_manager.validate_trade(
            pair='BTC/USD',
            side='buy',
            quantity=0.2,
            price=45000,
            signal_confidence=0.8
        )
        
        # Should have high portfolio impact and potentially be restricted
        self.assertGreater(assessment_btc.portfolio_impact, 0.15)
        
        # Test diversifying with ETH (should be more favorable)
        assessment_eth = self.risk_manager.validate_trade(
            pair='ETH/USD',
            side='buy',
            quantity=5.0,
            price=2800,
            signal_confidence=0.8
        )
        
        # Should have better risk profile for diversification
        self.assertLess(assessment_eth.portfolio_impact, assessment_btc.portfolio_impact)
    
    def test_dynamic_risk_adjustment_over_time(self):
        """Test dynamic risk adjustment as market conditions change."""
        self._setup_mock_market_data()
        
        # Simulate changing market conditions over time
        test_scenarios = [
            {
                'name': 'Normal Market',
                'volatility_multiplier': 1.0,
                'correlation_increase': 0.0,
                'expected_risk_level': [RiskLevel.LOW, RiskLevel.MEDIUM]
            },
            {
                'name': 'High Volatility Market',
                'volatility_multiplier': 2.5,
                'correlation_increase': 0.1,
                'expected_risk_level': [RiskLevel.MEDIUM, RiskLevel.HIGH]
            },
            {
                'name': 'Crisis Market',
                'volatility_multiplier': 4.0,
                'correlation_increase': 0.3,
                'expected_risk_level': [RiskLevel.HIGH, RiskLevel.EXTREME]
            }
        ]
        
        positions_config = {
            'BTC': {'balance': 0.3},
            'ETH': {'balance': 2.0}
        }
        self._setup_mock_positions(positions_config)
        
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.1, "Valid")
        )
        
        for scenario in test_scenarios:
            with self.subTest(scenario=scenario['name']):
                # Adjust volatility
                with patch.object(self.risk_manager, '_get_pair_volatility') as mock_vol:
                    mock_vol.return_value = 0.5 * scenario['volatility_multiplier']
                    
                    # Adjust correlations
                    base_correlations = {
                        ('BTC/USD', 'ETH/USD'): 0.75,
                        ('ETH/USD', 'BTC/USD'): 0.75,
                        ('BTC/USD', 'ADA/USD'): 0.5,
                        ('ADA/USD', 'BTC/USD'): 0.5
                    }
                    
                    adjusted_correlations = {}
                    for key, value in base_correlations.items():
                        adjusted_correlations[key] = min(0.95, value + scenario['correlation_increase'])
                    
                    self.risk_manager.correlation_matrix = adjusted_correlations
                    
                    # Test trade assessment
                    assessment = self.risk_manager.validate_trade(
                        pair='ADA/USD',
                        side='buy',
                        quantity=2000,
                        price=0.45,
                        signal_confidence=0.7
                    )
                    
                    # Risk level should increase with market stress
                    self.assertIn(assessment.risk_level, scenario['expected_risk_level'])
                    
                    # Position size should decrease with higher risk
                    if scenario['volatility_multiplier'] > 2.0:
                        self.assertLess(assessment.volatility_adjustment, 0.7)
    
    def test_multi_pair_trading_coordination(self):
        """Test coordinated risk management across multiple trading pairs."""
        self._setup_mock_market_data()
        
        # Set up moderate positions across multiple pairs
        positions_config = {
            'BTC': {'balance': 0.4},
            'ETH': {'balance': 3.0},
            'ADA': {'balance': 4000}
        }
        self._setup_mock_positions(positions_config)
        
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 0.1, "Valid")
        )
        
        # Test simultaneous trade assessments
        trade_requests = [
            {'pair': 'BTC/USD', 'quantity': 0.1, 'price': 45000, 'confidence': 0.8},
            {'pair': 'ETH/USD', 'quantity': 2.0, 'price': 2800, 'confidence': 0.7},
            {'pair': 'DOT/USD', 'quantity': 300, 'price': 6.5, 'confidence': 0.75},
            {'pair': 'ADA/USD', 'quantity': 3000, 'price': 0.45, 'confidence': 0.6}
        ]
        
        assessments = []
        for request in trade_requests:
            assessment = self.risk_manager.validate_trade(
                pair=request['pair'],
                side='buy',
                quantity=request['quantity'],
                price=request['price'],
                signal_confidence=request['confidence']
            )
            assessments.append((request['pair'], assessment))
        
        # Check that risk management is coordinated
        valid_trades = [pair for pair, assessment in assessments if assessment.is_valid]
        total_exposure = sum(
            assessment.recommended_size * request['price']
            for (pair, assessment), request in zip(assessments, trade_requests)
            if assessment.is_valid
        )
        
        # Total exposure should not exceed portfolio limits
        self.assertLess(total_exposure, self.portfolio_value * self.risk_settings.max_portfolio_exposure)
        
        # At least some trades should be valid in normal conditions
        self.assertGreater(len(valid_trades), 0)
    
    def test_risk_metrics_calculation_accuracy(self):
        """Test accuracy of risk metrics calculations."""
        self._setup_mock_market_data()
        
        # Set up known positions for testing
        positions_config = {
            'BTC': {'balance': 0.5},
            'ETH': {'balance': 4.0},
            'ADA': {'balance': 5000}
        }
        self._setup_mock_positions(positions_config)
        
        # Calculate portfolio risk
        portfolio_risk = self.risk_manager.check_portfolio_risk()
        
        # Verify calculations
        expected_btc_value = 0.5 * self.market_data['BTC/USD'].iloc[-1]['close']
        expected_eth_value = 4.0 * self.market_data['ETH/USD'].iloc[-1]['close']
        expected_ada_value = 5000 * self.market_data['ADA/USD'].iloc[-1]['close']
        expected_total = expected_btc_value + expected_eth_value + expected_ada_value
        
        self.assertAlmostEqual(portfolio_risk.total_exposure_usd, expected_total, delta=100)
        
        # Check individual exposures
        self.assertAlmostEqual(
            portfolio_risk.exposure_by_pair['BTC/USD'], 
            expected_btc_value, 
            delta=50
        )
        self.assertAlmostEqual(
            portfolio_risk.exposure_by_pair['ETH/USD'], 
            expected_eth_value, 
            delta=50
        )
        self.assertAlmostEqual(
            portfolio_risk.exposure_by_pair['ADA/USD'], 
            expected_ada_value, 
            delta=50
        )
        
        # Concentration risk should be reasonable
        self.assertGreater(portfolio_risk.concentration_risk, 0)
        self.assertLess(portfolio_risk.concentration_risk, 1.0)
        
        # VaR should be positive and reasonable
        self.assertGreater(portfolio_risk.value_at_risk_95, 0)
        self.assertLess(portfolio_risk.value_at_risk_95, expected_total * 0.5)
    
    def test_performance_under_stress(self):
        """Test system performance under stress conditions."""
        self._setup_mock_market_data()
        
        # Set up large number of positions
        positions_config = {f'ASSET{i}': {'balance': 100} for i in range(10)}
        self._setup_mock_positions(positions_config)
        
        # Mock additional trading pairs
        extended_pairs = [f'ASSET{i}/USD' for i in range(10)]
        self.risk_manager.trading_pairs = extended_pairs
        
        # Mock base validation
        self.risk_manager.base_risk_manager.validate_position_size = Mock(
            return_value=(True, 100, "Valid")
        )
        
        # Test rapid-fire trade validations
        start_time = time.time()
        
        for i in range(50):  # 50 rapid trade assessments
            assessment = self.risk_manager.validate_trade(
                pair=f'ASSET{i % 10}/USD',
                side='buy',
                quantity=50,
                price=10.0,
                signal_confidence=0.7
            )
            # Should complete without errors
            self.assertIsNotNone(assessment)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete within reasonable time (less than 5 seconds)
        self.assertLess(execution_time, 5.0)
        
        # Test portfolio risk calculation under stress
        start_time = time.time()
        portfolio_risk = self.risk_manager.check_portfolio_risk()
        end_time = time.time()
        
        self.assertLess(end_time - start_time, 2.0)  # Should complete quickly
        self.assertIsNotNone(portfolio_risk)


if __name__ == '__main__':
    unittest.main()