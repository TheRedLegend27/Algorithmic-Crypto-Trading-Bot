#!/usr/bin/env python3
"""
Configure the adaptive bot for $480 capital with aggressive strategy.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def configure_aggressive_capital():
    """Configure the bot for $480 aggressive trading."""
    print("🚀 Configuring Aggressive $480 Trading Bot")
    print("="*50)
    
    # Configuration for aggressive small capital trading
    aggressive_config = {
        # Capital settings
        'initial_capital': 480.0,
        'paper_trading': True,
        
        # Aggressive position sizing (higher risk, higher reward)
        'position_size_pct': 0.15,  # 15% per trade (vs 2-5% conservative)
        'max_positions': 3,         # Focus on fewer, larger positions
        'max_portfolio_risk': 0.25, # 25% total portfolio risk (vs 10% conservative)
        
        # Aggressive risk management
        'max_risk_per_trade': 0.08,    # 8% max loss per trade (vs 2% conservative)
        'stop_loss_pct': 0.06,         # 6% stop loss (tighter for aggressive)
        'take_profit_pct': 0.18,       # 18% take profit (3:1 reward/risk ratio)
        'max_drawdown_threshold': 0.20, # 20% max drawdown before emergency stop
        
        # Aggressive adaptation settings
        'adaptation_confidence_threshold': 0.5,  # Lower threshold = more adaptations
        'min_performance_threshold': -0.05,      # Adapt after 5% drop (vs 10%)
        'max_adaptations_per_hour': 5,           # More frequent adaptations
        'min_time_between_adaptations_minutes': 10, # Faster adaptation cycles
        
        # Aggressive strategy weights (favor momentum and breakout strategies)
        'strategy_weights': {
            'enhanced_momentum': 0.4,      # High momentum focus
            'volatility_breakout': 0.3,    # Breakout trading
            'price_action': 0.2,           # Quick price action
            'mean_reversion': 0.1          # Minimal mean reversion
        },
        
        # ML settings for aggressive learning
        'ml_confidence_threshold': 0.4,    # Lower threshold for ML signals
        'min_training_samples': 25,        # Faster initial learning
        'retrain_frequency_hours': 6,      # More frequent retraining
        
        # Market regime preferences (favor high volatility)
        'preferred_regimes': ['high_volatility', 'trending_bull', 'trending_bear'],
        'avoid_regimes': ['low_volatility', 'ranging'],
        
        # Trading frequency
        'min_signal_strength': 0.6,        # Lower threshold = more trades
        'signal_timeout_minutes': 30,      # Faster signal expiration
        'max_trades_per_day': 15,          # Higher trading frequency
    }
    
    print("📊 Aggressive Configuration Summary:")
    print(f"   💰 Starting Capital: ${aggressive_config['initial_capital']:,.0f}")
    print(f"   📈 Position Size: {aggressive_config['position_size_pct']:.1%} per trade")
    print(f"   🎯 Max Positions: {aggressive_config['max_positions']}")
    print(f"   ⚠️  Risk Per Trade: {aggressive_config['max_risk_per_trade']:.1%}")
    print(f"   🛑 Stop Loss: {aggressive_config['stop_loss_pct']:.1%}")
    print(f"   🎯 Take Profit: {aggressive_config['take_profit_pct']:.1%}")
    print(f"   📊 Max Portfolio Risk: {aggressive_config['max_portfolio_risk']:.1%}")
    
    return aggressive_config

def update_adaptive_config_for_aggressive():
    """Update the adaptive configuration for aggressive trading."""
    print("\n🔧 Updating adaptive configuration...")
    
    # Read current adaptive config
    try:
        with open('bot/adaptive/adaptive_config.py', 'r') as f:
            content = f.read()
        
        # Aggressive configuration updates
        updates = [
            # Capital settings
            ('initial_capital: float = 10000.0', 'initial_capital: float = 480.0'),
            
            # Risk management - more aggressive
            ('max_risk_per_trade: float = 0.02', 'max_risk_per_trade: float = 0.08'),
            ('max_portfolio_risk: float = 0.1', 'max_portfolio_risk: float = 0.25'),
            ('max_drawdown_threshold: float = 0.15', 'max_drawdown_threshold: float = 0.20'),
            
            # Adaptation - more frequent
            ('max_adaptations_per_hour: int = 3', 'max_adaptations_per_hour: int = 5'),
            ('min_time_between_adaptations_minutes: int = 15', 'min_time_between_adaptations_minutes: int = 10'),
            ('adaptation_confidence_threshold: float = 0.6', 'adaptation_confidence_threshold: float = 0.5'),
            ('min_performance_threshold: float = -0.1', 'min_performance_threshold: float = -0.05'),
            
            # ML settings - faster learning
            ('min_training_samples: int = 50', 'min_training_samples: int = 25'),
            ('retrain_frequency_hours: int = 12', 'retrain_frequency_hours: int = 6'),
            ('min_model_confidence: float = 0.4', 'min_model_confidence: float = 0.3'),
        ]
        
        # Apply updates
        modified_content = content
        for old, new in updates:
            if old in modified_content:
                modified_content = modified_content.replace(old, new)
                print(f"   ✅ Updated: {old.split(':')[0]} -> {new.split(':')[1].strip()}")
            else:
                print(f"   ⚠️  Not found: {old.split(':')[0]}")
        
        # Write back the modified content
        with open('bot/adaptive/adaptive_config.py', 'w') as f:
            f.write(modified_content)
        
        print("✅ Adaptive configuration updated for aggressive trading")
        return True
        
    except Exception as e:
        print(f"❌ Error updating adaptive config: {str(e)}")
        return False

def update_paper_trading_config():
    """Update paper trading configuration for $480 aggressive trading."""
    print("\n🔧 Updating paper trading configuration...")
    
    try:
        # Read the paper trading file
        with open('bot/adaptive/paper_trading.py', 'r') as f:
            content = f.read()
        
        # Find the PaperTradingConfig class and update defaults
        updates = [
            ('initial_capital: float = 10000.0', 'initial_capital: float = 480.0'),
            ('max_position_size: float = 1000.0', 'max_position_size: float = 72.0'),  # 15% of $480
            ('min_position_size: float = 10.0', 'min_position_size: float = 5.0'),
            ('max_positions: int = 10', 'max_positions: int = 3'),
            ('position_size_pct: float = 0.02', 'position_size_pct: float = 0.15'),  # 15% aggressive
        ]
        
        modified_content = content
        for old, new in updates:
            if old in modified_content:
                modified_content = modified_content.replace(old, new)
                print(f"   ✅ Updated: {old.split(':')[0]} -> {new.split(':')[1].strip()}")
        
        # Write back
        with open('bot/adaptive/paper_trading.py', 'w') as f:
            f.write(modified_content)
        
        print("✅ Paper trading configuration updated")
        return True
        
    except Exception as e:
        print(f"❌ Error updating paper trading config: {str(e)}")
        return False

def create_aggressive_strategy_weights():
    """Create aggressive strategy weight configuration."""
    print("\n🎯 Configuring aggressive strategy weights...")
    
    aggressive_strategies = """
