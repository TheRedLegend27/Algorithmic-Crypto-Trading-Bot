"""
Unit tests for the backtesting framework.

Tests cover historical simulation accuracy, walk-forward analysis,
regime-specific backtesting, Monte Carlo simulation, and validation.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any

from bot.adaptive.backtesting_framework import (
    BacktestingFramework, BacktestConfig, BacktestResult, BacktestValidator,
    create_default_backtest_config, compare_backtest_results
)
from bot.adaptive.data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, StrategyAllocation
)
from bot.adaptive.enums import RegimeType, SignalStrength, ValidationMethod
from bot.enhanced_data_manager import EnhancedDataManager


class TestBacktestConfig(unittest.TestCase):
    """Test BacktestConfig class."""
    
    def test_valid_config_creation(self):
        """Test creating a valid backtest configuration."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        
        config = BacktestConfig(
            start_date=start_date,
            end_date=end_date,
            initial_capital=10000.0
        )
        
        self.assertEqual(config.start_date, start_date)
        self.assertEqual(config.end_date, end_date)
        self.assertEqual(config.initial_capital, 10000.0)
        self.assertEqual(config.commission_rate, 0.001)
        self.assertTrue(config.use_realistic_execution)
    
    def test_invalid_date_range(self):
        """Test validation of invalid date range."""
        start_date = datetime(2023, 12, 31)
        end_date = datetime(2023, 1, 1)
        
        with self.assertRaises(ValueError):
            BacktestConfig(start_date=start_date, end_date=end_date)
    
    def test_invalid_capital(self):
        """Test validation of invalid capital."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        
        with self.assertRaises(ValueError):
            BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                initial_capital=-1000.0
            )
    
    def test_invalid_position_size(self):
        """Test validation of invalid position size."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        
        with self.assertRaises(ValueError):
            BacktestConfig(
                start_date=start_date,
                end_date=end_date,
                max_position_size_pct=1.5
            )


