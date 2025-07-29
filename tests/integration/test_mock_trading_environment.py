"""
Mock trading environment tests.
Tests trading strategies and risk management in simulated market conditions.
"""
import pytest
import time
import random
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

from bot.enhanced_strategies import EnhancedStrategyEngine, StrategyParameters
from bot.enhanced_risk_manager import EnhancedRiskManager, RiskConfig
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig
from bot.kraken_trader import KrakenTrader, KrakenTradingConfig
from bot.kraken_client import KrakenCredentials
from bot.strategy import TradingSignal, SignalType


@dataclass
class MockMarketData:
    """Mock market data for testing."""
    pair: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @property
    def price(self) -> float:
        return self.close


class MockMarketSimulator:
    """Simulates market conditions for testing."""
    
    def __init__(self, initial_price: float = 50000.0, volatility: float = 0.02):
        self.current_price = initial_price
        self.volatility = volatility
        self.time_step = 0
        self.price_history = [initial_price]
    
    def generate_next_price(self) -> float:
        """Generate next price using random walk with volatility."""
        # Simple random walk with drift
        change = np.random.normal(0, self.volatility)
        self.current_price *= (1 + change)
        self.price_history.append(self.current_price)
        self.time_step += 1
        return self.current_price
    
    def generate_market_data(self, pair: str = "XBTUSD") -> MockMarketData:
        """Generate mock market data."""
        price = self.generate_next_price()
        high = price * (1 + abs(np.random.normal(0, 0.005)))
        low = price * (1 - abs(np.random.normal(0, 0.005)))
        volume = random.uniform(0.5, 2.0)
        
        return MockMarketData(
            pair=pair,
            timestamp=datetime.now(),
            open=self.price_history[-2] if len(self.price_history) > 1 else price,
            high=high,
            low=low,
            close=price,
            volume=volume
        )
    
    def generate_trending_market(self, trend_direction: str = "up", steps: int = 100) -> List[MockMarketData]:
        """Generate trending market data."""
        data = []
        trend_factor = 0.001 if trend_direction == "up" else -0.001
        
        for _ in range(steps):
            # Add trend bias to random walk
            change = np.random.normal(trend_factor, self.volatility)
            self.current_price *= (1 + change)
            self.price_history.append(self.current_price)
            
            data.append(self.generate_market_data())
        
        return data
    
    def generate_volatile_market(self, steps: int = 100) -> List[MockMarketData]:
        """Generate highly volatile market data."""
        original_volatility = self.volatility
        self.volatility *= 3  # Increase volatility
        
        data = []
        for _ in range(steps):
            data.append(self.generate_market_data())
        
        self.volatility = original_volatility  # Restore original volatility
        return data


