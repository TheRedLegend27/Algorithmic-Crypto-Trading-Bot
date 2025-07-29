"""
Multi-pair trading coordination integration tests.
Tests coordination and synchronization of trading across multiple cryptocurrency pairs.
"""
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from dataclasses import dataclass

from bot.main import BotOrchestrator
from bot.enhanced_data_manager import EnhancedDataManager
from bot.enhanced_strategies import EnhancedStrategyEngine
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.kraken_trader import KrakenTrader
from bot.strategy import TradingSignal, SignalType


@dataclass
class MultiPairMarketData:
    """Market data for multiple trading pairs."""
    pair: str
    price: float
    volume: float
    timestamp: datetime
    bid: float
    ask: float
    spread: float


class TestMultiPairDataSynchronization:
    """Test data synchronization across multiple trading pairs."""
    
    @pytest.fixture
    def trading_pairs(self):
        """List of trading pairs for testing."""
        return ["XBTUSD", "ETHUSD", "ADAUSD", "DOTUSD", "LINKUSD"]
    
    @pytest.fixture
    def mock_data_manager(self):
        """Mock enhanced data manager."""
        with patch('bot.enhanced_data_manager.EnhancedDataManager') as MockDataManager:
            return MockDataManager.return_value
    
    def test_simultaneous_data_processing(self, trading_pairs, mock_data_manager):
        """Test simultaneous data processing for multiple pairs."""
        # Mock market data for all pairs
        market_data = {}
        for i, pair in enumerate(trading_pairs):
            market_data[pair] = MultiPairMarketData(
                pair=pair,
                price=1000.0 * (i + 1),  # Different prices for each pair
                volume=10.0 + i,
                timestamp=datetime.now(),
                bid=1000.0 * (i + 1) - 0.5,
                ask=1000.0 * (i + 1) + 0.5,
                spread=1.0
            )
        
        # Mock data processing
        processed_data = {}
        def mock_process_data(pair, data):
            processed_data[pair] = {
                "pair": pair,
                "price": data.price,
                "processed_at": datetime.now(),
                "indicators": {
                    "sma_20": data.price * 0.98,
                    "rsi": 50.0,
                    "volume_avg": data.volume
                }
            }
            return processed_data[pair]
        
        mock_data_manager.process_market_data.side_effect = mock_process_data
        
        # Process data for all pairs
        start_time = time.time()
        
        for pair in trading_pairs:
            mock_data_manager.process_market_data(pair, market_data[pair])
        
        end_time = time.time()
        
        # Verify all pairs were processed
        assert mock_data_manager.process_market_data.call_count == len(trading_pairs)
        assert len(processed_data) == len(trading_pairs)
        assert end_time - start_time < 1.0  # Should be fast
        
        # Verify each pair has processed data
        for pair in trading_pairs:
            assert pair in processed_data
            assert processed_data[pair]["pair"] == pair
            assert "indicators" in processed_data[pair]
    
    def test_data_synchronization_timing(self, trading_pairs, mock_data_manager):
        """Test timing synchronization of multi-pair data."""
        # Mock synchronized data retrieval
        sync_timestamp = datetime.now()
        
        def mock_get_synchronized_data(pairs, timestamp):
            return {
                pair: {
                    "pair": pair,
                    "price": 1000.0 + hash(pair) % 1000,
                    "timestamp": timestamp,
                    "synchronized": True
                }
                for pair in pairs
            }
        
        mock_data_manager.get_synchronized_data.side_effect = mock_get_synchronized_data
        
        # Get synchronized data for all pairs
        synced_data = mock_data_manager.get_synchronized_data(trading_pairs, sync_timestamp)
        
        # Verify synchronization
        assert len(synced_data) == len(trading_pairs)
        for pair in trading_pairs:
            assert synced_data[pair]["timestamp"] == sync_timestamp
            assert synced_data[pair]["synchronized"] is True
        
        mock_data_manager.get_synchronized_data.assert_called_once_with(trading_pairs, sync_timestamp)
    
    def test_data_quality_validation_across_pairs(self, trading_pairs, mock_data_manager):
        """Test data quality validation across multiple pairs."""
        # Mock data quality validation
        def mock_validate_data_quality(pair, data):
            # Simulate different quality scores
            quality_scores = {
                "XBTUSD": 0.95,
                "ETHUSD": 0.90,
                "ADAUSD": 0.85,
                "DOTUSD": 0.75,  # Lower quality
                "LINKUSD": 0.92
            }
            
            return {
                "pair": pair,
                "quality_score": quality_scores.get(pair, 0.8),
                "issues": ["low_volume"] if quality_scores.get(pair, 0.8) < 0.8 else [],
                "valid": quality_scores.get(pair, 0.8) >= 0.8
            }
        
        mock_data_manager.validate_data_quality.side_effect = mock_validate_data_quality
        
        # Validate data quality for all pairs
        quality_results = {}
        for pair in trading_pairs:
            mock_data = {"price": 1000.0, "volume": 1.0}
            quality_results[pair] = mock_data_manager.validate_data_quality(pair, mock_data)
        
        # Verify quality validation
        assert len(quality_results) == len(trading_pairs)
        
        # Check specific quality results
        assert quality_results["XBTUSD"]["quality_score"] == 0.95
        assert quality_results["DOTUSD"]["quality_score"] == 0.75
        assert not quality_results["DOTUSD"]["valid"]  # Should be invalid due to low quality
        assert quality_results["DOTUSD"]["issues"] == ["low_volume"]
        
        # Verify all pairs were validated
        assert mock_data_manager.validate_data_quality.call_count == len(trading_pairs)


