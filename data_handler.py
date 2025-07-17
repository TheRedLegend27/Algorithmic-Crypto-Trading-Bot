import pandas as pd
from alpaca_py.data.historical import CryptoHistoricalDataClient
from alpaca_py.data.models import CryptoTrade
from alpaca_py.data.live.crypto import CryptoDataStream
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY, CRYPTO_PAIR, TIME_FRAME
from utils import logger

class DataHandler:
    def __init__(self, api_key, secret_key, crypto_pair):
        self.historical_client = CryptoHistoricalDataClient(api_key, secret_key)
        self.stream_client = CryptoDataStream(api_key, secret_key)
        self.crypto_pair = crypto_pair
        self.latest_trade = None
        self.trade_history = []

    async def on_trade(self, trade: CryptoTrade):
        """Callback function to handle incoming trades."""
        self.latest_trade = trade
        self.trade_history.append({
            'price': trade.price,
            'size': trade.size,
            'timestamp': trade.timestamp
        })
        # Keep trade history to a manageable size
        if len(self.trade_history) > 1000:
            self.trade_history.pop(0)

        logger.info(f"Received trade: {trade.price:.2f} @ {trade.timestamp}")

    def run_stream(self):
        """Starts the data stream."""
        self.stream_client.subscribe_trades(self.on_trade, self.crypto_pair)
        self.stream_client.run()

    def get_recent_trades_df(self, lookback_period=20):
        """Returns a DataFrame of recent trades."""
        if len(self.trade_history) < lookback_period:
            return None
        return pd.DataFrame(self.trade_history[-lookback_period:])