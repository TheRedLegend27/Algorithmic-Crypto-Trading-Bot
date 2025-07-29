#!/usr/bin/env python3
"""
Trading Opportunity Alert System - Lightweight monitor for trading signals.
"""
import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.enhanced_strategies import EnhancedMomentumStrategy, PriceActionStrategy, BollingerBandsRSIStrategy, EnhancedStrategyEngine
from bot.utils import log_info, log_error


class TradingOpportunityAlert:
    """Lightweight alert system for trading opportunities."""
    
    def __init__(self, credentials: KrakenCredentials, pair: str = "XBTUSD"):
        self.client = KrakenClient(credentials)
        self.pair = pair
        self.last_alert_time = None
        self.alert_cooldown = 180  # 3 minutes between alerts
        
        # Initialize strategy engine with multiple strategies
        strategies = [
            EnhancedMomentumStrategy(
                short_period=3, 
                medium_period=8, 
                momentum_threshold=0.002,  # 0.2% threshold
                volume_threshold=1.2
            ),
            PriceActionStrategy(lookback=15, min_body_pct=0.002),
            BollingerBandsRSIStrategy(bb_period=20, rsi_period=14)
        ]
        
        self.strategy_engine = EnhancedStrategyEngine(strategies)
        
        # Set more aggressive confidence threshold for alerts
        self.strategy_engine.parameters.confidence_threshold = 0.2
        
        log_info(f"Trading opportunity alert initialized for {pair}")
    
    def get_recent_data(self) -> Optional[List[Dict]]:
        """Get recent market data for signal generation."""
        try:
            # Get 5-minute intervals for more responsive signals
            ohlc_data = self.client.get_ohlc_data(self.pair, interval=5)
            
            # Find the correct key
            data_key = None
            for key in ohlc_data.keys():
                if key.startswith('X') and 'BT' in key and 'USD' in key:
                    data_key = key
                    break
            
            if not data_key:
                return None
            
            raw_data = ohlc_data[data_key]
            
            # Convert to list of dicts (compatible with strategy engine)
            market_data = []
            for candle in raw_data[-100:]:  # Last 100 candles
                market_data.append({
                    'timestamp': datetime.fromtimestamp(candle[0]),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'vwap': float(candle[5]),
                    'volume': float(candle[6]),
                    'count': int(candle[7])
                })
            
            return market_data
            
        except Exception as e:
            log_error(f"Error getting market data: {e}")
            return None
    
    def check_for_signals(self) -> Optional[Dict]:
        """Check for trading signals."""
        try:
            # Get market data
            market_data = self.get_recent_data()
            if not market_data or len(market_data) < 50:
                return None
            
            # Convert to DataFrame for strategy engine
            import pandas as pd
            df = pd.DataFrame(market_data)
            
            # Get signal from strategy engine
            signal = self.strategy_engine.calculate_weighted_signal(df)
            
            if signal and signal.confidence > 0.2:  # Only alert on decent confidence
                return {
                    'action': signal.action.name,
                    'confidence': signal.confidence,
                    'price': signal.price,
                    'timestamp': signal.timestamp,
                    'strategies': signal.metadata.get('contributing_strategies', []),
                    'strategy_count': signal.metadata.get('strategy_count', 0)
                }
            
            return None
            
        except Exception as e:
            log_error(f"Error checking for signals: {e}")
            return None
    
    def send_trading_alert(self, signal_data: Dict) -> None:
        """Send trading opportunity alert."""
        current_time = datetime.now()
        
        # Check cooldown
        if (self.last_alert_time and 
            (current_time - self.last_alert_time).seconds < self.alert_cooldown):
            return
        
        action = signal_data['action']
        confidence = signal_data['confidence']
        price = signal_data['price']
        
        # Different alert styles based on action
        if action == 'BUY':
            emoji = "🟢📈"
            color = "GREEN"
        elif action == 'SELL':
            emoji = "🔴📉"
            color = "RED"
        else:
            return  # Don't alert on HOLD
        
        print(f"\n{emoji} TRADING OPPORTUNITY DETECTED! {emoji}")
        print("=" * 50)
        print(f"⏰ Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Action: {action} ({color})")
        print(f"💪 Confidence: {confidence:.1%}")
        print(f"💰 Price: ${price:,.2f}")
        print(f"🧠 Strategies: {signal_data['strategy_count']} agreeing")
        
        print(f"\n🚀 QUICK START COMMANDS:")
        print(f"   # Paper Trading (Recommended)")
        print(f"   python3 run_enhanced_kraken_bot.py --paper-trading --confidence 0.2")
        print(f"   ")
        print(f"   # Real Trading (Use with caution)")
        print(f"   python3 run_enhanced_kraken_bot.py --confidence 0.3")
        
        print("=" * 50 + "\n")
        
        self.last_alert_time = current_time
        
        # Save alert
        self.save_alert(signal_data)
    
    def save_alert(self, signal_data: Dict) -> None:
        """Save alert to file."""
        try:
            alert_file = "trading_alerts.json"
            alerts = []
            
            if os.path.exists(alert_file):
                with open(alert_file, 'r') as f:
                    alerts = json.load(f)
            
            # Add timestamp as string for JSON serialization
            alert_data = signal_data.copy()
            alert_data['alert_time'] = datetime.now().isoformat()
            alert_data['timestamp'] = signal_data['timestamp'].isoformat()
            
            alerts.append(alert_data)
            alerts = alerts[-50:]  # Keep last 50 alerts
            
            with open(alert_file, 'w') as f:
                json.dump(alerts, f, indent=2)
                
        except Exception as e:
            log_error(f"Error saving alert: {e}")
    
    def run_alert_monitor(self, check_interval: int = 30) -> None:
        """Run continuous alert monitoring."""
        print("🚨 Trading Opportunity Alert Monitor")
        print("=" * 40)
        print(f"📊 Monitoring: {self.pair}")
        print(f"⏱️  Check Interval: {check_interval} seconds")
        print(f"🎯 Min Confidence: 20%")
        print(f"📱 Alert Cooldown: {self.alert_cooldown} seconds")
        print("\nWaiting for trading opportunities...\n")
        
        check_count = 0
        alert_count = 0
        
        try:
            while True:
                check_count += 1
                
                # Check for signals
                signal_data = self.check_for_signals()
                
                if signal_data:
                    if signal_data['action'] != 'HOLD':
                        alert_count += 1
                        self.send_trading_alert(signal_data)
                    else:
                        # Just show status for HOLD
                        print(f"⏸️  {datetime.now().strftime('%H:%M:%S')} - HOLD signal (confidence: {signal_data['confidence']:.1%})")
                else:
                    # Show periodic status
                    if check_count % 10 == 0:  # Every 10 checks
                        print(f"🔍 {datetime.now().strftime('%H:%M:%S')} - Monitoring... (Checks: {check_count}, Alerts: {alert_count})")
                
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Alert monitor stopped")
            print(f"📊 Total checks: {check_count}")
            print(f"🚨 Total alerts: {alert_count}")