# Aggressive Strategy Configuration for $480 Capital
AGGRESSIVE_STRATEGY_CONFIG = {
    # Strategy weights optimized for small capital aggressive trading
    'strategy_weights': {
        'enhanced_momentum': 0.4,      # High momentum for quick gains
        'volatility_breakout': 0.3,    # Breakout trading for big moves
        'price_action': 0.2,           # Quick scalping opportunities
        'mean_reversion': 0.1          # Minimal conservative plays
    },
    
    # Aggressive parameters for each strategy
    'enhanced_momentum': {
        'momentum_threshold': 0.002,    # Lower threshold = more signals
        'volume_threshold': 1.05,       # Lower volume requirement
        'confidence_multiplier': 1.2,   # Boost signal confidence
    },
    
    'volatility_breakout': {
        'breakout_threshold': 0.015,    # 1.5% breakout threshold
        'volume_confirmation': True,    # Require volume confirmation
        'false_breakout_filter': 0.8,  # Less strict filtering
    },
    
    'price_action': {
        'min_body_pct': 0.001,         # Smaller candle body requirement
        'lookback_periods': 10,        # Shorter lookback for faster signals
        'signal_strength_multiplier': 1.3,
    },
    
    # Risk management per strategy
    'risk_management': {
        'stop_loss_pct': 0.06,         # 6% stop loss
        'take_profit_pct': 0.18,       # 18% take profit (3:1 ratio)
        'trailing_stop_pct': 0.04,     # 4% trailing stop
        'max_holding_hours': 24,       # Don't hold positions too long
    },
    
    # Market regime preferences
    'regime_preferences': {
        'high_volatility': 1.5,        # Boost signals in high volatility
        'trending_bull': 1.3,          # Strong bull market preference
        'trending_bear': 1.2,          # Also trade bear markets aggressively
        'ranging': 0.5,                # Reduce ranging market activity
        'low_volatility': 0.3,         # Minimal low volatility trading
    }
}
"""
    
    # Save the aggressive strategy configuration
    with open('aggressive_strategy_config.py', 'w') as f:
        f.write(aggressive_strategies)
    
    print("✅ Aggressive strategy configuration saved to: aggressive_strategy_config.py")
    return aggressive_strategies

def calculate_aggressive_projections():
    """Calculate potential returns with aggressive strategy."""
    print("\n📊 Aggressive Strategy Projections:")
    print("="*40)
    
    initial_capital = 480.0
    
    # Aggressive scenario parameters
    scenarios = {
        'Conservative Aggressive': {
            'monthly_return': 0.15,  # 15% per month
            'win_rate': 0.65,
            'avg_trade_size': 72,    # 15% of capital
            'trades_per_month': 40,
        },
        'Moderate Aggressive': {
            'monthly_return': 0.25,  # 25% per month
            'win_rate': 0.60,
            'avg_trade_size': 72,
            'trades_per_month': 60,
        },
        'High Aggressive': {
            'monthly_return': 0.40,  # 40% per month
            'win_rate': 0.55,
            'avg_trade_size': 72,
            'trades_per_month': 80,
        }
    }
    
    for scenario_name, params in scenarios.items():
        print(f"\n{scenario_name} Scenario:")
        capital = initial_capital
        
        for month in range(1, 7):  # 6 months projection
            monthly_gain = capital * params['monthly_return']
            capital += monthly_gain
            
            print(f"   Month {month}: ${capital:,.0f} (+${monthly_gain:,.0f})")
        
        print(f"   📈 Total Return: {((capital - initial_capital) / initial_capital) * 100:.0f}%")
        print(f"   💰 Profit: ${capital - initial_capital:,.0f}")
        print(f"   📊 Win Rate: {params['win_rate']:.1%}")
        print(f"   🔄 Trades/Month: {params['trades_per_month']}")

def show_risk_warnings():
    """Show important risk warnings for aggressive trading."""
    print("\n" + "="*50)
    print("⚠️  AGGRESSIVE TRADING RISK WARNINGS")
    print("="*50)
    
    warnings = [
        "🔥 Higher potential returns come with higher potential losses",
        "📉 Aggressive strategies can have 20-30% drawdown periods",
        "⚡ More frequent trading = higher transaction costs",
        "🎯 Requires closer monitoring and faster decision making",
        "📊 Win rate may be lower but winners should be bigger",
        "🛑 Emergency stops are crucial - respect them!",
        "💡 Start with paper trading to test the strategy",
        "📈 Be prepared for volatile equity curves",
    ]
    
    for warning in warnings:
        print(f"   {warning}")
    
    print("\n✅ BENEFITS OF AGGRESSIVE APPROACH:")
    benefits = [
        "🚀 Faster capital growth potential",
        "📊 More trading opportunities and data for ML learning",
        "🎯 Better suited for small capital accounts",
        "⚡ Quicker adaptation to market changes",
        "💰 Higher absolute returns on successful trades",
    ]
    
    for benefit in benefits:
        print(f"   {benefit}")

def main():
    """Main configuration function."""
    print("🚀 AGGRESSIVE $480 BOT CONFIGURATION")
    print("="*60)
    
    # Step 1: Show configuration
    config = configure_aggressive_capital()
    
    # Step 2: Update configurations
    print("\n" + "="*60)
    print("UPDATING CONFIGURATION FILES")
    print("="*60)
    
    adaptive_updated = update_adaptive_config_for_aggressive()
    paper_updated = update_paper_trading_config()
    strategy_config = create_aggressive_strategy_weights()
    
    # Step 3: Show projections
    calculate_aggressive_projections()
    
    # Step 4: Show warnings
    show_risk_warnings()
    
    # Step 5: Final summary
    print("\n" + "="*60)
    print("🎯 CONFIGURATION COMPLETE!")
    print("="*60)
    
    if adaptive_updated and paper_updated:
        print("✅ All configurations updated successfully!")
        print("\n🚀 Ready to run aggressive $480 bot:")
        print("   python3 run_adaptive_bot.py")
        print("\n📊 Monitor progress with:")
        print("   python3 analyze_bot_session.py")
        print("\n⚠️  Remember: This is aggressive trading - monitor closely!")
    else:
        print("❌ Some configurations failed to update")
        print("   Please check the error messages above")

if __name__ == "__main__":
    main()