#!/usr/bin/env python3
"""
Demo script showing how to use MockTrader as a drop-in replacement for live Trader.

This script demonstrates the seamless integration between mock and live trading environments.
Simply change the USE_MOCK_TRADING flag to switch between environments.
"""

from datetime import datetime
from bot.config import AlpacaCredentials, TradingSettings
from bot.strategy import TradingSignal, SignalType

# Configuration flag - change this to switch between mock and live trading
USE_MOCK_TRADING = True

def create_trader():
    """Create either a MockTrader or live Trader based on configuration."""
    
    # These credentials work for both mock and live trading
    credentials = AlpacaCredentials(
        api_key="your_api_key_here",
        secret_key="your_secret_key_here", 
        base_url="https://paper-api.alpaca.markets",
        paper_trading=True
    )
    
    settings = TradingSettings(
        symbol="BTC/USD",
        trade_amount=100.0,
        max_position_size=500.0,
        stop_loss_pct=0.05,
        take_profit_pct=0.1,
        min_trade_interval=0  # Allow immediate trades for demo
    )
    
    if USE_MOCK_TRADING:
        from mock_trading.mock_trader import MockTrader
        print("🎭 Using MockTrader (simulation mode)")
        return MockTrader(credentials, settings)
    else:
        from bot.trader import Trader
        print("📈 Using live Trader (real trading)")
        return Trader(credentials, settings)

def demo_trading_workflow():
    """Demonstrate a complete trading workflow."""
    
    # Create trader (mock or live based on configuration)
    trader = create_trader()
    
    print("\n=== Initial Account State ===")
    account_info = trader.get_account_info()
    print(f"💰 Cash: ${account_info['cash']:,.2f}")
    print(f"📊 Portfolio Value: ${account_info['portfolio_value']:,.2f}")
    
    # Create a buy signal
    buy_signal = TradingSignal(
        action=SignalType.BUY,
        confidence=0.8,
        strategy="DemoStrategy",
        timestamp=datetime.now(),
        price=50000.0,
        reasoning="Demo buy signal for testing"
    )
    
    print("\n=== Executing Buy Trade ===")
    buy_result = trader.execute_trade(buy_signal)
    
    if buy_result:
        print(f"✅ Buy executed: {buy_result.quantity} {buy_result.symbol} @ ${buy_result.price:.2f}")
        print(f"💸 Fees: ${buy_result.fees:.2f}")
        print(f"🆔 Order ID: {buy_result.order_id}")
        
        # Check position
        position_qty = trader.position_manager.get_position_quantity("BTC/USD")
        position_value = trader.position_manager.get_position_value("BTC/USD")
        avg_entry = trader.position_manager.get_average_entry_price("BTC/USD")
        
        print(f"📍 Position: {position_qty} BTC/USD")
        print(f"💵 Position Value: ${position_value:.2f}")
        print(f"📈 Avg Entry Price: ${avg_entry:.2f}")
        
    else:
        print("❌ Buy trade was not executed")
        return
    
    print("\n=== Account After Buy ===")
    account_info = trader.get_account_info()
    print(f"💰 Cash: ${account_info['cash']:,.2f}")
    print(f"📊 Portfolio Value: ${account_info['portfolio_value']:,.2f}")
    
    # Create a sell signal
    sell_signal = TradingSignal(
        action=SignalType.SELL,
        confidence=0.7,
        strategy="DemoStrategy",
        timestamp=datetime.now(),
        price=51000.0,
        reasoning="Demo sell signal for profit taking"
    )
    
    print("\n=== Executing Sell Trade ===")
    sell_result = trader.execute_trade(sell_signal)
    
    if sell_result:
        print(f"✅ Sell executed: {sell_result.quantity} {sell_result.symbol} @ ${sell_result.price:.2f}")
        print(f"💸 Fees: ${sell_result.fees:.2f}")
        
        # Check final position
        final_position_qty = trader.position_manager.get_position_quantity("BTC/USD")
        print(f"📍 Final Position: {final_position_qty} BTC/USD")
        
    else:
        print("❌ Sell trade was not executed")
    
    print("\n=== Final Account State ===")
    account_info = trader.get_account_info()
    print(f"💰 Cash: ${account_info['cash']:,.2f}")
    print(f"📊 Portfolio Value: ${account_info['portfolio_value']:,.2f}")
    
    # Calculate profit/loss
    initial_value = 10000.0 if USE_MOCK_TRADING else account_info['portfolio_value']  # Assume starting value
    pnl = account_info['portfolio_value'] - initial_value
    print(f"📈 P&L: ${pnl:.2f}")

