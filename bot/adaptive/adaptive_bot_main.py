"""
Main Adaptive Bot Application

This module implements the main application class that orchestrates all adaptive
components including market regime detection, strategy selection, ML engine,
parameter optimization, and adaptation control.
"""
import asyncio
import logging
import signal
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
import pandas as pd
import numpy as np
from pathlib import Path
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Core adaptive components
from .market_regime_detector import MarketRegimeDetector
from .adaptive_strategy_engine import AdaptiveStrategyEngine
from .ml_engine import MLEngine
from .parameter_optimizer import ParameterOptimizer
from .performance_analyzer import PerformanceAnalyzer
from .adaptation_controller import AdaptationController, AdaptationLimits
from .monitoring_dashboard import MonitoringDashboard
from .alerting_system import AlertingSystem
from .adaptive_config import AdaptiveBotConfig as AdaptiveConfig
from .paper_trading import PaperTradingEngine
from .portfolio_optimizer import PortfolioOptimizer, PortfolioPosition, OpportunityScore

# Data models and interfaces
from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics,
    AdaptationEvent, StrategyAllocation
)
from .enums import RegimeType, AdaptationType, SignalStrength
from .interfaces import (
    MarketRegimeDetectorInterface, AdaptiveStrategyEngineInterface,
    MLEngineInterface, ParameterOptimizerInterface,
    PerformanceAnalyzerInterface, AdaptationControllerInterface
)

# Enhanced system integration
from ..enhanced_data_manager import EnhancedDataManager
from ..enhanced_risk_manager import EnhancedRiskManager
from ..kraken_client import KrakenClient
from ..utils import setup_logging, log_info, log_warning, log_error


@dataclass
class AdaptiveBotConfig:
    """Configuration for the adaptive bot - AGGRESSIVE $480 SETUP."""
    # Trading configuration
    trading_pairs: List[str] = field(default_factory=lambda: ["BTC/USD", "ETH/USD"])
    paper_trading: bool = True
    initial_capital: float = 480.0
    max_positions: int = 3  # Reduced for aggressive focus
    
    # Adaptive behavior configuration - AGGRESSIVE
    adaptation_enabled: bool = True
    adaptation_frequency_minutes: int = 30  # More frequent adaptations
    min_adaptation_confidence: float = 0.5  # Lower threshold for more adaptations
    max_adaptations_per_day: int = 15  # More adaptations allowed
    
    # Risk management - AGGRESSIVE
    max_risk_per_trade: float = 0.08  # 8% per trade (aggressive)
    max_portfolio_risk: float = 0.25   # 25% total portfolio risk
    max_drawdown_threshold: float = 0.20  # 20% max drawdown
    
    # Performance thresholds - AGGRESSIVE
    min_performance_threshold: float = -0.05  # Adapt after 5% drop
    performance_evaluation_hours: int = 12  # Faster evaluation cycles
    
    # Data and monitoring
    data_retention_days: int = 90
    monitoring_enabled: bool = True
    alerting_enabled: bool = True
    
    # System configuration
    max_threads: int = 4
    health_check_interval_seconds: int = 30
    state_persistence_interval_minutes: int = 15


@dataclass
class SystemHealth:
    """System health status."""
    overall_status: str = "healthy"  # healthy, degraded, critical
    component_status: Dict[str, str] = field(default_factory=dict)
    last_health_check: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    warning_count: int = 0
    uptime_seconds: float = 0.0
    
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return self.overall_status == "healthy"
    
    def add_error(self, component: str, error: str):
        """Add an error to the health status."""
        self.error_count += 1
        self.component_status[component] = f"error: {error}"
        if self.error_count > 5:
            self.overall_status = "critical"
        elif self.error_count > 2:
            self.overall_status = "degraded"
    
    def add_warning(self, component: str, warning: str):
        """Add a warning to the health status."""
        self.warning_count += 1
        self.component_status[component] = f"warning: {warning}"
        if self.overall_status == "healthy" and self.warning_count > 3:
            self.overall_status = "degraded"


