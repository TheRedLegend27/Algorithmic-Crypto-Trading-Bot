#!/usr/bin/env python3
"""
Test Alpaca API connection for stock data instead of crypto.
"""
import os
from dotenv import load_dotenv
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

def test_stock_data():
    """Test stock data access."""
    
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    
    print("Testing Stock Data Access...")
    
    # Create stock client
    try:
        client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret_key
        )
        print("✅ Stock client created successfully")
    except Exception as e:
        print(f"❌ Failed to create stock client: {e}")
        return
    
    # Test stock data request
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        
        print(f"Requesting AAPL stock data from {start_time} to {end_time}")
        
        request = StockBarsRequest(
            symbol_or_symbols="AAPL",
            timeframe=TimeFrame.Minute,
            start=start_time,
            end=end_time
        )
        
        bars = client.get_stock_bars(request)
        print(f"✅ Stock data request successful")
        print(f"Response type: {type(bars)}")
        
        # Try to access data
        if hasattr(bars, 'data'):
            print(f"Data keys: {list(bars.data.keys()) if bars.data else 'No data'}")
            if bars.data and "AAPL" in bars.data:
                aapl_data = bars.data["AAPL"]
                print(f"AAPL data points: {len(aapl_data)}")
                if aapl_data:
                    print(f"First data point: {aapl_data[0]}")
                    print("✅ Stock data access confirmed!")
        
    except Exception as e:
        print(f"❌ Stock data request failed: {e}")

def test_crypto_etfs():
    """Test crypto ETF data as alternative to direct crypto."""
    
    load_dotenv()
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    
    print("\nTesting Crypto ETF Data Access...")
    
    try:
        client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret_key
        )
        
        # Test crypto-related ETFs and stocks
        crypto_symbols = ["BITO", "COIN", "MSTR", "RIOT", "MARA"]
        
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=6)
        
        for symbol in crypto_symbols:
            try:
                print(f"Testing {symbol}...")
                request = StockBarsRequest(
                    symbol_or_symbols=symbol,
                    timeframe=TimeFrame.Minute,
                    start=start_time,
                    end=end_time
                )
                
                bars = client.get_stock_bars(request)
                if hasattr(bars, 'data') and bars.data and symbol in bars.data:
                    data_points = len(bars.data[symbol])
                    print(f"✅ {symbol}: {data_points} data points")
                else:
                    print(f"❌ {symbol}: No data")
                    
            except Exception as e:
                print(f"❌ {symbol} failed: {e}")
                
    except Exception as e:
        print(f"❌ Failed to test crypto ETFs: {e}")

if __name__ == "__main__":
    test_stock_data()
    test_crypto_etfs()