def main():
    """Main function."""
    print("🚨 Trading Opportunity Alert System")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Missing Kraken API credentials!")
        return 1
    
    # Create credentials
    credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
    
    # Initialize alert system
    alert_system = TradingOpportunityAlert(credentials, "XBTUSD")
    
    # Test connection
    if not alert_system.client.test_connection():
        print("❌ Failed to connect to Kraken API")
        return 1
    
    print("✅ Connected to Kraken API")
    
    # Quick signal check
    print("\n🔍 Quick Signal Check:")
    signal_data = alert_system.check_for_signals()
    
    if signal_data:
        action = signal_data['action']
        confidence = signal_data['confidence']
        print(f"📊 Current Signal: {action} (confidence: {confidence:.1%})")
        
        if action != 'HOLD' and confidence > 0.3:
            print("🚀 Strong signal detected! Consider starting the bot.")
        elif action != 'HOLD':
            print("⚡ Weak signal detected. Monitor for stronger signals.")
        else:
            print("⏸️  HOLD signal - waiting for better opportunities.")
    else:
        print("📊 No signals detected currently.")
    
    # Ask for continuous monitoring
    print(f"\n🔄 Start continuous alert monitoring?")
    response = input("Enter 'y' for yes: ").lower().strip()
    
    if response in ['y', 'yes']:
        alert_system.run_alert_monitor(check_interval=30)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())