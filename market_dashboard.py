#!/usr/bin/env python3
"""
Real-time Market Dashboard - Visual display of market conditions.
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
from bot.utils import log_info, log_error


class MarketDashboard:
    """Real-time market dashboard."""
    
    def __init__(self, credentials: KrakenCredentials, pair: str = "XBTUSD"):
        self.client = KrakenClient(credentials)
        self.pair = pair
        self.start_time = datetime.now()
        
    def get_market_snapshot(self) -> Dict:
        """Get current market snapshot."""
        try:
            # Get current price
            current_price = self.client.get_current_price(self.pair)
            
            # Get ticker data
            ticker_data = self.client.get_ticker([self.pair])
            
            # Find correct key
            ticker_key = None
            for key in ticker_data.keys():
                if 'BT' in key and 'USD' in key:
                    ticker_key = key
                    break
            
            if not ticker_key or not current_price:
                return {}
            
            ticker = ticker_data[ticker_key]
            
            # Get recent OHLC for trend analysis
            ohlc_data = self.client.get_ohlc_data(self.pair, interval=5)
            
            # Find OHLC key
            ohlc_key = None
            for key in ohlc_data.keys():
                if 'BT' in key and 'USD' in key:
                    ohlc_key = key
                    break
            
            recent_candles = []
            if ohlc_key and ohlc_key in ohlc_data:
                recent_candles = ohlc_data[ohlc_key][-20:]  # Last 20 candles
            
            # Calculate trend
            trend = "NEUTRAL"
            trend_strength = 0.0
            
            if len(recent_candles) >= 10:
                prices = [float(candle[4]) for candle in recent_candles[-10:]]  # Close prices
                if prices[-1] > prices[0]:
                    trend = "BULLISH"
                    trend_strength = ((prices[-1] - prices[0]) / prices[0]) * 100
                elif prices[-1] < prices[0]:
                    trend = "BEARISH"
                    trend_strength = ((prices[0] - prices[-1]) / prices[0]) * 100
            
            # Parse ticker data
            bid = float(ticker['b'][0])
            ask = float(ticker['a'][0])
            spread = ask - bid
            spread_pct = (spread / current_price) * 100
            
            volume_24h = float(ticker['v'][1])  # 24h volume
            high_24h = float(ticker['h'][1])    # 24h high
            low_24h = float(ticker['l'][1])     # 24h low
            open_24h = float(ticker['o'])       # 24h open
            
            change_24h = current_price - open_24h
            change_24h_pct = (change_24h / open_24h) * 100
            
            return {
                'price': current_price,
                'bid': bid,
                'ask': ask,
                'spread': spread,
                'spread_pct': spread_pct,
                'volume_24h': volume_24h,
                'high_24h': high_24h,
                'low_24h': low_24h,
                'open_24h': open_24h,
                'change_24h': change_24h,
                'change_24h_pct': change_24h_pct,
                'trend': trend,
                'trend_strength': trend_strength,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            log_error(f"Error getting market snapshot: {e}")
            return {}
    
    def format_price(self, price: float) -> str:
        """Format price with appropriate precision."""
        if price >= 1000:
            return f"${price:,.2f}"
        elif price >= 1:
            return f"${price:.4f}"
        else:
            return f"${price:.6f}"
    
    def format_volume(self, volume: float) -> str:
        """Format volume with K/M suffixes."""
        if volume >= 1_000_000:
            return f"{volume/1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"{volume/1_000:.1f}K"
        else:
            return f"{volume:.1f}"
    
    def get_trend_emoji(self, trend: str, strength: float) -> str:
        """Get emoji for trend display."""
        if trend == "BULLISH":
            if strength > 2:
                return "🚀"
            elif strength > 1:
                return "📈"
            else:
                return "🟢"
        elif trend == "BEARISH":
            if strength > 2:
                return "💥"
            elif strength > 1:
                return "📉"
            else:
                return "🔴"
        else:
            return "⚪"
    
    def print_dashboard(self, snapshot: Dict) -> None:
        """Print formatted dashboard."""
        if not snapshot:
            print("❌ Unable to get market data")
            return
        
        # Clear screen (works on most terminals)
        os.system('clear' if os.name == 'posix' else 'cls')
        
        # Header
        print("🚀 CRYPTO MARKET DASHBOARD 🚀")
        print("=" * 60)
        print(f"📊 Pair: {self.pair}")
        print(f"⏰ Time: {snapshot['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕐 Uptime: {datetime.now() - self.start_time}")
        print("=" * 60)
        
        # Price section
        price = snapshot['price']
        change_24h = snapshot['change_24h']
        change_24h_pct = snapshot['change_24h_pct']
        
        change_emoji = "📈" if change_24h >= 0 else "📉"
        change_color = "+" if change_24h >= 0 else ""
        
        print(f"\n💰 PRICE INFORMATION")
        print(f"   Current Price: {self.format_price(price)}")
        print(f"   24h Change: {change_emoji} {change_color}{self.format_price(change_24h)} ({change_color}{change_24h_pct:.2f}%)")
        print(f"   24h High: {self.format_price(snapshot['high_24h'])}")
        print(f"   24h Low: {self.format_price(snapshot['low_24h'])}")
        print(f"   24h Open: {self.format_price(snapshot['open_24h'])}")
        
        # Order book section
        print(f"\n📋 ORDER BOOK")
        print(f"   Bid: {self.format_price(snapshot['bid'])}")
        print(f"   Ask: {self.format_price(snapshot['ask'])}")
        print(f"   Spread: {self.format_price(snapshot['spread'])} ({snapshot['spread_pct']:.3f}%)")
        
        # Volume and trend
        trend_emoji = self.get_trend_emoji(snapshot['trend'], snapshot['trend_strength'])
        
        print(f"\n📊 MARKET ACTIVITY")
        print(f"   24h Volume: {self.format_volume(snapshot['volume_24h'])} BTC")
        print(f"   Trend: {trend_emoji} {snapshot['trend']}")
        if snapshot['trend_strength'] > 0:
            print(f"   Trend Strength: {snapshot['trend_strength']:.2f}%")
        
        # Trading conditions assessment
        print(f"\n🎯 TRADING CONDITIONS")
        
        # Simple condition checks
        conditions = []
        
        # Volatility check (based on 24h range)
        volatility = ((snapshot['high_24h'] - snapshot['low_24h']) / snapshot['price']) * 100
        if volatility > 3:
            conditions.append("🟢 High volatility")
        elif volatility > 1.5:
            conditions.append("🟡 Medium volatility")
        else:
            conditions.append("🔴 Low volatility")
        
        # Spread check
        if snapshot['spread_pct'] < 0.01:
            conditions.append("🟢 Tight spread")
        elif snapshot['spread_pct'] < 0.05:
            conditions.append("🟡 Normal spread")
        else:
            conditions.append("🔴 Wide spread")
        
        # Trend check
        if snapshot['trend_strength'] > 1:
            conditions.append(f"🟢 Strong {snapshot['trend'].lower()} trend")
        elif snapshot['trend'] != "NEUTRAL":
            conditions.append(f"🟡 Weak {snapshot['trend'].lower()} trend")
        else:
            conditions.append("🔴 No clear trend")
        
        for condition in conditions:
            print(f"   {condition}")
        
        # Overall assessment
        green_count = sum(1 for c in conditions if c.startswith("🟢"))
        
        print(f"\n🚦 OVERALL ASSESSMENT")
        if green_count >= 2:
            print("   🟢 FAVORABLE - Consider trading")
            print("   💡 Command: python3 run_enhanced_kraken_bot.py --paper-trading")
        elif green_count == 1:
            print("   🟡 NEUTRAL - Monitor closely")
            print("   💡 Command: python3 trading_opportunity_alert.py")
        else:
            print("   🔴 UNFAVORABLE - Wait for better conditions")
            print("   💡 Command: python3 market_monitor.py")
        
        print("\n" + "=" * 60)
        print("Press Ctrl+C to stop dashboard")
    
    def run_dashboard(self, refresh_interval: int = 10) -> None:
        """Run real-time dashboard."""
        print("🚀 Starting Market Dashboard...")
        print(f"📊 Monitoring {self.pair}")
        print(f"🔄 Refresh every {refresh_interval} seconds")
        print("\nPress Ctrl+C to stop\n")
        
        try:
            while True:
                snapshot = self.get_market_snapshot()
                self.print_dashboard(snapshot)
                time.sleep(refresh_interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Dashboard stopped")


def main():
    """Main function."""
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
    
    # Initialize dashboard
    dashboard = MarketDashboard(credentials, "XBTUSD")
    
    # Test connection
    if not dashboard.client.test_connection():
        print("❌ Failed to connect to Kraken API")
        return 1
    
    # Run dashboard
    dashboard.run_dashboard(refresh_interval=10)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())