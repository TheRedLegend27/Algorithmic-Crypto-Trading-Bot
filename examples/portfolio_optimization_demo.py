#!/usr/bin/env python3
"""
Portfolio Optimization Demo

This script demonstrates the portfolio optimization capabilities of the adaptive bot,
including multi-pair coordination, capital allocation optimization, and rebalancing.
"""
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from bot.adaptive.portfolio_optimizer import PortfolioOptimizer, PortfolioPosition
from bot.adaptive.data_models import MarketRegime, AdaptiveSignal
from bot.adaptive.enums import RegimeType, SignalStrength


def create_sample_market_data(pair: str, trend: float = 0.0) -> pd.DataFrame:
    """Create sample market data with specified trend."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='5min')
    
    # Create trending price data
    base_price = {'BTC/USD': 45000, 'ETH/USD': 3000, 'SOL/USD': 100}.get(pair, 1000)
    prices = []
    current_price = base_price
    
    for i in range(100):
        # Add trend and random walk
        trend_component = trend * 0.001  # 0.1% trend per period
        random_component = np.random.normal(0, 0.01)  # 1% volatility
        
        current_price *= (1 + trend_component + random_component)
        prices.append(current_price)
    
    return pd.DataFrame({
        'timestamp': dates,
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': np.random.uniform(100, 1000, 100)
    })


def create_sample_signal(pair: str, signal_type: str = "buy", confidence: float = 0.8) -> AdaptiveSignal:
    """Create sample adaptive signal."""
    regime_type = RegimeType.TRENDING_BULL if signal_type == "buy" else RegimeType.TRENDING_BEAR
    
    return AdaptiveSignal(
        pair=pair,
        signal_type=signal_type,
        strength=SignalStrength.STRONG,
        confidence=confidence,
        price=45000.0 if pair == 'BTC/USD' else 3000.0 if pair == 'ETH/USD' else 100.0,
        timestamp=datetime.now(),
        regime_context=MarketRegime(
            regime_type=regime_type,
            confidence=0.8,
            volatility_level=0.6,
            trend_strength=0.7 if signal_type == "buy" else -0.7,
            momentum=0.5 if signal_type == "buy" else -0.5,
            detected_at=datetime.now()
        ),
        ml_confidence=0.75,
        strategy_weights={'momentum': 0.6, 'mean_reversion': 0.4}
    )


def create_sample_positions() -> dict:
    """Create sample portfolio positions."""
    return {
        'BTC/USD': PortfolioPosition(
            pair='BTC/USD',
            size=2000.0,
            entry_price=44000.0,
            current_price=45000.0,
            unrealized_pnl=200.0,
            realized_pnl=100.0,
            allocation_percentage=0.4,
            risk_contribution=0.3
        ),
        'ETH/USD': PortfolioPosition(
            pair='ETH/USD',
            size=1500.0,
            entry_price=2900.0,
            current_price=3000.0,
            unrealized_pnl=150.0,
            realized_pnl=50.0,
            allocation_percentage=0.3,
            risk_contribution=0.2
        )
    }


async def demonstrate_portfolio_optimization():
    """Demonstrate portfolio optimization features."""
    print("🚀 Portfolio Optimization Demo")
    print("=" * 50)
    
    # Initialize portfolio optimizer
    config = {
        'max_pairs': 5,
        'max_correlation': 0.7,
        'max_single_pair_allocation': 0.4,
        'min_single_pair_allocation': 0.05,
        'rebalance_threshold': 0.1,
        'target_volatility': 0.15
    }
    
    optimizer = PortfolioOptimizer(config)
    print(f"✅ Portfolio optimizer initialized with config: {config}")
    
    # Set up initial portfolio state
    positions = create_sample_positions()
    total_capital = 10000.0
    available_capital = 5000.0
    
    optimizer.update_portfolio_state(positions, total_capital, available_capital)
    print(f"\n📊 Portfolio State Updated:")
    print(f"   Total Capital: ${total_capital:,.2f}")
    print(f"   Available Capital: ${available_capital:,.2f}")
    print(f"   Positions: {len(positions)}")
    
    # Display current portfolio metrics
    metrics = optimizer.portfolio_metrics
    if metrics:
        print(f"\n📈 Portfolio Metrics:")
        print(f"   Total Value: ${metrics.total_value:,.2f}")
        print(f"   Total P&L: ${metrics.total_pnl:,.2f}")
        print(f"   Return: {metrics.total_return_pct:.2%}")
        print(f"   Correlation Risk: {metrics.correlation_risk:.3f}")
        print(f"   Concentration Risk: {metrics.concentration_risk:.3f}")
    
    # Create market data for correlation analysis
    print(f"\n🔍 Creating Market Data for Analysis...")
    market_data = {
        'BTC/USD': create_sample_market_data('BTC/USD', trend=0.5),
        'ETH/USD': create_sample_market_data('ETH/USD', trend=0.3),
        'SOL/USD': create_sample_market_data('SOL/USD', trend=0.8),
        'AVAX/USD': create_sample_market_data('AVAX/USD', trend=-0.2)
    }
    
    # Update correlation matrix
    optimizer.update_correlation_matrix(market_data)
    print(f"✅ Correlation matrix updated for {len(market_data)} pairs")
    
    if optimizer.correlation_matrix is not None:
        print(f"\n📊 Correlation Matrix:")
        print(optimizer.correlation_matrix.round(3))
    
    # Add trading opportunities
    print(f"\n🎯 Adding Trading Opportunities...")
    opportunities = {}
    
    pairs_and_signals = [
        ('BTC/USD', 'buy', 0.8),
        ('ETH/USD', 'buy', 0.7),
        ('SOL/USD', 'buy', 0.9),
        ('AVAX/USD', 'sell', 0.6)
    ]
    
    for pair, signal_type, confidence in pairs_and_signals:
        signal = create_sample_signal(pair, signal_type, confidence)
        market_data_pair = market_data[pair]
        
        opportunity = optimizer.add_opportunity(signal, market_data_pair)
        opportunities[pair] = opportunity
        
        print(f"   {pair}: {signal_type.upper()} signal (confidence: {confidence:.1%}, "
              f"score: {opportunity.final_score:.3f})")
    
    # Optimize capital allocation
    print(f"\n⚙️ Optimizing Capital Allocation...")
    optimal_allocations = optimizer.optimize_capital_allocation()
    
    print(f"📊 Optimal Allocations:")
    total_allocation = 0.0
    for pair, allocation in sorted(optimal_allocations.items(), key=lambda x: x[1], reverse=True):
        print(f"   {pair}: {allocation:.1%} (${allocation * total_capital:,.2f})")
        total_allocation += allocation
    
    print(f"   Total Allocation: {total_allocation:.1%}")
    
    # Check rebalancing needs
    print(f"\n🔄 Checking Rebalancing Needs...")
    
    # Force rebalancing by setting old timestamp
    optimizer.last_rebalance = datetime.now() - timedelta(hours=12)
    
    should_rebalance = optimizer.should_rebalance()
    print(f"   Should Rebalance: {should_rebalance}")
    
    if should_rebalance:
        rebalancing_orders = optimizer.generate_rebalancing_orders()
        print(f"\n📋 Rebalancing Orders ({len(rebalancing_orders)} orders):")
        
        for i, order in enumerate(rebalancing_orders, 1):
            print(f"   {i}. {order['pair']}: {order['type'].upper()} ${order['size']:,.2f}")
            print(f"      Reason: {order['reason']}")
            print(f"      Target Allocation: {order['target_allocation']:.1%}")
            print(f"      Current Allocation: {order['current_allocation']:.1%}")
    
    # Portfolio summary
    print(f"\n📊 Portfolio Summary:")
    summary = optimizer.get_portfolio_summary()
    
    for key, value in summary.items():
        if isinstance(value, float):
            if 'pct' in key or 'return' in key:
                print(f"   {key.replace('_', ' ').title()}: {value:.2%}")
            elif 'value' in key or 'pnl' in key:
                print(f"   {key.replace('_', ' ').title()}: ${value:,.2f}")
            else:
                print(f"   {key.replace('_', ' ').title()}: {value:.3f}")
        else:
            print(f"   {key.replace('_', ' ').title()}: {value}")
    
    # Demonstrate risk analysis
    print(f"\n⚠️ Risk Analysis:")
    correlation_risk = optimizer.calculate_correlation_risk()
    concentration_risk = optimizer._calculate_concentration_risk()
    
    print(f"   Correlation Risk: {correlation_risk:.3f}")
    print(f"   Concentration Risk: {concentration_risk:.3f}")
    
    if correlation_risk > 0.6:
        print("   ⚠️ High correlation risk detected!")
    
    if concentration_risk > 0.7:
        print("   ⚠️ High concentration risk detected!")
    
    # Clean up expired opportunities
    print(f"\n🧹 Cleaning Up Opportunities...")
    initial_count = len(optimizer.opportunities)
    optimizer.cleanup_expired_opportunities()
    final_count = len(optimizer.opportunities)
    
    print(f"   Opportunities: {initial_count} → {final_count}")
    
    print(f"\n✅ Portfolio Optimization Demo Complete!")


def demonstrate_opportunity_scoring():
    """Demonstrate opportunity scoring system."""
    print(f"\n🎯 Opportunity Scoring Demo")
    print("=" * 30)
    
    optimizer = PortfolioOptimizer()
    
    # Create different types of signals to show scoring differences
    test_cases = [
        ("High Confidence Bull", "buy", 0.9, RegimeType.TRENDING_BULL),
        ("Medium Confidence Bull", "buy", 0.6, RegimeType.TRENDING_BULL),
        ("High Confidence Bear", "sell", 0.9, RegimeType.TRENDING_BEAR),
        ("Uncertain Market", "buy", 0.5, RegimeType.UNCERTAIN),
        ("High Volatility", "buy", 0.7, RegimeType.HIGH_VOLATILITY),
    ]
    
    market_data = create_sample_market_data('BTC/USD')
    
    print(f"📊 Opportunity Scoring Comparison:")
    print(f"{'Case':<20} {'Type':<4} {'Conf':<4} {'Regime':<15} {'Score':<5}")
    print("-" * 55)
    
    for case_name, signal_type, confidence, regime_type in test_cases:
        signal = AdaptiveSignal(
            pair="BTC/USD",
            signal_type=signal_type,
            strength=SignalStrength.STRONG,
            confidence=confidence,
            price=45000.0,
            timestamp=datetime.now(),
            regime_context=MarketRegime(
                regime_type=regime_type,
                confidence=0.8,
                volatility_level=0.6,
                trend_strength=0.7 if signal_type == "buy" else -0.7,
                momentum=0.5,
                detected_at=datetime.now()
            ),
            ml_confidence=0.75
        )
        
        opportunity = optimizer.add_opportunity(signal, market_data)
        
        print(f"{case_name:<20} {signal_type.upper():<4} {confidence:<4.1f} "
              f"{regime_type.value:<15} {opportunity.final_score:<5.3f}")


async def main():
    """Main demo function."""
    print("🚀 Adaptive Bot Portfolio Optimization Demo")
    print("=" * 60)
    
    try:
        await demonstrate_portfolio_optimization()
        demonstrate_opportunity_scoring()
        
    except Exception as e:
        print(f"❌ Error in demo: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())