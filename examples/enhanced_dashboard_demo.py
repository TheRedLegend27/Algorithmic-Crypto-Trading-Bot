#!/usr/bin/env python3
"""
Enhanced Dashboard Demo

This script demonstrates the enhanced dashboard functionality with real-time monitoring,
portfolio visualization, trading activity feed, performance charts, and manual trading controls.
"""
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import Mock

from bot.enhanced_dashboard import (
    EnhancedDashboard, DashboardConfig, Portfolio, TradeExecution,
    SystemHealth, PortfolioMetrics
)
from bot.enhanced_data_manager import EnhancedDataManager, MarketData
from bot.enhanced_data_manager import PerformanceMetrics as DataPerformanceMetrics
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.kraken_client import KrakenClient


def create_mock_dependencies():
    """Create mock dependencies for the dashboard demo."""
    # Mock data manager
    mock_data_manager = Mock(spec=EnhancedDataManager)
    mock_data_manager.calculate_performance_metrics.return_value = DataPerformanceMetrics(
        fetch_time_ms=45.2,
        cache_hit_rate=0.87,
        data_quality_score=0.96,
        indicator_calculation_time_ms=23.1,
        memory_usage_mb=142.5,
        active_pairs=4,
        total_data_points=8500
    )
    
    # Mock logger
    mock_logger = Mock(spec=EnhancedLogger)
    
    # Mock risk manager
    mock_risk_manager = Mock(spec=EnhancedRiskManager)
    
    # Mock Kraken client
    mock_kraken_client = Mock(spec=KrakenClient)
    
    return mock_data_manager, mock_logger, mock_risk_manager, mock_kraken_client


def simulate_trading_activity(dashboard):
    """Simulate trading activity for demo purposes."""
    trading_pairs = ["BTC/USD", "ETH/USD", "ADA/USD", "DOT/USD"]
    
    # Simulate market data updates
    def update_market_data():
        market_data = {}
        for pair in trading_pairs:
            base_price = {"BTC/USD": 50000, "ETH/USD": 3000, "ADA/USD": 0.5, "DOT/USD": 8.0}[pair]
            price_variation = base_price * 0.02  # 2% variation
            
            import random
            current_price = base_price + random.uniform(-price_variation, price_variation)
            
            market_data[pair] = MarketData(
                pair=pair,
                timestamp=datetime.now(),
                price=current_price,
                volume=random.uniform(100, 1000),
                bid=current_price * 0.999,
                ask=current_price * 1.001,
                spread=0.002,
                volatility=random.uniform(0.015, 0.035),
                indicators={
                    "rsi": random.uniform(30, 70),
                    "macd": random.uniform(-0.5, 0.5),
                    "bb_upper": current_price * 1.02,
                    "bb_lower": current_price * 0.98
                }
            )
        
        dashboard.update_market_data(market_data)
    
    # Simulate portfolio updates
    def update_portfolio():
        total_value = random.uniform(9500, 10500)
        daily_pnl = random.uniform(-200, 300)
        
        portfolio = Portfolio(
            total_value_usd=total_value,
            available_balance=random.uniform(1500, 2500),
            positions={
                "BTC/USD": {"volume": 0.2, "value": total_value * 0.6},
                "ETH/USD": {"volume": 2.5, "value": total_value * 0.3},
                "ADA/USD": {"volume": 1000, "value": total_value * 0.1}
            },
            daily_pnl=daily_pnl,
            unrealized_pnl=random.uniform(-100, 400),
            realized_pnl=random.uniform(200, 800)
        )
        
        dashboard.update_portfolio_data(portfolio)
    
    # Simulate trade executions
    def simulate_trades():
        import random
        
        trade_id = f"demo_trade_{int(time.time())}"
        pair = random.choice(trading_pairs)
        side = random.choice(["BUY", "SELL"])
        
        trade = TradeExecution(
            trade_id=trade_id,
            pair=pair,
            side=side,
            order_type=random.choice(["MARKET", "LIMIT"]),
            volume=random.uniform(0.01, 0.5),
            price=random.uniform(1000, 60000),
            fee=random.uniform(5, 50),
            timestamp=datetime.now(),
            strategy=random.choice(["Enhanced Momentum", "Mean Reversion", "Volatility Breakout"]),
            signal_confidence=random.uniform(0.6, 0.95),
            execution_time_ms=random.randint(50, 300),
            status="FILLED"
        )
        
        dashboard.add_trade_event(trade)
    
    # Simulate system health updates
    def update_system_health():
        import psutil
        
        health = SystemHealth(
            bot_uptime=random.uniform(20, 30),
            cpu_usage=psutil.cpu_percent() or random.uniform(20, 60),
            memory_usage=random.uniform(50, 80),
            api_rate_limit_used=random.randint(700, 950),
            api_rate_limit_max=1000,
            websocket_connected=True,
            last_heartbeat=datetime.now(),
            error_rate_24h=random.uniform(0.01, 0.05),
            active_strategies=["Enhanced Momentum", "Mean Reversion", "Volatility Breakout"],
            trading_enabled=True
        )
        
        dashboard.update_system_health(health)
    
    # Run simulation loop
    counter = 0
    while True:
        try:
            # Update market data every 2 seconds
            if counter % 2 == 0:
                update_market_data()
            
            # Update portfolio every 5 seconds
            if counter % 5 == 0:
                update_portfolio()
            
            # Simulate trades every 10-30 seconds
            if counter % random.randint(10, 30) == 0:
                simulate_trades()
            
            # Update system health every 10 seconds
            if counter % 10 == 0:
                update_system_health()
            
            counter += 1
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\\nStopping simulation...")
            break
        except Exception as e:
            print(f"Simulation error: {e}")
            time.sleep(1)