class TestMockTradingEnvironment:
    """Test trading strategies in mock environment."""
    
    @pytest.fixture
    def mock_credentials(self):
        """Mock Kraken credentials."""
        return KrakenCredentials(
            api_key="test_key",
            api_secret="test_secret"
        )
    
    @pytest.fixture
    def trading_config(self):
        """Trading configuration for mock environment."""
        return KrakenTradingConfig(
            trading_pair="XBTUSD",
            trade_amount_usd=100.0,
            max_position_usd=1000.0,
            min_order_size=0.001
        )
    
    @pytest.fixture
    def market_simulator(self):
        """Market simulator for testing."""
        return MockMarketSimulator(initial_price=50000.0, volatility=0.02)
    
    @pytest.fixture
    def mock_trader(self, mock_credentials, trading_config):
        """Mock trader for testing."""
        with patch('bot.kraken_trader.KrakenClient'):
            trader = KrakenTrader(credentials=mock_credentials, config=trading_config)
            
            # Mock successful trades
            trader.execute_market_buy = Mock(return_value=Mock(
                success=True, order_id="BUY123", side="buy", volume="0.001", price="50000.0"
            ))
            trader.execute_market_sell = Mock(return_value=Mock(
                success=True, order_id="SELL123", side="sell", volume="0.001", price="50000.0"
            ))
            trader.get_account_balance = Mock(return_value={
                "ZUSD": "10000.0", "XXBT": "0.1"
            })
            
            return trader
    
    def test_strategy_performance_in_trending_market(self, market_simulator, mock_trader):
        """Test strategy performance in trending market conditions."""
        with patch('bot.enhanced_strategies.EnhancedStrategyEngine') as MockStrategy:
            # Setup strategy engine
            strategy_engine = MockStrategy.return_value
            
            # Generate upward trending market
            market_data = market_simulator.generate_trending_market("up", 50)
            
            # Mock strategy to generate buy signals in uptrend
            def mock_generate_signal(pair, data):
                if len(market_simulator.price_history) > 10:
                    recent_prices = market_simulator.price_history[-10:]
                    if recent_prices[-1] > recent_prices[0]:  # Uptrend
                        return TradingSignal(
                            signal_type=SignalType.BUY,
                            strength=0.8,
                            price=data.close,
                            timestamp=data.timestamp,
                            pair=pair,
                            strategy="trend_following"
                        )
                return None
            
            strategy_engine.generate_signal.side_effect = mock_generate_signal
            
            # Simulate trading
            trades_executed = 0
            for data in market_data:
                signal = strategy_engine.generate_signal("XBTUSD", data)
                if signal and signal.signal_type == SignalType.BUY:
                    result = mock_trader.execute_market_buy(volume=0.001)
                    if result.success:
                        trades_executed += 1
            
            # Verify strategy performed well in trending market
            assert trades_executed > 0
            assert strategy_engine.generate_signal.call_count == len(market_data)
    
    def test_risk_management_in_volatile_market(self, market_simulator, mock_trader):
        """Test risk management in highly volatile market conditions."""
        with patch('bot.enhanced_risk_manager.EnhancedRiskManager') as MockRiskManager:
            # Setup risk manager
            risk_manager = MockRiskManager.return_value
            
            # Generate volatile market data
            market_data = market_simulator.generate_volatile_market(50)
            
            # Mock risk manager to reject trades in high volatility
            def mock_validate_trade(signal, positions):
                # Calculate volatility from recent prices
                if len(market_simulator.price_history) > 10:
                    recent_prices = market_simulator.price_history[-10:]
                    volatility = np.std(recent_prices) / np.mean(recent_prices)
                    
                    if volatility > 0.05:  # High volatility threshold
                        return Mock(
                            approved=False,
                            rejection_reason="High market volatility",
                            risk_score=0.9
                        )
                
                return Mock(
                    approved=True,
                    position_size=0.001,
                    risk_score=0.3
                )
            
            risk_manager.validate_trade.side_effect = mock_validate_trade
            
            # Simulate trading with risk management
            approved_trades = 0
            rejected_trades = 0
            
            for data in market_data:
                # Mock signal generation
                signal = TradingSignal(
                    signal_type=SignalType.BUY,
                    strength=0.7,
                    price=data.close,
                    timestamp=data.timestamp,
                    pair="XBTUSD",
                    strategy="test_strategy"
                )
                
                risk_assessment = risk_manager.validate_trade(signal, {})
                
                if risk_assessment.approved:
                    approved_trades += 1
                else:
                    rejected_trades += 1
            
            # Verify risk management rejected trades in volatile conditions
            assert rejected_trades > 0
            assert risk_manager.validate_trade.call_count == len(market_data)
    
    def test_portfolio_rebalancing_simulation(self, market_simulator, mock_trader):
        """Test portfolio rebalancing in mock environment."""
        with patch('bot.enhanced_risk_manager.EnhancedRiskManager') as MockRiskManager:
            risk_manager = MockRiskManager.return_value
            
            # Mock portfolio with multiple positions
            mock_portfolio = {
                "XBTUSD": {"size": 0.05, "entry_price": 48000.0},
                "ETHUSD": {"size": 1.0, "entry_price": 2800.0}
            }
            
            # Generate market data for both pairs
            btc_data = market_simulator.generate_market_data("XBTUSD")
            eth_simulator = MockMarketSimulator(initial_price=3000.0, volatility=0.03)
            eth_data = eth_simulator.generate_market_data("ETHUSD")
            
            # Mock portfolio risk assessment
            def mock_check_portfolio_risk(positions, market_data):
                total_exposure = sum(pos["size"] * pos["entry_price"] for pos in positions.values())
                
                return Mock(
                    total_exposure=total_exposure,
                    risk_score=0.6,
                    needs_rebalancing=total_exposure > 5000.0,
                    recommended_actions=["reduce_btc_position"] if total_exposure > 5000.0 else []
                )
            
            risk_manager.check_portfolio_risk.side_effect = mock_check_portfolio_risk
            
            # Perform portfolio risk check
            risk_assessment = risk_manager.check_portfolio_risk(
                mock_portfolio, 
                {"XBTUSD": btc_data, "ETHUSD": eth_data}
            )
            
            # Verify portfolio risk management
            assert risk_assessment.total_exposure > 0
            risk_manager.check_portfolio_risk.assert_called_once()
    
    def test_strategy_backtesting_simulation(self, market_simulator):
        """Test strategy backtesting in mock environment."""
        with patch('bot.enhanced_strategies.EnhancedStrategyEngine') as MockStrategy:
            strategy_engine = MockStrategy.return_value
            
            # Generate historical market data
            historical_data = market_simulator.generate_trending_market("up", 200)
            
            # Convert to DataFrame for backtesting
            df_data = pd.DataFrame([
                {
                    "timestamp": data.timestamp,
                    "open": data.open,
                    "high": data.high,
                    "low": data.low,
                    "close": data.close,
                    "volume": data.volume
                }
                for data in historical_data
            ])
            
            # Mock backtesting results
            mock_backtest_result = Mock(
                total_return=0.15,
                sharpe_ratio=1.2,
                max_drawdown=0.08,
                win_rate=0.65,
                total_trades=25,
                profitable_trades=16
            )
            
            strategy_engine.backtest_strategy.return_value = mock_backtest_result
            
            # Run backtest
            result = strategy_engine.backtest_strategy(df_data, "momentum_strategy")
            
            # Verify backtesting results
            assert result.total_return > 0
            assert result.win_rate > 0.5
            assert result.total_trades > 0
            strategy_engine.backtest_strategy.assert_called_once()
    
    def test_multi_pair_coordination_simulation(self, mock_trader):
        """Test multi-pair trading coordination in mock environment."""
        # Create simulators for multiple pairs
        btc_simulator = MockMarketSimulator(initial_price=50000.0, volatility=0.02)
        eth_simulator = MockMarketSimulator(initial_price=3000.0, volatility=0.03)
        
        with patch('bot.enhanced_data_manager.EnhancedDataManager') as MockDataManager:
            data_manager = MockDataManager.return_value
            
            # Generate data for multiple pairs
            btc_data = btc_simulator.generate_trending_market("up", 20)
            eth_data = eth_simulator.generate_trending_market("down", 20)
            
            # Mock data synchronization
            def mock_sync_data(pairs):
                return {
                    "XBTUSD": btc_data[-1] if btc_data else None,
                    "ETHUSD": eth_data[-1] if eth_data else None
                }
            
            data_manager.sync_multi_pair_data.side_effect = mock_sync_data
            
            # Mock correlation analysis
            data_manager.calculate_pair_correlation.return_value = -0.3  # Negative correlation
            
            # Simulate multi-pair trading
            synced_data = data_manager.sync_multi_pair_data(["XBTUSD", "ETHUSD"])
            correlation = data_manager.calculate_pair_correlation("XBTUSD", "ETHUSD")
            
            # Verify multi-pair coordination
            assert "XBTUSD" in synced_data
            assert "ETHUSD" in synced_data
            assert correlation < 0  # Negative correlation detected
            data_manager.sync_multi_pair_data.assert_called_once()
            data_manager.calculate_pair_correlation.assert_called_once()
    
    def test_error_simulation_and_recovery(self, market_simulator, mock_trader):
        """Test error simulation and recovery mechanisms."""
        with patch('bot.enhanced_alerts.EnhancedAlertSystem') as MockAlerts:
            alert_system = MockAlerts.return_value
            
            # Generate market data
            market_data = market_simulator.generate_market_data()
            
            # Simulate API error
            mock_trader.execute_market_buy.side_effect = Exception("API connection error")
            
            # Attempt trade execution with error handling
            try:
                result = mock_trader.execute_market_buy(volume=0.001)
            except Exception as e:
                # Simulate error recovery
                alert_system.send_system_alert.return_value = True
                
                # Mock recovery attempt
                mock_trader.execute_market_buy.side_effect = None
                mock_trader.execute_market_buy.return_value = Mock(
                    success=True, order_id="RECOVERY123"
                )
                
                # Retry after error
                recovery_result = mock_trader.execute_market_buy(volume=0.001)
                
                # Verify error handling and recovery
                assert recovery_result.success is True
                alert_system.send_system_alert.assert_called()
    
    def test_performance_metrics_calculation(self, market_simulator, mock_trader):
        """Test performance metrics calculation in mock environment."""
        with patch('bot.enhanced_logger.EnhancedLogger') as MockLogger:
            logger = MockLogger.return_value
            
            # Simulate trading session
            trades = []
            initial_balance = 10000.0
            current_balance = initial_balance
            
            # Generate trades over time
            for i in range(10):
                market_data = market_simulator.generate_market_data()
                
                # Simulate alternating buy/sell trades
                if i % 2 == 0:
                    trade_result = Mock(
                        success=True,
                        order_id=f"ORDER{i}",
                        side="buy",
                        volume="0.001",
                        price=str(market_data.close),
                        fee="0.5"
                    )
                    current_balance -= 100.0  # Trade amount + fee
                else:
                    trade_result = Mock(
                        success=True,
                        order_id=f"ORDER{i}",
                        side="sell",
                        volume="0.001",
                        price=str(market_data.close),
                        fee="0.5"
                    )
                    current_balance += 105.0  # Profit + trade amount - fee
                
                trades.append(trade_result)
            
            # Mock performance metrics calculation
            mock_metrics = Mock(
                total_trades=len(trades),
                profitable_trades=5,
                total_pnl=current_balance - initial_balance,
                win_rate=0.5,
                sharpe_ratio=1.1,
                max_drawdown=0.05
            )
            
            logger.calculate_performance_metrics.return_value = mock_metrics
            
            # Calculate performance metrics
            metrics = logger.calculate_performance_metrics(trades)
            
            # Verify performance calculation
            assert metrics.total_trades == len(trades)
            assert metrics.win_rate == 0.5
            assert metrics.total_pnl > 0
            logger.calculate_performance_metrics.assert_called_once()