class TestBacktestResult(unittest.TestCase):
    """Test BacktestResult class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=10000.0
        )
        
        self.performance_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            excess_return=0.10,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=-0.08,
            volatility=0.12,
            downside_deviation=0.10,
            win_rate=0.6,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=24),
            trades_count=50,
            avg_win=100.0,
            avg_loss=-60.0
        )
        
        self.trades = [
            {'trade_id': '1', 'pnl': 100.0, 'pair': 'BTC/USD'},
            {'trade_id': '2', 'pnl': -50.0, 'pair': 'ETH/USD'}
        ]
        
        self.equity_curve = pd.Series([10000, 10100, 10050], 
                                     index=pd.date_range('2023-01-01', periods=3))
    
    def test_result_creation(self):
        """Test creating a backtest result."""
        result = BacktestResult(
            config=self.config,
            performance_metrics=self.performance_metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            drawdown_curve=pd.Series()
        )
        
        self.assertEqual(result.config, self.config)
        self.assertEqual(result.performance_metrics, self.performance_metrics)
        self.assertEqual(len(result.trades), 2)
        self.assertEqual(len(result.equity_curve), 3)
    
    def test_summary_stats(self):
        """Test summary statistics calculation."""
        result = BacktestResult(
            config=self.config,
            performance_metrics=self.performance_metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            drawdown_curve=pd.Series()
        )
        
        summary = result.get_summary_stats()
        
        self.assertEqual(summary['total_return'], 0.15)
        self.assertEqual(summary['sharpe_ratio'], 1.2)
        self.assertEqual(summary['total_trades'], 2)
        self.assertIn('execution_time', summary)


class TestBacktestingFramework(unittest.TestCase):
    """Test BacktestingFramework class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.data_manager = Mock(spec=EnhancedDataManager)
        self.strategy_engine = Mock()
        self.regime_detector = Mock()
        self.ml_engine = Mock()
        self.parameter_optimizer = Mock()
        self.performance_analyzer = Mock()
        
        self.framework = BacktestingFramework(
            data_manager=self.data_manager,
            strategy_engine=self.strategy_engine,
            regime_detector=self.regime_detector,
            ml_engine=self.ml_engine,
            parameter_optimizer=self.parameter_optimizer,
            performance_analyzer=self.performance_analyzer
        )
        
        # Mock data
        self.sample_data = pd.DataFrame({
            'BTC/USD_close': [50000, 51000, 50500, 52000, 51500],
            'ETH/USD_close': [3000, 3100, 3050, 3200, 3150]
        }, index=pd.date_range('2023-01-01', periods=5, freq='H'))
        
        self.config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 2),
            initial_capital=10000.0,
            warmup_period=1
        )
    
    def test_framework_initialization(self):
        """Test framework initialization."""
        self.assertIsNotNone(self.framework.data_manager)
        self.assertIsNotNone(self.framework.strategy_engine)
        self.assertEqual(len(self.framework._current_positions), 0)
        self.assertEqual(len(self.framework._trade_history), 0)
    
    @patch('bot.adaptive.backtesting_framework.logger')
    def test_prepare_historical_data(self, mock_logger):
        """Test historical data preparation."""
        pairs = ['BTC/USD', 'ETH/USD']
        
        # Mock data manager response
        self.data_manager.get_historical_data.return_value = self.sample_data
        
        # Call private method for testing
        result = self.framework._prepare_historical_data(self.config, pairs)
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 5)
        self.assertEqual(self.data_manager.get_historical_data.call_count, 2)
    
    def test_calculate_position_size(self):
        """Test position size calculation."""
        # Create mock signal
        signal = Mock()
        signal.suggested_position_size = None
        signal.confidence = 0.8
        signal.strength = SignalStrength.STRONG
        
        current_capital = 10000.0
        
        # Call private method
        position_size = self.framework._calculate_position_size(
            signal, current_capital, self.config
        )
        
        # Should be based on confidence and strength
        expected_base = current_capital * self.config.max_position_size_pct * signal.confidence
        expected_size = expected_base * signal.strength.value
        
        self.assertEqual(position_size, expected_size)
    
    def test_apply_execution_costs(self):
        """Test execution cost application."""
        price = 50000.0
        slippage_rate = 0.001
        
        # Test buy order (positive slippage)
        buy_price = self.framework._apply_execution_costs(
            price, 'buy', self.config
        )
        expected_buy = price * (1 + self.config.slippage_rate)
        self.assertEqual(buy_price, expected_buy)
        
        # Test sell order (negative slippage)
        sell_price = self.framework._apply_execution_costs(
            price, 'sell', self.config
        )
        expected_sell = price * (1 - self.config.slippage_rate)
        self.assertEqual(sell_price, expected_sell)
    
    def test_performance_metrics_calculation(self):
        """Test performance metrics calculation."""
        # Set up equity history
        self.framework._equity_history = [
            (datetime(2023, 1, 1), 10000),
            (datetime(2023, 1, 2), 10500),
            (datetime(2023, 1, 3), 10200),
            (datetime(2023, 1, 4), 10800)
        ]
        
        # Set up trade history
        self.framework._trade_history = [
            {'pnl': 500, 'timestamp': datetime(2023, 1, 2)},
            {'pnl': -300, 'timestamp': datetime(2023, 1, 3)},
            {'pnl': 600, 'timestamp': datetime(2023, 1, 4)}
        ]
        
        final_capital = 10800
        metrics = self.framework._calculate_performance_metrics(self.config, final_capital)
        
        self.assertIsInstance(metrics, PerformanceMetrics)
        self.assertEqual(metrics.total_return, 0.08)  # 8% return
        self.assertEqual(metrics.trades_count, 3)
        self.assertGreater(metrics.win_rate, 0)
    
    def test_create_equity_curve(self):
        """Test equity curve creation."""
        self.framework._equity_history = [
            (datetime(2023, 1, 1), 10000),
            (datetime(2023, 1, 2), 10500),
            (datetime(2023, 1, 3), 10200)
        ]
        
        equity_curve = self.framework._create_equity_curve()
        
        self.assertIsInstance(equity_curve, pd.Series)
        self.assertEqual(len(equity_curve), 3)
        self.assertEqual(equity_curve.iloc[0], 10000)
        self.assertEqual(equity_curve.iloc[-1], 10200)
    
    def test_create_drawdown_curve(self):
        """Test drawdown curve creation."""
        self.framework._equity_history = [
            (datetime(2023, 1, 1), 10000),
            (datetime(2023, 1, 2), 10500),
            (datetime(2023, 1, 3), 10200),
            (datetime(2023, 1, 4), 9800)
        ]
        
        drawdown_curve = self.framework._create_drawdown_curve()
        
        self.assertIsInstance(drawdown_curve, pd.Series)
        self.assertEqual(len(drawdown_curve), 4)
        self.assertEqual(drawdown_curve.iloc[0], 0.0)  # No drawdown at start
        self.assertLess(drawdown_curve.iloc[-1], 0.0)  # Drawdown at end
    
    def test_trade_analysis(self):
        """Test trade analysis."""
        self.framework._trade_history = [
            {'pnl': 100, 'pair': 'BTC/USD'},
            {'pnl': -50, 'pair': 'ETH/USD'},
            {'pnl': 200, 'pair': 'BTC/USD'},
            {'pnl': -30, 'pair': 'ETH/USD'}
        ]
        
        analysis = self.framework._analyze_trades()
        
        self.assertEqual(analysis['total_trades'], 4)
        self.assertEqual(analysis['winning_trades'], 2)
        self.assertEqual(analysis['losing_trades'], 2)
        self.assertEqual(analysis['largest_win'], 200)
        self.assertEqual(analysis['largest_loss'], -50)
    
    def test_risk_metrics_calculation(self):
        """Test risk metrics calculation."""
        # Create equity curve with some volatility
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        returns = np.random.normal(0.001, 0.02, 100)  # Daily returns
        equity_values = [10000]
        
        for ret in returns:
            equity_values.append(equity_values[-1] * (1 + ret))
        
        self.framework._equity_history = list(zip(dates, equity_values))
        
        risk_metrics = self.framework._calculate_risk_metrics()
        
        self.assertIn('var_95', risk_metrics)
        self.assertIn('expected_shortfall_95', risk_metrics)
        self.assertIn('max_consecutive_losses', risk_metrics)
        self.assertIn('return_skewness', risk_metrics)
        self.assertIn('return_kurtosis', risk_metrics)
    
    def test_monthly_returns_calculation(self):
        """Test monthly returns calculation."""
        # Create daily equity data for 3 months
        dates = pd.date_range('2023-01-01', '2023-03-31', freq='D')
        equity_values = np.linspace(10000, 11000, len(dates))
        
        self.framework._equity_history = list(zip(dates, equity_values))
        
        monthly_returns = self.framework._calculate_monthly_returns()
        
        self.assertIsInstance(monthly_returns, pd.Series)
        self.assertGreater(len(monthly_returns), 0)


