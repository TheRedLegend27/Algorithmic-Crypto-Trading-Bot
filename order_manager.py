from alpaca_py.trading.client import TradingClient
from alpaca_py.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest, OrderSide, TimeInForce
from alpaca_py.common.exceptions import APIError
from utils import logger

class OrderManager:
    def __init__(self, api_key: str, secret_key: str, base_url: str):
        self.trading_client = TradingClient(api_key, secret_key, paper=True if "paper" in base_url else False)

    def place_trade(self, symbol: str, quantity: float, side: OrderSide, take_profit_price: float, stop_loss_price: float):
        """Places a market order with associated take profit and stop loss."""
        try:
            market_order_data = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.GTC, # Good 'Til Canceled
                take_profit=TakeProfitRequest(limit_price=take_profit_price),
                stop_loss=StopLossRequest(stop_price=stop_loss_price)
            )
            market_order = self.trading_client.submit_order(order_data=market_order_data)
            logger.info(f"Placed {side.value} order for {quantity} of {symbol} with TP @ {take_profit_price} and SL @ {stop_loss_price}. Order ID: {market_order.id}")
            return market_order
        except APIError as e:
            logger.error(f"API Error placing trade: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred during trade placement: {e}")
            return None
            
    def get_open_positions(self):
        """Retrieves all open positions."""
        try:
            positions = self.trading_client.get_all_positions()
            return positions
        except APIError as e:
            logger.error(f"API Error getting open positions: {e}")
            return []

    def close_position(self, symbol: str):
        """Closes a specific position."""
        try:
            self.trading_client.close_position(symbol)
            logger.info(f"Closed position for {symbol}.")
        except APIError as e:
            logger.error(f"API Error closing position for {symbol}: {e}")