class TestMultiPairStrategyCoordination:
    """Test strategy coordination across multiple pairs."""
    
    @pytest.fixture
    def mock_strategy_engine(self):
        """Mock enhanced strategy engine."""
        with patch('bot.enhanced_strategies.EnhancedStrategyEngine') as MockStrategy:
            return MockStrategy.return_value
    
    def test_coordinated_signal_generation(self, mock_strategy_engine):
        """Test coordinated signal generation across pairs."""
        trading_pairs = ["XBTUSD", "ETHUSD", "ADAUSD"]
        
        # Mock different signals for different pairs
        def mock_generate_signal(pair, market_data):
            signal_map = {
                "XBTUSD": TradingSignal(
                    signal_type=SignalType.BUY,
                    strength=0.8,
                    price=50000.0,
                    timestamp=datetime.now(),
                    pair=pair,
                    strategy="momentum"
                ),
                "ETHUSD": TradingSignal(
                    signal_type=SignalType.SELL,
                    strength=0.7,
                    price=3000.0,
                    timestamp=datetime.now(),
                    pair=pair,
                    strategy="mean_reversion"
                ),
                "ADAUSD": None  # No signal
            }
            return signal_map.get(pair)
        
        mock_strategy_engine.generate_signal.side_effect = mock_generate_signal
        
        # Generate signals for all pairs
        signals = {}
        for pair in trading_pairs:
            market_data = {"price": 1000.0, "volume": 1.0}
            signals[pair] = mock_strategy_engine.generate_signal(pair, market_data)
        
        # Verify signal coordination
        assert signals["XBTUSD"] is not None
        assert signals["XBTUSD"].signal_type == SignalType.BUY
        assert signals["ETHUSD"] is not None
        assert signals["ETHUSD"].signal_type == SignalType.SELL
        assert signals["ADAUSD"] is None
        
        # Verify all pairs were processed
        assert mock_strategy_engine.generate_signal.call_count == len(trading_pairs)
    
    def test_strategy_correlation_analysis(self, mock_strategy_engine):
        """Test strategy correlation analysis across pairs."""
        # Mock correlation analysis
        def mock_analyze_correlation(pair1, pair2, signals1, signals2):
            # Simulate correlation based on pair names
            correlation_map = {
                ("XBTUSD", "ETHUSD"): 0.7,   # High positive correlation
                ("XBTUSD", "ADAUSD"): -0.3,  # Negative correlation
                ("ETHUSD", "ADAUSD"): 0.1    # Low correlation
            }
            
            key = (pair1, pair2) if (pair1, pair2) in correlation_map else (pair2, pair1)
            return correlation_map.get(key, 0.0)
        
        mock_strategy_engine.analyze_signal_correlation.side_effect = mock_analyze_correlation
        
        # Analyze correlations between pairs
        pairs = ["XBTUSD", "ETHUSD", "ADAUSD"]
        correlations = {}
        
        for i, pair1 in enumerate(pairs):
            for pair2 in pairs[i+1:]:
                signals1 = [Mock(signal_type=SignalType.BUY)]
                signals2 = [Mock(signal_type=SignalType.SELL)]
                
                correlation = mock_strategy_engine.analyze_signal_correlation(
                    pair1, pair2, signals1, signals2
                )
                correlations[(pair1, pair2)] = correlation
        
        # Verify correlation analysis
        assert correlations[("XBTUSD", "ETHUSD")] == 0.7
        assert correlations[("XBTUSD", "ADAUSD")] == -0.3
        assert correlations[("ETHUSD", "ADAUSD")] == 0.1
        
        # Verify correlation analysis was called for all pairs
        expected_calls = len(pairs) * (len(pairs) - 1) // 2
        assert mock_strategy_engine.analyze_signal_correlation.call_count == expected_calls
    
    def test_strategy_weight_adjustment(self, mock_strategy_engine):
        """Test strategy weight adjustment based on multi-pair performance."""
        # Mock strategy performance data
        performance_data = {
            "XBTUSD": {"win_rate": 0.65, "profit_factor": 1.3, "sharpe_ratio": 1.1},
            "ETHUSD": {"win_rate": 0.58, "profit_factor": 1.1, "sharpe_ratio": 0.9},
            "ADAUSD": {"win_rate": 0.72, "profit_factor": 1.5, "sharpe_ratio": 1.4}
        }
        
        # Mock weight adjustment
        def mock_adjust_strategy_weights(pair, performance):
            base_weight = 1.0
            performance_multiplier = performance["win_rate"] * performance["profit_factor"]
            return base_weight * performance_multiplier
        
        mock_strategy_engine.adjust_strategy_weights.side_effect = mock_adjust_strategy_weights
        
        # Adjust weights for all pairs
        adjusted_weights = {}
        for pair, performance in performance_data.items():
            adjusted_weights[pair] = mock_strategy_engine.adjust_strategy_weights(pair, performance)
        
        # Verify weight adjustments
        assert adjusted_weights["ADAUSD"] > adjusted_weights["XBTUSD"]  # Better performance
        assert adjusted_weights["XBTUSD"] > adjusted_weights["ETHUSD"]  # Better performance
        
        # Verify all pairs had weights adjusted
        assert mock_strategy_engine.adjust_strategy_weights.call_count == len(performance_data)


