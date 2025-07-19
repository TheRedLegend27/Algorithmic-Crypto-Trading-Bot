"""
Yahoo Finance data fetcher for crypto and stock data.
Alternative to Alpaca when API access is limited.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import time

from bot.utils import log_info, log_error, log_warning


class YahooDataFetcher:
    """Fetches real market data from Yahoo Finance."""
    
    def __init__(self):
        """Initialize the Yahoo Finance data fetcher."""
        self.last_request_time = 0
        self.rate_limit_wait = 1.0  # 1 second between requests
        
        # Symbol mapping for crypto
        self.crypto_symbols = {
            "BTC/USD": "BTC-USD",
            "ETH/USD": "ETH-USD", 
            "SOL/USD": "SOL-USD",
            "AVAX/USD": "AVAX-USD",
            "MATIC/USD": "MATIC-USD",
            "ADA/USD": "ADA-USD",
            "DOT/USD": "DOT-USD",
            "LINK/USD": "LINK-USD"
        }
        
        # Crypto ETFs as alternatives
        self.crypto_etfs = {
            "BTC/USD": "BITO",  # Bitcoin ETF
            "ETH/USD": "ETHE",  # Ethereum ETF
        }
    
    def _respect_rate_limit(self):
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_wait:
            time.sleep(self.rate_limit_wait - elapsed)
        self.last_request_time = time.time()
    
    def fetch_crypto_data(self, symbol: str, timeframe: str = "5Min", 
                         limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch crypto data from Yahoo Finance.
        
        Args:
            symbol: Trading pair (e.g., "BTC/USD")
            timeframe: Timeframe ("1Min", "5Min", "15Min", "1H", "1D")
            limit: Number of data points to retrieve
            
        Returns:
            DataFrame with OHLCV data or None if failed
        """
        self._respect_rate_limit()
        
        # Map symbol to Yahoo Finance format
        yahoo_symbol = self.crypto_symbols.get(symbol, symbol)
        
        log_info(f"Fetching {symbol} ({yahoo_symbol}) data with {timeframe} timeframe")
        
        try:
            # Calculate period based on timeframe and limit
            period_mapping = {
                "1Min": timedelta(minutes=limit),
                "5Min": timedelta(minutes=limit * 5),
                "15Min": timedelta(minutes=limit * 15),
                "1H": timedelta(hours=limit),
                "1D": timedelta(days=limit)
            }
            
            if timeframe not in period_mapping:
                log_error(f"Unsupported timeframe: {timeframe}")
                return None
            
            # Calculate start and end times
            end_time = datetime.now()
            start_time = end_time - period_mapping[timeframe] * 2  # Get extra data
            
            # Map timeframe to Yahoo Finance interval
            interval_mapping = {
                "1Min": "1m",
                "5Min": "5m", 
                "15Min": "15m",
                "1H": "1h",
                "1D": "1d"
            }
            
            interval = interval_mapping[timeframe]
            
            # Fetch data
            ticker = yf.Ticker(yahoo_symbol)
            data = ticker.history(
                start=start_time,
                end=end_time,
                interval=interval,
                auto_adjust=True,
                prepost=True
            )
            
            if data.empty:
                log_warning(f"No data returned for {yahoo_symbol}")
                
                # Try ETF alternative if available
                if symbol in self.crypto_etfs:
                    etf_symbol = self.crypto_etfs[symbol]
                    log_info(f"Trying ETF alternative: {etf_symbol}")
                    
                    ticker = yf.Ticker(etf_symbol)
                    data = ticker.history(
                        start=start_time,
                        end=end_time,
                        interval=interval,
                        auto_adjust=True,
                        prepost=True
                    )
                
                if data.empty:
                    return None
            
            # Standardize column names
            data.columns = data.columns.str.lower()
            
            # Ensure we have the required columns
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in data.columns:
                    log_error(f"Missing required column: {col}")
                    return None
            
            # Keep only required columns
            data = data[required_columns].copy()
            
            # Remove any NaN values
            data = data.dropna()
            
            # Limit to requested number of points
            if len(data) > limit:
                data = data.tail(limit)
            
            log_info(f"Successfully fetched {len(data)} data points for {symbol}")
            
            return data
            
        except Exception as e:
            log_error(f"Error fetching data for {symbol}: {str(e)}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """Get current price for a symbol."""
        try:
            yahoo_symbol = self.crypto_symbols.get(symbol, symbol)
            ticker = yf.Ticker(yahoo_symbol)
            info = ticker.info
            
            # Try different price fields
            price_fields = ['regularMarketPrice', 'currentPrice', 'price', 'lastPrice']
            for field in price_fields:
                if field in info and info[field]:
                    return float(info[field])
            
            # Fallback to recent history
            data = ticker.history(period="1d", interval="1m")
            if not data.empty:
                return float(data['Close'].iloc[-1])
                
            return None
            
        except Exception as e:
            log_error(f"Error getting current price for {symbol}: {str(e)}")
            return None
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """Validate the fetched data."""
        if data is None or data.empty:
            return False
        
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_columns):
            return False
        
        # Check for reasonable values
        if (data[['open', 'high', 'low', 'close']] <= 0).any().any():
            return False
        
        # Check high >= low
        if (data['high'] < data['low']).any():
            return False
        
        return True