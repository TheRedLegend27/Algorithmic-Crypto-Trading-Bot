#!/usr/bin/env python3
"""
Test risk manager portfolio value calculation.
"""
import os
import sys
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.crypto_position_manager import CryptoPositionManager
from bot.crypto_risk_manager import CryptoRiskManager
from bot.data_fetcher import DataFetcher
from bot.utils import log_info, log_error


def test_risk_manager():
    """Test risk manager portfolio value calculation."""
    print("🛡️ Testing Risk Manager")
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
    position_manager = CryptoPositionManager(client)
    data_fetcher = DataFetcher()
    
    # Create risk manager
    risk_manager = CryptoRiskManager(
        position_manager=position_manager,
        data_fetcher=data_fetcher,
        client=client
    )
    
    print(f"\n💰 Initial Portfolio Value: ${risk_manager.starting_portfolio_value:.2f}")
    
    # Test portfolio value calculation
    current_value = risk_manager._get_portfolio_value()
    print(f"💰 Current Portfolio Value: ${current_value:.2f}")
    
    # Test portfolio metrics update
    print("\n📊 Portfolio Metrics:")
    metrics = risk_manager.update_portfolio_metrics()
    
    for key, value in metrics.items():
        if key == 'timestamp':
            print(f"   {key}: {value}")
        elif isinstance(value, float):
            if 'pct' in key:
                print(f"   {key}: {value:.2%}")
            elif 'value' in key or 'pnl' in key:
                print(f"   {key}: ${value:.2f}")
            else:
                print(f"   {key}: {value:.4f}")
        else:
            print(f"   {key}: {value}")
    
    # Test position size validation
    print("\n🔍 Position Size Validation Test:")
    btc_price = client.get_current_price('XBTUSD')
    if btc_price:
        print(f"   Current BTC Price: ${btc_price:,.2f}")
        
        # Test small position
        is_valid, adjusted_size, reason = risk_manager.validate_position_size('BTC', 0.001, btc_price)
        print(f"   Small Position (0.001 BTC): Valid={is_valid}, Size={adjusted_size:.6f}, Reason={reason}")
        
        # Test large position
        is_valid, adjusted_size, reason = risk_manager.validate_position_size('BTC', 1.0, btc_price)
        print(f"   Large Position (1.0 BTC): Valid={is_valid}, Size={adjusted_size:.6f}, Reason={reason}")
    else:
        print("   ❌ Could not get BTC price")


if __name__ == "__main__":
    test_risk_manager()