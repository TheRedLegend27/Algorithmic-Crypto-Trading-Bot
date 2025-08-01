"""
Enhanced data management system for multi-pair cryptocurrency trading.
Provides data synchronization, caching, indicator calculations, and quality validation.
"""
import time
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import threading
import json
import os
from pathlib import Path

from bot.utils import log_error, log_info, log_warning, retry_with_backoff, safe_execute
from bot.data_fetcher import DataFetcher

# Adaptive components imports
try:
    from bot.adaptive.data_models import MarketRegime, PerformanceMetrics as AdaptivePerformanceMetrics, AdaptationEvent
    from bot.adaptive.enums import RegimeType
    from bot.adaptive.interfaces import DataManagerInterface
    ADAPTIVE_AVAILABLE = True
except ImportError:
    # Fallback for when adaptive components are not available
    ADAPTIVE_AVAILABLE = False
    MarketRegime = None
    AdaptivePerformanceMetrics = None
    AdaptationEvent = None
    RegimeType = None
    DataManagerInterface = object


@dataclass
class CacheConfig:
    """Configuration for data caching."""
    enabled: bool = True
    max_memory_mb: int = 100  # Maximum memory usage for cache
    retention_hours: int = 24  # How long to keep cached data
    persist_to_disk: bool = True
    cache_directory: str = "cache"
    cleanup_interval_minutes: int = 60  # How often to clean up old data