def main():
    """Main demo function."""
    print("🚀 Enhanced Dashboard Demo")
    print("=" * 50)
    
    # Create dashboard configuration
    config = DashboardConfig(
        host="localhost",
        port=8080,
        debug=True,
        auto_refresh_interval=2,
        enable_manual_trading=True,
        enable_websocket=True,
        theme="dark"
    )
    
    # Create mock dependencies
    mock_data_manager, mock_logger, mock_risk_manager, mock_kraken_client = create_mock_dependencies()
    
    # Create dashboard instance
    dashboard = EnhancedDashboard(
        config,
        mock_data_manager,
        mock_logger,
        mock_risk_manager,
        mock_kraken_client
    )
    
    print(f"Dashboard configured:")
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Manual Trading: {'Enabled' if config.enable_manual_trading else 'Disabled'}")
    print(f"  WebSocket: {'Enabled' if config.enable_websocket else 'Disabled'}")
    print(f"  Theme: {config.theme}")
    print()
    
    # Start simulation in background thread
    simulation_thread = threading.Thread(target=simulate_trading_activity, args=(dashboard,))
    simulation_thread.daemon = True
    simulation_thread.start()
    
    print("Starting dashboard server...")
    print(f"Dashboard will be available at: http://{config.host}:{config.port}")
    print()
    print("Features available:")
    print("  ✓ Real-time portfolio visualization")
    print("  ✓ Live market data and price charts")
    print("  ✓ Trading activity feed")
    print("  ✓ Performance metrics monitoring")
    print("  ✓ System health dashboard")
    print("  ✓ Manual trading controls")
    print("  ✓ WebSocket real-time updates")
    print("  ✓ Bot control functions")
    print()
    print("Press Ctrl+C to stop the demo")
    print("=" * 50)
    
    try:
        # Start the dashboard server (this will block)
        dashboard.start_server()
    except KeyboardInterrupt:
        print("\\n🛑 Dashboard demo stopped")
        dashboard.stop_server()
    except Exception as e:
        print(f"\\n❌ Dashboard error: {e}")
        dashboard.stop_server()


if __name__ == "__main__":
    main()