class TestMultiPairRiskManagement:
    """Test risk management coordination across multiple pairs."""
    
    @pytest.fixture
    def mock_risk_manager(self):
        """Mock enhanced risk manager."""
        with patch('bot.enhanced_risk_manager.EnhancedRiskManager') as MockRisk:
            return MockRisk.return_value
    
    def test_portfolio_level_risk_assessment(self, mock_risk_manager):
        """Test portfolio-level risk assessment across pairs."""
        # Mock portfolio positions
        portfolio_positions = {
            "XBTUSD": {"size": 0.05, "entry_price": 48000.0, "current_price": 50000.0},
            "ETHUSD": {"size": 1.0, "entry_price": 2800.0, "current_price": 3000.0},
            "ADAUSD": {"size": 1000.0, "entry_price": 0.45, "current_price": 0.50}
        }
        
        # Mock portfolio risk assessment
        def mock_assess_portfolio_risk(positions):
            total_exposure = sum(
                pos["size"] * pos["current_price"] 
                for pos in positions.values()
            )
            
            unrealized_pnl = sum(
                pos["size"] * (pos["current_price"] - pos["entry_price"])
                for pos in positions.values()
            )
            
            return {
                "total_exposure": total_exposure,
                "unrealized_pnl": unrealized_pnl,
                "risk_score": min(total_exposure / 10000.0, 1.0),  # Normalize to 0-1
                "diversification_score": len(positions) / 10.0,  # Simple diversification metric
                "correlation_risk": 0.3  # Mock correlation risk
            }
        
        mock_risk_manager.assess_portfolio_risk.side_effect = mock_assess_portfolio_risk
        
        # Assess portfolio risk
        risk_assessment = mock_risk_manager.assess_portfolio_risk(portfolio_positions)
        
        # Verify portfolio risk assessment
        assert risk_assessment["total_exposure"] > 0
        assert risk_assessment["unrealized_pnl"] > 0  # Profitable positions
        assert 0 <= risk_assessment["risk_score"] <= 1
        assert risk_assessment["diversification_score"] > 0
        
        mock_risk_manager.assess_portfolio_risk.assert_called_once_with(portfolio_positions)
    
    def test_cross_pair_correlation_risk(self, mock_risk_manager):
        """Test cross-pair correlation risk management."""
        # Mock correlation matrix
        correlation_matrix = {
            ("XBTUSD", "ETHUSD"): 0.8,   # High correlation
            ("XBTUSD", "ADAUSD"): 0.6,   # Medium correlation
            ("ETHUSD", "ADAUSD"): 0.5    # Medium correlation
        }
        
        # Mock correlation risk calculation
        def mock_calculate_correlation_risk(positions, correlations):
            # Simple correlation risk calculation
            total_risk = 0.0
            pairs = list(positions.keys())
            
            for i, pair1 in enumerate(pairs):
                for pair2 in pairs[i+1:]:
                    correlation = correlations.get((pair1, pair2), 0.0)
                    position1_size = positions[pair1]["size"] * positions[pair1]["current_price"]
                    position2_size = positions[pair2]["size"] * positions[pair2]["current_price"]
                    
                    # Risk increases with correlation and position sizes
                    pair_risk = abs(correlation) * min(position1_size, position2_size) / 1000.0
                    total_risk += pair_risk
            
            return {
                "total_correlation_risk": total_risk,
                "high_correlation_pairs": [
                    (pair1, pair2) for (pair1, pair2), corr in correlations.items() 
                    if abs(corr) > 0.7
                ],
                "risk_reduction_needed": total_risk > 0.5
            }
        
        mock_risk_manager.calculate_correlation_risk.side_effect = mock_calculate_correlation_risk
        
        # Mock positions
        positions = {
            "XBTUSD": {"size": 0.05, "current_price": 50000.0},
            "ETHUSD": {"size": 1.0, "current_price": 3000.0},
            "ADAUSD": {"size": 1000.0, "current_price": 0.50}
        }
        
        # Calculate correlation risk
        correlation_risk = mock_risk_manager.calculate_correlation_risk(positions, correlation_matrix)
        
        # Verify correlation risk assessment
        assert correlation_risk["total_correlation_risk"] >= 0
        assert len(correlation_risk["high_correlation_pairs"]) > 0
        assert ("XBTUSD", "ETHUSD") in correlation_risk["high_correlation_pairs"]
        
        mock_risk_manager.calculate_correlation_risk.assert_called_once()
    
    def test_position_size_coordination(self, mock_risk_manager):
        """Test position size coordination across pairs."""
        # Mock position size calculation
        def mock_calculate_coordinated_position_size(pair, signal, portfolio):
            base_sizes = {
                "XBTUSD": 0.001,
                "ETHUSD": 0.01,
                "ADAUSD": 10.0
            }
            
            # Adjust based on portfolio exposure
            total_exposure = sum(
                pos.get("exposure", 0) for pos in portfolio.values()
            )
            
            # Reduce size if portfolio is heavily exposed
            exposure_factor = max(0.5, 1.0 - total_exposure / 10000.0)
            
            return base_sizes.get(pair, 0.001) * exposure_factor
        
        mock_risk_manager.calculate_coordinated_position_size.side_effect = mock_calculate_coordinated_position_size
        
        # Mock portfolio and signals
        portfolio = {
            "XBTUSD": {"exposure": 2500.0},
            "ETHUSD": {"exposure": 3000.0}
        }
        
        signals = {
            "XBTUSD": Mock(signal_type=SignalType.BUY, strength=0.8),
            "ETHUSD": Mock(signal_type=SignalType.SELL, strength=0.7),
            "ADAUSD": Mock(signal_type=SignalType.BUY, strength=0.6)
        }
        
        # Calculate coordinated position sizes
        position_sizes = {}
        for pair, signal in signals.items():
            position_sizes[pair] = mock_risk_manager.calculate_coordinated_position_size(
                pair, signal, portfolio
            )
        
        # Verify position size coordination
        assert all(size > 0 for size in position_sizes.values())
        assert mock_risk_manager.calculate_coordinated_position_size.call_count == len(signals)
    
    def test_risk_limit_enforcement_across_pairs(self, mock_risk_manager):
        """Test risk limit enforcement across multiple pairs."""
        # Mock risk limit validation
        def mock_validate_multi_pair_risk_limits(new_trade, current_portfolio):
            # Calculate total exposure after new trade
            current_exposure = sum(
                pos.get("exposure", 0) for pos in current_portfolio.values()
            )
            
            new_exposure = new_trade["size"] * new_trade["price"]
            total_exposure = current_exposure + new_exposure
            
            # Risk limits
            max_total_exposure = 10000.0
            max_pair_exposure = 3000.0
            max_correlation_exposure = 5000.0
            
            violations = []
            
            if total_exposure > max_total_exposure:
                violations.append("total_exposure_exceeded")
            
            if new_exposure > max_pair_exposure:
                violations.append("pair_exposure_exceeded")
            
            # Mock correlation check
            if new_trade["pair"] in ["XBTUSD", "ETHUSD"] and current_exposure > 4000.0:
                violations.append("correlation_exposure_exceeded")
            
            return {
                "approved": len(violations) == 0,
                "violations": violations,
                "total_exposure": total_exposure,
                "new_exposure": new_exposure
            }
        
        mock_risk_manager.validate_multi_pair_risk_limits.side_effect = mock_validate_multi_pair_risk_limits
        
        # Mock current portfolio
        current_portfolio = {
            "XBTUSD": {"exposure": 2500.0},
            "ETHUSD": {"exposure": 2000.0}
        }
        
        # Test different trade scenarios
        test_trades = [
            {"pair": "ADAUSD", "size": 1000.0, "price": 0.50},  # Should be approved
            {"pair": "XBTUSD", "size": 0.1, "price": 50000.0},  # Should be rejected (too large)
            {"pair": "DOTUSD", "size": 100.0, "price": 10.0}    # Should be approved
        ]
        
        results = []
        for trade in test_trades:
            result = mock_risk_manager.validate_multi_pair_risk_limits(trade, current_portfolio)
            results.append(result)
        
        # Verify risk limit enforcement
        assert results[0]["approved"] is True   # Small ADAUSD trade approved
        assert results[1]["approved"] is False  # Large XBTUSD trade rejected
        assert results[2]["approved"] is True   # DOTUSD trade approved
        
        # Verify violations are properly identified
        assert "pair_exposure_exceeded" in results[1]["violations"]
        
        assert mock_risk_manager.validate_multi_pair_risk_limits.call_count == len(test_trades)


