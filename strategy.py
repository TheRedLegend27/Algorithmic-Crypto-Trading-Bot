import pandas as pd
import numpy as np
from utils import logger
from config import RSI_PERIOD, VWAP_LENGTH

class Strategy:
    def __init__(self):
        self.rsi_period = RSI_PERIOD
        self.vwap_length = VWAP_LENGTH

    def calculate_vwap(self, df: pd.DataFrame):
        """Calculates the Volume-Weighted Average Price (VWAP)."""
        if df is None or 'price' not in df.columns or 'size' not in df.columns:
            return None
        q = df['size'].values
        p = df['price'].values
        return (p * q).sum() / q.sum() if q.sum() > 0 else None

    def calculate_rsi(self, df: pd.DataFrame, period: int):
        """Calculates the Relative Strength Index (RSI)."""
        if df is None or len(df) < period:
            return None
        delta = df['price'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def generate_signal(self, current_price: float, trade_df: pd.DataFrame):
        """Generates a trading signal based on VWAP and RSI."""
        if trade_df is None:
            return "HOLD"

        vwap = self.calculate_vwap(trade_df)
        rsi_series = self.calculate_rsi(trade_df, self.rsi_period)
        
        if vwap is None or rsi_series is None or rsi_series.empty:
            return "HOLD"
            
        rsi = rsi_series.iloc[-1]

        logger.info(f"Current Price: {current_price:.2f}, VWAP: {vwap:.2f}, RSI: {rsi:.2f}")

        if current_price < vwap and rsi < 30:
            return "BUY"
        elif current_price > vwap and rsi > 70:
            return "SELL"
        
        return "HOLD"