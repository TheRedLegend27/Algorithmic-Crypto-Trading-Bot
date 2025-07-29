#!/usr/bin/env python3
"""
Market Condition Monitor - Alerts when trading conditions become favorable.
"""
import os
import sys
import time
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

# Add bot directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'bot'))

from bot.kraken_client import KrakenCredentials, KrakenClient
from bot.enhanced_strategies import EnhancedMomentumStrategy, PriceActionStrategy, BollingerBandsRSIStrategy
from bot.utils import log_info, log_error, log_warning


@dataclass
class MarketCondition:
    """Market condition assessment."""
    timestamp: datetime
    price: float
    volatility: float
    volume_ratio: float
    momentum_1h: float
    momentum_4h: float
    rsi: float
    bb_position: float  # Position within Bollinger Bands (0-1)
    trend_strength: float
    trading_score: float  # Overall trading favorability (0-100)
    is_favorable: bool
    reasons: List[str]


@dataclass
class AlertThresholds:
    """Thresholds for market condition alerts."""
    min_volatility: float = 0.02  # 2% daily volatility
    min_volume_ratio: float = 1.3  # 30% above average
    min_momentum: float = 0.005  # 0.5% momentum
    min_trading_score: float = 60  # 60/100 trading score
    rsi_oversold: float = 30
    rsi_overbought: float = 70