def demo_order_management():
    """Demonstrate order management functionality."""
    
    trader = create_trader()
    
    print("\n=== Order Management Demo ===")
    
    # Place a market order
    from alpaca.trading.enums import OrderSide
    order = trader.order_manager.place_market_order("BTC/USD", OrderSide.BUY, 0.001)
    
    if order:
        print(f"📝 Order placed: {order.id}")
        print(f"📊 Order details: {order.side.value} {order.quantity} {order.symbol}")
        print(f"🔄 Status: {order.status.value}")
        
        # Check order status
        status = trader.order_manager.get_order_status(order.id)
        print(f"✅ Current status: {status}")
        
        # Get recent orders
        recent_orders = trader.order_manager.get_recent_orders(limit=5)
        print(f"📋 Recent orders count: {len(recent_orders)}")
        
    else:
        print("❌ Failed to place order")

def demo_risk_management():
    """Demonstrate risk management functionality."""
    
    trader = create_trader()
    
    print("\n=== Risk Management Demo ===")
    
    # First, create a position
    buy_signal = TradingSignal(
        action=SignalType.BUY,
        confidence=0.8,
        strategy="RiskDemo",
        timestamp=datetime.now(),
        price=50000.0,
        reasoning="Create position for risk management demo"
    )
    
    buy_result = trader.execute_trade(buy_signal)
    if not buy_result:
        print("❌ Could not create position for risk management demo")
        return
    
    print(f"✅ Position created: {buy_result.quantity} BTC/USD @ ${buy_result.price:.2f}")
    
    # Test stop loss trigger (price drops 6% - should trigger 5% stop loss)
    stop_loss_price = buy_result.price * 0.94  # 6% drop
    print(f"🔻 Testing stop loss at ${stop_loss_price:.2f}")
    
    stop_loss_triggered = trader.check_risk_management_triggers("BTC/USD", stop_loss_price)
    print(f"🛑 Stop loss triggered: {stop_loss_triggered}")
    
    # Test take profit trigger (price rises 11% - should trigger 10% take profit)
    take_profit_price = buy_result.price * 1.11  # 11% rise
    print(f"🔺 Testing take profit at ${take_profit_price:.2f}")
    
    take_profit_triggered = trader.check_risk_management_triggers("BTC/USD", take_profit_price)
    print(f"💰 Take profit triggered: {take_profit_triggered}")

def demo_error_handling():
    """Demonstrate error handling and validation."""
    
    trader = create_trader()
    
    print("\n=== Error Handling Demo ===")
    
    # Test invalid signal (low confidence)
    invalid_signal = TradingSignal(
        action=SignalType.BUY,
        confidence=0.3,  # Too low
        strategy="ErrorDemo",
        timestamp=datetime.now(),
        price=50000.0,
        reasoning="Low confidence signal"
    )
    
    print("🔍 Testing low confidence signal...")
    result = trader.execute_trade(invalid_signal)
    print(f"❌ Low confidence trade result: {result}")
    
    # Test order validation
    from mock_trading.mock_models import Order, OrderType
    from alpaca.trading.enums import OrderSide
    
    print("🔍 Testing order validation...")
    
    # Valid order
    valid_order = Order(
        symbol="BTCUSD",
        quantity=0.001,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET
    )
    
    # Invalid order
    invalid_order = Order(
        symbol="INVALID_SYMBOL",
        quantity=-1.0,  # Negative quantity
        side=OrderSide.BUY,
        order_type=OrderType.MARKET
    )
    
    print(f"✅ Valid order validation: {trader.validate_order(valid_order)}")
    print(f"❌ Invalid order validation: {trader.validate_order(invalid_order)}")

if __name__ == "__main__":
    print("🚀 MockTrader Integration Demo")
    print("=" * 50)
    
    try:
        # Run all demos
        demo_trading_workflow()
        demo_order_management()
        demo_risk_management()
        demo_error_handling()
        
        print("\n" + "=" * 50)
        print("✅ Demo completed successfully!")
        print(f"🎭 Mode: {'Mock Trading' if USE_MOCK_TRADING else 'Live Trading'}")
        print("\n💡 To switch between mock and live trading, change USE_MOCK_TRADING flag")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()