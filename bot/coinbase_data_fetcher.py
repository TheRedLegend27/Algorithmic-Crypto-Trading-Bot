"""
Coinbase market data fetcher with crypto data support.
Handles fetching OHLCV data, latest prices, and 24h stats from Coinbase Advanced Trade API.
Includes WebSocket integration for real-time market data.
"""
import time
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import requests

from bot.coinbase_client import CoinbaseClient, CoinbaseCredentials
from bot.coinbase_websocket import CoinbaseWebSocketManager
from bot.utils import log_error, log_info, log_warning, retry_with_backoff


class CoinbaseDataFetcher:
    """
    Handles market data fetching from Coinbase Advanced Trade API.
    Provides crypto-specific data validation and fallback mechanisms.
    """
    
    def __init__(self, credentials: CoinbaseCredentials):
        """
        Initialize the CoinbaseDataFetcher with API credentials.
        
        Args:
            credentials: CoinbaseCredentials object containing API keys and settings
        """
        self.credentials = credentials
        self.client = CoinbaseClient(credentials)
        self.last_request_time = 0
        self.rate_limit_wait = 0.1  # 100ms minimum between requests for public endpoints
        
        # WebSocket manager for real-time data
        self.ws_manager = CoinbaseWebSocketManager(credentials, self)
        self.websocket_enabled = True
        self.subscribed_products = set()
        
        # Cache for product information
        self._products_cache = {}
        self._cache_expiry = 0
        self._cache_ttl = 300  # 5 minutes cache TTL
    
    def _respect_rate_limit(self) -> None:
        """
        Ensure we don't exceed API rate limits by adding delay between requests.
        """
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_wait:
            time.sleep(self.rate_limit_wait - elapsed)
        self.last_request_time = time.time()
    
    def _get_products_cache(self) -> Dict[str, Dict]:
        """
        Get cached product information or fetch if expired.
        
        Returns:
            Dictionary mapping product IDs to product info
        """
        current_time = time.time()
        if current_time > self._cache_expiry or not self._products_cache:
            try:
                products = self.client.get_products()
                self._products_cache = {p['id']: p for p in products}
                self._cache_expiry = current_time + self._cache_ttl
                log_info(f"Cached {len(self._products_cache)} products")
            except Exception as e:
                log_warning(f"Failed to update products cache: {str(e)}")
                # Use existing cache if available
        
        return self._products_cache
    
    def _validate_product_id(self, product_id: str) -> bool:
        """
        Validate that a product ID exists on Coinbase.
        
        Args:
            product_id: Product ID to validate (e.g., 'BTC-USD')
            
        Returns:
            True if product exists, False otherwise
        """
        products = self._get_products_cache()
        return product_id in products
    
    def _convert_symbol_format(self, symbol: str) -> str:
        """
        Convert symbol from various formats to Coinbase product ID format.
        
        Args:
            symbol: Symbol in various formats (BTC/USD, BTCUSD, BTC-USD)
            
        Returns:
            Coinbase product ID format (BTC-USD)
        """
        # Handle different symbol formats
        if '/' in symbol:
            # BTC/USD -> BTC-USD
            return symbol.replace('/', '-')
        elif '-' in symbol:
            # Already in correct format
            return symbol
        else:
            # BTCUSD -> BTC-USD (assume USD as quote currency)
            if symbol.endswith('USD'):
                base = symbol[:-3]
                return f"{base}-USD"
            elif symbol.endswith('USDT'):
                base = symbol[:-4]
                return f"{base}-USDT"
            else:
                # Default to USD
                return f"{symbol}-USD"
    
    def _granularity_to_seconds(self, timeframe: str) -> int:
        """
        Convert timeframe string to granularity in seconds for Coinbase API.
        
        Args:
            timeframe: Timeframe string (1Min, 5Min, 15Min, 1H, 1D)
            
        Returns:
            Granularity in seconds
        """
        mapping = {
            "1Min": 60,
            "5Min": 300,
            "15Min": 900,
            "1H": 3600,
            "1D": 86400
        }
        return mapping.get(timeframe, 300)  # Default to 5 minutes
    
    def _calculate_time_range(self, timeframe: str, limit: int) -> tuple[str, str]:
        """
        Calculate start and end times for historical data request.
        
        Args:
            timeframe: Timeframe string
            limit: Number of data points requested
            
        Returns:
            Tuple of (start_time, end_time) in ISO format
        """
        end_time = datetime.utcnow()
        
        # Calculate duration based on timeframe and limit
        if timeframe == "1Min":
            duration = timedelta(minutes=limit)
        elif timeframe == "5Min":
            duration = timedelta(minutes=5 * limit)
        elif timeframe == "15Min":
            duration = timedelta(minutes=15 * limit)
        elif timeframe == "1H":
            duration = timedelta(hours=limit)
        elif timeframe == "1D":
            duration = timedelta(days=limit)
        else:
            duration = timedelta(hours=limit)  # Default
        
        start_time = end_time - duration
        
        # Format as ISO strings
        start_iso = start_time.isoformat() + 'Z'
        end_iso = end_time.isoformat() + 'Z'
        
        return start_iso, end_iso
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0,
                       exceptions=(requests.exceptions.RequestException, ValueError))
    def fetch_crypto_ohlcv(self, symbol: str, timeframe: str = "5Min", 
                          limit: int = 50) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a cryptocurrency.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD", "BTC-USD")
            timeframe: The timeframe for the data (1Min, 5Min, 15Min, 1H, 1D)
            limit: Number of data points to retrieve
            
        Returns:
            DataFrame containing OHLCV data with timestamp index
            
        Raises:
            ValueError: If data validation fails or symbol is invalid
            requests.exceptions.RequestException: If API request fails
        """
        self._respect_rate_limit()
        
        # Convert symbol to Coinbase format
        product_id = self._convert_symbol_format(symbol)
        
        # Validate product exists
        if not self._validate_product_id(product_id):
            raise ValueError(f"Invalid product ID: {product_id}")
        
        # Get granularity and time range
        granularity = self._granularity_to_seconds(timeframe)
        start_time, end_time = self._calculate_time_range(timeframe, limit)
        
        log_info(f"Fetching {product_id} OHLCV data: {timeframe} from {start_time} to {end_time}")
        
        try:
            # Fetch candle data from Coinbase
            candles = self.client.get_product_candles(
                product_id=product_id,
                start=start_time,
                end=end_time,
                granularity=granularity
            )
            
            if not candles:
                raise ValueError(f"No candle data returned for {product_id}")
            
            # Convert to DataFrame
            df = self._candles_to_dataframe(candles)
            
            # Validate the data
            if not self.validate_crypto_data(df):
                raise ValueError("Crypto data validation failed")
            
            # Sort by timestamp and limit results
            df = df.sort_index()
            if len(df) > limit:
                df = df.tail(limit)
            
            log_info(f"Successfully fetched {len(df)} OHLCV data points for {product_id}")
            return df
            
        except Exception as e:
            log_error(f"Error fetching OHLCV data for {product_id}: {str(e)}")
            # Try fallback data source
            try:
                return self._fetch_fallback_ohlcv(symbol, timeframe, limit)
            except Exception as fallback_error:
                log_error(f"Fallback data fetch also failed: {str(fallback_error)}")
                raise e
    
    def _candles_to_dataframe(self, candles: List[List]) -> pd.DataFrame:
        """
        Convert Coinbase candle data to pandas DataFrame.
        
        Args:
            candles: List of candle arrays from Coinbase API
                    Format: [timestamp, low, high, open, close, volume]
            
        Returns:
            DataFrame with OHLCV data and timestamp index
        """
        data = []
        for candle in candles:
            if len(candle) >= 6:
                timestamp = datetime.fromtimestamp(candle[0])
                data.append({
                    'timestamp': timestamp,
                    'open': float(candle[3]),
                    'high': float(candle[2]),
                    'low': float(candle[1]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })
        
        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
        
        return df
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_latest_price(self, symbol: str) -> float:
        """
        Get the latest price for a cryptocurrency.
        Uses WebSocket if available, falls back to REST API.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            Latest price as float
            
        Raises:
            ValueError: If unable to get the latest price
        """
        # Try WebSocket first if enabled and connected
        if self.websocket_enabled and self.ws_manager and self.ws_manager.is_websocket_healthy():
            product_id = self._convert_symbol_format(symbol)
            ws_price = self.ws_manager.get_real_time_price(product_id)
            if ws_price is not None:
                log_info(f"Latest price from WebSocket for {product_id}: ${ws_price}")
                return ws_price
        
        # Fallback to REST API
        self._respect_rate_limit()
        
        # Convert symbol to Coinbase format
        product_id = self._convert_symbol_format(symbol)
        
        # Validate product exists
        if not self._validate_product_id(product_id):
            raise ValueError(f"Invalid product ID: {product_id}")
        
        try:
            # Get ticker data
            ticker = self.client.get_product_ticker(product_id)
            
            if 'price' not in ticker:
                raise ValueError(f"No price data in ticker response for {product_id}")
            
            price = float(ticker['price'])
            log_info(f"Latest price from REST API for {product_id}: ${price}")
            return price
            
        except Exception as e:
            log_error(f"Error getting latest price for {product_id}: {str(e)}")
            # Try fallback
            try:
                return self._fetch_fallback_price(symbol)
            except Exception as fallback_error:
                log_error(f"Fallback price fetch also failed: {str(fallback_error)}")
                raise ValueError(f"Failed to get latest price for {symbol}: {str(e)}")
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_24h_stats(self, symbol: str) -> Dict[str, Any]:
        """
        Get 24-hour statistics for a cryptocurrency.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            Dictionary containing 24h stats (open, high, low, volume, etc.)
            
        Raises:
            ValueError: If unable to get 24h stats
        """
        self._respect_rate_limit()
        
        # Convert symbol to Coinbase format
        product_id = self._convert_symbol_format(symbol)
        
        # Validate product exists
        if not self._validate_product_id(product_id):
            raise ValueError(f"Invalid product ID: {product_id}")
        
        try:
            # Get 24h stats
            stats = self.client.get_product_stats(product_id)
            
            # Normalize the response
            normalized_stats = {
                'open': float(stats.get('open', 0)),
                'high': float(stats.get('high', 0)),
                'low': float(stats.get('low', 0)),
                'last': float(stats.get('last', 0)),
                'volume': float(stats.get('volume', 0)),
                'volume_30day': float(stats.get('volume_30day', 0))
            }
            
            log_info(f"24h stats for {product_id}: {normalized_stats}")
            return normalized_stats
            
        except Exception as e:
            log_error(f"Error getting 24h stats for {product_id}: {str(e)}")
            raise ValueError(f"Failed to get 24h stats for {symbol}: {str(e)}")
    
    def get_order_book(self, symbol: str, level: int = 1) -> Dict[str, Any]:
        """
        Get order book data for a cryptocurrency.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            level: Order book level (1, 2, or 3)
            
        Returns:
            Dictionary containing order book data
            
        Raises:
            ValueError: If unable to get order book data
        """
        self._respect_rate_limit()
        
        # Convert symbol to Coinbase format
        product_id = self._convert_symbol_format(symbol)
        
        # Validate product exists
        if not self._validate_product_id(product_id):
            raise ValueError(f"Invalid product ID: {product_id}")
        
        try:
            # Note: This would require implementing order book endpoint in CoinbaseClient
            # For now, we'll use ticker data as a simplified order book
            ticker = self.client.get_product_ticker(product_id)
            
            # Simplified order book from ticker
            order_book = {
                'sequence': int(ticker.get('trade_id', 0)),
                'bids': [[ticker.get('bid', '0'), ticker.get('bid_size', '0')]],
                'asks': [[ticker.get('ask', '0'), ticker.get('ask_size', '0')]]
            }
            
            return order_book
            
        except Exception as e:
            log_error(f"Error getting order book for {product_id}: {str(e)}")
            raise ValueError(f"Failed to get order book for {symbol}: {str(e)}")
    
    def validate_crypto_data(self, data: pd.DataFrame) -> bool:
        """
        Validate crypto data for quality and completeness with 24/7 market considerations.
        
        Args:
            data: DataFrame containing OHLCV data
            
        Returns:
            True if data is valid, False otherwise
        """
        # Check if DataFrame is empty
        if data.empty:
            log_warning("Empty DataFrame received")
            return False
        
        # Check for minimum number of rows
        if len(data) < 1:
            log_warning(f"Insufficient data points: {len(data)}")
            return False
        
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
        if (data[['open', 'high', 'low', 'close']] <= 0).any().any():
            log_warning("Non-positive prices found")
            return False
        
        # Check for negative volume
        if (data['volume'] < 0).any():
            log_warning("Negative volume found")
            return False
        
        # Crypto-specific validations for 24/7 markets
        
        # Check for extreme price volatility (more lenient for crypto)
        price_changes = data['close'].pct_change().abs()
        extreme_changes = price_changes > 0.5  # 50% change threshold
        if extreme_changes.any():
            log_warning(f"Extreme price changes detected: {extreme_changes.sum()} instances")
            # Don't fail validation, just warn for crypto volatility
        
        # Check for data gaps (crypto markets are 24/7, so gaps are unusual)
        if len(data) > 1:
            time_diffs = data.index.to_series().diff()
            median_diff = time_diffs.median()
            large_gaps = time_diffs > median_diff * 3  # 3x median gap
            if large_gaps.any():
                log_warning(f"Large time gaps detected: {large_gaps.sum()} instances")
                # Don't fail validation, just warn
        
        # Check for stale data (crypto markets never close)
        try:
            latest_timestamp = data.index.max()
            if hasattr(latest_timestamp, 'to_pydatetime'):
                latest_dt = latest_timestamp.to_pydatetime()
            else:
                latest_dt = latest_timestamp
            
            time_diff = datetime.now() - latest_dt
            if time_diff > timedelta(hours=2):  # More lenient for crypto
                log_warning(f"Data may be stale. Latest timestamp: {latest_timestamp}, "
                           f"Time difference: {time_diff}")
                # Don't fail validation, just warn
        except Exception as e:
            log_warning(f"Could not check data staleness: {str(e)}")
        
        return True
    
    def _fetch_fallback_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """
        Fetch OHLCV data from fallback source (CoinGecko) when Coinbase fails.
        
        Args:
            symbol: The trading pair symbol
            timeframe: The timeframe for the data
            limit: Number of data points to retrieve
            
        Returns:
            DataFrame containing OHLCV data
        """
        log_info(f"Using CoinGecko API as fallback for {symbol} OHLCV data")
        
        # Convert symbol to CoinGecko format
        symbol_mapping = {
            "BTC-USD": "bitcoin",
            "ETH-USD": "ethereum",
            "SOL-USD": "solana",
            "ADA-USD": "cardano",
            "DOT-USD": "polkadot",
            "MATIC-USD": "matic-network",
            "AVAX-USD": "avalanche-2"
        }
        
        # Handle different symbol formats
        normalized_symbol = self._convert_symbol_format(symbol)
        coin_id = symbol_mapping.get(normalized_symbol, "bitcoin")
        
        # Calculate days needed
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
            
            # Extract price and volume data
            prices = data.get("prices", [])
            volumes = data.get("total_volumes", [])
            
            if not prices:
                raise ValueError("No price data received from CoinGecko")
            
            # Convert to DataFrame with OHLC approximation
            df_data = []
            for i, (timestamp_ms, price) in enumerate(prices):
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
                volume = volumes[i][1] if i < len(volumes) else 1000000
                
                # Generate OHLC from price (simplified approximation)
                price_variation = price * 0.002  # 0.2% variation
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
            
            log_info(f"Successfully fetched {len(df)} fallback OHLCV data points for {symbol}")
            return df
            
        except Exception as e:
            log_error(f"CoinGecko fallback failed: {str(e)}")
            raise
    
    def _fetch_fallback_price(self, symbol: str) -> float:
        """
        Fetch latest price from fallback source when Coinbase fails.
        
        Args:
            symbol: The trading pair symbol
            
        Returns:
            Latest price as float
        """
        log_info(f"Using CoinGecko API as fallback for {symbol} price")
        
        # Convert symbol to CoinGecko format
        symbol_mapping = {
            "BTC-USD": "bitcoin",
            "ETH-USD": "ethereum",
            "SOL-USD": "solana",
            "ADA-USD": "cardano",
            "DOT-USD": "polkadot"
        }
        
        normalized_symbol = self._convert_symbol_format(symbol)
        coin_id = symbol_mapping.get(normalized_symbol, "bitcoin")
        
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd"
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if coin_id not in data or 'usd' not in data[coin_id]:
                raise ValueError(f"No price data for {coin_id}")
            
            price = float(data[coin_id]['usd'])
            log_info(f"Fallback price for {symbol}: ${price}")
            return price
            
        except Exception as e:
            log_error(f"CoinGecko price fallback failed: {str(e)}")
            raise
    
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
    
    def subscribe_to_websocket(self, symbols: List[str]) -> bool:
        """
        Subscribe to WebSocket feeds for real-time market data.
        
        Args:
            symbols: List of symbols to subscribe to (e.g., ['BTC-USD', 'ETH-USD'])
            
        Returns:
            True if subscription successful, False otherwise
        """
        if not self.websocket_enabled:
            log_info("WebSocket is disabled, skipping subscription")
            return False
        
        try:
            # Convert symbols to Coinbase format
            product_ids = [self._convert_symbol_format(symbol) for symbol in symbols]
            
            # Validate all product IDs
            for product_id in product_ids:
                if not self._validate_product_id(product_id):
                    log_warning(f"Invalid product ID: {product_id}, skipping")
                    product_ids.remove(product_id)
            
            if not product_ids:
                log_error("No valid product IDs to subscribe to")
                return False
            
            # Start WebSocket manager
            if self.ws_manager.start(product_ids):
                self.subscribed_products.update(product_ids)
                log_info(f"Successfully subscribed to WebSocket feeds for: {product_ids}")
                return True
            else:
                log_error("Failed to start WebSocket manager")
                return False
                
        except Exception as e:
            log_error(f"Error subscribing to WebSocket: {str(e)}")
            return False
    
    def unsubscribe_from_websocket(self) -> None:
        """Unsubscribe from all WebSocket feeds and stop the manager."""
        try:
            if self.ws_manager:
                self.ws_manager.stop()
                self.subscribed_products.clear()
                log_info("Unsubscribed from all WebSocket feeds")
        except Exception as e:
            log_error(f"Error unsubscribing from WebSocket: {str(e)}")
    
    def get_real_time_price(self, symbol: str) -> Optional[float]:
        """
        Get real-time price using WebSocket if available, fallback to REST API.
        
        Args:
            symbol: The trading pair symbol (e.g., "BTC/USD")
            
        Returns:
            Real-time price or None if not available
        """
        try:
            # Convert symbol to Coinbase format
            product_id = self._convert_symbol_format(symbol)
            
            # Try WebSocket first
            if self.websocket_enabled and self.ws_manager:
                price = self.ws_manager.get_real_time_price(product_id)
                if price is not None:
                    return price
            
            # Fallback to REST API
            log_info(f"Using REST API fallback for {symbol} price")
            return self.get_latest_price(symbol)
            
        except Exception as e:
            log_error(f"Error getting real-time price for {symbol}: {str(e)}")
            return None
    
    def is_websocket_connected(self) -> bool:
        """
        Check if WebSocket connection is active and healthy.
        
        Returns:
            True if WebSocket is connected, False otherwise
        """
        if not self.websocket_enabled or not self.ws_manager:
            return False
        
        return self.ws_manager.is_websocket_healthy()
    
    def get_websocket_status(self) -> Dict[str, Any]:
        """
        Get detailed WebSocket connection status.
        
        Returns:
            Dictionary containing WebSocket status information
        """
        if not self.websocket_enabled or not self.ws_manager:
            return {
                "enabled": False,
                "connected": False,
                "subscribed_products": [],
                "fallback_active": True
            }
        
        status = self.ws_manager.get_connection_status()
        status["enabled"] = self.websocket_enabled
        status["subscribed_products"] = list(self.subscribed_products)
        
        return status
    
    def enable_websocket(self) -> None:
        """Enable WebSocket functionality."""
        self.websocket_enabled = True
        log_info("WebSocket functionality enabled")
    
    def disable_websocket(self) -> None:
        """Disable WebSocket functionality and stop connections."""
        self.websocket_enabled = False
        self.unsubscribe_from_websocket()
        log_info("WebSocket functionality disabled")
    
    def handle_api_errors(self, error: Exception) -> bool:
        """
        Handle API errors with appropriate recovery strategies.
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if error was handled and retry is recommended, False otherwise
        """
        error_str = str(error).lower()
        
        # Handle rate limiting errors
        if "rate limit" in error_str or "429" in error_str:
            log_warning("Rate limit hit, backing off")
            time.sleep(5)
            return True
        
        # Handle authentication errors
        if "auth" in error_str or "401" in error_str or "403" in error_str:
            log_error("Authentication error with Coinbase API", error)
            return False  # Can't recover from auth errors
        
        # Handle network errors
        if isinstance(error, requests.exceptions.ConnectionError):
            log_warning("Network connection error, will retry")
            return True
        
        # Handle timeout errors
        if isinstance(error, requests.exceptions.Timeout):
            log_warning("Request timed out, will retry")
            return True
        
        # Handle invalid product errors
        if "invalid" in error_str and "product" in error_str:
            log_error("Invalid product ID", error)
            return False  # Can't recover from invalid product
        
        # Handle general API errors
        log_warning(f"API error: {str(error)}, will retry")
        return True