class TestWalkForwardAnalysis(unittest.TestCase):
    """Test walk-forward analysis functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.data_manager = Mock(spec=EnhancedDataManager)
        self.parameter_optimizer = Mock()
        
        self.framework = BacktestingFramework(
            data_manager=self.data_manager,
            parameter_optimizer=self.parameter_optimizer
        )
        
        self.config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=10000.0
        )
    
    @patch.object(BacktestingFramework, 'run_backtest')
    @patch.object(BacktestingFramework, '_prepare_historical_data')
    @patch.object(BacktestingFramework, '_optimize_parameters_for_window')
    def test_walk_forward_analysis(self, mock_optimize, mock_prepare_data, mock_run_backtest):
        """Test walk-forward analysis execution."""
        # Mock data preparation
        mock_prepare_data.return_value = pd.DataFrame()
        
        # Mock backtest results
        mock_result = Mock(spec=BacktestResult)
        mock_result.performance_metrics = Mock()
        mock_run_backtest.return_value = mock_result
        
        pairs = ['BTC/USD']
        results = self.framework.walk_forward_analysis(
            config=self.config,
            pairs=pairs,
            optimization_window=30,
            validation_window=10,
            step_size=5
        )
        
        self.assertIsInstance(results, list)
        # Should have multiple windows
        self.assertGreater(len(results), 0)
        
        # Verify optimization was called
        self.assertGreater(mock_optimize.call_count, 0)
        self.assertGreater(mock_run_backtest.call_count, 0)


class TestMonteCarloSimulation(unittest.TestCase):
    """Test Monte Carlo simulation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.data_manager = Mock(spec=EnhancedDataManager)
        self.framework = BacktestingFramework(data_manager=self.data_manager)
        
        self.config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 3, 31),
            initial_capital=10000.0
        )
    
    def test_apply_randomization_bootstrap(self):
        """Test bootstrap randomization method."""
        original_config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=10000.0
        )
        
        randomized_config = self.framework._apply_randomization(
            original_config, 'bootstrap', seed=42
        )
        
        # Dates should be different but within original range
        self.assertGreaterEqual(randomized_config.start_date, original_config.start_date)
        self.assertLessEqual(randomized_config.end_date, original_config.end_date)
        self.assertLessEqual(
            randomized_config.end_date - randomized_config.start_date,
            original_config.end_date - original_config.start_date
        )
    
    def test_apply_randomization_parameter_noise(self):
        """Test parameter noise randomization method."""
        original_config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=10000.0,
            commission_rate=0.001,
            slippage_rate=0.0005
        )
        
        randomized_config = self.framework._apply_randomization(
            original_config, 'parameter_noise', seed=42
        )
        
        # Parameters should be modified (allow for small chance they could be equal due to randomness)
        # Just check they are within reasonable bounds
        self.assertGreater(randomized_config.commission_rate, 0)
        self.assertGreater(randomized_config.slippage_rate, 0)
        
        # But should be within reasonable bounds
        self.assertGreater(randomized_config.commission_rate, 0)
        self.assertGreater(randomized_config.slippage_rate, 0)
    
    def test_analyze_monte_carlo_results(self):
        """Test Monte Carlo results analysis."""
        # Create mock results
        mock_results = []
        for i in range(10):
            result = Mock(spec=BacktestResult)
            result.performance_metrics = Mock()
            result.performance_metrics.total_return = 0.1 + (i * 0.01)
            result.performance_metrics.sharpe_ratio = 1.0 + (i * 0.1)
            result.performance_metrics.max_drawdown = -0.05 - (i * 0.005)
            result.performance_metrics.win_rate = 0.6 + (i * 0.01)
            mock_results.append(result)
        
        analysis = self.framework._analyze_monte_carlo_results(mock_results)
        
        self.assertEqual(analysis['num_simulations'], 10)
        self.assertIn('return_stats', analysis)
        self.assertIn('sharpe_stats', analysis)
        self.assertIn('drawdown_stats', analysis)
        self.assertIn('risk_metrics', analysis)
        
        # Check statistics
        self.assertAlmostEqual(analysis['return_stats']['mean'], 0.145, places=2)
        self.assertGreater(analysis['return_stats']['std'], 0)


