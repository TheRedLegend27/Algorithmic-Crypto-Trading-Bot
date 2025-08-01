"""
Integration tests for the main adaptive bot application.

These tests verify that all components work together correctly and that
the main application can start up, run cycles, and shut down gracefully.
"""
import asyncio
import pytest
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import pandas as pd
import numpy as np

from bot.adaptive.adaptive_bot_main import AdaptiveBotMain, AdaptiveBotConfig, SystemHealth
from bot.adaptive.data_models import MarketRegime, AdaptiveSignal, PerformanceMetrics
from bot.adaptive.enums import RegimeType, SignalStrength


class TestAdaptiveBotMainIntegration:
    """Integration tests for the main adaptive bot application."""
    
    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        return AdaptiveBotConfig(
            trading_pairs=["BTC/USD"],
            paper_trading=True,
            initial_capital=1000.0,
            adaptation_enabled=True,
            adaptation_frequency_minutes=1,  # Fast for testing
            health_check_interval_seconds=1,
            state_persistence_interval_minutes=1
        )
    
    @pytest.fixture
    def mock_market_data(self):
        """Create mock market data."""
        dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
        data = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.uniform(40000, 45000, 100),
            'high': np.random.uniform(45000, 50000, 100),
            'low': np.random.uniform(35000, 40000, 100),
            'close': np.random.uniform(40000, 45000, 100),
            'volume': np.random.uniform(100, 1000, 100)
        })
        data['close'] = data['close'].cumsum() / 100 + 40000  # Trending data
        return data
    
    @pytest.fixture
    def mock_regime(self):
        """Create mock market regime."""
        return MarketRegime(
            regime_type=RegimeType.TRENDING_BULL,
            confidence=0.8,
            volatility_level=0.6,
            trend_strength=0.7,
            momentum=0.5,
            detected_at=datetime.now(),
            supporting_indicators={'rsi': 65.0, 'macd': 0.5}
        )
    
    @pytest.fixture
    def mock_signal(self):
        """Create mock adaptive signal."""
        return AdaptiveSignal(
            pair="BTC/USD",
            signal_type="buy",
            strength=SignalStrength.STRONG,
            confidence=0.8,
            price=45000.0,
            timestamp=datetime.now(),
            regime_context=MarketRegime(
                regime_type=RegimeType.TRENDING_BULL,
                confidence=0.8,
                volatility_level=0.6,
                trend_strength=0.7,
                momentum=0.5,
                detected_at=datetime.now()
            ),
            ml_confidence=0.75,
            strategy_weights={'momentum': 0.6, 'mean_reversion': 0.4}
        )
    
    @pytest.mark.asyncio
    async def test_bot_initialization(self, test_config, mock_market_data):
        """Test that the bot initializes all components correctly."""
        # Create mock classes that return mock instances
        mock_data_manager_class = Mock()
        mock_data_manager_instance = Mock()
        mock_data_manager_instance.initialize = AsyncMock()
        mock_data_manager_instance.get_market_data = AsyncMock(return_value=mock_market_data)
        mock_data_manager_class.return_value = mock_data_manager_instance
        
        with patch.multiple(
            'bot.adaptive.adaptive_bot_main',
            EnhancedDataManager=mock_data_manager_class,
            EnhancedRiskManager=Mock(),
            MarketRegimeDetector=Mock(),
            AdaptiveStrategyEngine=Mock(),
            MLEngine=Mock(),
            ParameterOptimizer=Mock(),
            PerformanceAnalyzer=Mock(),
            AdaptationController=Mock(),
            MonitoringDashboard=Mock(),
            AlertingSystem=Mock(),
            PaperTradingEngine=Mock(),
            AdaptiveConfig=Mock(),
            KrakenClient=Mock()
        ):
            bot = AdaptiveBotMain(test_config)
            
            success = await bot.initialize_components()
            assert success
            assert bot.health.component_status["data_manager"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_bot_startup_and_shutdown(self, test_config):
        """Test bot startup and graceful shutdown."""
        with patch.multiple(
            'bot.adaptive.adaptive_bot_main',
            EnhancedDataManager=Mock(),
            EnhancedRiskManager=Mock(),
            MarketRegimeDetector=Mock(),
            AdaptiveStrategyEngine=Mock(),
            MLEngine=Mock(),
            ParameterOptimizer=Mock(),
            PerformanceAnalyzer=Mock(),
            AdaptationController=Mock(),
            MonitoringDashboard=Mock(),
            AlertingSystem=Mock(),
            PaperTradingEngine=Mock(),
            AdaptiveConfig=Mock()
        ):
            bot = AdaptiveBotMain(test_config)
            
            # Mock component initialization
            with patch.object(bot, 'initialize_components', return_value=True):
                with patch.object(bot, '_load_state'):
                    with patch.object(bot, '_start_background_tasks'):
                        success = await bot.start()
                        assert success
                        assert bot.is_running
            
            # Test shutdown
            with patch.object(bot, '_save_state'):
                await bot.shutdown()
                assert not bot.is_running
                assert bot.shutdown_requested
    
    @pytest.mark.asyncio
    async def test_trading_cycle_execution(self, test_config, mock_market_data, mock_regime, mock_signal):
        """Test execution of a complete trading cycle."""
        bot = AdaptiveBotMain(test_config)
        
        # Mock all components
        bot.data_manager = Mock()
        bot.data_manager.get_market_data = AsyncMock(return_value=mock_market_data)
        bot.data_manager.store_regime_data = Mock()
        
        bot.regime_detector = Mock()
        bot.regime_detector.detect_regime = Mock(return_value=mock_regime)
        
        bot.strategy_engine = Mock()
        bot.strategy_engine.execute_adaptive_signal = AsyncMock(return_value=mock_signal)
        
        bot.risk_manager = Mock()
        bot.risk_manager.validate_signal = Mock(return_value=True)
        
        bot.paper_trading_engine = Mock()
        bot.paper_trading_engine.execute_trade = AsyncMock(return_value={'status': 'executed'})
        
        # Execute trading cycle
        await bot._execute_pair_trading_cycle("BTC/USD")
        
        # Verify calls
        bot.data_manager.get_market_data.assert_called_once_with("BTC/USD", limit=200)
        bot.regime_detector.detect_regime.assert_called_once()
        bot.strategy_engine.execute_adaptive_signal.assert_called_once()
        bot.risk_manager.validate_signal.assert_called_once()
        bot.paper_trading_engine.execute_trade.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_adaptation_execution(self, test_config):
        """Test adaptation execution logic."""
        bot = AdaptiveBotMain(test_config)
        
        # Mock components
        bot.performance_analyzer = Mock()
        mock_metrics = PerformanceMetrics(
            total_return=-0.08,  # Below threshold
            annualized_return=-0.15,
            excess_return=-0.05,
            sharpe_ratio=-0.5,
            sortino_ratio=-0.3,
            calmar_ratio=-0.2,
            max_drawdown=-0.12,
            volatility=0.25,
            downside_deviation=0.18,
            win_rate=0.35,
            profit_factor=0.8,
            avg_trade_duration=timedelta(hours=2),
            trades_count=50,
            avg_win=100.0,
            avg_loss=-80.0
        )
        bot.performance_analyzer.analyze_strategy_performance = AsyncMock(return_value=mock_metrics)
        
        bot.adaptation_controller = Mock()
        bot.adaptation_controller.should_adapt = Mock(return_value=True)
        bot.adaptation_controller.execute_adaptation = Mock(return_value=True)
        
        bot.alerting_system = Mock()
        bot.alerting_system.send_adaptation_alert = AsyncMock()
        
        # Set last adaptation time to allow new adaptation
        bot.last_adaptation_time = datetime.now() - timedelta(hours=2)
        
        # Execute adaptation check
        await bot._check_and_execute_adaptations()
        
        # Verify adaptation was triggered
        bot.adaptation_controller.should_adapt.assert_called_once()
        bot.adaptation_controller.execute_adaptation.assert_called_once()
        assert len(bot.adaptation_history) > 0
    
    @pytest.mark.asyncio
    async def test_state_persistence(self, test_config):
        """Test state saving and loading."""
        with tempfile.TemporaryDirectory() as temp_dir:
            bot = AdaptiveBotMain(test_config)
            bot.state_file = Path(temp_dir) / "test_state.json"
            
            # Set some state
            bot.cycle_count = 42
            bot.last_adaptation_time = datetime.now()
            bot.health.error_count = 2
            bot.health.warning_count = 5
            
            # Save state
            await bot._save_state()
            assert bot.state_file.exists()
            
            # Create new bot and load state
            new_bot = AdaptiveBotMain(test_config)
            new_bot.state_file = bot.state_file
            await new_bot._load_state()
            
            assert new_bot.cycle_count == 42
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self, test_config):
        """Test health monitoring functionality."""
        bot = AdaptiveBotMain(test_config)
        
        # Test initial health
        assert bot.health.is_healthy()
        assert bot.health.overall_status == "healthy"
        
        # Add errors and test health degradation
        bot.health.add_error("test_component", "test error")
        assert bot.health.error_count == 1
        
        bot.health.add_error("test_component2", "another error")
        bot.health.add_error("test_component3", "third error")
        assert bot.health.overall_status == "degraded"
        
        # Add more errors to trigger critical status
        for i in range(4, 7):
            bot.health.add_error(f"test_component{i}", f"error {i}")
        assert bot.health.overall_status == "critical"
    
    @pytest.mark.asyncio
    async def test_multi_pair_coordination(self, test_config, mock_market_data, mock_regime, mock_signal):
        """Test coordination across multiple trading pairs."""
        # Configure for multiple pairs
        test_config.trading_pairs = ["BTC/USD", "ETH/USD", "SOL/USD"]
        bot = AdaptiveBotMain(test_config)
        
        # Mock components for all pairs
        bot.data_manager = Mock()
        bot.data_manager.get_market_data = AsyncMock(return_value=mock_market_data)
        bot.data_manager.store_regime_data = Mock()
        
        bot.regime_detector = Mock()
        bot.regime_detector.detect_regime = Mock(return_value=mock_regime)
        
        bot.strategy_engine = Mock()
        bot.strategy_engine.execute_adaptive_signal = AsyncMock(return_value=mock_signal)
        
        bot.risk_manager = Mock()
        bot.risk_manager.validate_signal = Mock(return_value=True)
        
        bot.paper_trading_engine = Mock()
        bot.paper_trading_engine.execute_trade = AsyncMock(return_value={'status': 'executed'})
        
        # Initialize portfolio optimizer
        from bot.adaptive.portfolio_optimizer import PortfolioOptimizer
        bot.portfolio_optimizer = PortfolioOptimizer()
        
        # Execute trading cycle for all pairs
        await bot._execute_trading_cycle()
        
        # Verify all pairs were processed (may be called multiple times due to portfolio optimization)
        assert bot.data_manager.get_market_data.call_count >= 3
        assert bot.regime_detector.detect_regime.call_count == 3
        assert bot.strategy_engine.execute_adaptive_signal.call_count == 3
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self, test_config, mock_market_data):
        """Test error handling and recovery mechanisms."""
        bot = AdaptiveBotMain(test_config)
        
        # Mock components with some failures
        bot.data_manager = Mock()
        bot.data_manager.get_market_data = AsyncMock(side_effect=[
            Exception("Network error"),  # First call fails
            mock_market_data,  # Second call succeeds
        ])
        
        bot.regime_detector = Mock()
        bot.regime_detector.detect_regime = Mock(return_value=MarketRegime(
            regime_type=RegimeType.UNCERTAIN,
            confidence=0.3,
            volatility_level=0.8,
            trend_strength=0.0,
            momentum=0.0,
            detected_at=datetime.now()
        ))
        
        # First cycle should handle the error gracefully
        await bot._execute_trading_cycle()
        assert bot.health.error_count > 0
        
        # Second cycle should succeed
        await bot._execute_trading_cycle()
        # Should still have the error count from first cycle
        assert bot.health.error_count > 0
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, test_config):
        """Test integration with performance monitoring."""
        bot = AdaptiveBotMain(test_config)
        
        # Mock monitoring dashboard
        bot.monitoring_dashboard = Mock()
        bot.monitoring_dashboard.update_metrics = AsyncMock()
        
        # Mock performance analyzer
        bot.performance_analyzer = Mock()
        bot.performance_analyzer.analyze_strategy_performance = AsyncMock(
            return_value=PerformanceMetrics(
                total_return=0.05,
                annualized_return=0.15,
                excess_return=0.02,
                sharpe_ratio=1.2,
                sortino_ratio=1.5,
                calmar_ratio=0.8,
                max_drawdown=-0.03,
                volatility=0.15,
                downside_deviation=0.08,
                win_rate=0.65,
                profit_factor=1.8,
                avg_trade_duration=timedelta(hours=1),
                trades_count=100,
                avg_win=150.0,
                avg_loss=-85.0
            )
        )
        
        # Test performance monitoring
        await bot._check_and_execute_adaptations()
        
        # Verify performance was analyzed
        bot.performance_analyzer.analyze_strategy_performance.assert_called()
    
    def test_status_reporting(self, test_config):
        """Test status and health check reporting."""
        bot = AdaptiveBotMain(test_config)
        bot.is_running = True
        bot.cycle_count = 100
        bot.health.uptime_seconds = 3600
        
        # Test status report
        status = bot.get_status()
        assert status['is_running'] is True
        assert status['cycle_count'] == 100
        assert status['uptime_seconds'] == 3600
        assert 'health' in status
        assert 'config' in status
        
        # Test health check
        health_check = bot.get_health_check()
        assert 'status' in health_check
        assert 'timestamp' in health_check
        assert 'uptime_seconds' in health_check
        assert 'components' in health_check
    
    @pytest.mark.asyncio
    async def test_component_integration_validation(self, test_config, mock_market_data, mock_regime):
        """Test validation of component integration."""
        bot = AdaptiveBotMain(test_config)
        
        # Mock components for validation
        bot.data_manager = Mock()
        bot.data_manager.get_market_data = AsyncMock(return_value=mock_market_data)
        
        bot.regime_detector = Mock()
        bot.regime_detector.detect_regime = Mock(return_value=mock_regime)
        
        bot.strategy_engine = Mock()
        bot.strategy_engine.execute_adaptive_signal = AsyncMock(return_value=None)  # No signal
        
        bot.ml_engine = Mock()
        bot.ml_engine.get_model_confidence = Mock(return_value=0.75)
        
        # Test validation
        await bot._validate_component_integration()
        
        # Verify all components were tested
        bot.data_manager.get_market_data.assert_called_once()
        bot.regime_detector.detect_regime.assert_called_once()
        bot.strategy_engine.execute_adaptive_signal.assert_called_once()
        bot.ml_engine.get_model_confidence.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_graceful_shutdown_on_signal(self, test_config):
        """Test graceful shutdown when receiving system signals."""
        bot = AdaptiveBotMain(test_config)
        bot.is_running = True
        
        # Mock the save state method
        with patch.object(bot, '_save_state', new_callable=AsyncMock):
            # Simulate signal handler
            bot._signal_handler(2, None)  # SIGINT
            
            assert bot.shutdown_requested is True
            
            # Test shutdown
            await bot.shutdown()
            assert bot.is_running is False


