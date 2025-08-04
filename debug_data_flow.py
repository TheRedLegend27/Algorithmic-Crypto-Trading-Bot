#!/usr/bin/env python3
"""
Debug data flow issues in the adaptive bot.
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.adaptive.adaptive_bot_main import AdaptiveBotMain
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

async def debug_data_flow():
    """Debug the data flow in the adaptive bot."""
    print("🔍 Debugging adaptive bot data flow...")
    
    try:
        # Create bot instance
        bot = AdaptiveBotMain()
        
        # Initialize components
        print("📊 Initializing bot components...")
        success = await bot.initialize_components()
        
        if not success:
            print("❌ Failed to initialize bot")
            return
        
        print("✅ Bot initialized successfully")
        
        # Test data manager
        print("\n📊 Testing data manager...")
        if bot.data_manager:
            try:
                # Test with mock data since real API might not be available
                print("  Creating mock market data...")
                mock_data = create_mock_market_data()
                print(f"  Mock data shape: {mock_data.shape}")
                print(f"  Mock data columns: {list(mock_data.columns)}")
                
                # Test regime detection
                print("\n🔍 Testing regime detection...")
                if bot.regime_detector:
                    regime = bot.regime_detector.detect_regime(mock_data, "BTCUSD")
                    print(f"  Detected regime: {regime.regime_type.value}")
                    print(f"  Confidence: {regime.confidence:.3f}")
                    print(f"  Volatility: {regime.volatility_level:.3f}")
                    print(f"  Trend strength: {regime.trend_strength:.3f}")
                else:
                    print("  ❌ Regime detector not initialized")
                
                # Test strategy engine
                print("\n🎯 Testing strategy engine...")
                if bot.strategy_engine:
                    signal = bot.strategy_engine.execute_adaptive_signal("BTCUSD", mock_data)
                    if signal:
                        print(f"  Generated signal: {signal.signal_type}")
                        print(f"  Signal strength: {signal.strength.value}")
                        print(f"  Confidence: {signal.confidence:.3f}")
                        print(f"  ML confidence: {signal.ml_confidence:.3f}")
                    else:
                        print("  ⚠️  No signal generated (this may be normal)")
                else:
                    print("  ❌ Strategy engine not initialized")
                
                # Test ML engine
                print("\n🧠 Testing ML engine...")
                if bot.ml_engine:
                    confidence = bot.ml_engine.get_model_confidence("ensemble")
                    print(f"  ML engine confidence: {confidence:.3f}")
                    
                    # Test prediction if we have a signal
                    if signal:
                        market_conditions = {
                            'rsi': 50.0,
                            'volatility': 0.02,
                            'volume_ratio': 1.0
                        }
                        prediction = bot.ml_engine.predict_trade_outcome(signal, market_conditions)
                        print(f"  Trade outcome prediction: {prediction:.3f}")
                else:
                    print("  ❌ ML engine not initialized")
                
                # Test paper trading
                print("\n📝 Testing paper trading...")
                if bot.paper_trading_engine and signal:
                    result = bot.paper_trading_engine.execute_signal(signal)
                    print(f"  Paper trade result: {result}")
                else:
                    print("  ⚠️  Paper trading not available or no signal")
                
            except Exception as e:
                print(f"  ❌ Error in data flow test: {str(e)}")
                import traceback
                print(f"  Traceback: {traceback.format_exc()}")
        else:
            print("  ❌ Data manager not initialized")
        
        print("\n✅ Data flow debugging complete!")
        
    except Exception as e:
        print(f"❌ Error in debug: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

def create_mock_market_data():
    """Create mock market data for testing."""
    # Generate 200 data points (about 16 hours of 5-minute data)
    periods = 200
    dates = pd.date_range(start=datetime.now() - timedelta(hours=16), periods=periods, freq='5min')
    
    # Generate realistic price data with some trend and volatility
    np.random.seed(42)  # For reproducible results
    
    # Start with a base price
    base_price = 45000.0
    
    # Generate returns with some autocorrelation (trending behavior)
    returns = np.random.normal(0, 0.002, periods)  # 0.2% volatility
    
    # Add some trend
    trend = np.linspace(-0.001, 0.001, periods)  # Slight upward trend
    returns += trend
    
    # Add some momentum (autocorrelation)
    for i in range(1, len(returns)):
        returns[i] += 0.1 * returns[i-1]  # 10% momentum
    
    # Calculate prices
    prices = [base_price]
    for ret in returns[1:]:
        prices.append(prices[-1] * (1 + ret))
    
    # Generate OHLC data
    data = []
    for i, price in enumerate(prices):
        # Add some intraday volatility
        high = price * (1 + abs(np.random.normal(0, 0.001)))
        low = price * (1 - abs(np.random.normal(0, 0.001)))
        open_price = prices[i-1] if i > 0 else price
        close_price = price
        
        # Ensure OHLC consistency
        high = max(high, open_price, close_price)
        low = min(low, open_price, close_price)
        
        # Generate volume (higher volume on larger price moves)
        volume = abs(np.random.normal(1000, 200)) * (1 + abs(returns[i]) * 10)
        
        data.append({
            'timestamp': dates[i],
            'open': open_price,
            'high': high,
            'low': low,
            'close': close_price,
            'volume': volume
        })
    
    df = pd.DataFrame(data)
    df.set_index('timestamp', inplace=True)
    
    return df

if __name__ == "__main__":
    asyncio.run(debug_data_flow())