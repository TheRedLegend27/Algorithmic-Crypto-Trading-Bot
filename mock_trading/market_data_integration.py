"""
Market Data Integration for Mock Trading Environment

This module integrates existing market data sources with the mock trading environment,
providing real-time price updates, market data validation, fallback mechanisms,
and market hours handling for realistic simulation.
"""
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import json
from pathlib import Path

from bot.data_fetcher import DataFetcher
from bot.yahoo_data_fetcher import YahooDataFetcher
from bot.config import AlpacaCredentials
from bot.utils import log_info, log_error, log_warning, retry_with_backoff
from .mock_config import MockTradingConfig, MarketConfig
from .mock_models import validate_numeric


class MarketDataSource(Enum):
    """Enum for different market data sources."""
    ALPACA = "ALPACA"
    YAHOO = "YAHOO"
    CACHED = "CACHED"
    FALLBACK = "FALLBACK"


class MarketStatus(Enum):
    """Enum for market status."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PRE_MARKET = "PRE_MARKET"
    AFTER_HOURS = "AFTER_HOURS"
    HOLIDAY = "HOLIDAY"


@dataclass
class MarketDataPoint:
    """Single market data point with metadata."""
    symbol: str
    price: float
    bid: float
    ask: float
    volume: float
    timestamp: datetime
    source: MarketDataSource
    volatility: float = 0.0
    spread: float = 0.0
    quality_score: float = 1.0  # 0.0 to 1.0, higher is better
    
    def __post_init__(self):
        """Calculate derived fields after initialization."""
        if self.bid > 0 and self.ask > 0:
            self.spread = (self.ask - self.bid) / self.price if self.price > 0 else 0.0
        
        # Validate data quality
        if not self._validate_data():
            self.quality_score = 0.0
    
    def _validate_data(self) -> bool:
        """Validate market data point."""
        if self.price <= 0:
            return False
        if self.bid < 0 or self.ask < 0:
            return False
        if self.bid > 0 and self.ask > 0 and self.bid >= self.ask:
            return False
        if self.volume < 0:
            return False
        return True
    
    def is_stale(self, max_age_minutes: int = 5) -> bool:
        """Check if data point is stale."""
        age = datetime.now() - self.timestamp
        return age.total_seconds() > (max_age_minutes * 60)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source.value,
            "volatility": self.volatility,
            "spread": self.spread,
            "quality_score": self.quality_score
        }


@dataclass
class MarketHours:
    """Market hours configuration."""
    market_open: str = "09:30"  # EST
    market_close: str = "16:00"  # EST
    pre_market_start: str = "04:00"  # EST
    after_hours_end: str = "20:00"  # EST
    timezone_name: str = "US/Eastern"
    
    def get_market_status(self, dt: Optional[datetime] = None) -> MarketStatus:
        """Get current market status."""
        if dt is None:
            dt = datetime.now(timezone.utc)
        
        # Convert to market timezone
        market_tz = timezone.utc  # Simplified for now
        market_time = dt.astimezone(market_tz)
        
        # Check if it's a weekend
        if market_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return MarketStatus.CLOSED
        
        # Get time components
        current_time = market_time.strftime("%H:%M")
        
        # Check market status
        if self.market_open <= current_time < self.market_close:
            return MarketStatus.OPEN
        elif self.pre_market_start <= current_time < self.market_open:
            return MarketStatus.PRE_MARKET
        elif self.market_close <= current_time < self.after_hours_end:
            return MarketStatus.AFTER_HOURS
        else:
            return MarketStatus.CLOSED
    
    def is_trading_allowed(self, extended_hours: bool = False) -> bool:
        """Check if trading is allowed at current time."""
        status = self.get_market_status()
        
        if status == MarketStatus.OPEN:
            return True
        elif extended_hours and status in [MarketStatus.PRE_MARKET, MarketStatus.AFTER_HOURS]:
            return True
        else:
            return False


class MarketDataCache:
    """Cache for market data with TTL and persistence."""
    
    def __init__(self, cache_dir: str = "mock_trading/cache", max_age_minutes: int = 5):
        """
        Initialize market data cache.
        
        Args:
            cache_dir: Directory for cache files
            max_age_minutes: Maximum age for cached data in minutes
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_minutes = max_age_minutes
        self.memory_cache: Dict[str, MarketDataPoint] = {}
        self.cache_lock = threading.RLock()
    
    def get(self, symbol: str) -> Optional[MarketDataPoint]:
        """Get cached market data for symbol."""
        with self.cache_lock:
            # Check memory cache first
            if symbol in self.memory_cache:
                data_point = self.memory_cache[symbol]
                if not data_point.is_stale(self.max_age_minutes):
                    return data_point
                else:
                    # Remove stale data
                    del self.memory_cache[symbol]
            
            # Check disk cache
            cache_file = self.cache_dir / f"{symbol.replace('/', '_')}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                    
                    # Reconstruct MarketDataPoint
                    data_point = MarketDataPoint(
                        symbol=data["symbol"],
                        price=data["price"],
                        bid=data["bid"],
                        ask=data["ask"],
                        volume=data["volume"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        source=MarketDataSource(data["source"]),
                        volatility=data.get("volatility", 0.0),
                        spread=data.get("spread", 0.0),
                        quality_score=data.get("quality_score", 1.0)
                    )
                    
                    if not data_point.is_stale(self.max_age_minutes):
                        self.memory_cache[symbol] = data_point
                        return data_point
                    else:
                        # Remove stale cache file
                        cache_file.unlink()
                
                except Exception as e:
                    log_warning(f"Error reading cache file for {symbol}: {e}")
                    if cache_file.exists():
                        cache_file.unlink()
        
        return None
    
    def get_stale_data(self, symbol: str) -> Optional[MarketDataPoint]:
        """Get cached data even if stale, for emergency fallback."""
        with self.cache_lock:
            # Check memory cache first (including stale data)
            if symbol in self.memory_cache:
                return self.memory_cache[symbol]
            
            # Check disk cache (including stale data)
            cache_file = self.cache_dir / f"{symbol.replace('/', '_')}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        data = json.load(f)
                    
                    # Reconstruct MarketDataPoint
                    data_point = MarketDataPoint(
                        symbol=data["symbol"],
                        price=data["price"],
                        bid=data["bid"],
                        ask=data["ask"],
                        volume=data["volume"],
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        source=MarketDataSource(data["source"]),
                        volatility=data.get("volatility", 0.0),
                        spread=data.get("spread", 0.0),
                        quality_score=data.get("quality_score", 1.0)
                    )
                    
                    return data_point
                
                except Exception as e:
                    log_warning(f"Error reading stale cache file for {symbol}: {e}")
        
        return None
    
    def set(self, symbol: str, data_point: MarketDataPoint) -> None:
        """Cache market data for symbol."""
        with self.cache_lock:
            # Update memory cache
            self.memory_cache[symbol] = data_point
            
            # Update disk cache
            cache_file = self.cache_dir / f"{symbol.replace('/', '_')}.json"
            try:
                with open(cache_file, 'w') as f:
                    json.dump(data_point.to_dict(), f, indent=2)
            except Exception as e:
                log_warning(f"Error writing cache file for {symbol}: {e}")
    
    def clear_stale(self) -> None:
        """Clear stale data from cache."""
        with self.cache_lock:
            # Clear memory cache
            stale_symbols = [
                symbol for symbol, data_point in self.memory_cache.items()
                if data_point.is_stale(self.max_age_minutes)
            ]
            for symbol in stale_symbols:
                del self.memory_cache[symbol]
            
            # Clear disk cache
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    if cache_file.stat().st_mtime < (time.time() - self.max_age_minutes * 60):
                        cache_file.unlink()
                except Exception as e:
                    log_warning(f"Error clearing cache file {cache_file}: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.cache_lock:
            disk_files = list(self.cache_dir.glob("*.json"))
            return {
                "memory_entries": len(self.memory_cache),
                "disk_files": len(disk_files),
                "cache_dir": str(self.cache_dir),
                "max_age_minutes": self.max_age_minutes
            }


class MarketDataValidator:
    """Validates market data quality and consistency."""
    
    def __init__(self, config: MarketConfig):
        """Initialize validator with market configuration."""
        self.config = config
        self.price_history: Dict[str, List[Tuple[datetime, float]]] = {}
        self.validation_lock = threading.RLock()
    
    def validate_data_point(self, data_point: MarketDataPoint) -> Tuple[bool, List[str]]:
        """
        Validate a single market data point.
        
        Args:
            data_point: Market data point to validate
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Basic validation
        if data_point.price <= 0:
            issues.append("Price must be positive")
        
        if data_point.bid < 0 or data_point.ask < 0:
            issues.append("Bid and ask prices cannot be negative")
        
        if data_point.bid > 0 and data_point.ask > 0 and data_point.bid >= data_point.ask:
            issues.append("Bid price must be less than ask price")
        
        if data_point.volume < 0:
            issues.append("Volume cannot be negative")
        
        # Spread validation
        if data_point.bid > 0 and data_point.ask > 0:
            spread_pct = (data_point.ask - data_point.bid) / data_point.price
            if spread_pct > 0.1:  # 10% spread seems excessive
                issues.append(f"Spread too wide: {spread_pct*100:.2f}%")
        
        # Price consistency validation
        with self.validation_lock:
            if data_point.symbol in self.price_history:
                recent_prices = self.price_history[data_point.symbol]
                if recent_prices:
                    last_price = recent_prices[-1][1]
                    price_change_pct = abs(data_point.price - last_price) / last_price
                    
                    # Flag extreme price movements (>50% in one update)
                    if price_change_pct > 0.5:
                        issues.append(f"Extreme price movement: {price_change_pct*100:.2f}%")
            
            # Update price history
            if data_point.symbol not in self.price_history:
                self.price_history[data_point.symbol] = []
            
            self.price_history[data_point.symbol].append(
                (data_point.timestamp, data_point.price)
            )
            
            # Keep only recent history (last 100 points)
            if len(self.price_history[data_point.symbol]) > 100:
                self.price_history[data_point.symbol] = self.price_history[data_point.symbol][-100:]
        
        return len(issues) == 0, issues
    
    def calculate_volatility(self, symbol: str, window: int = 20) -> float:
        """Calculate recent volatility for a symbol."""
        with self.validation_lock:
            if symbol not in self.price_history:
                return 0.02  # Default volatility
            
            prices = [price for _, price in self.price_history[symbol][-window:]]
            if len(prices) < 2:
                return 0.02
            
            # Calculate returns
            returns = []
            for i in range(1, len(prices)):
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
            
            if not returns:
                return 0.02
            
            # Calculate standard deviation
            mean_return = sum(returns) / len(returns)
            variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
            volatility = variance ** 0.5
            
            return max(0.001, min(1.0, volatility))  # Clamp between 0.1% and 100%


class MarketDataIntegration:
    """
    Main market data integration class that coordinates multiple data sources,
    provides real-time updates, and handles fallback mechanisms.
    """
    
    def __init__(self, config: MockTradingConfig, credentials: Optional[AlpacaCredentials] = None):
        """
        Initialize market data integration.
        
        Args:
            config: Mock trading configuration
            credentials: Optional Alpaca credentials for primary data source
        """
        self.config = config
        self.market_config = config.market
        
        # Initialize data sources
        self.primary_fetcher = None
        if credentials:
            try:
                self.primary_fetcher = DataFetcher(credentials)
                log_info("Alpaca data fetcher initialized as primary source")
            except Exception as e:
                log_warning(f"Failed to initialize Alpaca data fetcher: {e}")
        
        self.fallback_fetcher = YahooDataFetcher()
        log_info("Yahoo Finance data fetcher initialized as fallback source")
        
        # Initialize components
        self.cache = MarketDataCache()
        self.validator = MarketDataValidator(self.market_config)
        self.market_hours = MarketHours()
        
        # Real-time data management
        self.subscribers: Dict[str, List[Callable[[MarketDataPoint], None]]] = {}
        self.update_thread: Optional[threading.Thread] = None
        self.update_queue: queue.Queue = queue.Queue()
        self.running = False
        self.update_interval = 30  # seconds
        self.subscriber_lock = threading.RLock()
        
        # Tracked symbols
        self.tracked_symbols: set = set()
        
        log_info("Market data integration initialized")
    
    def start_real_time_updates(self) -> None:
        """Start real-time market data updates."""
        if self.running:
            log_warning("Real-time updates already running")
            return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        log_info("Real-time market data updates started")
    
    def stop_real_time_updates(self) -> None:
        """Stop real-time market data updates."""
        if not self.running:
            return
        
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        log_info("Real-time market data updates stopped")
    
    def subscribe_to_symbol(self, symbol: str, callback: Callable[[MarketDataPoint], None]) -> None:
        """
        Subscribe to real-time updates for a symbol.
        
        Args:
            symbol: Trading symbol to subscribe to
            callback: Function to call when new data is available
        """
        with self.subscriber_lock:
            if symbol not in self.subscribers:
                self.subscribers[symbol] = []
            
            self.subscribers[symbol].append(callback)
            self.tracked_symbols.add(symbol)
            
            log_info(f"Subscribed to real-time updates for {symbol}")
    
    def unsubscribe_from_symbol(self, symbol: str, callback: Callable[[MarketDataPoint], None]) -> None:
        """
        Unsubscribe from real-time updates for a symbol.
        
        Args:
            symbol: Trading symbol to unsubscribe from
            callback: Callback function to remove
        """
        with self.subscriber_lock:
            if symbol in self.subscribers and callback in self.subscribers[symbol]:
                self.subscribers[symbol].remove(callback)
                
                if not self.subscribers[symbol]:
                    del self.subscribers[symbol]
                    self.tracked_symbols.discard(symbol)
                
                log_info(f"Unsubscribed from real-time updates for {symbol}")
    
    @retry_with_backoff(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
    def get_current_price(self, symbol: str, use_cache: bool = True) -> Optional[MarketDataPoint]:
        """
        Get current market data for a symbol.
        
        Args:
            symbol: Trading symbol
            use_cache: Whether to use cached data if available
            
        Returns:
            MarketDataPoint if successful, None otherwise
        """
        # Check cache first if requested (but don't remove stale data yet)
        if use_cache:
            with self.cache.cache_lock:
                if symbol in self.cache.memory_cache:
                    cached_data = self.cache.memory_cache[symbol]
                    if not cached_data.is_stale(self.cache.max_age_minutes) and cached_data.quality_score > 0.5:
                        return cached_data
        
        # Try primary data source
        data_point = self._fetch_from_primary(symbol)
        if data_point:
            return self._process_and_cache_data(data_point)
        
        # Try fallback data source
        data_point = self._fetch_from_fallback(symbol)
        if data_point:
            return self._process_and_cache_data(data_point)
        
        # Return cached data even if stale as last resort
        if use_cache:
            cached_data = self.cache.get_stale_data(symbol)
            if cached_data:
                log_warning(f"Using stale cached data for {symbol}")
                return cached_data
        
        log_error(f"Failed to get current price for {symbol} from all sources")
        return None
    
    def get_historical_data(self, symbol: str, timeframe: str = "5Min", 
                          limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Get historical market data for a symbol.
        
        Args:
            symbol: Trading symbol
            timeframe: Data timeframe
            limit: Number of data points
            
        Returns:
            DataFrame with historical data if successful, None otherwise
        """
        # Try primary data source
        try:
            if self.primary_fetcher:
                data = self.primary_fetcher.fetch_crypto_data(symbol, timeframe, limit)
                if data is not None and not data.empty:
                    log_info(f"Retrieved {len(data)} historical data points for {symbol} from Alpaca")
                    return data
        except Exception as e:
            log_warning(f"Primary data source failed for historical data: {e}")
        
        # Try fallback data source
        try:
            data = self.fallback_fetcher.fetch_crypto_data(symbol, timeframe, limit)
            if data is not None and not data.empty:
                log_info(f"Retrieved {len(data)} historical data points for {symbol} from Yahoo Finance")
                return data
        except Exception as e:
            log_warning(f"Fallback data source failed for historical data: {e}")
        
        log_error(f"Failed to get historical data for {symbol} from all sources")
        return None
    
    def validate_market_hours(self, symbol: str) -> bool:
        """
        Validate if trading is allowed for the symbol at current time.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            bool: True if trading is allowed
        """
        if not self.market_config.market_hours_enforcement:
            return True
        
        market_status = self.market_hours.get_market_status()
        
        if market_status == MarketStatus.OPEN:
            return True
        elif self.market_config.extended_hours_trading and market_status in [
            MarketStatus.PRE_MARKET, MarketStatus.AFTER_HOURS
        ]:
            return True
        else:
            log_info(f"Trading not allowed for {symbol} - market status: {market_status.value}")
            return False
    
    def get_market_status(self) -> MarketStatus:
        """Get current market status."""
        return self.market_hours.get_market_status()
    
    def _fetch_from_primary(self, symbol: str) -> Optional[MarketDataPoint]:
        """Fetch data from primary source (Alpaca)."""
        if not self.primary_fetcher:
            return None
        
        try:
            price = self.primary_fetcher.get_latest_price(symbol)
            if price and price > 0:
                # Create market data point with estimated bid/ask
                spread = price * 0.001  # 0.1% spread estimate
                bid = price - spread / 2
                ask = price + spread / 2
                
                data_point = MarketDataPoint(
                    symbol=symbol,
                    price=price,
                    bid=bid,
                    ask=ask,
                    volume=1000000,  # Mock volume
                    timestamp=datetime.now(),
                    source=MarketDataSource.ALPACA,
                    volatility=self.validator.calculate_volatility(symbol)
                )
                
                return data_point
        
        except Exception as e:
            log_warning(f"Primary data source error for {symbol}: {e}")
        
        return None
    
    def _fetch_from_fallback(self, symbol: str) -> Optional[MarketDataPoint]:
        """Fetch data from fallback source (Yahoo Finance)."""
        try:
            price = self.fallback_fetcher.get_current_price(symbol)
            if price and price > 0:
                # Create market data point with estimated bid/ask
                spread = price * 0.002  # 0.2% spread estimate for fallback
                bid = price - spread / 2
                ask = price + spread / 2
                
                data_point = MarketDataPoint(
                    symbol=symbol,
                    price=price,
                    bid=bid,
                    ask=ask,
                    volume=500000,  # Mock volume (lower for fallback)
                    timestamp=datetime.now(),
                    source=MarketDataSource.YAHOO,
                    volatility=self.validator.calculate_volatility(symbol),
                    quality_score=0.8  # Slightly lower quality score for fallback
                )
                
                return data_point
        
        except Exception as e:
            log_warning(f"Fallback data source error for {symbol}: {e}")
        
        return None
    
    def _process_and_cache_data(self, data_point: MarketDataPoint) -> MarketDataPoint:
        """Process and cache market data point."""
        # Validate data
        is_valid, issues = self.validator.validate_data_point(data_point)
        
        if not is_valid:
            log_warning(f"Data validation issues for {data_point.symbol}: {issues}")
            data_point.quality_score *= 0.5  # Reduce quality score
        
        # Update volatility
        data_point.volatility = self.validator.calculate_volatility(data_point.symbol)
        
        # Cache the data
        self.cache.set(data_point.symbol, data_point)
        
        # Notify subscribers
        self._notify_subscribers(data_point)
        
        return data_point
    
    def _notify_subscribers(self, data_point: MarketDataPoint) -> None:
        """Notify subscribers of new market data."""
        with self.subscriber_lock:
            if data_point.symbol in self.subscribers:
                for callback in self.subscribers[data_point.symbol]:
                    try:
                        callback(data_point)
                    except Exception as e:
                        log_error(f"Error in subscriber callback for {data_point.symbol}: {e}")
    
    def _update_loop(self) -> None:
        """Main update loop for real-time data."""
        log_info("Market data update loop started")
        
        while self.running:
            try:
                # Update all tracked symbols
                if self.tracked_symbols:
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        futures = {
                            executor.submit(self.get_current_price, symbol, use_cache=False): symbol
                            for symbol in self.tracked_symbols.copy()
                        }
                        
                        for future in as_completed(futures, timeout=30):
                            symbol = futures[future]
                            try:
                                data_point = future.result()
                                if data_point:
                                    log_info(f"Updated market data for {symbol}: ${data_point.price:.4f}")
                            except Exception as e:
                                log_error(f"Error updating {symbol}: {e}")
                
                # Clean up stale cache entries
                self.cache.clear_stale()
                
                # Wait for next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                log_error(f"Error in market data update loop: {e}")
                time.sleep(5)  # Short delay before retrying
        
        log_info("Market data update loop stopped")
    
    def get_multiple_prices(self, symbols: List[str], use_cache: bool = True) -> Dict[str, Optional[MarketDataPoint]]:
        """
        Get current market data for multiple symbols efficiently.
        
        Args:
            symbols: List of trading symbols
            use_cache: Whether to use cached data if available
            
        Returns:
            Dictionary mapping symbols to their market data points
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        
        # Use thread pool for concurrent fetching
        with ThreadPoolExecutor(max_workers=min(len(symbols), 5)) as executor:
            futures = {
                executor.submit(self.get_current_price, symbol, use_cache): symbol
                for symbol in symbols
            }
            
            for future in as_completed(futures, timeout=30):
                symbol = futures[future]
                try:
                    data_point = future.result()
                    results[symbol] = data_point
                except Exception as e:
                    log_error(f"Error fetching data for {symbol}: {e}")
                    results[symbol] = None
        
        return results
    
    def get_data_quality_report(self) -> Dict[str, Any]:
        """
        Get a report on data quality across all tracked symbols.
        
        Returns:
            Dictionary with data quality metrics
        """
        report = {
            "total_symbols": len(self.tracked_symbols),
            "symbols_with_data": 0,
            "symbols_with_stale_data": 0,
            "symbols_with_low_quality": 0,
            "average_quality_score": 0.0,
            "data_sources_used": {},
            "validation_issues": {}
        }
        
        if not self.tracked_symbols:
            return report
        
        total_quality = 0.0
        symbols_processed = 0
        
        for symbol in self.tracked_symbols:
            cached_data = self.cache.get(symbol)
            if cached_data:
                report["symbols_with_data"] += 1
                total_quality += cached_data.quality_score
                symbols_processed += 1
                
                # Track data sources
                source = cached_data.source.value
                report["data_sources_used"][source] = report["data_sources_used"].get(source, 0) + 1
                
                # Check for stale data
                if cached_data.is_stale(self.cache.max_age_minutes):
                    report["symbols_with_stale_data"] += 1
                
                # Check for low quality
                if cached_data.quality_score < 0.5:
                    report["symbols_with_low_quality"] += 1
                
                # Validate and collect issues
                is_valid, issues = self.validator.validate_data_point(cached_data)
                if issues:
                    report["validation_issues"][symbol] = issues
        
        if symbols_processed > 0:
            report["average_quality_score"] = total_quality / symbols_processed
        
        return report
    
    def get_integration_stats(self) -> Dict[str, Any]:
        """Get integration statistics."""
        cache_stats = self.cache.get_cache_stats()
        quality_report = self.get_data_quality_report()
        
        return {
            "tracked_symbols": len(self.tracked_symbols),
            "subscribers": sum(len(callbacks) for callbacks in self.subscribers.values()),
            "running": self.running,
            "update_interval": self.update_interval,
            "market_status": self.get_market_status().value,
            "cache_stats": cache_stats,
            "primary_source_available": self.primary_fetcher is not None,
            "fallback_source_available": True,
            "data_quality": quality_report
        }
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop_real_time_updates()
        self.cache.clear_stale()
        log_info("Market data integration cleaned up")