class MarketMonitor:
    """Monitor market conditions and alert when favorable for trading."""
    
    def __init__(self, credentials: KrakenCredentials, pair: str = "XBTUSD"):
        self.client = KrakenClient(credentials)
        self.pair = pair
        self.thresholds = AlertThresholds()
        self.history: List[MarketCondition] = []
        self.last_alert_time = None
        self.alert_cooldown = 300  # 5 minutes between alerts
        
        # Initialize strategies for analysis
        self.momentum_strategy = EnhancedMomentumStrategy(
            short_period=3, medium_period=8, momentum_threshold=0.001
        )
        self.price_action_strategy = PriceActionStrategy(lookback=20)
        self.bb_rsi_strategy = BollingerBandsRSIStrategy(bb_period=20, rsi_period=14)
        
        log_info(f"Market monitor initialized for {pair}")
    
    def get_market_data(self) -> Optional[pd.DataFrame]:
        """Get recent market data for analysis."""
        try:
            # Get 4-hour data for better trend analysis
            ohlc_data = self.client.get_ohlc_data(self.pair, interval=60)  # 1-hour intervals
            
            # Find the correct key (Kraken returns XXBTZUSD instead of XBTUSD)
            data_key = None
            for key in ohlc_data.keys():
                if key.startswith('X') and 'BT' in key and 'USD' in key:
                    data_key = key
                    break
            
            if not data_key:
                log_error("No BTC/USD data found in response")
                return None
            
            raw_data = ohlc_data[data_key]
            
            # Convert to DataFrame
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
            
            return market_data
            
        except Exception as e:
            log_error(f"Error getting market data: {e}")
            return None
    
    def calculate_indicators(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate technical indicators for market assessment."""
        if len(data) < 50:
            return {}
        
        try:
            # Price changes
            data['price_change'] = data['close'].pct_change()
            
            # Volatility (rolling standard deviation)
            data['volatility'] = data['price_change'].rolling(window=24).std()  # 24-hour volatility
            
            # Volume analysis
            data['volume_ma'] = data['volume'].rolling(window=24).mean()
            data['volume_ratio'] = data['volume'] / data['volume_ma']
            
            # Momentum indicators
            data['momentum_1h'] = data['close'].pct_change(periods=1)
            data['momentum_4h'] = data['close'].pct_change(periods=4)
            
            # RSI calculation
            delta = data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            data['rsi'] = 100 - (100 / (1 + rs))
            
            # Bollinger Bands
            data['bb_middle'] = data['close'].rolling(window=20).mean()
            data['bb_std'] = data['close'].rolling(window=20).std()
            data['bb_upper'] = data['bb_middle'] + (data['bb_std'] * 2)
            data['bb_lower'] = data['bb_middle'] - (data['bb_std'] * 2)
            data['bb_position'] = (data['close'] - data['bb_lower']) / (data['bb_upper'] - data['bb_lower'])
            
            # Trend strength (ADX-like calculation)
            high_low = data['high'] - data['low']
            high_close = abs(data['high'] - data['close'].shift())
            low_close = abs(data['low'] - data['close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            data['atr'] = true_range.rolling(window=14).mean()
            
            # Price momentum strength
            price_change_abs = abs(data['price_change'])
            data['trend_strength'] = price_change_abs.rolling(window=10).mean()
            
            latest = data.iloc[-1]
            
            return {
                'volatility': latest['volatility'] if pd.notna(latest['volatility']) else 0.0,
                'volume_ratio': latest['volume_ratio'] if pd.notna(latest['volume_ratio']) else 1.0,
                'momentum_1h': latest['momentum_1h'] if pd.notna(latest['momentum_1h']) else 0.0,
                'momentum_4h': latest['momentum_4h'] if pd.notna(latest['momentum_4h']) else 0.0,
                'rsi': latest['rsi'] if pd.notna(latest['rsi']) else 50.0,
                'bb_position': latest['bb_position'] if pd.notna(latest['bb_position']) else 0.5,
                'trend_strength': latest['trend_strength'] if pd.notna(latest['trend_strength']) else 0.0,
                'price': latest['close']
            }
            
        except Exception as e:
            log_error(f"Error calculating indicators: {e}")
            return {}
    
    def assess_market_condition(self, data: pd.DataFrame) -> MarketCondition:
        """Assess current market conditions for trading favorability."""
        indicators = self.calculate_indicators(data)
        
        if not indicators:
            return MarketCondition(
                timestamp=datetime.now(),
                price=0.0,
                volatility=0.0,
                volume_ratio=1.0,
                momentum_1h=0.0,
                momentum_4h=0.0,
                rsi=50.0,
                bb_position=0.5,
                trend_strength=0.0,
                trading_score=0.0,
                is_favorable=False,
                reasons=["Insufficient data for analysis"]
            )
        
        # Calculate trading score based on multiple factors
        score = 0.0
        reasons = []
        
        # Volatility score (0-25 points)
        vol_score = min(25, indicators['volatility'] * 1000)  # Scale volatility
        score += vol_score
        if vol_score > 15:
            reasons.append(f"Good volatility: {indicators['volatility']:.3f}")
        
        # Volume score (0-20 points)
        vol_ratio_score = min(20, (indicators['volume_ratio'] - 1) * 50)
        score += vol_ratio_score
        if vol_ratio_score > 10:
            reasons.append(f"High volume: {indicators['volume_ratio']:.2f}x average")
        
        # Momentum score (0-25 points)
        momentum_score = min(25, abs(indicators['momentum_1h']) * 2000)
        score += momentum_score
        if momentum_score > 10:
            reasons.append(f"Strong momentum: {indicators['momentum_1h']:.3f}%")
        
        # Trend consistency score (0-15 points)
        if indicators['momentum_1h'] * indicators['momentum_4h'] > 0:  # Same direction
            trend_score = 15
            score += trend_score
            reasons.append("Consistent trend direction")
        
        # RSI extremes score (0-15 points)
        rsi = indicators['rsi']
        if rsi < self.thresholds.rsi_oversold or rsi > self.thresholds.rsi_overbought:
            rsi_score = 15
            score += rsi_score
            reasons.append(f"RSI extreme: {rsi:.1f}")
        
        # Bollinger Bands position (bonus points for extremes)
        bb_pos = indicators['bb_position']
        if bb_pos < 0.1 or bb_pos > 0.9:
            score += 10
            reasons.append(f"BB extreme: {bb_pos:.2f}")
        
        is_favorable = score >= self.thresholds.min_trading_score
        
        if not is_favorable:
            reasons = [
                f"Low volatility: {indicators['volatility']:.3f}",
                f"Volume ratio: {indicators['volume_ratio']:.2f}x",
                f"Weak momentum: {indicators['momentum_1h']:.3f}%",
                f"Score: {score:.1f}/100"
            ]
        
        return MarketCondition(
            timestamp=datetime.now(),
            price=indicators['price'],
            volatility=indicators['volatility'],
            volume_ratio=indicators['volume_ratio'],
            momentum_1h=indicators['momentum_1h'],
            momentum_4h=indicators['momentum_4h'],
            rsi=indicators['rsi'],
            bb_position=indicators['bb_position'],
            trend_strength=indicators['trend_strength'],
            trading_score=score,
            is_favorable=is_favorable,
            reasons=reasons
        )
    
    def send_alert(self, condition: MarketCondition) -> None:
        """Send alert when favorable conditions are detected."""
        current_time = datetime.now()
        
        # Check cooldown
        if (self.last_alert_time and 
            (current_time - self.last_alert_time).seconds < self.alert_cooldown):
            return
        
        print("\n" + "🚨" * 20)
        print("🚨 FAVORABLE TRADING CONDITIONS DETECTED! 🚨")
        print("🚨" * 20)
        print(f"⏰ Time: {condition.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"💰 Price: ${condition.price:,.2f}")
        print(f"📊 Trading Score: {condition.trading_score:.1f}/100")
        print(f"📈 Volatility: {condition.volatility:.3f}")
        print(f"📊 Volume: {condition.volume_ratio:.2f}x average")
        print(f"⚡ Momentum 1h: {condition.momentum_1h:.3f}%")
        print(f"🎯 RSI: {condition.rsi:.1f}")
        print(f"📍 BB Position: {condition.bb_position:.2f}")
        print("\n🎯 Reasons:")
        for reason in condition.reasons:
            print(f"   ✅ {reason}")
        
        print(f"\n🚀 RECOMMENDED ACTION:")
        print(f"   Run: python3 run_enhanced_kraken_bot.py --paper-trading --confidence 0.3")
        print("🚨" * 20 + "\n")
        
        self.last_alert_time = current_time
        
        # Save alert to file
        self.save_alert(condition)
    
    def save_alert(self, condition: MarketCondition) -> None:
        """Save alert to file for tracking."""
        try:
            alert_file = "market_alerts.json"
            alerts = []
            
            # Load existing alerts
            if os.path.exists(alert_file):
                with open(alert_file, 'r') as f:
                    alerts = json.load(f)
            
            # Add new alert
            alert_data = asdict(condition)
            alert_data['timestamp'] = condition.timestamp.isoformat()
            alerts.append(alert_data)
            
            # Keep only last 100 alerts
            alerts = alerts[-100:]
            
            # Save back to file
            with open(alert_file, 'w') as f:
                json.dump(alerts, f, indent=2)
                
        except Exception as e:
            log_error(f"Error saving alert: {e}")
    
    def print_status(self, condition: MarketCondition) -> None:
        """Print current market status."""
        status = "🟢 FAVORABLE" if condition.is_favorable else "🔴 UNFAVORABLE"
        
        print(f"\n📊 Market Status: {status}")
        print(f"⏰ {condition.timestamp.strftime('%H:%M:%S')}")
        print(f"💰 Price: ${condition.price:,.2f}")
        print(f"📈 Score: {condition.trading_score:.1f}/100")
        print(f"📊 Vol: {condition.volatility:.3f} | Volume: {condition.volume_ratio:.2f}x")
        print(f"⚡ Mom: {condition.momentum_1h:.3f}% | RSI: {condition.rsi:.1f}")
        
        if condition.reasons:
            print(f"💡 {condition.reasons[0]}")
    
    def run_continuous_monitoring(self, check_interval: int = 60) -> None:
        """Run continuous market monitoring."""
        print("🔍 Starting Continuous Market Monitoring")
        print("=" * 50)
        print(f"📊 Pair: {self.pair}")
        print(f"⏱️  Check Interval: {check_interval} seconds")
        print(f"🎯 Alert Threshold: {self.thresholds.min_trading_score}/100")
        print(f"📱 Alert Cooldown: {self.alert_cooldown} seconds")
        print("\nPress Ctrl+C to stop monitoring\n")
        
        try:
            while True:
                # Get market data
                data = self.get_market_data()
                
                if data is not None and len(data) > 50:
                    # Assess conditions
                    condition = self.assess_market_condition(data)
                    self.history.append(condition)
                    
                    # Keep only last 100 conditions
                    self.history = self.history[-100:]
                    
                    # Print status
                    self.print_status(condition)
                    
                    # Send alert if favorable
                    if condition.is_favorable:
                        self.send_alert(condition)
                    
                else:
                    print(f"⚠️  {datetime.now().strftime('%H:%M:%S')} - Unable to get market data")
                
                # Wait for next check
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            print(f"\n🛑 Monitoring stopped by user")
            self.print_summary()
    
    def print_summary(self) -> None:
        """Print monitoring summary."""
        if not self.history:
            return
        
        print(f"\n📊 Monitoring Summary:")
        print(f"   Total Checks: {len(self.history)}")
        
        favorable_count = sum(1 for c in self.history if c.is_favorable)
        print(f"   Favorable Conditions: {favorable_count}")
        
        if self.history:
            avg_score = sum(c.trading_score for c in self.history) / len(self.history)
            max_score = max(c.trading_score for c in self.history)
            print(f"   Average Score: {avg_score:.1f}/100")
            print(f"   Max Score: {max_score:.1f}/100")


def main():
    """Main function."""
    print("🔍 Market Condition Monitor")
    print("=" * 40)
    
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Missing Kraken API credentials!")
        print("Please set KRAKEN_API_KEY and KRAKEN_API_SECRET in your .env file")
        return 1
    
    # Create credentials
    credentials = KrakenCredentials(api_key=api_key, api_secret=api_secret)
    
    # Initialize monitor
    monitor = MarketMonitor(credentials, "XBTUSD")
    
    # Test connection
    if not monitor.client.test_connection():
        print("❌ Failed to connect to Kraken API")
        return 1
    
    print("✅ Connected to Kraken API")
    
    # Get current assessment
    print("\n🔍 Current Market Assessment:")
    data = monitor.get_market_data()
    
    if data is not None and len(data) > 50:
        condition = monitor.assess_market_condition(data)
        monitor.print_status(condition)
        
        if condition.is_favorable:
            print("\n🚀 Market conditions are currently FAVORABLE for trading!")
        else:
            print("\n⏳ Waiting for better market conditions...")
    
    # Ask user if they want continuous monitoring
    print(f"\n🔄 Start continuous monitoring?")
    response = input("Enter 'y' for yes, or any other key for single check: ").lower().strip()
    
    if response in ['y', 'yes']:
        monitor.run_continuous_monitoring(check_interval=60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())