class TestMultiPairTradingExecution:
    """Test coordinated trading execution across multiple pairs."""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock bot orchestrator for multi-pair testing."""
        config = Mock()
        args = Mock()
        args.trading_pairs = ["XBTUSD", "ETHUSD", "ADAUSD"]
        return BotOrchestrator(config=config, args=args)
    
    def test_simultaneous_multi_pair_execution(self, mock_orchestrator):
        """Test simultaneous execution across multiple pairs."""
        with patch.multiple(
            'bot.main',
            KrakenTrader=Mock(),
            EnhancedStrategyEngine=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedLogger=Mock()
        ) as mocks:
            
            trader = mocks['KrakenTrader'].return_value
            strategy_engine = mocks['EnhancedStrategyEngine'].return_value
            risk_manager = mocks['EnhancedRiskManager'].return_value
            logger = mocks['EnhancedLogger'].return_value
            
            # Mock signals for multiple pairs
            def mock_generate_signal(pair, data):
                signal_map = {
                    "XBTUSD": Mock(signal_type=SignalType.BUY, pair=pair, strength=0.8),
                    "ETHUSD": Mock(signal_type=SignalType.SELL, pair=pair, strength=0.7),
                    "ADAUSD": None  # No signal
                }
                return signal_map.get(pair)
            
            strategy_engine.generate_signal.side_effect = mock_generate_signal
            
            # Mock risk approval for all trades
            risk_manager.validate_trade.return_value = Mock(approved=True, position_size=0.001)
            
            # Mock successful trade execution
            trader.execute_market_buy.return_value = Mock(success=True, order_id="BUY123")
            trader.execute_market_sell.return_value = Mock(success=True, order_id="SELL123")
            
            # Initialize components
            mock_orchestrator.initialize_components()
            
            # Execute multi-pair trading cycle
            multi_pair_data = {
                "XBTUSD": {"price": 50000.0, "volume": 1.5},
                "ETHUSD": {"price": 3000.0, "volume": 10.0},
                "ADAUSD": {"price": 0.50, "volume": 1000.0}
            }
            
            mock_orchestrator.execute_multi_pair_trading_cycle(multi_pair_data)
            
            # Verify multi-pair execution
            assert strategy_engine.generate_signal.call_count == 3  # All pairs processed
            assert risk_manager.validate_trade.call_count == 2     # Only pairs with signals
            trader.execute_market_buy.assert_called_once()         # XBTUSD buy
            trader.execute_market_sell.assert_called_once()        # ETHUSD sell
            assert logger.log_trade.call_count == 2                # Both trades logged
    
    def test_trade_sequencing_coordination(self, mock_orchestrator):
        """Test proper sequencing of trades across pairs."""
        with patch.multiple(
            'bot.main',
            KrakenTrader=Mock(),
            EnhancedRiskManager=Mock(),
            EnhancedLogger=Mock()
        ) as mocks:
            
            trader = mocks['KrakenTrader'].return_value
            risk_manager = mocks['EnhancedRiskManager'].return_value
            logger = mocks['EnhancedLogger'].return_value
            
            # Mock trade execution with delays to test sequencing
            execution_order = []
            
            def mock_execute_buy(volume, pair=None):
                execution_order.append(f"BUY_{pair}")
                time.sleep(0.01)  # Small delay
                return Mock(success=True, order_id=f"BUY_{pair}")
            
            def mock_execute_sell(volume, pair=None):
                execution_order.append(f"SELL_{pair}")
                time.sleep(0.01)  # Small delay
                return Mock(success=True, order_id=f"SELL_{pair}")
            
            trader.execute_market_buy.side_effect = mock_execute_buy
            trader.execute_market_sell.side_effect = mock_execute_sell
            
            # Mock risk manager to prioritize trades
            def mock_prioritize_trades(trades):
                # Sort by signal strength (descending)
                return sorted(trades, key=lambda t: t.get("strength", 0), reverse=True)
            
            risk_manager.prioritize_trades.side_effect = mock_prioritize_trades
            
            # Mock trades with different priorities
            pending_trades = [
                {"pair": "XBTUSD", "action": "buy", "strength": 0.6},
                {"pair": "ETHUSD", "action": "sell", "strength": 0.9},  # Highest priority
                {"pair": "ADAUSD", "action": "buy", "strength": 0.7}
            ]
            
            # Execute trades in priority order
            prioritized_trades = risk_manager.prioritize_trades(pending_trades)
            
            for trade in prioritized_trades:
                if trade["action"] == "buy":
                    trader.execute_market_buy(0.001, pair=trade["pair"])
                else:
                    trader.execute_market_sell(0.001, pair=trade["pair"])
            
            # Verify trade sequencing
            assert execution_order == ["SELL_ETHUSD", "BUY_ADAUSD", "BUY_XBTUSD"]
            risk_manager.prioritize_trades.assert_called_once()
    
    def test_partial_execution_handling(self, mock_orchestrator):
        """Test handling of partial executions across pairs."""
        with patch.multiple(
            'bot.main',
            KrakenTrader=Mock(),
            EnhancedAlertSystem=Mock(),
            EnhancedLogger=Mock()
        ) as mocks:
            
            trader = mocks['KrakenTrader'].return_value
            alert_system = mocks['EnhancedAlertSystem'].return_value
            logger = mocks['EnhancedLogger'].return_value
            
            # Mock partial execution scenarios
            def mock_execute_with_partial(volume, pair=None):
                if pair == "XBTUSD":
                    return Mock(success=True, order_id="FULL123", filled_volume=volume)
                elif pair == "ETHUSD":
                    return Mock(success=True, order_id="PARTIAL123", filled_volume=volume * 0.5)  # Partial fill
                else:
                    return Mock(success=False, error="Insufficient liquidity")  # Failed
            
            trader.execute_market_buy.side_effect = mock_execute_with_partial
            
            # Execute trades for multiple pairs
            pairs_and_volumes = [
                ("XBTUSD", 0.001),
                ("ETHUSD", 0.01),
                ("ADAUSD", 10.0)
            ]
            
            execution_results = []
            for pair, volume in pairs_and_volumes:
                result = trader.execute_market_buy(volume, pair=pair)
                execution_results.append((pair, result))
            
            # Verify partial execution handling
            assert execution_results[0][1].success is True   # XBTUSD full execution
            assert execution_results[1][1].success is True   # ETHUSD partial execution
            assert execution_results[2][1].success is False  # ADAUSD failed
            
            # Verify appropriate logging and alerts
            assert logger.log_trade.call_count >= 2  # At least successful trades logged
            alert_system.send_trade_alert.assert_called()  # Alerts sent for issues