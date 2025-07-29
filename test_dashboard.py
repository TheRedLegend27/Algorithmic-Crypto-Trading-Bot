#!/usr/bin/env python3
"""
Test script to demonstrate the enhanced dashboard functionality.
"""
import os
import sys
import time
import threading
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.enhanced_dashboard import EnhancedDashboard, DashboardConfig, Portfolio, SystemHealth
from bot.enhanced_logger import EnhancedLogger
from datetime import datetime


class MockKrakenClient:
    """Mock Kraken client for testing."""
    
    def get_account_balance(self):
        """Mock account balance."""
        return {
            'USD': '1250.50',
            'BTC': '0.05432',
            'ETH': '2.1234',
            'ADA': '1000.0'
        }
    
    def place_market_order(self, pair, side, volume):
        """Mock market order."""
        return {
            'txid': ['TEST123456']
        }
    
    def place_limit_order(self, pair, side, volume, price):
        """Mock limit order."""
        return {
            'txid': ['TEST789012']
        }


class MockDataManager:
    """Mock data manager for testing."""
    
    def get_uptime_hours(self):
        return 12.5
    
    def get_daily_pnl(self):
        return 45.67
    
    def get_unrealized_pnl(self):
        return 23.45
    
    def get_realized_pnl(self):
        return 78.90
    
    def is_trading_enabled(self):
        return True
    
    def get_active_strategies(self):
        return ["Enhanced Momentum", "Mean Reversion"]


class MockRiskManager:
    """Mock risk manager for testing."""
    pass


def main():
    """Main function to test the enhanced dashboard."""
    print("Starting Enhanced Dashboard Test...")
    
    try:
        # Initialize mock components
        logger = EnhancedLogger()
        kraken_client = MockKrakenClient()
        data_manager = MockDataManager()
        risk_manager = MockRiskManager()
        
        # Dashboard configuration
        dashboard_config = DashboardConfig(
            host="localhost",
            port=8080,
            debug=True,
            auto_refresh_interval=3,
            enable_manual_trading=True,
            enable_websocket=True,
            theme="dark"
        )
        
        # Initialize dashboard
        dashboard = EnhancedDashboard(
            config=dashboard_config,
            data_manager=data_manager,
            logger=logger,
            risk_manager=risk_manager,
            kraken_client=kraken_client
        )
        
        print(f"Dashboard will be available at: http://{dashboard_config.host}:{dashboard_config.port}")
        print("Features available:")
        print("- Real-time portfolio overview")
        print("- System health monitoring")
        print("- Manual trading interface")
        print("- WebSocket real-time updates")
        print("\nPress Ctrl+C to stop the dashboard")
        
        # Start the dashboard server
        dashboard.start_server()
        
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
    except Exception as e:
        print(f"Error starting dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()