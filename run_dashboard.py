#!/usr/bin/env python3
"""
Run the enhanced dashboard with real Kraken trading data.
"""
import os
import sys
import asyncio
import threading
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bot.enhanced_dashboard import EnhancedDashboard, DashboardConfig
from bot.enhanced_data_manager import EnhancedDataManager
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_risk_manager import EnhancedRiskManager
from bot.kraken_client import KrakenClient
from bot.config import Config


def main():
    """Main function to run the enhanced dashboard."""
    print("Starting Enhanced Crypto Trading Dashboard...")
    
    try:
        # Load configuration
        config = Config()
        if not config.load_env_variables():
            print("Error: Failed to load environment variables")
            sys.exit(1)
        
        if not config.validate_config():
            print("Error: Invalid configuration")
            sys.exit(1)
        
        kraken_creds = config.get_kraken_credentials()
        enhanced_config = config.get_enhanced_config()
        
        # Initialize components
        logger = EnhancedLogger()
        kraken_client = KrakenClient(
            api_key=kraken_creds.api_key,
            api_secret=kraken_creds.api_secret,
            logger=logger
        )
        
        data_manager = EnhancedDataManager(
            kraken_client=kraken_client,
            logger=logger
        )
        
        risk_manager = EnhancedRiskManager(
            config=enhanced_config,
            logger=logger
        )
        
        # Dashboard configuration
        dashboard_config = DashboardConfig(
            host=enhanced_config.dashboard_host,
            port=enhanced_config.dashboard_port,
            debug=False,
            auto_refresh_interval=5,
            enable_manual_trading=True,
            enable_websocket=enhanced_config.enable_websocket,
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
        print("Press Ctrl+C to stop the dashboard")
        
        # Start the dashboard server
        dashboard.start_server()
        
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
    except Exception as e:
        print(f"Error starting dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()