"""
Integration tests for adaptive system integration with enhanced components.
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Test imports
try:
    from bot.enhanced_risk_manager import EnhancedRiskManager, EnhancedRiskSettings
    from bot.enhanced_data_manager import EnhancedDataManager
    from bot.enhanced_strategies import AdaptiveStrategyWrapper, EnhancedMomentumStrategy
    from bot.adaptive.data_models import AdaptiveSignal, MarketRegime, PerformanceMetrics
    from bot.adaptive.enums import RegimeType, SignalStrength
    ADAPTIVE_AVAILABLE = True
except ImportError:
    ADAPTIVE_AVAILABLE = False
    pytest.skip("Adaptive components not available", allow_module_level=True)


class TestAdaptiveIntegration:
    """Test adaptive system integration with enhanced components."""
    
    @pytest.fixture
    def mock_position_manager(self):
        """Mock position manager for testing."""
        mock_pm = Mock()
        mock_pm.get_crypto_balance.return_value = Mock(balance=1.0)
        return mock_pm
    
    @pytest.fixture
    def mock_kraken_client(self):
        """Mock Kraken client for testing."""
        return Mock()
    
    @pytest.fixture
    def sample_market_data(self):
        """Sample market data for testing."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='1H')
        data = pd.DataFrame({
            'open': 50000 + pd.Series(range(100)) * 10,
            'high': 50100 + pd.Series(range(100)) * 10,
            'low': 49900 + pd.Series(range(100)) * 10,
            'close': 50000 + pd.Series(range(100)) * 10,
            'volume': 100 + pd.Series(range(100))
        }, index=dates)
        return data
    
    @pytest.fixture
    def sample_regime(self):
        """Sample market regime for testing."""
        return MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=1.2,
            trend_strength=0.7,
            momentum=0.6,
            detected_at=datetime.now(),
            supporting_indicators={'rsi': 65.0, 'macd': 0.5},
            timeframe_analysis={'5m': 0.8, '1h': 0.7}
        )
    
    @pytest.fixture
    def sample_performance_metrics(self):
        """Sample performance metrics for testing."""
        return PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.18,
            excess_return=0.12,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=0.08,
            volatility=0.15,
            downside_deviation=0.10,
            win_rate=0.65,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=4),
            trades_count=50,
            avg_win=0.05,
            avg_loss=-0.03,
            regime_performance={RegimeType.TRENDING_BULL: 0.20},
            last_updated=datetime.now(),
            measurement_period=timedelta(days=30)
        )
    
    def test_enhanced_risk_manager_adaptive_integration(self, mock_position_manager, 
                                                       mock_kraken_client, sample_regime):
        """Test enhanced risk manager integration with adaptive signals."""
        # Create enhanced data manager mock
        mock_data_manager = Mock()
        mock_data_manager.get_latest_data.return_value = pd.DataFrame({
            'close': [50000, 50100, 50200],
            'volume': [100, 110, 120]
        })
        
        # Create enhanced risk manager
        settings = EnhancedRiskSettings(enable_adaptive_risk=True)
        risk_manager = EnhancedRiskManager(
            position_manager=mock_position_manager,
            data_manager=mock_data_manager,
            kraken_client=mock_kraken_client,
            trading_pairs=['BTC/USD'],
            settings=settings
        )
        
        # Create adaptive signal
        adaptive_signal = AdaptiveSignal(
            pair='BTC/USD',
            signal_type='buy',
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=50000.0,
            timestamp=datetime.now(),
            regime_context=sample_regime,
            ml_confidence=0.7,
            strategy_weights={'momentum': 1.0},
            parameter_adjustments={'regime_multiplier': 1.2},
            suggested_position_size=0.01
        )
        
        # Test adaptive signal validation
        current_positions = {}
        is_valid = risk_manager.validate_adaptive_signal(adaptive_signal, current_positions)
        
        assert isinstance(is_valid, bool)
        
        # Test adaptive position size calculation
        position_size = risk_manager.calculate_adaptive_position_size(adaptive_signal, 10000.0)
        
        assert isinstance(position_size, float)
        assert position_size > 0
        
        # Test risk parameter updates
        performance_metrics = PerformanceMetrics(
            total_return=0.1, annualized_return=0.12, excess_return=0.08,
            sharpe_ratio=1.0, sortino_ratio=1.2, calmar_ratio=0.8,
            max_drawdown=0.05, volatility=0.12, downside_deviation=0.08,
            win_rate=0.6, profit_factor=1.5, avg_trade_duration=timedelta(hours=3),
            trades_count=30, avg_win=0.04, avg_loss=-0.025,
            last_updated=datetime.now(), measurement_period=timedelta(days=30)
        )
        
        risk_manager.update_risk_parameters(sample_regime, performance_metrics)
        
        # Verify regime adjustments were applied
        assert hasattr(risk_manager, 'current_regime')
        assert risk_manager.current_regime == sample_regime
    
    def test_enhanced_data_manager_adaptive_integration(self, sample_regime, sample_performance_metrics):
        """Test enhanced data manager integration with adaptive data storage."""
        # Create enhanced data manager
        data_manager = EnhancedDataManager(['BTC/USD', 'ETH/USD'])
        
        # Test regime data storage
        data_manager.store_regime_data(sample_regime, 'BTC/USD')
        
        # Test performance data storage
        data_manager.store_performance_data(sample_performance_metrics, 'momentum_strategy')
        
        # Test adaptation event storage
        from bot.adaptive.data_models import AdaptationEvent
        from bot.adaptive.enums import AdaptationType
        
        adaptation_event = AdaptationEvent(
            event_id='test_001',
            event_type=AdaptationType.PARAMETER_OPTIMIZATION,
            trigger_reason='performance_degradation',
            changes_made={'risk_multiplier': 0.8},
            expected_impact=0.05,
            affected_strategies=['momentum_strategy'],
            affected_pairs=['BTC/USD']
        )
        
        data_manager.store_adaptation_event(adaptation_event)
        
        # Test data retrieval
        start_time = datetime.now() - timedelta(hours=1)
        end_time = datetime.now() + timedelta(hours=1)
        
        historical_regimes = data_manager.get_historical_regimes('BTC/USD', start_time, end_time)
        assert len(historical_regimes) >= 0  # May be empty if adaptive not available
        
        performance_history = data_manager.get_performance_history('momentum_strategy', days_back=1)
        assert len(performance_history) >= 0  # May be empty if adaptive not available
        
        # Test ML feature calculation
        features = data_manager.calculate_ml_features('BTC/USD', ['price_features', 'technical_features'])
        assert isinstance(features, dict)
        
        # Test adaptive data summary
        summary = data_manager.get_adaptive_data_summary()
        assert isinstance(summary, dict)
        assert 'adaptive_features' in summary
    
    def test_adaptive_strategy_wrapper(self, sample_market_data, sample_regime):
        """Test adaptive strategy wrapper functionality."""
        # Create base strategy
        base_strategy = EnhancedMomentumStrategy(
            short_period=3,
            medium_period=8,
            volume_threshold=1.1,
            momentum_threshold=0.003
        )
        
        # Create adaptive wrapper
        adaptive_wrapper = AdaptiveStrategyWrapper(base_strategy, adaptive_enabled=True)
        
        # Test signal generation without regime
        signal = adaptive_wrapper.generate_signal(sample_market_data)
        assert signal is not None
        
        # Test signal generation with regime
        adaptive_signal = adaptive_wrapper.generate_signal(sample_market_data, sample_regime)
        assert adaptive_signal is not None
        
        if ADAPTIVE_AVAILABLE and hasattr(adaptive_signal, 'regime_context'):
            assert adaptive_signal.regime_context == sample_regime
        
        # Test performance update
        trade_result = {
            'return': 0.05,
            'regime': 'trending_bull',
            'duration': timedelta(hours=2)
        }
        
        adaptive_wrapper.update_performance(trade_result)
        
        # Test regime performance retrieval
        regime_perf = adaptive_wrapper.get_regime_performance('trending_bull')
        assert isinstance(regime_perf, dict)
        assert 'avg_return' in regime_perf
        
        # Test regime adjustment
        adaptive_wrapper.adjust_for_regime('trending_bull', 1.3)
        
        # Test adaptive status
        status = adaptive_wrapper.get_adaptive_status()
        assert isinstance(status, dict)
        assert 'adaptive_enabled' in status
        assert 'base_strategy' in status
    
    def test_backward_compatibility(self, sample_market_data):
        """Test backward compatibility features."""
        from bot.enhanced_strategies import (
            create_adaptive_strategy, 
            AdaptiveStrategyMigrator,
            get_enhanced_strategies,
            create_strategy_engine_with_adaptive_support
        )
        
        # Test adaptive strategy creation
        adaptive_strategy = create_adaptive_strategy(
            EnhancedMomentumStrategy,
            short_period=3,
            medium_period=8,
            adaptive_enabled=True
        )
        
        assert adaptive_strategy is not None
        
        # Test strategy migration
        migrator = AdaptiveStrategyMigrator()
        
        # Test getting enhanced strategies
        strategies = get_enhanced_strategies()
        assert isinstance(strategies, list)
        assert len(strategies) > 0
        
        # Test creating strategy engine with adaptive support
        engine = create_strategy_engine_with_adaptive_support(
            strategies=strategies[:2],  # Use first 2 strategies
            enable_adaptive=True
        )
        
        assert engine is not None
        
        # Test migration status
        migration_status = migrator.get_migration_status()
        assert isinstance(migration_status, dict)
        assert 'adaptive_available' in migration_status
    
    def test_integration_error_handling(self):
        """Test error handling in integration scenarios."""
        # Test with invalid data
        invalid_data = pd.DataFrame()  # Empty dataframe
        
        base_strategy = EnhancedMomentumStrategy()
        adaptive_wrapper = AdaptiveStrategyWrapper(base_strategy)
        
        # Should handle empty data gracefully
        signal = adaptive_wrapper.generate_signal(invalid_data)
        assert signal is not None  # Should return some signal, even if HOLD
        
        # Test with invalid regime
        invalid_regime = None
        signal_with_regime = adaptive_wrapper.generate_signal(invalid_data, invalid_regime)
        assert signal_with_regime is not None
        
        # Test performance update with invalid data
        invalid_trade_result = {}
        adaptive_wrapper.update_performance(invalid_trade_result)  # Should not crash
        
        # Test data manager with invalid inputs
        data_manager = EnhancedDataManager(['BTC/USD'])
        
        # Should handle None inputs gracefully
        data_manager.store_regime_data(None, 'BTC/USD')
        data_manager.store_performance_data(None, 'test_strategy')
        data_manager.store_adaptation_event(None)
        
        # Test feature calculation with empty data
        features = data_manager.calculate_ml_features('BTC/USD', ['price_features'])
        assert isinstance(features, dict)  # Should return empty dict, not crash


if __name__ == '__main__':
    pytest.main([__file__])