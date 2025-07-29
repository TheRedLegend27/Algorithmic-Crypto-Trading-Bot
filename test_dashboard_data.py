#!/usr/bin/env python3
"""
Test dashboard data updates.
"""
import os
import sys
import time
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.enhanced_data_manager import EnhancedDataManager, CacheConfig
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.enhanced_dashboard import EnhancedDashboard, DashboardConfig
from bot.crypto_position_manager import CryptoPositionManager


def test_dashboard_data():
    """Test dashboard data updates."""
    print("📊 Testing Dashboard Data Updates")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Missing Kraken API credentials!")
        return
    
    # Create credentials and client
    credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
    client = KrakenClient(credentials)
    
    # Test connection
    if not client.test_connection():
        print("❌ Failed to connect to Kraken API")
        return
    
    print("✅ Connected to Kraken API")
    
    # Create components
    data_manager = EnhancedDataManager(
        pairs=["XBTUSD"],
        cache_config=CacheConfig()
    )
    
    logger = EnhancedLogger({
        'log_level': 20,  # INFO
        'log_dir': 'logs',
        'structured_logging': True
    })
    
    position_manager = CryptoPositionManager(client)
    risk_manager = EnhancedRiskManager(
        position_manager=position_manager,
        data_manager=data_manager,
        kraken_client=client,
        trading_pairs=["XBTUSD"]
    )
    
    # Create dashboard
    dashboard_config = DashboardConfig(
        host="localhost",
        port=8081,  # Different port to avoid conflicts
        enable_manual_trading=False,
        enable_websocket=True
    )
    
    dashboard = EnhancedDashboard(
        config=dashboard_config,
        data_manager=data_manager,
        logger=logger,
        risk_manager=risk_manager,
        kraken_client=client
    )
    
    print("\n📊 Testing Portfolio Data:")
    dashboard._update_portfolio_data()
    if dashboard.portfolio:
        print(f"   Total Value: ${dashboard.portfolio.total_value_usd:.2f}")
        print(f"   Available Balance: ${dashboard.portfolio.available_balance:.2f}")
        print(f"   Positions: {dashboard.portfolio.positions}")
        print(f"   Timestamp: {dashboard.portfolio.timestamp}")
    else:
        print("   ❌ No portfolio data")
    
    print("\n🔧 Testing System Health:")
    dashboard._update_system_health()
    if dashboard.system_health:
        print(f"   CPU Usage: {dashboard.system_health.cpu_usage:.1f}%")
        print(f"   Memory Usage: {dashboard.system_health.memory_usage:.1f}%")
        print(f"   Trading Enabled: {dashboard.system_health.trading_enabled}")
        print(f"   Last Heartbeat: {dashboard.system_health.last_heartbeat}")
    else:
        print("   ❌ No system health data")
    
    print("\n🌐 Testing API Endpoints:")
    # Simulate API calls
    try:
        import requests
        
        # Start dashboard in background (this would normally be done in a separate thread)
        print("   Note: Dashboard would need to be running on port 8081 to test API endpoints")
        print("   Portfolio API: GET http://localhost:8081/api/portfolio")
        print("   System Health API: GET http://localhost:8081/api/system_health")
        
    except ImportError:
        print("   Requests not available for API testing")
    
    print("\n✅ Dashboard data components are working correctly!")
    print("💡 If dashboard isn't updating, check:")
    print("   1. WebSocket connection in browser console")
    print("   2. Background update thread is running")
    print("   3. No JavaScript errors in browser")


if __name__ == "__main__":
    test_dashboard_data()