class AdaptiveBotMain:
    """
    Main adaptive bot application that orchestrates all components.
    
    This class manages the lifecycle of the adaptive trading bot, including:
    - Component initialization and validation
    - Main trading loop execution
    - Health monitoring and alerting
    - Graceful shutdown with state persistence
    - Multi-pair coordination
    """
    
    def __init__(self, config: AdaptiveBotConfig = None):
        """
        Initialize the adaptive bot main application.
        
        Args:
            config: Configuration for the adaptive bot
        """
        self.config = config or AdaptiveBotConfig()
        self.logger = logging.getLogger(__name__)
        
        # System state
        self.is_running = False
        self.start_time = datetime.now()
        self.shutdown_requested = False
        self.health = SystemHealth()
        
        # Core components (initialized in startup)
        self.data_manager: Optional[EnhancedDataManager] = None
        self.risk_manager: Optional[EnhancedRiskManager] = None
        self.regime_detector: Optional[MarketRegimeDetector] = None
        self.strategy_engine: Optional[AdaptiveStrategyEngine] = None
        self.ml_engine: Optional[MLEngine] = None
        self.parameter_optimizer: Optional[ParameterOptimizer] = None
        self.performance_analyzer: Optional[PerformanceAnalyzer] = None
        self.adaptation_controller: Optional[AdaptationController] = None
        self.monitoring_dashboard: Optional[MonitoringDashboard] = None
        self.alerting_system: Optional[AlertingSystem] = None
        self.paper_trading_engine: Optional[PaperTradingEngine] = None
        self.kraken_client: Optional[KrakenClient] = None
        self.portfolio_optimizer: Optional[PortfolioOptimizer] = None
        
        # Threading and execution
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_threads)
        self.background_tasks: List[threading.Thread] = []
        
        # State persistence
        self.state_file = Path("adaptive_bot_state.json")
        self.last_state_save = datetime.now()
        
        # Performance tracking
        self.cycle_count = 0
        self.last_adaptation_time = datetime.now()
        self.adaptation_history: List[AdaptationEvent] = []
        
        # Signal handling for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
    
    async def initialize_components(self) -> bool:
        """
        Initialize all adaptive bot components.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            self.logger.info("🚀 Initializing adaptive bot components...")
            
            # Load adaptive configuration
            self.adaptive_config = AdaptiveConfig()
            
            # Initialize data manager
            self.logger.info("📊 Initializing enhanced data manager...")
            self.data_manager = EnhancedDataManager(self.adaptive_config.trading_pairs)
            self.health.component_status["data_manager"] = "healthy"
            
            # Initialize Kraken client first (needed by other components)
            temp_kraken_client = None
            if not self.adaptive_config.paper_trading:
                self.logger.info("🔗 Initializing Kraken client...")
                from ..kraken_client import KrakenClient
                temp_kraken_client = KrakenClient()
            
            # Initialize position manager (required for risk manager)
            self.logger.info("💰 Initializing position manager...")
            from ..crypto_position_manager import CryptoPositionManager
            self.position_manager = CryptoPositionManager(temp_kraken_client)
            
            # Initialize risk manager
            self.logger.info("🛡️ Initializing enhanced risk manager...")
            from ..enhanced_risk_manager import EnhancedRiskManager
            
            self.risk_manager = EnhancedRiskManager(
                position_manager=self.position_manager,
                data_manager=self.data_manager,
                kraken_client=temp_kraken_client,
                trading_pairs=self.adaptive_config.trading_pairs
            )
            self.health.component_status["risk_manager"] = "healthy"
            
            # Initialize Kraken client if not paper trading
            if not self.config.paper_trading:
                self.logger.info("🔗 Initializing Kraken client...")
                self.kraken_client = KrakenClient()
                if not await self.kraken_client.test_connection():
                    raise Exception("Failed to connect to Kraken API")
                self.health.component_status["kraken_client"] = "healthy"
            
            # Initialize paper trading engine if needed
            if self.config.paper_trading:
                self.logger.info("📝 Initializing paper trading engine...")
                from .paper_trading import PaperTradingConfig
                paper_config = PaperTradingConfig(initial_capital=self.adaptive_config.initial_capital)
                self.paper_trading_engine = PaperTradingEngine(
                    config=paper_config,
                    data_manager=self.data_manager
                )
                self.health.component_status["paper_trading"] = "healthy"
            
            # Initialize market regime detector
            self.logger.info("🔍 Initializing market regime detector...")
            regime_config = self.adaptive_config.get_regime_detector_config()
            self.regime_detector = MarketRegimeDetector(regime_config)
            self.health.component_status["regime_detector"] = "healthy"
            
            # Initialize ML engine
            self.logger.info("🧠 Initializing ML engine...")
            ml_config = self.adaptive_config.get_ml_engine_config()
            model_path = ml_config.get('model_storage_path', 'models/adaptive')
            self.ml_engine = MLEngine(model_path)
            self.health.component_status["ml_engine"] = "healthy"
            
            # Initialize parameter optimizer
            self.logger.info("⚙️ Initializing parameter optimizer...")
            optimizer_config = self.adaptive_config.get_optimizer_config()
            self.parameter_optimizer = ParameterOptimizer(optimizer_config)
            self.health.component_status["parameter_optimizer"] = "healthy"
            
            # Initialize performance analyzer
            self.logger.info("📈 Initializing performance analyzer...")
            perf_config = self.adaptive_config.get_performance_config()
            self.performance_analyzer = PerformanceAnalyzer(perf_config)
            self.health.component_status["performance_analyzer"] = "healthy"
            
            # Initialize adaptive strategy engine
            self.logger.info("🎯 Initializing adaptive strategy engine...")
            strategy_config = self.adaptive_config.get_strategy_engine_config()
            self.strategy_engine = AdaptiveStrategyEngine(strategy_config)
            self.health.component_status["strategy_engine"] = "healthy"
            
            # Initialize adaptation controller
            self.logger.info("🎛️ Initializing adaptation controller...")
            adaptation_config = self.adaptive_config.get_adaptation_config()
            # Convert dictionary to AdaptationLimits object with proper field mapping
            adaptation_limits = AdaptationLimits(
                max_adaptations_per_hour=adaptation_config.get('max_adaptations_per_hour', 2),
                max_adaptations_per_day=adaptation_config.get('max_adaptations_per_day', 10),
                min_time_between_adaptations=timedelta(minutes=adaptation_config.get('min_time_between_adaptations_minutes', 30)),
                min_performance_threshold=adaptation_config.get('min_performance_threshold', -0.05),
                min_confidence_threshold=adaptation_config.get('adaptation_confidence_threshold', 0.6),
                max_parameter_change_percent=adaptation_config.get('max_parameter_change_percent', 0.2),
                max_strategy_weight_change=adaptation_config.get('max_strategy_weight_change', 0.1),
                min_data_points_for_adaptation=adaptation_config.get('min_data_points_for_adaptation', 100),
                min_evaluation_period=timedelta(hours=adaptation_config.get('min_evaluation_period_hours', 2)),
                emergency_drawdown_threshold=adaptation_config.get('emergency_drawdown_threshold', -0.1),
                emergency_performance_threshold=adaptation_config.get('emergency_performance_threshold', -0.15)
            )
            self.adaptation_controller = AdaptationController(adaptation_limits)
            self.health.component_status["adaptation_controller"] = "healthy"
            
            # Initialize monitoring dashboard
            if self.config.monitoring_enabled:
                self.logger.info("📊 Initializing monitoring dashboard...")
                self.monitoring_dashboard = MonitoringDashboard()
                self.health.component_status["monitoring"] = "healthy"
            
            # Initialize alerting system
            if self.config.alerting_enabled:
                self.logger.info("🚨 Initializing alerting system...")
                self.alerting_system = AlertingSystem()
                self.health.component_status["alerting"] = "healthy"
            
            # Initialize portfolio optimizer
            self.logger.info("📊 Initializing portfolio optimizer...")
            portfolio_config = {
                'max_pairs': len(self.adaptive_config.trading_pairs),
                'max_correlation': 0.7,
                'max_single_pair_allocation': 0.4,
                'rebalance_threshold': 0.1,
                'target_volatility': 0.15
            }
            self.portfolio_optimizer = PortfolioOptimizer(portfolio_config)
            self.health.component_status["portfolio_optimizer"] = "healthy"
            
            # Validate component integration
            await self._validate_component_integration()
            
            self.logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize components: {str(e)}")
            self.health.add_error("initialization", str(e))
            return False
    
    async def _validate_component_integration(self):
        """Validate that all components can work together."""
        self.logger.info("🔍 Validating component integration...")
        
        # Test data flow
        test_pair = self.adaptive_config.trading_pairs[0]
        
        # Check if data manager has async method
        if hasattr(self.data_manager, 'get_market_data'):
            if asyncio.iscoroutinefunction(self.data_manager.get_market_data):
                test_data = await self.data_manager.get_market_data(test_pair, limit=100)
            else:
                test_data = self.data_manager.get_latest_data(test_pair, periods=100)
        else:
            # Create mock data for testing
            import pandas as pd
            import numpy as np
            dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
            test_data = pd.DataFrame({
                'timestamp': dates,
                'open': np.random.uniform(40000, 45000, 100),
                'high': np.random.uniform(45000, 50000, 100),
                'low': np.random.uniform(35000, 40000, 100),
                'close': np.random.uniform(40000, 45000, 100),
                'volume': np.random.uniform(100, 1000, 100)
            })
        
        if test_data is None or (hasattr(test_data, 'empty') and test_data.empty):
            raise Exception(f"Failed to fetch test data for {test_pair}")
        
        # Test regime detection
        if hasattr(self.regime_detector, 'detect_regime'):
            regime = self.regime_detector.detect_regime(test_data, test_pair)
            if regime is None:
                raise Exception("Regime detection failed")
        
        # Test strategy engine
        if hasattr(self.strategy_engine, 'execute_adaptive_signal'):
            if asyncio.iscoroutinefunction(self.strategy_engine.execute_adaptive_signal):
                signal = await self.strategy_engine.execute_adaptive_signal(test_pair, test_data)
            else:
                signal = self.strategy_engine.execute_adaptive_signal(test_pair, test_data)
            
            if signal is None:
                self.logger.warning("Strategy engine returned no signal (this may be normal)")
        
        # Test ML engine if it has models
        try:
            if hasattr(self.ml_engine, 'get_model_confidence'):
                confidence = self.ml_engine.get_model_confidence("ensemble")
                self.logger.info(f"ML engine confidence: {confidence}")
        except Exception as e:
            self.logger.warning(f"ML engine not ready: {e}")
        
        self.logger.info("✅ Component integration validation passed")
    
    async def start(self) -> bool:
        """
        Start the adaptive bot.
        
        Returns:
            bool: True if startup successful, False otherwise
        """
        try:
            self.logger.info("🚀 Starting Adaptive Trading Bot...")
            
            # Initialize components
            if not await self.initialize_components():
                return False
            
            # Load previous state if available
            await self._load_state()
            
            # Start background tasks
            self._start_background_tasks()
            
            # Mark as running
            self.is_running = True
            self.start_time = datetime.now()
            
            self.logger.info("✅ Adaptive bot started successfully")
            self.logger.info(f"📊 Trading pairs: {', '.join(self.adaptive_config.trading_pairs)}")
            self.logger.info(f"💰 Initial capital: ${self.adaptive_config.initial_capital:,.2f}")
            self.logger.info(f"📝 Paper trading: {self.adaptive_config.paper_trading}")
            self.logger.info(f"🎛️ Adaptation enabled: {self.adaptive_config.adaptation_enabled}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start adaptive bot: {str(e)}")
            self.health.add_error("startup", str(e))
            return False
    
    def _start_background_tasks(self):
        """Start background monitoring and maintenance tasks."""
        # Health monitoring task
        health_task = threading.Thread(
            target=self._health_monitoring_loop,
            daemon=True,
            name="health_monitor"
        )
        health_task.start()
        self.background_tasks.append(health_task)
        
        # State persistence task
        persistence_task = threading.Thread(
            target=self._state_persistence_loop,
            daemon=True,
            name="state_persistence"
        )
        persistence_task.start()
        self.background_tasks.append(persistence_task)
        
        # Performance monitoring task
        perf_task = threading.Thread(
            target=self._performance_monitoring_loop,
            daemon=True,
            name="performance_monitor"
        )
        perf_task.start()
        self.background_tasks.append(perf_task)
        
        self.logger.info(f"✅ Started {len(self.background_tasks)} background tasks")
    
    async def run_main_loop(self):
        """
        Run the main adaptive bot trading loop.
        """
        self.logger.info("🔄 Starting main trading loop...")
        
        while self.is_running and not self.shutdown_requested:
            try:
                cycle_start = time.time()
                self.cycle_count += 1
                
                self.logger.info(f"🔄 Cycle #{self.cycle_count} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Execute trading cycle for all pairs
                try:
                    await self._execute_trading_cycle()
                except Exception as e:
                    self.logger.error(f"❌ Error in trading cycle: {str(e)}")
                    import traceback
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Check for adaptations
                if self.config.adaptation_enabled:
                    await self._check_and_execute_adaptations()
                
                # Update system health
                self.health.uptime_seconds = time.time() - self.start_time.timestamp()
                self.health.last_health_check = datetime.now()
                
                # Calculate cycle time and sleep
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, 60 - cycle_time)  # Target 1-minute cycles
                
                if sleep_time > 0:
                    self.logger.debug(f"⏳ Cycle completed in {cycle_time:.2f}s, sleeping {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                else:
                    self.logger.warning(f"⚠️ Cycle took {cycle_time:.2f}s (longer than 60s target)")
                
            except Exception as e:
                self.logger.error(f"❌ Error in main loop: {str(e)}")
                self.health.add_error("main_loop", str(e))
                await asyncio.sleep(5)  # Brief pause before retrying
        
        self.logger.info("🛑 Main trading loop stopped")
    
    async def _execute_trading_cycle(self):
        """Execute trading cycle for all configured pairs with portfolio optimization."""
        self.logger.debug(f"🔄 Executing trading cycle for pairs: {self.adaptive_config.trading_pairs}")
        
        # Step 1: Collect opportunities from all pairs
        opportunities = {}
        market_data_cache = {}
        
        for pair in self.adaptive_config.trading_pairs:
            try:
                # Fetch market data
                self.logger.debug(f"📊 Fetching market data for {pair}")
                market_data = await self.data_manager.get_market_data(pair, limit=200)
                if market_data is None or market_data.empty:
                    self.logger.warning(f"⚠️ No market data for {pair}")
                    continue
                
                self.logger.debug(f"✅ Got {len(market_data)} data points for {pair}")
                
                market_data_cache[pair] = market_data
                
                # Detect market regime
                regime = self.regime_detector.detect_regime(market_data, pair)
                
                # Generate adaptive signal
                signal = self.strategy_engine.execute_adaptive_signal(pair, market_data)
                
                if signal is not None:
                    # Add opportunity to portfolio optimizer
                    opportunity = self.portfolio_optimizer.add_opportunity(signal, market_data)
                    opportunities[pair] = opportunity
                    
                    self.logger.debug(f"📊 Opportunity for {pair}: score={opportunity.final_score:.3f}")
                
            except Exception as e:
                self.logger.error(f"❌ Error processing {pair}: {str(e)}")
                self.health.add_error(f"trading_{pair}", str(e))
        
        # Step 2: Update portfolio state
        await self._update_portfolio_state()
        
        # Step 3: Update correlation matrix
        if market_data_cache:
            self.portfolio_optimizer.update_correlation_matrix(market_data_cache)
        
        # Step 4: Check for rebalancing opportunities
        if self.portfolio_optimizer.should_rebalance():
            await self._execute_portfolio_rebalancing()
        
        # Step 5: Execute new opportunities based on portfolio optimization
        if opportunities:
            await self._execute_portfolio_optimized_trades(opportunities)
        
        # Step 6: Clean up expired opportunities
        self.portfolio_optimizer.cleanup_expired_opportunities()
    
    async def _execute_pair_trading_cycle(self, pair: str):
        """Execute trading cycle for a specific pair."""
        try:
            # Fetch market data
            market_data = await self.data_manager.get_market_data(pair, limit=200)
            if market_data is None or market_data.empty:
                self.logger.warning(f"⚠️ No market data for {pair}")
                return
            
            # Detect market regime
            regime = self.regime_detector.detect_regime(market_data, pair)
            
            # Generate adaptive signal
            signal = self.strategy_engine.execute_adaptive_signal(pair, market_data)
            
            if signal is None:
                self.logger.debug(f"📊 No signal generated for {pair}")
                return
            
            # Validate signal with risk management
            if not self.risk_manager.validate_signal(signal, market_data):
                self.logger.info(f"🛡️ Signal for {pair} rejected by risk management")
                return
            
            # Execute trade
            if self.config.paper_trading:
                await self._execute_paper_trade(signal, market_data)
            else:
                await self._execute_real_trade(signal, market_data)
            
            # Update performance tracking
            await self._update_performance_tracking(pair, signal, regime)
            
        except Exception as e:
            self.logger.error(f"❌ Error in trading cycle for {pair}: {str(e)}")
            raise
    
    async def _execute_paper_trade(self, signal: AdaptiveSignal, market_data: pd.DataFrame):
        """Execute a paper trade."""
        if self.paper_trading_engine:
            result = self.paper_trading_engine.execute_signal(signal)
            self.logger.info(f"📝 Paper trade executed: {result}")
    
    async def _execute_real_trade(self, signal: AdaptiveSignal, market_data: pd.DataFrame):
        """Execute a real trade through Kraken."""
        if self.kraken_client:
            # Implementation would go here
            self.logger.info(f"💰 Real trade would be executed: {signal}")
            pass
    
    async def _update_performance_tracking(self, pair: str, signal: AdaptiveSignal, regime: MarketRegime):
        """Update performance tracking for the pair and signal."""
        # Store regime data
        self.data_manager.store_regime_data(regime, pair)
        
        # Update strategy performance if we have results
        # This would be called after trade completion with actual results
        pass
    
    async def _update_portfolio_state(self):
        """Update the portfolio optimizer with current portfolio state."""
        try:
            # Get current positions (this would come from the trading engine)
            positions = {}
            total_capital = self.adaptive_config.initial_capital
            available_capital = total_capital
            
            # In a real implementation, this would fetch actual positions
            # For now, we'll use mock data or paper trading positions
            if self.paper_trading_engine:
                # Get positions from paper trading engine
                paper_positions = getattr(self.paper_trading_engine, 'positions', {})
                
                for pair, position_data in paper_positions.items():
                    if isinstance(position_data, dict):
                        positions[pair] = PortfolioPosition(
                            pair=pair,
                            size=position_data.get('size', 0.0),
                            entry_price=position_data.get('entry_price', 0.0),
                            current_price=position_data.get('current_price', 0.0),
                            unrealized_pnl=position_data.get('unrealized_pnl', 0.0),
                            realized_pnl=position_data.get('realized_pnl', 0.0),
                            allocation_percentage=position_data.get('allocation_percentage', 0.0),
                            risk_contribution=position_data.get('risk_contribution', 0.0)
                        )
                
                # Update capital from paper trading
                total_capital = getattr(self.paper_trading_engine, 'total_capital', self.adaptive_config.initial_capital)
                available_capital = getattr(self.paper_trading_engine, 'available_capital', total_capital)
            
            # Update portfolio optimizer
            self.portfolio_optimizer.update_portfolio_state(positions, total_capital, available_capital)
            
        except Exception as e:
            self.logger.error(f"❌ Error updating portfolio state: {str(e)}")
    
    async def _execute_portfolio_rebalancing(self):
        """Execute portfolio rebalancing orders."""
        try:
            rebalancing_orders = self.portfolio_optimizer.generate_rebalancing_orders()
            
            if not rebalancing_orders:
                return
            
            self.logger.info(f"🔄 Executing {len(rebalancing_orders)} rebalancing orders")
            
            for order in rebalancing_orders:
                pair = order['pair']
                order_type = order['type']
                size = order['size']
                reason = order['reason']
                
                self.logger.info(f"📊 Rebalancing {pair}: {order_type} ${size:,.2f} ({reason})")
                
                # Execute rebalancing order
                if self.config.paper_trading and self.paper_trading_engine:
                    # Create a mock signal for rebalancing
                    rebalance_signal = AdaptiveSignal(
                        pair=pair,
                        signal_type=order_type,
                        strength=SignalStrength.MODERATE,
                        confidence=0.8,
                        price=0.0,  # Would be filled by execution
                        timestamp=datetime.now(),
                        regime_context=MarketRegime(
                            regime_type=RegimeType.UNCERTAIN,
                            confidence=0.5,
                            volatility_level=0.5,
                            trend_strength=0.0,
                            momentum=0.0,
                            detected_at=datetime.now()
                        ),
                        ml_confidence=0.7,
                        suggested_position_size=size
                    )
                    
                    # Execute through paper trading
                    market_data = await self.data_manager.get_market_data(pair, limit=10)
                    if market_data is not None:
                        await self._execute_paper_trade(rebalance_signal, market_data)
                
                elif not self.config.paper_trading and self.kraken_client:
                    # Execute real rebalancing trade
                    await self._execute_real_trade_with_size(pair, order_type, size)
            
        except Exception as e:
            self.logger.error(f"❌ Error executing portfolio rebalancing: {str(e)}")
    
    async def _execute_portfolio_optimized_trades(self, opportunities: Dict[str, OpportunityScore]):
        """Execute trades based on portfolio optimization."""
        try:
            # Get optimal capital allocation
            optimal_allocations = self.portfolio_optimizer.optimize_capital_allocation(opportunities)
            
            if not optimal_allocations:
                self.logger.debug("📊 No optimal allocations found")
                return
            
            self.logger.info(f"📊 Executing portfolio-optimized trades for {len(optimal_allocations)} pairs")
            
            for pair, allocation in optimal_allocations.items():
                if pair not in opportunities:
                    continue
                
                opportunity = opportunities[pair]
                signal = opportunity.signal
                
                # Validate signal with risk management
                market_data = await self.data_manager.get_market_data(pair, limit=10)
                if market_data is None:
                    continue
                
                if not self.risk_manager.validate_signal(signal, market_data):
                    self.logger.info(f"🛡️ Signal for {pair} rejected by risk management")
                    continue
                
                # Calculate position size based on allocation
                position_size = allocation * self.portfolio_optimizer.total_capital
                
                # Update signal with portfolio-optimized position size
                signal.suggested_position_size = position_size
                
                self.logger.info(f"📊 Portfolio trade {pair}: {signal.signal_type} "
                               f"${position_size:,.2f} (allocation: {allocation:.1%})")
                
                # Execute trade
                if self.config.paper_trading:
                    await self._execute_paper_trade(signal, market_data)
                else:
                    await self._execute_real_trade(signal, market_data)
                
                # Update performance tracking
                regime = signal.regime_context
                await self._update_performance_tracking(pair, signal, regime)
            
        except Exception as e:
            self.logger.error(f"❌ Error executing portfolio-optimized trades: {str(e)}")
    
    async def _execute_real_trade_with_size(self, pair: str, order_type: str, size: float):
        """Execute a real trade with specific size for rebalancing."""
        if self.kraken_client:
            # Implementation would go here for real trading
            self.logger.info(f"💰 Real rebalancing trade would be executed: {pair} {order_type} ${size:,.2f}")
            pass
    
    async def _check_and_execute_adaptations(self):
        """Check if adaptations should be executed and execute them."""
        try:
            # Check if enough time has passed since last adaptation
            time_since_last = datetime.now() - self.last_adaptation_time
            min_interval = timedelta(minutes=self.config.adaptation_frequency_minutes)
            
            if time_since_last < min_interval:
                return
            
            # Get current performance metrics
            performance_metrics = {}
            for pair in self.adaptive_config.trading_pairs:
                metrics = self.performance_analyzer.analyze_strategy_performance(
                    "adaptive_ensemble", 
                    f"{self.config.performance_evaluation_hours}h"
                )
                performance_metrics[pair] = metrics
            
            # Check if adaptation is needed
            for pair, metrics in performance_metrics.items():
                should_adapt = self.adaptation_controller.should_adapt(metrics, "adaptive_ensemble")
                
                if should_adapt:
                    self.logger.info(f"🎛️ Adaptation triggered for {pair}")
                    await self._execute_adaptation(pair, metrics)
            
        except Exception as e:
            self.logger.error(f"❌ Error in adaptation check: {str(e)}")
            self.health.add_error("adaptation", str(e))
    
    async def _execute_adaptation(self, pair: str, metrics: PerformanceMetrics):
        """Execute an adaptation for a specific pair."""
        try:
            # Create adaptation event
            event = AdaptationEvent(
                event_id=str(uuid.uuid4()),
                event_type=AdaptationType.STRATEGY_REBALANCING,
                trigger_reason=f"Performance below threshold for {pair}",
                changes_made={},
                expected_impact=0.05,  # Expected 5% improvement
                affected_pairs=[pair]
            )
            
            # Execute the adaptation through the controller
            success = self.adaptation_controller.execute_adaptation(event)
            
            if success:
                self.adaptation_history.append(event)
                self.last_adaptation_time = datetime.now()
                self.logger.info(f"✅ Adaptation executed successfully for {pair}")
                
                # Send alert if alerting is enabled
                if self.alerting_system:
                    # Create an alert for the adaptation event
                    from .alerting_system import Alert, AlertLevel, AlertChannel
                    alert = Alert(
                        level=AlertLevel.INFO,
                        title="Adaptation Executed",
                        message=f"Adaptation executed for {pair}",
                        timestamp=datetime.now(),
                        source="adaptation_controller"
                    )
                    self.alerting_system.send_alert(alert, [AlertChannel.LOG])
            else:
                self.logger.warning(f"⚠️ Adaptation failed for {pair}")
            
        except Exception as e:
            self.logger.error(f"❌ Error executing adaptation: {str(e)}")
            self.health.add_error("adaptation_execution", str(e))
    
    def _health_monitoring_loop(self):
        """Background task for health monitoring."""
        while self.is_running and not self.shutdown_requested:
            try:
                # Update health status
                self.health.last_health_check = datetime.now()
                
                # Check component health
                self._check_component_health()
                
                # Send health alerts if needed
                if not self.health.is_healthy() and self.alerting_system:
                    asyncio.create_task(self.alerting_system.send_health_alert(self.health))
                
                time.sleep(self.config.health_check_interval_seconds)
                
            except Exception as e:
                self.logger.error(f"❌ Error in health monitoring: {str(e)}")
                time.sleep(30)  # Wait longer on error
    
    def _check_component_health(self):
        """Check the health of all components."""
        # This would implement actual health checks for each component
        # For now, we'll just update the uptime
        self.health.uptime_seconds = time.time() - self.start_time.timestamp()
    
    def _state_persistence_loop(self):
        """Background task for state persistence."""
        while self.is_running and not self.shutdown_requested:
            try:
                time_since_save = datetime.now() - self.last_state_save
                save_interval = timedelta(minutes=self.config.state_persistence_interval_minutes)
                
                if time_since_save >= save_interval:
                    asyncio.create_task(self._save_state())
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                self.logger.error(f"❌ Error in state persistence: {str(e)}")
                time.sleep(300)  # Wait 5 minutes on error
    
    def _performance_monitoring_loop(self):
        """Background task for performance monitoring."""
        while self.is_running and not self.shutdown_requested:
            try:
                # Monitor system performance
                if self.monitoring_dashboard:
                    asyncio.create_task(self.monitoring_dashboard.update_metrics())
                
                time.sleep(300)  # Update every 5 minutes
                
            except Exception as e:
                self.logger.error(f"❌ Error in performance monitoring: {str(e)}")
                time.sleep(300)
    
    async def _save_state(self):
        """Save current system state to disk."""
        try:
            state = {
                'start_time': self.start_time.isoformat(),
                'cycle_count': self.cycle_count,
                'last_adaptation_time': self.last_adaptation_time.isoformat(),
                'adaptation_history': [
                    {
                        'event_id': event.event_id,
                        'event_type': event.event_type.value,
                        'timestamp': event.timestamp.isoformat(),
                        'success': event.success
                    }
                    for event in self.adaptation_history[-10:]  # Keep last 10
                ],
                'health': {
                    'overall_status': self.health.overall_status,
                    'error_count': self.health.error_count,
                    'warning_count': self.health.warning_count,
                    'uptime_seconds': self.health.uptime_seconds
                }
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            self.last_state_save = datetime.now()
            self.logger.debug("💾 System state saved")
            
        except Exception as e:
            self.logger.error(f"❌ Error saving state: {str(e)}")
    
    async def _load_state(self):
        """Load previous system state from disk."""
        try:
            if not self.state_file.exists():
                self.logger.info("📂 No previous state file found")
                return
            
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            # Restore relevant state
            self.cycle_count = state.get('cycle_count', 0)
            
            if 'last_adaptation_time' in state:
                self.last_adaptation_time = datetime.fromisoformat(state['last_adaptation_time'])
            
            self.logger.info(f"📂 Previous state loaded (cycle #{self.cycle_count})")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error loading previous state: {str(e)}")
    
    async def shutdown(self):
        """Gracefully shutdown the adaptive bot."""
        self.logger.info("🛑 Initiating graceful shutdown...")
        
        # Mark as shutting down
        self.is_running = False
        self.shutdown_requested = True
        
        try:
            # Save final state
            await self._save_state()
            
            # Shutdown components
            if self.data_manager:
                await self.data_manager.shutdown()
            
            # Wait for background tasks to complete
            for task in self.background_tasks:
                if task.is_alive():
                    task.join(timeout=5)
            
            # Shutdown executor
            self.executor.shutdown(wait=True, timeout=10)
            
            self.logger.info("✅ Graceful shutdown completed")
            
        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        return {
            'is_running': self.is_running,
            'uptime_seconds': self.health.uptime_seconds,
            'cycle_count': self.cycle_count,
            'health': {
                'overall_status': self.health.overall_status,
                'component_status': self.health.component_status,
                'error_count': self.health.error_count,
                'warning_count': self.health.warning_count
            },
            'config': {
                'trading_pairs': self.adaptive_config.trading_pairs,
                'paper_trading': self.config.paper_trading,
                'adaptation_enabled': self.config.adaptation_enabled
            },
            'last_adaptation': self.last_adaptation_time.isoformat() if self.last_adaptation_time else None,
            'adaptations_today': len([
                event for event in self.adaptation_history
                if event.timestamp.date() == datetime.now().date()
            ])
        }
    
    def get_health_check(self) -> Dict[str, Any]:
        """Get health check endpoint response."""
        return {
            'status': self.health.overall_status,
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': self.health.uptime_seconds,
            'components': self.health.component_status,
            'errors': self.health.error_count,
            'warnings': self.health.warning_count
        }


# Main execution functions
async def main():
    """Main function for running the adaptive bot."""
    # Setup logging
    setup_logging("INFO")
    logger = logging.getLogger(__name__)
    
    try:
        # Create configuration
        config = AdaptiveBotConfig()
        
        # Create and start the bot
        bot = AdaptiveBotMain(config)
        
        if not await bot.start():
            logger.error("❌ Failed to start adaptive bot")
            sys.exit(1)
        
        # Run the main loop
        await bot.run_main_loop()
        
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown requested by user")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)
    finally:
        if 'bot' in locals():
            await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())