#!/usr/bin/env python3
"""
Simple test to verify Alpaca API connection and account status.
"""
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest

def test_basic_connection():
    """Test basic Alpaca connection."""
    
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL")
    
    print("🔍 Testing Alpaca API Connection")
    print(f"API Key: {api_key[:8]}..." if api_key else "No API Key")
    print(f"Base URL: {base_url}")
    
    try:
        # Create trading client
        trading_client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=True  # Use paper trading
        )
        
        print("✅ Trading client created successfully")
        
        # Test account access
        print("\n📊 Testing account access...")
        account = trading_client.get_account()
        
        print("✅ Account access successful!")
        print(f"Account Status: {account.status}")
        print(f"Trading Blocked: {account.trading_blocked}")
        print(f"Account Blocked: {account.account_blocked}")
        print(f"Pattern Day Trader: {account.pattern_day_trader}")
        print(f"Buying Power: ${float(account.buying_power):,.2f}")
        print(f"Cash: ${float(account.cash):,.2f}")
        print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False

def test_market_data():
    """Test market data access."""
    
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL")
    
    try:
        # Create data client
        data_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret_key
        )
        
        print("\n📈 Testing market data access...")
        
        # Test getting a simple quote
        request = StockLatestQuoteRequest(symbol_or_symbols="AAPL")
        quotes = data_client.get_stock_latest_quote(request)
        
        if "AAPL" in quotes:
            quote = quotes["AAPL"]
            print(f"✅ AAPL Quote: Bid ${quote.bid_price}, Ask ${quote.ask_price}")
        else:
            print("❌ No AAPL quote data")
        
        return True
        
    except Exception as e:
        print(f"❌ Market data failed: {str(e)}")
        return False

def test_positions():
    """Test positions access."""
    
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL")
    
    try:
        trading_client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=True
        )
        
        print("\n💼 Testing positions access...")
        positions = trading_client.get_all_positions()
        print(f"✅ Positions retrieved: {len(positions)} positions")
        
        if positions:
            for pos in positions:
                print(f"   {pos.symbol}: {pos.qty} shares @ ${pos.avg_cost}")
        else:
            print("   No positions found (expected for new account)")
        
        return True
        
    except Exception as e:
        print(f"❌ Positions failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Alpaca API Connection Test")
    print("=" * 40)
    
    # Test basic connection
    if test_basic_connection():
        # Test market data
        test_market_data()
        
        # Test positions
        test_positions()
        
        print("\n✅ All tests completed!")
    else:
        print("\n❌ Basic connection failed - check your API credentials")