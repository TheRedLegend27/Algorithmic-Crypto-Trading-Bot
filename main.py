import time
import asyncio
from alpaca_py.trading.enums import OrderSide
from config import (
    ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL, CRYPTO_PAIR,
    RISK_PER_TRADE, TAKE_PROFIT_PERCENTAGE, STOP_LOSS_PERCENTAGE, VWAP_LENGTH
)
from data_handler import DataHandler
from strategy import Strategy
from order_manager import OrderManager
from risk_manager import RiskManager
from utils import logger

class TradingBot:
    def __init__(self):
        self.data_handler = DataHandler(ALPACA_API_KEY, ALPACA_SECRET_KEY, CRYPTO_PAIR)
        self.strategy = Strategy()
        self.order_manager = OrderManager(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL)
        self.risk_manager = RiskManager(self.order_manager.trading_client, RISK_PER_TRADE)
        self.last_signal = None
        self.is_position_open = False

    async def run(self):
        """Main loop for the trading bot."""
        # Start the data stream in a separate thread/task
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, self.data_handler.run_stream)

        logger.info("Bot started. Waiting for market data...")

        while True:
            await asyncio.sleep(1) # Main loop delay
            
            # Check if we have an open position for the current pair
            open_positions = self.order_manager.get_open_positions()
            self.is_position_open = any(p.symbol == CRYPTO_PAIR for p in open_positions)

            if self.data_handler.latest_trade and not self.is_position_open:
                current_price = self.data_handler.latest_trade.price
                trade_df = self.data_handler.get_recent_trades_df(lookback_period=VWAP_LENGTH)

                if trade_df is not None:
                    signal = self.strategy.generate_signal(current_price, trade_df)
                    
                    if signal != "HOLD" and signal != self.last_signal:
                        logger.info(f"New signal: {signal}")
                        self.last_signal = signal
                        
                        if signal == "BUY":
                            side = OrderSide.BUY
                            tp_price = current_price * (1 + TAKE_PROFIT_PERCENTAGE)
                            sl_price = current_price * (1 - STOP_LOSS_PERCENTAGE)
                        elif signal == "SELL":
                            # Note: Shorting crypto might not be available. This is for demonstration.
                            # Alpaca's crypto trading is typically long-only.
                            # This part of the logic assumes shorting is possible.
                            side = OrderSide.SELL
                            tp_price = current_price * (1 - TAKE_PROFIT_PERCENTAGE)
                            sl_price = current_price * (1 + STOP_LOSS_PERCENTAGE)
                        
                        quantity = self.risk_manager.get_trade_quantity(current_price, sl_price)
                        
                        if quantity > 0:
                            self.order_manager.place_trade(CRYPTO_PAIR, quantity, side, tp_price, sl_price)
                            
            elif self.is_position_open:
                logger.info("Position is open, holding.")


if __name__ == "__main__":
    bot = TradingBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
        # Optional: Implement logic to close open positions on shutdown
    except Exception as e:
        logger.error(f"An unexpected error occurred in the main loop: {e}")