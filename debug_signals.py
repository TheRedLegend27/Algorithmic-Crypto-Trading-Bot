#!/usr/bin/env python3
"""
Debug script to test signal generation and see what's happening.
"""
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.enhanced_strategies import EnhancedMomentumStrategy, PriceActionStrategy, BollingerBandsRSIStrategy
from bot.enhanced_data_manager import EnhancedDataManager
from bot.utils import log_info, log_error


def test_signal_generation():
    """Test signal generation with real market data."""
    print("🔍 Testing Signal Generation")
    print("=" * 50)
    
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
    
    # Get recent market data
    try:
        # Get OHLC data for the last few hours
        ohlc_data = client.get_ohlc_data("XBTUSD", interval=5)  # 5-minute intervals
        
        print(f"📊 OHLC data keys: {list(ohlc_data.keys())}")
        
        # Kraken returns data with XXBTZUSD key instead of XBTUSD
        data_key = None
        for key in ohlc_data.keys():
            if key.startswith('X') and 'BT' in key and 'USD' in key:
                data_key = key
                break
        
        if not data_key:
            print("❌ No BTC/USD data found in response")
            return
        
        # Convert to DataFrame
        raw_data = ohlc_data[data_key]
        
        # Create DataFrame with proper column names
        df_data = []
        for candle in raw_data:
            df_data.append({
                'timestamp': datetime.fromtimestamp(candle[0]),
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'vwap': float(candle[5]),
                'volume': float(candle[6]),
                'count': int(candle[7])
            })
        
        market_data = pd.DataFrame(df_data)
        market_data = market_data.sort_values('timestamp').reset_index(drop=True)
        
        print(f"📊 Got {len(market_data)} data points")
        print(f"📈 Price range: ${market_data['low'].min():.2f} - ${market_data['high'].max():.2f}")
        print(f"🕐 Time range: {market_data['timestamp'].min()} to {market_data['timestamp'].max()}")
        
        # Test different strategies
        strategies = [
            EnhancedMomentumStrategy(short_period=3, medium_period=8, momentum_threshold=0.001),
            PriceActionStrategy(lookback=10, min_body_pct=0.001),
            BollingerBandsRSIStrategy(bb_period=20, rsi_period=14)
        ]
        
        print("\n🎯 Testing Strategies:")
        print("-" * 30)
        
        for strategy in strategies:
            try:
                signal = strategy.calculate_signals(market_data)
                
                if signal:
                    print(f"✅ {strategy.name}:")
                    print(f"   Action: {signal.action.name}")
                    print(f"   Confidence: {signal.confidence:.3f}")
                    print(f"   Price: ${signal.price:.2f}")
                    print(f"   Reasoning: {signal.reasoning}")
                else:
                    print(f"❌ {strategy.name}: No signal generated")
                
            except Exception as e:
                print(f"❌ {strategy.name}: Error - {str(e)}")
        
        # Test with very low thresholds
        print("\n🔬 Testing with Ultra-Low Thresholds:")
        print("-" * 40)
        
        ultra_momentum = EnhancedMomentumStrategy(
            short_period=2, 
            medium_period=5, 
            momentum_threshold=0.0001,  # 0.01%
            volume_threshold=1.01       # 1% above average
        )
        
        try:
            signal = ultra_momentum.calculate_signals(market_data)
            if signal:
                print(f"✅ Ultra-Sensitive Momentum:")
                print(f"   Action: {signal.action.name}")
                print(f"   Confidence: {signal.confidence:.3f}")
                print(f"   Reasoning: {signal.reasoning}")
            else:
                print(f"❌ Even ultra-sensitive strategy generated no signal")
        except Exception as e:
            print(f"❌ Ultra-sensitive strategy error: {str(e)}")
        
        # Show recent price movements
        print(f"\n📈 Recent Price Action (last 10 candles):")
        print("-" * 50)
        recent = market_data.tail(10)
        for _, row in recent.iterrows():
            change = ((row['close'] - row['open']) / row['open']) * 100
            print(f"{row['timestamp'].strftime('%H:%M')} | "
                  f"${row['open']:.2f} → ${row['close']:.2f} | "
                  f"{change:+.2f}% | Vol: {row['volume']:.1f}")
        
    except Exception as e:
        print(f"❌ Error getting market data: {str(e)}")


if __name__ == "__main__":
    test_signal_generation()