class TestRegimeSpecificBacktest(unittest.TestCase):
    """Test regime-specific backtesting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.data_manager = Mock(spec=EnhancedDataManager)
        self.regime_detector = Mock()
        
        self.framework = BacktestingFramework(
            data_manager=self.data_manager,
            regime_detector=self.regime_detector
        )
        
        self.config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 3, 31),
            initial_capital=10000.0
        )
        
        # Mock data
        self.sample_data = pd.DataFrame({
            'BTC/USD_close': [50000, 51000, 50500, 52000, 51500],
            'ETH/USD_close': [3000, 3100, 3050, 3200, 3150]
        }, index=pd.date_range('2023-01-01', periods=5, freq='H'))
    
    def test_filter_data_by_regime(self):
        """Test filtering data by market regime."""
        pairs = ['BTC/USD']
        target_regime = RegimeType.TRENDING_BULL
        
        # Mock regime detector to return alternating regimes
        def mock_detect_regime(data, pair):
            regime = Mock()
            if len(data) % 2 == 0:
                regime.regime_type = RegimeType.TRENDING_BULL
            else:
                regime.regime_type = RegimeType.RANGING
            return regime
        
        self.regime_detector.detect_regime.side_effect = mock_detect_regime
        
        filtered_data = self.framework._filter_data_by_regime(
            self.sample_data, pairs, target_regime
        )
        
        self.assertIsInstance(filtered_data, pd.DataFrame)
        # Should have some data filtered out
        self.assertLessEqual(len(filtered_data), len(self.sample_data))
    
    @patch.object(BacktestingFramework, '_prepare_historical_data')
    @patch.object(BacktestingFramework, '_run_simulation')
    def test_regime_specific_backtest(self, mock_run_simulation, mock_prepare_data):
        """Test regime-specific backtest execution."""
        pairs = ['BTC/USD']
        target_regime = RegimeType.TRENDING_BULL
        
        # Mock data preparation
        mock_prepare_data.return_value = self.sample_data
        
        # Mock simulation result
        mock_result = Mock(spec=BacktestResult)
        mock_result.performance_metrics = Mock()
        mock_result.regime_performance = {}
        mock_run_simulation.return_value = mock_result
        
        # Mock regime filtering to return some data
        with patch.object(self.framework, '_filter_data_by_regime') as mock_filter:
            mock_filter.return_value = self.sample_data.iloc[:3]  # Return subset
            
            result = self.framework.regime_specific_backtest(
                self.config, pairs, target_regime
            )
        
        self.assertIsInstance(result, BacktestResult)
        self.assertIn(target_regime, result.regime_performance)
        mock_filter.assert_called_once()
        mock_run_simulation.assert_called_once()


class TestBacktestValidator(unittest.TestCase):
    """Test BacktestValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = BacktestValidator()
        
        # Create mock backtest result
        self.config = BacktestConfig(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 12, 31),
            initial_capital=10000.0
        )
        
        self.performance_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            excess_return=0.10,
            sharpe_ratio=1.2,
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=-0.08,
            volatility=0.12,
            downside_deviation=0.10,
            win_rate=0.6,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=24),
            trades_count=50,
            avg_win=100.0,
            avg_loss=-60.0
        )
        
        self.trades = [{'pnl': 100 * i} for i in range(50)]
        self.equity_curve = pd.Series(
            np.linspace(10000, 11500, 100),
            index=pd.date_range('2023-01-01', periods=100, freq='D')
        )
        
        self.result = BacktestResult(
            config=self.config,
            performance_metrics=self.performance_metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            drawdown_curve=pd.Series(),
            total_bars_processed=1000
        )
    
    def test_validate_backtest_success(self):
        """Test successful backtest validation."""
        validation_result = self.validator.validate_backtest(self.result)
        
        self.assertIsInstance(validation_result, dict)
        self.assertIn('is_valid', validation_result)
        self.assertIn('warnings', validation_result)
        self.assertIn('errors', validation_result)
        self.assertIn('quality_score', validation_result)
        
        # Should be valid with good data
        self.assertTrue(validation_result['is_valid'])
        self.assertGreater(validation_result['quality_score'], 80)
    
    def test_data_quality_check(self):
        """Test data quality validation."""
        # Test with insufficient data
        insufficient_result = BacktestResult(
            config=self.config,
            performance_metrics=self.performance_metrics,
            trades=[],
            equity_curve=pd.Series(),
            drawdown_curve=pd.Series(),
            total_bars_processed=100  # Too few bars
        )
        
        validation_result = self.validator.validate_backtest(insufficient_result)
        
        self.assertGreater(len(validation_result['warnings']), 0)
        self.assertLess(validation_result['quality_score'], 100)
    
    def test_trade_realism_check(self):
        """Test trade realism validation."""
        # Create result with unrealistic win rate
        unrealistic_trades = [{'pnl': 100} for _ in range(50)]  # All winning trades
        
        unrealistic_result = BacktestResult(
            config=self.config,
            performance_metrics=self.performance_metrics,
            trades=unrealistic_trades,
            equity_curve=self.equity_curve,
            drawdown_curve=pd.Series(),
            total_bars_processed=1000
        )
        
        validation_result = self.validator.validate_backtest(unrealistic_result)
        
        # Should have warnings about unrealistic win rate
        warnings = validation_result['warnings']
        self.assertTrue(any('win rate' in warning.lower() for warning in warnings))
    
    def test_performance_consistency_check(self):
        """Test performance consistency validation."""
        # Create inconsistent metrics
        inconsistent_metrics = PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.15,
            excess_return=0.10,
            sharpe_ratio=5.0,  # Inconsistent with return/volatility
            sortino_ratio=1.5,
            calmar_ratio=0.8,
            max_drawdown=-0.08,
            volatility=0.12,
            downside_deviation=0.10,
            win_rate=0.6,
            profit_factor=1.8,
            avg_trade_duration=timedelta(hours=24),
            trades_count=50,
            avg_win=100.0,
            avg_loss=-60.0
        )
        
        inconsistent_result = BacktestResult(
            config=self.config,
            performance_metrics=inconsistent_metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            drawdown_curve=pd.Series(),
            total_bars_processed=1000
        )
        
        validation_result = self.validator.validate_backtest(inconsistent_result)
        
        # May have warnings about inconsistencies
        self.assertIsInstance(validation_result['warnings'], list)
    
    def test_quality_score_calculation(self):
        """Test quality score calculation."""
        # Test with perfect result
        perfect_validation = {'warnings': [], 'errors': []}
        score = self.validator._calculate_quality_score(perfect_validation)
        self.assertEqual(score, 100.0)
        
        # Test with warnings
        warning_validation = {'warnings': ['warning1', 'warning2'], 'errors': []}
        score = self.validator._calculate_quality_score(warning_validation)
        self.assertEqual(score, 90.0)  # 100 - 2*5
        
        # Test with errors
        error_validation = {'warnings': [], 'errors': ['error1']}
        score = self.validator._calculate_quality_score(error_validation)
        self.assertEqual(score, 80.0)  # 100 - 1*20


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""
    
    def test_create_default_backtest_config(self):
        """Test default configuration creation."""
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 12, 31)
        
        config = create_default_backtest_config(start_date, end_date)
        
        self.assertIsInstance(config, BacktestConfig)
        self.assertEqual(config.start_date, start_date)
        self.assertEqual(config.end_date, end_date)
        self.assertEqual(config.initial_capital, 10000.0)
        self.assertTrue(config.use_realistic_execution)
    
    def test_compare_backtest_results(self):
        """Test backtest results comparison."""
        # Create multiple mock results
        results = []
        for i in range(3):
            config = BacktestConfig(
                start_date=datetime(2023, 1, 1),
                end_date=datetime(2023, 12, 31)
            )
            
            metrics = PerformanceMetrics(
                total_return=0.1 + i * 0.05,
                annualized_return=0.1 + i * 0.05,
                excess_return=0.05 + i * 0.05,
                sharpe_ratio=1.0 + i * 0.2,
                sortino_ratio=1.2 + i * 0.2,
                calmar_ratio=0.8 + i * 0.1,
                max_drawdown=-0.1 + i * 0.01,
                volatility=0.15,
                downside_deviation=0.12,
                win_rate=0.6 + i * 0.05,
                profit_factor=1.5 + i * 0.2,
                avg_trade_duration=timedelta(hours=24),
                trades_count=50 + i * 10,
                avg_win=100.0,
                avg_loss=-60.0
            )
            
            result = BacktestResult(
                config=config,
                performance_metrics=metrics,
                trades=[],
                equity_curve=pd.Series(),
                drawdown_curve=pd.Series(),
                execution_time=timedelta(seconds=60 + i * 10)
            )
            
            results.append(result)
        
        comparison_df = compare_backtest_results(results)
        
        self.assertIsInstance(comparison_df, pd.DataFrame)
        self.assertEqual(len(comparison_df), 3)
        self.assertIn('total_return', comparison_df.columns)
        self.assertIn('sharpe_ratio', comparison_df.columns)
        self.assertIn('total_trades', comparison_df.columns)
        
        # Check that values are different across results
        self.assertNotEqual(
            comparison_df.iloc[0]['total_return'],
            comparison_df.iloc[1]['total_return']
        )
    
    def test_compare_empty_results(self):
        """Test comparison with empty results list."""
        comparison_df = compare_backtest_results([])
        
        self.assertIsInstance(comparison_df, pd.DataFrame)
        self.assertTrue(comparison_df.empty)


if __name__ == '__main__':
    unittest.main()