class TestSystemHealth:
    """Test the SystemHealth class."""
    
    def test_initial_health_status(self):
        """Test initial health status."""
        health = SystemHealth()
        assert health.is_healthy()
        assert health.overall_status == "healthy"
        assert health.error_count == 0
        assert health.warning_count == 0
    
    def test_error_handling(self):
        """Test error handling and status changes."""
        health = SystemHealth()
        
        # Add single error
        health.add_error("component1", "test error")
        assert health.error_count == 1
        assert health.overall_status == "healthy"  # Still healthy with 1 error
        
        # Add more errors to trigger degraded status
        health.add_error("component2", "another error")
        health.add_error("component3", "third error")
        assert health.overall_status == "degraded"
        
        # Add more errors to trigger critical status
        for i in range(4, 7):
            health.add_error(f"component{i}", f"error {i}")
        assert health.overall_status == "critical"
    
    def test_warning_handling(self):
        """Test warning handling."""
        health = SystemHealth()
        
        # Add warnings
        for i in range(4):
            health.add_warning(f"component{i}", f"warning {i}")
        
        assert health.warning_count == 4
        assert health.overall_status == "degraded"  # Should be degraded with many warnings
    
    def test_component_status_tracking(self):
        """Test component status tracking."""
        health = SystemHealth()
        
        health.add_error("data_manager", "connection failed")
        health.add_warning("ml_engine", "model drift detected")
        
        assert "data_manager" in health.component_status
        assert "ml_engine" in health.component_status
        assert "error: connection failed" in health.component_status["data_manager"]
        assert "warning: model drift detected" in health.component_status["ml_engine"]


if __name__ == "__main__":
    pytest.main([__file__])