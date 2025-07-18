"""
Data fetching module for retrieving market data from Alpaca API.
"""
import time
import pandas as pd
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import requests
from alpaca.data import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.models import Bar

from bot.config import AlpacaCredentials
from bot.utils import log_error, log_info, log_warning, retry_with_backoff


class DataFetcher:
    """Handles data fetching from Alpaca API."""
    
    def __init__(self, credentials: AlpacaCredentials):
        """
        Initialize the DataFetcher with Alpaca API credentials.
        
        Args:
            credentials: AlpacaCredentials object containing API keys and settings
        """
        self.credentials = credentials
        self.client = CryptoHistoricalDataClient(
            api_key=credentials.api_key,
            secret_key=credentials.secret_key
        )
        self.last_request_time = 0
        self.rate_limit_wait = 0.2  # 200ms minimum between requests
    
    def _respect_rate_limit(self) -> None:
        """
        Ensure we don't exceed API rate limits by adding delay between requests.
        """
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_wait:
            time.sleep(self.rate_limit_wait - elapsed)
        self.last_request_time = time.time()
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0, 
                       exceptions=(requests.exceptions.RequestException, ValueError))
    def fetch_crypto_data(self, symbol: str, timeframe: str = "5Min", 
                         limit: int = 50) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a cryptocurrency.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            timeframe: The timeframe for the data (e.g., "5Min", "1H", "1D")
            limit: Number of data points to retrieve
            
        Returns:
            DataFrame containing OHLCV data
            
        Raises:
            ValueError: If data validation fails
            requests.exceptions.RequestException: If API request fails
        """
        self._respect_rate_limit()
        
        # Parse timeframe string to TimeFrame enum
        tf_mapping = {
            "1Min": TimeFrame.Minute,
            "5Min": TimeFrame.Minute,
            "15Min": TimeFrame.Minute,
            "1H": TimeFrame.Hour,
            "1D": TimeFrame.Day
        }
        
        if timeframe not in tf_mapping:
            raise ValueError(f"Invalid timeframe: {timeframe}. Must be one of {list(tf_mapping.keys())}")
        
        # Calculate start and end times
        end_time = datetime.now()
        start_time = self._calculate_start_time(end_time, timeframe, limit * 2)
        
        log_info(f"Fetching {symbol} data from {start_time} to {end_time}")
        
        # Create the request with appropriate timeframe
        tf = tf_mapping[timeframe]
        
        # Handle special cases for 5Min and 15Min by using 1Min data and resampling
        if timeframe in ["5Min", "15Min"]:
            request_params = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=start_time,
                end=end_time
            )
        else:
            request_params = CryptoBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                start=start_time,
                end=end_time
            )
        
        # Make the request
        try:
            log_info(f"Requesting data for symbol: {symbol}, timeframe: {timeframe}")
            bars = self.client.get_crypto_bars(request_params)
            
            # Debug: Log the response type and content
            log_info(f"Response type: {type(bars)}")
            log_info(f"Response content: {bars}")
            
            # Convert to DataFrame
            # Handle BarSet response format from Alpaca API
            if hasattr(bars, 'data') and isinstance(bars.data, dict):
                # BarSet format: bars.data is a dictionary with symbol keys
                available_symbols = list(bars.data.keys()) if bars.data else []
                log_info(f"Available symbols in response: {available_symbols}")
                if not bars.data or symbol not in bars.data:
                    log_error(f"No data returned for {symbol}. Available symbols: {available_symbols}")
                    raise ValueError(f"No data returned for {symbol}")
                df = self._bars_to_dataframe(bars.data[symbol])
            elif hasattr(bars, 'keys'):
                # Dictionary-like response
                available_symbols = list(bars.keys()) if bars else []
                log_info(f"Available symbols in response: {available_symbols}")
                if not bars or symbol not in bars:
                    log_error(f"No data returned for {symbol}. Available symbols: {available_symbols}")
                    raise ValueError(f"No data returned for {symbol}")
                df = self._bars_to_dataframe(bars[symbol])
            else:
                # Other formats
                log_info(f"Response attributes: {dir(bars)}")
                if hasattr(bars, 'df'):
                    # Some versions return a dataframe directly
                    df = bars.df
                    if df.empty:
                        raise ValueError(f"No data returned for {symbol}")
                else:
                    log_error(f"No data returned for {symbol}. Response type: {type(bars)}")
                    raise ValueError(f"No data returned for {symbol}")
            
            # Resample data if needed
            if timeframe == "5Min":
                df = self._resample_dataframe(df, '5T')
            elif timeframe == "15Min":
                df = self._resample_dataframe(df, '15T')
            
            # Validate the data
            if not self.validate_data(df):
                raise ValueError("Data validation failed")
                
            # Trim to requested limit
            if len(df) > limit:
                df = df.tail(limit)
                
            return df
            
        except Exception as e:
            log_error(f"Error fetching data for {symbol}: {str(e)}")
            raise
    
    def _calculate_start_time(self, end_time: datetime, timeframe: str, 
                             num_bars: int) -> datetime:
        """
        Calculate the start time based on the timeframe and number of bars.
        
        Args:
            end_time: The end time for the data request
            timeframe: The timeframe string
            num_bars: Number of bars to calculate
            
        Returns:
            datetime: The calculated start time
        """
        if timeframe == "1Min":
            return end_time - timedelta(minutes=num_bars)
        elif timeframe == "5Min":
            return end_time - timedelta(minutes=5 * num_bars)
        elif timeframe == "15Min":
            return end_time - timedelta(minutes=15 * num_bars)
        elif timeframe == "1H":
            return end_time - timedelta(hours=num_bars)
        elif timeframe == "1D":
            return end_time - timedelta(days=num_bars)
        else:
            # Default to 1 day
            return end_time - timedelta(days=1)
    
    def _bars_to_dataframe(self, bars: List[Bar]) -> pd.DataFrame:
        """
        Convert a list of Bar objects to a pandas DataFrame.
        
        Args:
            bars: List of Bar objects from Alpaca API
            
        Returns:
            DataFrame with OHLCV data
        """
        data = []
        for bar in bars:
            # Handle different timestamp formats
            timestamp = bar.timestamp
            if hasattr(timestamp, 'to_pydatetime'):
                timestamp = timestamp.to_pydatetime()
            elif isinstance(timestamp, tuple):
                # Handle tuple format - convert to datetime
                from datetime import datetime
                timestamp = datetime(*timestamp[:6])  # year, month, day, hour, minute, second
            
            data.append({
                'timestamp': timestamp,
                'open': float(bar.open),
                'high': float(bar.high),
                'low': float(bar.low),
                'close': float(bar.close),
                'volume': float(bar.volume) if bar.volume else 0.0
            })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
        
        return df
        
    def _resample_dataframe(self, df: pd.DataFrame, rule: str) -> pd.DataFrame:
        """
        Resample a DataFrame to a different timeframe.
        
        Args:
            df: DataFrame to resample
            rule: Pandas resampling rule (e.g., '5T' for 5 minutes)
            
        Returns:
            Resampled DataFrame
        """
        if df.empty:
            return df
            
        # Make sure the index is a DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            log_warning("DataFrame index is not a DatetimeIndex, cannot resample")
            return df
            
        # Resample the data
        resampled = df.resample(rule).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        })
        
        # Drop rows with NaN values
        resampled.dropna(inplace=True)
        
        return resampled
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_latest_price(self, symbol: str) -> float:
        """
        Get the latest price for a cryptocurrency.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            float: The latest price
            
        Raises:
            ValueError: If unable to get the latest price
        """
        self._respect_rate_limit()
        
        try:
            # Get the most recent bar
            df = self.fetch_crypto_data(symbol, timeframe="1Min", limit=1)
            
            if df.empty:
                raise ValueError(f"No recent price data available for {symbol}")
                
            return df['close'].iloc[-1]
            
        except Exception as e:
            log_error(f"Error getting latest price for {symbol}: {str(e)}")
            raise ValueError(f"Failed to get latest price for {symbol}: {str(e)}")
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate the fetched data for quality and completeness.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            bool: True if data is valid, False otherwise
        """
        # Check if DataFrame is empty
        if data.empty:
            log_warning("Empty DataFrame received")
            return False
        
        # Check for minimum number of rows (be more lenient for health checks)
        if len(data) < 1:
            log_warning(f"No data points received: {len(data)}")
            return False
        elif len(data) < 2:
            log_warning(f"Limited data points: {len(data)} (this may be normal for recent data)")
            # Don't fail validation for this, just warn
        
        # Check for required columns
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            log_warning(f"Missing columns: {missing_columns}")
            return False
        
        # Check for NaN values in critical columns
        nan_counts = data[required_columns].isna().sum()
        if nan_counts.sum() > 0:
            log_warning(f"NaN values found: {nan_counts}")
            return False
        
        # Check for logical consistency in OHLC values
        invalid_rows = (
            (data['high'] < data['low']) | 
            (data['high'] < data['open']) | 
            (data['high'] < data['close']) |
            (data['low'] > data['open']) | 
            (data['low'] > data['close'])
        )
        
        if invalid_rows.any():
            log_warning(f"Found {invalid_rows.sum()} rows with invalid OHLC relationships")
            return False
        
        # Check for negative prices
        if (data[['open', 'high', 'low', 'close']] < 0).any().any():
            log_warning("Negative prices found")
            return False
        
        # Check for negative volume
        if (data['volume'] < 0).any():
            log_warning("Negative volume found")
            return False
        
        # Check for stale data (if the latest timestamp is too old)
        try:
            latest_timestamp = data.index.max()
            if hasattr(latest_timestamp, 'to_pydatetime'):
                latest_dt = latest_timestamp.to_pydatetime()
            else:
                latest_dt = latest_timestamp
            
            time_diff = datetime.now() - latest_dt
            if time_diff > timedelta(hours=1):
                log_warning(f"Data may be stale. Latest timestamp: {latest_timestamp}, "
                           f"Time difference: {time_diff}")
                # We don't fail validation for this, just warn
        except Exception as e:
            log_warning(f"Could not check data staleness: {str(e)}")
            # Continue without failing validation
        
        return True
    
    def _fetch_fallback_data(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """
        Fetch data from a free crypto API as fallback when Alpaca fails.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            timeframe: The timeframe for the data
            limit: Number of data points to retrieve
            
        Returns:
            DataFrame containing OHLCV data
        """
        log_info(f"Using CoinGecko API as fallback for {symbol}")
        
        # Convert symbol format (BTC/USD -> bitcoin)
        symbol_mapping = {
            "BTC/USD": "bitcoin",
            "ETH/USD": "ethereum",
            "SOL/USD": "solana",
            "ADA/USD": "cardano",
            "DOT/USD": "polkadot"
        }
        
        coin_id = symbol_mapping.get(symbol, "bitcoin")
        
        # Calculate days needed based on timeframe and limit
        if timeframe == "1Min":
            days = max(1, limit // (24 * 60))
        elif timeframe == "5Min":
            days = max(1, limit // (24 * 12))
        elif timeframe == "15Min":
            days = max(1, limit // (24 * 4))
        elif timeframe == "1H":
            days = max(1, limit // 24)
        else:  # 1D
            days = limit
            
        days = min(days, 90)  # CoinGecko free API limit
        
        # Fetch data from CoinGecko
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {
            "vs_currency": "usd",
            "days": days,
            "interval": "hourly" if timeframe in ["1H", "1D"] else "minutely"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Extract price data
            prices = data.get("prices", [])
            volumes = data.get("total_volumes", [])
            
            if not prices:
                raise ValueError("No price data received from CoinGecko")
            
            # Convert to DataFrame
            df_data = []
            for i, (timestamp_ms, price) in enumerate(prices):
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                volume = volumes[i][1] if i < len(volumes) else 1000000  # Default volume
                
                # Generate OHLC from price (simplified)
                price_variation = price * 0.001  # 0.1% variation
                df_data.append({
                    'timestamp': timestamp,
                    'open': price - price_variation,
                    'high': price + price_variation,
                    'low': price - price_variation,
                    'close': price,
                    'volume': volume
                })
            
            df = pd.DataFrame(df_data)
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            
            # Resample if needed
            if timeframe == "5Min":
                df = self._resample_dataframe(df, '5T')
            elif timeframe == "15Min":
                df = self._resample_dataframe(df, '15T')
            
            # Trim to requested limit
            if len(df) > limit:
                df = df.tail(limit)
            
            log_info(f"Successfully fetched {len(df)} data points from CoinGecko for {symbol}")
            return df
            
        except Exception as e:
            log_error(f"CoinGecko API failed: {str(e)}")
            raise
    
    def handle_api_errors(self, error: Exception) -> bool:
        """
        Handle API errors with appropriate strategies.
        
        Args:
            error: The exception that occurred
            
        Returns:
            bool: True if error was handled, False otherwise
        """
        error_str = str(error).lower()
        
        # Handle rate limiting errors
        if "rate limit" in error_str or "429" in error_str:
            log_warning("Rate limit hit, backing off")
            time.sleep(5)  # Wait 5 seconds before retrying
            return True
            
        # Handle authentication errors
        if "auth" in error_str or "401" in error_str or "403" in error_str:
            log_error("Authentication error with Alpaca API", error)
            return False  # Can't recover from auth errors
            
        # Handle network errors
        if isinstance(error, requests.exceptions.ConnectionError):
            log_warning("Network connection error, will retry")
            return True
            
        # Handle timeout errors
        if isinstance(error, requests.exceptions.Timeout):
            log_warning("Request timed out, will retry")
            return True
            
        # Handle general API errors
        log_warning(f"API error: {str(error)}, will retry")
        return True