@dataclass
class DataQualityReport:
    """Report on data quality validation."""
    is_valid: bool
    total_points: int
    missing_points: int
    invalid_ohlc_points: int
    negative_values: int
    stale_data_points: int
    duplicate_timestamps: int
    quality_score: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MarketData:
    """Enhanced market data structure."""
    pair: str
    timestamp: datetime
    price: float
    volume: float
    bid: float
    ask: float
    spread: float
    volatility: Optional[float] = None
    indicators: Dict[str, float] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Performance metrics for data operations."""
    fetch_time_ms: float
    cache_hit_rate: float
    data_quality_score: float
    indicator_calculation_time_ms: float
    memory_usage_mb: float
    active_pairs: int
    total_data_points: int
    last_updated: datetime = field(default_factory=datetime.now)


class IndicatorEngine:
    """Real-time technical indicator calculation engine."""
    
    def __init__(self):
        self.indicators = {
            'sma': self._calculate_sma,
            'ema': self._calculate_ema,
            'rsi': self._calculate_rsi,
            'macd': self._calculate_macd,
            'bollinger_bands': self._calculate_bollinger_bands,
            'atr': self._calculate_atr,
            'stochastic': self._calculate_stochastic,
            'williams_r': self._calculate_williams_r,
            'cci': self._calculate_cci,
            'momentum': self._calculate_momentum,
            'roc': self._calculate_roc,
            'volatility': self._calculate_volatility
        }
    
    def calculate_indicators(self, data: pd.DataFrame, indicators: List[str]) -> Dict[str, Any]:
        """
        Calculate multiple technical indicators for the given data.
        
        Args:
            data: DataFrame with OHLCV data
            indicators: List of indicator names to calculate
            
        Returns:
            Dictionary containing calculated indicators
        """
        results = {}
        
        for indicator in indicators:
            if indicator in self.indicators:
                try:
                    results[indicator] = self.indicators[indicator](data)
                except Exception as e:
                    log_warning(f"Failed to calculate {indicator}: {str(e)}")
                    results[indicator] = None
            else:
                log_warning(f"Unknown indicator: {indicator}")
                
        return results
    
    def _calculate_sma(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Simple Moving Average."""
        return data['close'].rolling(window=period).mean()
    
    def _calculate_ema(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return data['close'].ewm(span=period).mean()
    
    def _calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Calculate MACD indicator."""
        ema_fast = data['close'].ewm(span=fast).mean()
        ema_slow = data['close'].ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def _calculate_bollinger_bands(self, data: pd.DataFrame, period: int = 20, std_dev: float = 2) -> Dict[str, pd.Series]:
        """Calculate Bollinger Bands."""
        sma = data['close'].rolling(window=period).mean()
        std = data['close'].rolling(window=period).std()
        
        return {
            'upper': sma + (std * std_dev),
            'middle': sma,
            'lower': sma - (std * std_dev)
        }
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range."""
        high_low = data['high'] - data['low']
        high_close = np.abs(data['high'] - data['close'].shift())
        low_close = np.abs(data['low'] - data['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window=period).mean()
    
    def _calculate_stochastic(self, data: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """Calculate Stochastic Oscillator."""
        lowest_low = data['low'].rolling(window=k_period).min()
        highest_high = data['high'].rolling(window=k_period).max()
        
        k_percent = 100 * ((data['close'] - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()
        
        return {
            'k': k_percent,
            'd': d_percent
        }
    
    def _calculate_williams_r(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Williams %R."""
        highest_high = data['high'].rolling(window=period).max()
        lowest_low = data['low'].rolling(window=period).min()
        
        return -100 * ((highest_high - data['close']) / (highest_high - lowest_low))
    
    def _calculate_cci(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Commodity Channel Index."""
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        sma_tp = typical_price.rolling(window=period).mean()
        mean_deviation = typical_price.rolling(window=period).apply(
            lambda x: np.abs(x - x.mean()).mean()
        )
        
        return (typical_price - sma_tp) / (0.015 * mean_deviation)
    
    def _calculate_momentum(self, data: pd.DataFrame, period: int = 10) -> pd.Series:
        """Calculate Momentum."""
        return data['close'] - data['close'].shift(period)
    
    def _calculate_roc(self, data: pd.DataFrame, period: int = 10) -> pd.Series:
        """Calculate Rate of Change."""
        return ((data['close'] - data['close'].shift(period)) / data['close'].shift(period)) * 100
    
    def _calculate_volatility(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate price volatility (standard deviation of returns)."""
        returns = data['close'].pct_change()
        return returns.rolling(window=period).std() * np.sqrt(period)


class DataCache:
    """Thread-safe data cache with configurable retention and persistence."""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self._access_times: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._memory_usage = 0
        
        if config.persist_to_disk:
            self._setup_disk_cache()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
    
    def _setup_disk_cache(self):
        """Set up disk cache directory."""
        cache_path = Path(self.config.cache_directory)
        cache_path.mkdir(exist_ok=True)
    
    def get(self, pair: str, key: str) -> Optional[Any]:
        """Get cached data for a trading pair."""
        with self._lock:
            cache_key = f"{pair}:{key}"
            
            if cache_key in self._cache:
                self._access_times[cache_key] = datetime.now()
                return self._cache[cache_key]
            
            # Try to load from disk if enabled
            if self.config.persist_to_disk:
                return self._load_from_disk(pair, key)
            
            return None
    
    def set(self, pair: str, key: str, data: Any) -> bool:
        """Cache data for a trading pair."""
        with self._lock:
            cache_key = f"{pair}:{key}"
            
            # Estimate memory usage
            data_size = self._estimate_size(data)
            
            # Check memory limits
            if self._memory_usage + data_size > self.config.max_memory_mb * 1024 * 1024:
                self._evict_oldest()
            
            self._cache[cache_key] = data
            self._access_times[cache_key] = datetime.now()
            self._memory_usage += data_size
            
            # Persist to disk if enabled
            if self.config.persist_to_disk:
                self._save_to_disk(pair, key, data)
            
            return True
    
    def _estimate_size(self, data: Any) -> int:
        """Estimate memory size of data object."""
        if isinstance(data, pd.DataFrame):
            return data.memory_usage(deep=True).sum()
        elif isinstance(data, dict):
            return len(str(data)) * 4  # Rough estimate
        else:
            return len(str(data)) * 4
    
    def _evict_oldest(self):
        """Evict oldest cached items to free memory."""
        if not self._access_times:
            return
        
        # Sort by access time and remove oldest 25%
        sorted_items = sorted(self._access_times.items(), key=lambda x: x[1])
        items_to_remove = len(sorted_items) // 4
        
        for cache_key, _ in sorted_items[:items_to_remove]:
            if cache_key in self._cache:
                data_size = self._estimate_size(self._cache[cache_key])
                del self._cache[cache_key]
                del self._access_times[cache_key]
                self._memory_usage -= data_size
    
    def _save_to_disk(self, pair: str, key: str, data: Any):
        """Save data to disk cache."""
        try:
            cache_file = Path(self.config.cache_directory) / f"{pair}_{key}.json"
            
            if isinstance(data, pd.DataFrame):
                data.to_json(cache_file, orient='records', date_format='iso')
            else:
                with open(cache_file, 'w') as f:
                    json.dump(data, f, default=str)
        except Exception as e:
            log_warning(f"Failed to save cache to disk: {str(e)}")
    
    def _load_from_disk(self, pair: str, key: str) -> Optional[Any]:
        """Load data from disk cache."""
        try:
            cache_file = Path(self.config.cache_directory) / f"{pair}_{key}.json"
            
            if not cache_file.exists():
                return None
            
            # Check if file is too old
            file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if file_age > timedelta(hours=self.config.retention_hours):
                cache_file.unlink()
                return None
            
            with open(cache_file, 'r') as f:
                if key.endswith('_df'):  # DataFrame data
                    return pd.read_json(f, orient='records')
                else:
                    return json.load(f)
        except Exception as e:
            log_warning(f"Failed to load cache from disk: {str(e)}")
            return None
    
    def _cleanup_worker(self):
        """Background worker to clean up old cache entries."""
        while True:
            try:
                time.sleep(self.config.cleanup_interval_minutes * 60)
                self._cleanup_old_entries()
            except Exception as e:
                log_error(f"Cache cleanup error: {str(e)}")
    
    def _cleanup_old_entries(self):
        """Remove old cache entries."""
        with self._lock:
            current_time = datetime.now()
            retention_delta = timedelta(hours=self.config.retention_hours)
            
            keys_to_remove = []
            for cache_key, access_time in self._access_times.items():
                if current_time - access_time > retention_delta:
                    keys_to_remove.append(cache_key)
            
            for cache_key in keys_to_remove:
                if cache_key in self._cache:
                    data_size = self._estimate_size(self._cache[cache_key])
                    del self._cache[cache_key]
                    del self._access_times[cache_key]
                    self._memory_usage -= data_size
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                'total_entries': len(self._cache),
                'memory_usage_mb': self._memory_usage / (1024 * 1024),
                'oldest_entry': min(self._access_times.values()) if self._access_times else None,
                'newest_entry': max(self._access_times.values()) if self._access_times else None
            }


class EnhancedDataManager(DataManagerInterface if ADAPTIVE_AVAILABLE else object):
    """
    Enhanced data management system for multi-pair cryptocurrency trading.
    Provides data synchronization, caching, indicator calculations, quality validation,
    and adaptive data storage for regime detection, performance metrics, and adaptation events.
    """
    
    def __init__(self, pairs: List[str], cache_config: Optional[CacheConfig] = None):
        """
        Initialize the enhanced data manager.
        
        Args:
            pairs: List of trading pairs to manage
            cache_config: Configuration for data caching
        """
        self.pairs = pairs
        self.cache_config = cache_config or CacheConfig()
        
        # Initialize components
        self.data_fetcher = DataFetcher()
        self.indicator_engine = IndicatorEngine()
        self.cache = DataCache(self.cache_config) if self.cache_config.enabled else None
        
        # Data storage
        self._market_data: Dict[str, deque] = {pair: deque(maxlen=1000) for pair in pairs}
        self._latest_data: Dict[str, pd.DataFrame] = {}
        self._indicators: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        # Performance tracking
        self._performance_metrics = PerformanceMetrics(
            fetch_time_ms=0.0,
            cache_hit_rate=0.0,
            data_quality_score=0.0,
            indicator_calculation_time_ms=0.0,
            memory_usage_mb=0.0,
            active_pairs=len(pairs),
            total_data_points=0
        )
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Adaptive data storage
        if ADAPTIVE_AVAILABLE:
            self._regime_data: Dict[str, deque] = {pair: deque(maxlen=500) for pair in pairs}
            self._performance_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
            self._adaptation_events: deque = deque(maxlen=1000)
            self._ml_features_cache: Dict[str, Dict[str, Any]] = {}
            self._feature_cache_timestamps: Dict[str, datetime] = {}
        
        log_info(f"Enhanced data manager initialized for {len(pairs)} pairs"
                f" with adaptive features {'enabled' if ADAPTIVE_AVAILABLE else 'disabled'}")    

    def add_market_data(self, pair: str, data: MarketData) -> None:
        """
        Add new market data for a trading pair.
        
        Args:
            pair: Trading pair symbol
            data: MarketData object containing the new data
        """
        with self._lock:
            if pair not in self.pairs:
                log_warning(f"Pair {pair} not in managed pairs list")
                return
            
            self._market_data[pair].append(data)
            log_info(f"Added market data for {pair} at {data.timestamp}")
    
    def get_latest_data(self, pair: str, periods: int = 100) -> pd.DataFrame:
        """
        Get the latest market data for a trading pair.
        
        Args:
            pair: Trading pair symbol
            periods: Number of periods to retrieve
            
        Returns:
            DataFrame containing the latest market data
        """
        start_time = time.time()
        
        # Check cache first
        cache_key = f"latest_data_{periods}"
        if self.cache:
            cached_data = self.cache.get(pair, cache_key)
            if cached_data is not None:
                self._update_cache_hit_rate(True)
                return cached_data
        
        self._update_cache_hit_rate(False)
        
        try:
            # Fetch fresh data
            df = self.data_fetcher.fetch_crypto_data(pair, timeframe="5Min", limit=periods)
            
            # Cache the result
            if self.cache:
                self.cache.set(pair, cache_key, df)
            
            # Update latest data storage
            with self._lock:
                self._latest_data[pair] = df
            
            # Update performance metrics
            fetch_time = (time.time() - start_time) * 1000
            self._performance_metrics.fetch_time_ms = fetch_time
            
            return df
            
        except Exception as e:
            log_error(f"Failed to get latest data for {pair}: {str(e)}")
            # Return empty DataFrame with proper columns
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
    
    def get_historical_data(self, pair: str, start_time: datetime, end_time: datetime) -> pd.DataFrame:
        """
        Get historical market data for a trading pair within a time range.
        
        Args:
            pair: Trading pair symbol
            start_time: Start time for data retrieval
            end_time: End time for data retrieval
            
        Returns:
            DataFrame containing historical market data
        """
        cache_key = f"historical_{start_time.isoformat()}_{end_time.isoformat()}"
        
        # Check cache first
        if self.cache:
            cached_data = self.cache.get(pair, cache_key)
            if cached_data is not None:
                self._update_cache_hit_rate(True)
                return cached_data
        
        self._update_cache_hit_rate(False)
        
        try:
            # Calculate required periods based on time range
            time_diff = end_time - start_time
            periods = max(100, int(time_diff.total_seconds() / 300))  # 5-minute intervals
            
            # Fetch data
            df = self.data_fetcher.fetch_crypto_data(pair, timeframe="5Min", limit=periods)
            
            # Filter by time range
            if not df.empty:
                df = df[(df.index >= start_time) & (df.index <= end_time)]
            
            # Cache the result
            if self.cache:
                self.cache.set(pair, cache_key, df)
            
            return df
            
        except Exception as e:
            log_error(f"Failed to get historical data for {pair}: {str(e)}")
            return pd.DataFrame(columns=['open', 'high', 'low', 'close', 'volume'])
    
    def calculate_indicators(self, pair: str, indicators: List[str]) -> Dict[str, Any]:
        """
        Calculate technical indicators for a trading pair.
        
        Args:
            pair: Trading pair symbol
            indicators: List of indicator names to calculate
            
        Returns:
            Dictionary containing calculated indicators
        """
        start_time = time.time()
        
        # Get latest data for calculations
        data = self.get_latest_data(pair, periods=200)  # More data for accurate indicators
        
        if data.empty:
            log_warning(f"No data available for indicator calculation for {pair}")
            return {}
        
        try:
            # Calculate indicators
            results = self.indicator_engine.calculate_indicators(data, indicators)
            
            # Store results
            with self._lock:
                self._indicators[pair].update(results)
            
            # Update performance metrics
            calc_time = (time.time() - start_time) * 1000
            self._performance_metrics.indicator_calculation_time_ms = calc_time
            
            log_info(f"Calculated {len(indicators)} indicators for {pair}")
            return results
            
        except Exception as e:
            log_error(f"Failed to calculate indicators for {pair}: {str(e)}")
            return {}
    
    def validate_data_quality(self, data: pd.DataFrame) -> DataQualityReport:
        """
        Validate the quality of market data.
        
        Args:
            data: DataFrame containing market data to validate
            
        Returns:
            DataQualityReport containing validation results
        """
        if data.empty:
            return DataQualityReport(
                is_valid=False,
                total_points=0,
                missing_points=0,
                invalid_ohlc_points=0,
                negative_values=0,
                stale_data_points=0,
                duplicate_timestamps=0,
                quality_score=0.0,
                issues=["Empty dataset"]
            )
        
        issues = []
        total_points = len(data)
        
        # Check for missing values
        missing_points = data.isnull().sum().sum()
        if missing_points > 0:
            issues.append(f"{missing_points} missing values found")
        
        # Check for invalid OHLC relationships
        invalid_ohlc = (
            (data['high'] < data['low']) | 
            (data['high'] < data['open']) | 
            (data['high'] < data['close']) |
            (data['low'] > data['open']) | 
            (data['low'] > data['close'])
        ).sum()
        
        if invalid_ohlc > 0:
            issues.append(f"{invalid_ohlc} invalid OHLC relationships")
        
        # Check for negative values
        negative_values = (data[['open', 'high', 'low', 'close', 'volume']] < 0).sum().sum()
        if negative_values > 0:
            issues.append(f"{negative_values} negative values found")
        
        # Check for duplicate timestamps
        duplicate_timestamps = data.index.duplicated().sum()
        if duplicate_timestamps > 0:
            issues.append(f"{duplicate_timestamps} duplicate timestamps")
        
        # Check for stale data (only if we have recent data expected)
        stale_data_points = 0
        if not data.empty:
            try:
                latest_timestamp = data.index.max()
                if hasattr(latest_timestamp, 'to_pydatetime'):
                    latest_dt = latest_timestamp.to_pydatetime()
                else:
                    latest_dt = latest_timestamp
                
                time_diff = datetime.now() - latest_dt
                if time_diff > timedelta(hours=1):
                    stale_data_points = 1
                    issues.append(f"Data is stale (latest: {latest_timestamp})")
            except Exception:
                # Don't fail validation due to timestamp issues
                pass
        
        # Calculate quality score based on percentage of problematic data points
        # Weight different issues differently
        weighted_issues = (
            missing_points * 1.0 +  # Missing data is serious
            invalid_ohlc * 2.0 +    # Invalid OHLC is very serious
            negative_values * 2.0 +  # Negative values are very serious
            duplicate_timestamps * 0.5 +  # Duplicates are less serious
            stale_data_points * 0.1  # Stale data is least serious
        )
        
        # Quality score: 1.0 is perfect, 0.0 is completely bad
        quality_score = max(0.0, 1.0 - (weighted_issues / max(total_points, 1)))
        
        # Data is valid if quality score > 0.9 AND no critical issues
        critical_issues = invalid_ohlc + negative_values
        is_valid = quality_score > 0.9 and critical_issues == 0
        
        return DataQualityReport(
            is_valid=is_valid,
            total_points=total_points,
            missing_points=missing_points,
            invalid_ohlc_points=invalid_ohlc,
            negative_values=negative_values,
            stale_data_points=stale_data_points,
            duplicate_timestamps=duplicate_timestamps,
            quality_score=quality_score,
            issues=issues
        )
    
    def calculate_performance_metrics(self) -> PerformanceMetrics:
        """
        Calculate performance metrics for the data management system.
        
        Returns:
            PerformanceMetrics object containing current performance data
        """
        with self._lock:
            # Calculate memory usage
            memory_usage = 0
            total_data_points = 0
            
            for pair, data_queue in self._market_data.items():
                memory_usage += len(data_queue) * 200  # Rough estimate per data point
                total_data_points += len(data_queue)
            
            # Add cache memory usage
            if self.cache:
                cache_stats = self.cache.get_stats()
                memory_usage += cache_stats['memory_usage_mb'] * 1024 * 1024
            
            # Calculate average data quality
            quality_scores = []
            for pair in self.pairs:
                if pair in self._latest_data and not self._latest_data[pair].empty:
                    quality_report = self.validate_data_quality(self._latest_data[pair])
                    quality_scores.append(quality_report.quality_score)
            
            avg_quality_score = np.mean(quality_scores) if quality_scores else 0.0
            
            # Update performance metrics
            self._performance_metrics.memory_usage_mb = memory_usage / (1024 * 1024)
            self._performance_metrics.total_data_points = total_data_points
            self._performance_metrics.data_quality_score = avg_quality_score
            self._performance_metrics.last_updated = datetime.now()
            
            return self._performance_metrics
    
    def _update_cache_hit_rate(self, cache_hit: bool):
        """Update cache hit rate statistics."""
        # Simple exponential moving average for cache hit rate
        alpha = 0.1
        current_rate = 1.0 if cache_hit else 0.0
        self._performance_metrics.cache_hit_rate = (
            alpha * current_rate + (1 - alpha) * self._performance_metrics.cache_hit_rate
        )
    
    def get_pair_summary(self, pair: str) -> Dict[str, Any]:
        """
        Get a summary of data and indicators for a trading pair.
        
        Args:
            pair: Trading pair symbol
            
        Returns:
            Dictionary containing pair summary information
        """
        with self._lock:
            latest_data = self._latest_data.get(pair, pd.DataFrame())
            indicators = self._indicators.get(pair, {})
            market_data_count = len(self._market_data.get(pair, []))
            
            summary = {
                'pair': pair,
                'latest_data_points': len(latest_data),
                'market_data_count': market_data_count,
                'available_indicators': list(indicators.keys()),
                'last_price': None,
                'last_update': None,
                'data_quality': None
            }
            
            if not latest_data.empty:
                summary['last_price'] = float(latest_data['close'].iloc[-1])
                summary['last_update'] = latest_data.index[-1].isoformat()
                
                # Get data quality
                quality_report = self.validate_data_quality(latest_data)
                summary['data_quality'] = {
                    'is_valid': quality_report.is_valid,
                    'quality_score': quality_report.quality_score,
                    'issues': quality_report.issues
                }
            
            return summary
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get overall system status and health information.
        
        Returns:
            Dictionary containing system status information
        """
        performance_metrics = self.calculate_performance_metrics()
        cache_stats = self.cache.get_stats() if self.cache else {}
        
        # Get pair summaries
        pair_summaries = {}
        for pair in self.pairs:
            pair_summaries[pair] = self.get_pair_summary(pair)
        
        return {
            'active_pairs': len(self.pairs),
            'performance_metrics': {
                'fetch_time_ms': performance_metrics.fetch_time_ms,
                'cache_hit_rate': performance_metrics.cache_hit_rate,
                'data_quality_score': performance_metrics.data_quality_score,
                'indicator_calculation_time_ms': performance_metrics.indicator_calculation_time_ms,
                'memory_usage_mb': performance_metrics.memory_usage_mb,
                'total_data_points': performance_metrics.total_data_points,
                'last_updated': performance_metrics.last_updated.isoformat()
            },
            'cache_stats': cache_stats,
            'pair_summaries': pair_summaries
        }
    
    def cleanup(self):
        """Clean up resources and stop background threads."""
        log_info("Cleaning up enhanced data manager")
        # Cache cleanup is handled by its own thread
        # Additional cleanup can be added here if needed
    
    def add_trading_pair(self, pair: str) -> bool:
        """
        Add a new trading pair to the data manager.
        
        Args:
            pair: Trading pair symbol to add
            
        Returns:
            bool: True if pair was added successfully
        """
        with self._lock:
            if pair in self.pairs:
                log_warning(f"Pair {pair} already exists in data manager")
                return False
            
            self.pairs.append(pair)
            self._market_data[pair] = deque(maxlen=1000)
            self._performance_metrics.active_pairs = len(self.pairs)
            
            log_info(f"Added trading pair {pair} to data manager")
            return True
    
    def remove_trading_pair(self, pair: str) -> bool:
        """
        Remove a trading pair from the data manager.
        
        Args:
            pair: Trading pair symbol to remove
            
        Returns:
            bool: True if pair was removed successfully
        """
        with self._lock:
            if pair not in self.pairs:
                log_warning(f"Pair {pair} not found in data manager")
                return False
            
            self.pairs.remove(pair)
            if pair in self._market_data:
                del self._market_data[pair]
            if pair in self._latest_data:
                del self._latest_data[pair]
            if pair in self._indicators:
                del self._indicators[pair]
            
            self._performance_metrics.active_pairs = len(self.pairs)
            
            log_info(f"Removed trading pair {pair} from data manager")
            return True
    
    def sync_all_pairs(self) -> Dict[str, bool]:
        """
        Synchronize data for all trading pairs.
        
        Returns:
            Dictionary mapping pair names to sync success status
        """
        results = {}
        
        for pair in self.pairs:
            try:
                # Fetch latest data for each pair
                data = self.get_latest_data(pair, periods=100)
                results[pair] = not data.empty
                
                if not data.empty:
                    log_info(f"Successfully synchronized data for {pair}")
                else:
                    log_warning(f"No data retrieved for {pair}")
                    
            except Exception as e:
                log_error(f"Failed to sync data for {pair}: {str(e)}")
                results[pair] = False
        
        return results
    
    # Adaptive Data Management Methods
    
    def store_regime_data(self, regime: 'MarketRegime', pair: str) -> None:
        """
        Store regime detection data for a trading pair.
        
        Args:
            regime: MarketRegime object containing regime information
            pair: Trading pair symbol
        """
        if not ADAPTIVE_AVAILABLE:
            log_warning("Adaptive features not available - regime data not stored")
            return
        
        try:
            with self._lock:
                if pair not in self._regime_data:
                    self._regime_data[pair] = deque(maxlen=500)
                
                self._regime_data[pair].append(regime)
                
                # Cache regime data for quick access
                if self.cache:
                    cache_key = f"current_regime"
                    self.cache.set(pair, cache_key, regime)
                
                log_info(f"Stored regime data for {pair}: {regime.regime_type} (confidence: {regime.confidence:.3f})")
                
        except Exception as e:
            log_error(f"Error storing regime data for {pair}: {str(e)}")
    
    def store_performance_data(self, metrics: 'AdaptivePerformanceMetrics', strategy_name: str) -> None:
        """
        Store performance metrics for a strategy.
        
        Args:
            metrics: PerformanceMetrics object containing performance data
            strategy_name: Name of the strategy
        """
        if not ADAPTIVE_AVAILABLE:
            log_warning("Adaptive features not available - performance data not stored")
            return
        
        try:
            with self._lock:
                if strategy_name not in self._performance_data:
                    self._performance_data[strategy_name] = deque(maxlen=200)
                
                self._performance_data[strategy_name].append(metrics)
                
                # Cache latest performance data
                if self.cache:
                    cache_key = f"latest_performance"
                    self.cache.set(strategy_name, cache_key, metrics)
                
                log_info(f"Stored performance data for {strategy_name}: "
                        f"return={metrics.total_return:.4f}, sharpe={metrics.sharpe_ratio:.3f}")
                
        except Exception as e:
            log_error(f"Error storing performance data for {strategy_name}: {str(e)}")
    
    def store_adaptation_event(self, event: 'AdaptationEvent') -> None:
        """
        Store adaptation event data.
        
        Args:
            event: AdaptationEvent object containing adaptation information
        """
        if not ADAPTIVE_AVAILABLE:
            log_warning("Adaptive features not available - adaptation event not stored")
            return
        
        try:
            with self._lock:
                self._adaptation_events.append(event)
                
                # Cache recent adaptation events
                if self.cache:
                    cache_key = f"recent_adaptations"
                    recent_events = list(self._adaptation_events)[-10:]  # Last 10 events
                    self.cache.set("system", cache_key, recent_events)
                
                log_info(f"Stored adaptation event: {event.event_type} - {event.trigger_reason}")
                
        except Exception as e:
            log_error(f"Error storing adaptation event: {str(e)}")
    
    def get_historical_regimes(self, pair: str, start_time: datetime, end_time: datetime) -> List['MarketRegime']:
        """
        Retrieve historical regime data for a trading pair.
        
        Args:
            pair: Trading pair symbol
            start_time: Start time for data retrieval
            end_time: End time for data retrieval
            
        Returns:
            List of MarketRegime objects within the time range
        """
        if not ADAPTIVE_AVAILABLE:
            log_warning("Adaptive features not available - returning empty regime list")
            return []
        
        try:
            with self._lock:
                if pair not in self._regime_data:
                    return []
                
                # Filter regimes by time range
                filtered_regimes = []
                for regime in self._regime_data[pair]:
                    if start_time <= regime.detected_at <= end_time:
                        filtered_regimes.append(regime)
                
                log_info(f"Retrieved {len(filtered_regimes)} regime records for {pair} "
                        f"between {start_time} and {end_time}")
                
                return filtered_regimes
                
        except Exception as e:
            log_error(f"Error retrieving historical regimes for {pair}: {str(e)}")
            return []
    
    def get_performance_history(self, strategy_name: str, days_back: int = 30) -> List['AdaptivePerformanceMetrics']:
        """
        Get performance history for a strategy.
        
        Args:
            strategy_name: Name of the strategy
            days_back: Number of days to look back
            
        Returns:
            List of PerformanceMetrics objects
        """
        if not ADAPTIVE_AVAILABLE:
            log_warning("Adaptive features not available - returning empty performance list")
            return []
        
        try:
            with self._lock:
                if strategy_name not in self._performance_data:
                    return []
                
                # Filter by time range
                cutoff_time = datetime.now() - timedelta(days=days_back)
                filtered_metrics = []
                
                for metrics in self._performance_data[strategy_name]:
                    if metrics.last_updated >= cutoff_time:
                        filtered_metrics.append(metrics)
                
                log_info(f"Retrieved {len(filtered_metrics)} performance records for {strategy_name} "
                        f"from last {days_back} days")
                
                return filtered_metrics
                
        except Exception as e:
            log_error(f"Error retrieving performance history for {strategy_name}: {str(e)}")
            return []
    
    def cleanup_old_data(self, retention_days: int = 90) -> None:
        """
        Clean up old adaptive data beyond retention period.
        
        Args:
            retention_days: Number of days to retain data
        """
        if not ADAPTIVE_AVAILABLE:
            return
        
        try:
            cutoff_time = datetime.now() - timedelta(days=retention_days)
            
            with self._lock:
                # Clean up regime data
                for pair in self._regime_data:
                    original_count = len(self._regime_data[pair])
                    self._regime_data[pair] = deque(
                        [regime for regime in self._regime_data[pair] 
                         if regime.detected_at >= cutoff_time],
                        maxlen=500
                    )
                    cleaned_count = original_count - len(self._regime_data[pair])
                    if cleaned_count > 0:
                        log_info(f"Cleaned up {cleaned_count} old regime records for {pair}")
                
                # Clean up performance data
                for strategy_name in self._performance_data:
                    original_count = len(self._performance_data[strategy_name])
                    self._performance_data[strategy_name] = deque(
                        [metrics for metrics in self._performance_data[strategy_name]
                         if metrics.last_updated >= cutoff_time],
                        maxlen=200
                    )
                    cleaned_count = original_count - len(self._performance_data[strategy_name])
                    if cleaned_count > 0:
                        log_info(f"Cleaned up {cleaned_count} old performance records for {strategy_name}")
                
                # Clean up adaptation events
                original_count = len(self._adaptation_events)
                self._adaptation_events = deque(
                    [event for event in self._adaptation_events
                     if event.timestamp >= cutoff_time],
                    maxlen=1000
                )
                cleaned_count = original_count - len(self._adaptation_events)
                if cleaned_count > 0:
                    log_info(f"Cleaned up {cleaned_count} old adaptation events")
                
        except Exception as e:
            log_error(f"Error cleaning up old adaptive data: {str(e)}")
    
    def calculate_ml_features(self, pair: str, feature_set: List[str]) -> Dict[str, Any]:
        """
        Calculate ML features for a trading pair with caching.
        
        Args:
            pair: Trading pair symbol
            feature_set: List of features to calculate
            
        Returns:
            Dictionary containing calculated features
        """
        if not ADAPTIVE_AVAILABLE:
            log_warning("Adaptive features not available - returning empty features")
            return {}
        
        try:
            # Check cache first
            cache_key = f"ml_features_{hash(tuple(sorted(feature_set)))}"
            if (pair in self._feature_cache_timestamps and 
                datetime.now() - self._feature_cache_timestamps[pair] < timedelta(minutes=5)):
                
                if pair in self._ml_features_cache and cache_key in self._ml_features_cache[pair]:
                    log_info(f"Using cached ML features for {pair}")
                    return self._ml_features_cache[pair][cache_key]
            
            # Calculate features
            data = self.get_latest_data(pair, periods=200)  # Need more data for ML features
            if data.empty:
                return {}
            
            features = {}
            
            # Basic price features
            if 'price_features' in feature_set:
                features.update(self._calculate_price_features(data))
            
            # Technical indicator features
            if 'technical_features' in feature_set:
                features.update(self._calculate_technical_features(data))
            
            # Volume features
            if 'volume_features' in feature_set:
                features.update(self._calculate_volume_features(data))
            
            # Market microstructure features
            if 'microstructure_features' in feature_set:
                features.update(self._calculate_microstructure_features(data))
            
            # Time-based features
            if 'time_features' in feature_set:
                features.update(self._calculate_time_features())
            
            # Cache the results
            if pair not in self._ml_features_cache:
                self._ml_features_cache[pair] = {}
            
            self._ml_features_cache[pair][cache_key] = features
            self._feature_cache_timestamps[pair] = datetime.now()
            
            log_info(f"Calculated {len(features)} ML features for {pair}")
            return features
            
        except Exception as e:
            log_error(f"Error calculating ML features for {pair}: {str(e)}")
            return {}
    
    def get_adaptive_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of adaptive data storage.
        
        Returns:
            Dictionary containing adaptive data statistics
        """
        if not ADAPTIVE_AVAILABLE:
            return {'adaptive_features': False}
        
        try:
            with self._lock:
                regime_counts = {pair: len(regimes) for pair, regimes in self._regime_data.items()}
                performance_counts = {strategy: len(metrics) for strategy, metrics in self._performance_data.items()}
                
                return {
                    'adaptive_features': True,
                    'regime_data_points': sum(regime_counts.values()),
                    'regime_data_by_pair': regime_counts,
                    'performance_data_points': sum(performance_counts.values()),
                    'performance_data_by_strategy': performance_counts,
                    'adaptation_events': len(self._adaptation_events),
                    'ml_features_cached_pairs': len(self._ml_features_cache),
                    'last_regime_update': max([
                        max([regime.detected_at for regime in regimes], default=datetime.min)
                        for regimes in self._regime_data.values()
                    ], default=datetime.min),
                    'last_performance_update': max([
                        max([metrics.last_updated for metrics in metrics_list], default=datetime.min)
                        for metrics_list in self._performance_data.values()
                    ], default=datetime.min),
                    'last_adaptation_event': (
                        self._adaptation_events[-1].timestamp 
                        if self._adaptation_events else datetime.min
                    )
                }
                
        except Exception as e:
            log_error(f"Error getting adaptive data summary: {str(e)}")
            return {'adaptive_features': True, 'error': str(e)}
    
    # Helper methods for ML feature calculation
    
    def _calculate_price_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate price-based features for ML."""
        features = {}
        
        try:
            # Returns and volatility
            returns = data['close'].pct_change().dropna()
            features['return_mean'] = returns.mean()
            features['return_std'] = returns.std()
            features['return_skew'] = returns.skew()
            features['return_kurt'] = returns.kurtosis()
            
            # Price levels
            features['price_zscore'] = (data['close'].iloc[-1] - data['close'].mean()) / data['close'].std()
            features['high_low_ratio'] = data['high'].iloc[-1] / data['low'].iloc[-1]
            
            # Trend features
            features['price_trend_5'] = (data['close'].iloc[-1] - data['close'].iloc[-6]) / data['close'].iloc[-6]
            features['price_trend_20'] = (data['close'].iloc[-1] - data['close'].iloc[-21]) / data['close'].iloc[-21]
            
        except Exception as e:
            log_warning(f"Error calculating price features: {str(e)}")
        
        return features
    
    def _calculate_technical_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate technical indicator features for ML."""
        features = {}
        
        try:
            # RSI
            rsi = self.indicator_engine._calculate_rsi(data)
            if not rsi.empty:
                features['rsi'] = rsi.iloc[-1]
                features['rsi_oversold'] = 1.0 if rsi.iloc[-1] < 30 else 0.0
                features['rsi_overbought'] = 1.0 if rsi.iloc[-1] > 70 else 0.0
            
            # MACD
            macd_data = self.indicator_engine._calculate_macd(data)
            if 'macd' in macd_data and not macd_data['macd'].empty:
                features['macd'] = macd_data['macd'].iloc[-1]
                features['macd_signal'] = macd_data['signal'].iloc[-1]
                features['macd_histogram'] = macd_data['histogram'].iloc[-1]
            
            # Bollinger Bands
            bb_data = self.indicator_engine._calculate_bollinger_bands(data)
            if 'upper' in bb_data and not bb_data['upper'].empty:
                current_price = data['close'].iloc[-1]
                bb_upper = bb_data['upper'].iloc[-1]
                bb_lower = bb_data['lower'].iloc[-1]
                features['bb_position'] = (current_price - bb_lower) / (bb_upper - bb_lower)
                features['bb_squeeze'] = (bb_upper - bb_lower) / bb_data['middle'].iloc[-1]
            
        except Exception as e:
            log_warning(f"Error calculating technical features: {str(e)}")
        
        return features
    
    def _calculate_volume_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate volume-based features for ML."""
        features = {}
        
        try:
            # Volume statistics
            volume_mean = data['volume'].mean()
            features['volume_ratio'] = data['volume'].iloc[-1] / volume_mean if volume_mean > 0 else 1.0
            features['volume_trend'] = (data['volume'].iloc[-5:].mean() - data['volume'].iloc[-20:-5].mean()) / data['volume'].iloc[-20:-5].mean()
            
            # Price-volume relationship
            price_change = data['close'].pct_change()
            volume_change = data['volume'].pct_change()
            correlation = price_change.corr(volume_change)
            features['price_volume_corr'] = correlation if not pd.isna(correlation) else 0.0
            
        except Exception as e:
            log_warning(f"Error calculating volume features: {str(e)}")
        
        return features
    
    def _calculate_microstructure_features(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate market microstructure features for ML."""
        features = {}
        
        try:
            # Spread analysis (if bid/ask data available)
            if 'bid' in data.columns and 'ask' in data.columns:
                spread = data['ask'] - data['bid']
                mid_price = (data['ask'] + data['bid']) / 2
                features['spread_ratio'] = (spread / mid_price).mean()
                features['spread_volatility'] = spread.std()
            
            # OHLC relationships
            features['body_ratio'] = abs(data['close'] - data['open']) / (data['high'] - data['low'])
            features['upper_shadow'] = (data['high'] - data[['open', 'close']].max(axis=1)) / (data['high'] - data['low'])
            features['lower_shadow'] = (data[['open', 'close']].min(axis=1) - data['low']) / (data['high'] - data['low'])
            
            # Take the mean of the last few periods
            features['body_ratio'] = features['body_ratio'].iloc[-10:].mean()
            features['upper_shadow'] = features['upper_shadow'].iloc[-10:].mean()
            features['lower_shadow'] = features['lower_shadow'].iloc[-10:].mean()
            
        except Exception as e:
            log_warning(f"Error calculating microstructure features: {str(e)}")
        
        return features
    
    def _calculate_time_features(self) -> Dict[str, float]:
        """Calculate time-based features for ML."""
        features = {}
        
        try:
            now = datetime.now()
            
            # Time of day features
            features['hour_of_day'] = now.hour
            features['day_of_week'] = now.weekday()
            features['is_weekend'] = 1.0 if now.weekday() >= 5 else 0.0
            
            # Market session features (assuming UTC)
            # US session: 13:30-20:00 UTC
            # European session: 07:00-16:00 UTC
            # Asian session: 23:00-08:00 UTC
            hour = now.hour
            features['us_session'] = 1.0 if 13 <= hour <= 20 else 0.0
            features['eu_session'] = 1.0 if 7 <= hour <= 16 else 0.0
            features['asia_session'] = 1.0 if hour >= 23 or hour <= 8 else 0.0
            
        except Exception as e:
            log_warning(f"Error calculating time features: {str(e)}")
        
        return features