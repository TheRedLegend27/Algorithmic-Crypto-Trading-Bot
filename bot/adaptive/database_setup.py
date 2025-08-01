"""
Database Setup for Adaptive Trading Bot

This module handles database initialization, schema creation, and migration
for persistent storage of trading data, performance metrics, and system state.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import asyncpg
from asyncpg import Pool, Connection
from dataclasses import asdict

from .production_config import DatabaseConfig
from .data_models import (
    MarketRegime, AdaptiveSignal, PerformanceMetrics, 
    OptimizationResult, AdaptationEvent
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and operations"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.pool: Optional[Pool] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.config.get_connection_string(),
                min_size=1,
                max_size=self.config.connection_pool_size,
                max_inactive_connection_lifetime=300
            )
            
            # Create tables if they don't exist
            await self.create_tables()
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    async def close(self) -> None:
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            self._initialized = False
            logger.info("Database connections closed")
    
    async def create_tables(self) -> None:
        """Create database tables for adaptive bot data"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            # Market regimes table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS market_regimes (
                    id SERIAL PRIMARY KEY,
                    pair VARCHAR(20) NOT NULL,
                    regime_type VARCHAR(50) NOT NULL,
                    confidence FLOAT NOT NULL,
                    volatility_level FLOAT NOT NULL,
                    trend_strength FLOAT NOT NULL,
                    momentum FLOAT NOT NULL,
                    detected_at TIMESTAMP NOT NULL,
                    supporting_indicators JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Adaptive signals table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS adaptive_signals (
                    id SERIAL PRIMARY KEY,
                    pair VARCHAR(20) NOT NULL,
                    signal_type VARCHAR(20) NOT NULL,
                    strength FLOAT NOT NULL,
                    confidence FLOAT NOT NULL,
                    ml_confidence FLOAT,
                    regime_context JSONB,
                    strategy_weights JSONB,
                    parameter_adjustments JSONB,
                    adaptation_metadata JSONB,
                    generated_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Performance metrics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id SERIAL PRIMARY KEY,
                    strategy_name VARCHAR(100),
                    pair VARCHAR(20),
                    timeframe VARCHAR(20),
                    total_return FLOAT NOT NULL,
                    annualized_return FLOAT NOT NULL,
                    sharpe_ratio FLOAT,
                    sortino_ratio FLOAT,
                    max_drawdown FLOAT,
                    win_rate FLOAT,
                    profit_factor FLOAT,
                    avg_trade_duration_hours FLOAT,
                    trades_count INTEGER,
                    regime_performance JSONB,
                    period_start TIMESTAMP NOT NULL,
                    period_end TIMESTAMP NOT NULL,
                    last_updated TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Optimization results table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS optimization_results (
                    id SERIAL PRIMARY KEY,
                    strategy_name VARCHAR(100) NOT NULL,
                    pair VARCHAR(20),
                    old_parameters JSONB NOT NULL,
                    new_parameters JSONB NOT NULL,
                    performance_improvement FLOAT NOT NULL,
                    confidence_score FLOAT NOT NULL,
                    optimization_method VARCHAR(50) NOT NULL,
                    validation_period_hours INTEGER,
                    applied_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Adaptation events table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS adaptation_events (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(100) UNIQUE NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    trigger_reason TEXT NOT NULL,
                    changes_made JSONB NOT NULL,
                    expected_impact FLOAT,
                    actual_impact FLOAT,
                    success BOOLEAN,
                    timestamp TIMESTAMP NOT NULL,
                    rollback_available BOOLEAN DEFAULT TRUE,
                    rollback_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Trading positions table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trading_positions (
                    id SERIAL PRIMARY KEY,
                    position_id VARCHAR(100) UNIQUE NOT NULL,
                    pair VARCHAR(20) NOT NULL,
                    side VARCHAR(10) NOT NULL,
                    size FLOAT NOT NULL,
                    entry_price FLOAT NOT NULL,
                    exit_price FLOAT,
                    stop_loss FLOAT,
                    take_profit FLOAT,
                    strategy_name VARCHAR(100),
                    regime_at_entry VARCHAR(50),
                    ml_confidence FLOAT,
                    opened_at TIMESTAMP NOT NULL,
                    closed_at TIMESTAMP,
                    pnl FLOAT,
                    status VARCHAR(20) DEFAULT 'open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # System state table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    id SERIAL PRIMARY KEY,
                    component_name VARCHAR(100) NOT NULL,
                    state_data JSONB NOT NULL,
                    version INTEGER DEFAULT 1,
                    updated_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(component_name)
                );
            """)
            
            # Create indexes for better performance
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_market_regimes_pair_time ON market_regimes(pair, detected_at);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_adaptive_signals_pair_time ON adaptive_signals(pair, generated_at);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_performance_metrics_strategy_time ON performance_metrics(strategy_name, period_end);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_adaptation_events_time ON adaptation_events(timestamp);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_trading_positions_pair_status ON trading_positions(pair, status);")
            
            logger.info("Database tables created successfully")
    
    async def save_market_regime(self, pair: str, regime: MarketRegime) -> int:
        """Save market regime to database"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO market_regimes 
                (pair, regime_type, confidence, volatility_level, trend_strength, 
                 momentum, detected_at, supporting_indicators)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, pair, regime.regime_type.value, regime.confidence, 
                regime.volatility_level, regime.trend_strength, regime.momentum,
                regime.detected_at, json.dumps(regime.supporting_indicators))
            
            return result['id']
    
    async def save_adaptive_signal(self, pair: str, signal: AdaptiveSignal) -> int:
        """Save adaptive signal to database"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO adaptive_signals 
                (pair, signal_type, strength, confidence, ml_confidence, 
                 regime_context, strategy_weights, parameter_adjustments, 
                 adaptation_metadata, generated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
            """, pair, signal.base_signal.signal_type.value, signal.base_signal.strength,
                signal.base_signal.confidence, signal.ml_confidence,
                json.dumps(asdict(signal.regime_context)) if signal.regime_context else None,
                json.dumps(signal.strategy_weights),
                json.dumps(signal.parameter_adjustments),
                json.dumps(signal.adaptation_metadata),
                signal.base_signal.timestamp)
            
            return result['id']
    
    async def save_performance_metrics(self, metrics: PerformanceMetrics, 
                                     strategy_name: str = None, pair: str = None,
                                     timeframe: str = None) -> int:
        """Save performance metrics to database"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            # Calculate period based on metrics
            period_end = metrics.last_updated
            period_start = period_end - timedelta(days=30)  # Default 30-day window
            
            result = await conn.fetchrow("""
                INSERT INTO performance_metrics 
                (strategy_name, pair, timeframe, total_return, annualized_return,
                 sharpe_ratio, sortino_ratio, max_drawdown, win_rate, profit_factor,
                 avg_trade_duration_hours, trades_count, regime_performance,
                 period_start, period_end, last_updated)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                RETURNING id
            """, strategy_name, pair, timeframe, metrics.total_return, 
                metrics.annualized_return, metrics.sharpe_ratio, metrics.sortino_ratio,
                metrics.max_drawdown, metrics.win_rate, metrics.profit_factor,
                metrics.avg_trade_duration.total_seconds() / 3600,  # Convert to hours
                metrics.trades_count, json.dumps({k.value: v for k, v in metrics.regime_performance.items()}),
                period_start, period_end, metrics.last_updated)
            
            return result['id']
    
    async def save_optimization_result(self, result: OptimizationResult) -> int:
        """Save optimization result to database"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            db_result = await conn.fetchrow("""
                INSERT INTO optimization_results 
                (strategy_name, old_parameters, new_parameters, performance_improvement,
                 confidence_score, optimization_method, validation_period_hours, applied_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, result.strategy_name, json.dumps(result.old_parameters),
                json.dumps(result.new_parameters), result.performance_improvement,
                result.confidence_score, result.optimization_method,
                int(result.validation_period.total_seconds() / 3600),
                result.applied_at)
            
            return db_result['id']
    
    async def save_adaptation_event(self, event: AdaptationEvent) -> int:
        """Save adaptation event to database"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO adaptation_events 
                (event_id, event_type, trigger_reason, changes_made, expected_impact,
                 actual_impact, success, timestamp, rollback_available)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
            """, event.event_id, event.event_type.value, event.trigger_reason,
                json.dumps(event.changes_made), event.expected_impact,
                event.actual_impact, event.success, event.timestamp,
                event.rollback_available)
            
            return result['id']
    
    async def get_recent_regimes(self, pair: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent market regimes for a pair"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            results = await conn.fetch("""
                SELECT * FROM market_regimes 
                WHERE pair = $1 AND detected_at >= $2
                ORDER BY detected_at DESC
            """, pair, cutoff_time)
            
            return [dict(row) for row in results]
    
    async def get_performance_history(self, strategy_name: str = None, 
                                    pair: str = None, days: int = 30) -> List[Dict[str, Any]]:
        """Get performance history"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            query = "SELECT * FROM performance_metrics WHERE last_updated >= $1"
            params = [cutoff_time]
            
            if strategy_name:
                query += " AND strategy_name = $2"
                params.append(strategy_name)
            
            if pair:
                param_num = len(params) + 1
                query += f" AND pair = ${param_num}"
                params.append(pair)
            
            query += " ORDER BY last_updated DESC"
            
            results = await conn.fetch(query, *params)
            return [dict(row) for row in results]
    
    async def save_system_state(self, component_name: str, state_data: Dict[str, Any]) -> None:
        """Save system component state"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO system_state (component_name, state_data, updated_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (component_name) 
                DO UPDATE SET 
                    state_data = EXCLUDED.state_data,
                    updated_at = EXCLUDED.updated_at,
                    version = system_state.version + 1
            """, component_name, json.dumps(state_data), datetime.utcnow())
    
    async def load_system_state(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Load system component state"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT state_data FROM system_state 
                WHERE component_name = $1
            """, component_name)
            
            if result:
                return json.loads(result['state_data'])
            return None
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> None:
        """Clean up old data to manage database size"""
        if not self.pool:
            raise RuntimeError("Database not initialized")
        
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)
        
        async with self.pool.acquire() as conn:
            # Clean up old market regimes
            await conn.execute("""
                DELETE FROM market_regimes 
                WHERE detected_at < $1
            """, cutoff_time)
            
            # Clean up old adaptive signals
            await conn.execute("""
                DELETE FROM adaptive_signals 
                WHERE generated_at < $1
            """, cutoff_time)
            
            # Clean up old performance metrics (keep longer)
            perf_cutoff = datetime.utcnow() - timedelta(days=days_to_keep * 2)
            await conn.execute("""
                DELETE FROM performance_metrics 
                WHERE last_updated < $1
            """, perf_cutoff)
            
            logger.info(f"Cleaned up data older than {days_to_keep} days")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check"""
        if not self.pool:
            return {"status": "error", "message": "Database not initialized"}
        
        try:
            async with self.pool.acquire() as conn:
                # Test basic connectivity
                result = await conn.fetchval("SELECT 1")
                
                # Check table counts
                tables = ['market_regimes', 'adaptive_signals', 'performance_metrics', 
                         'optimization_results', 'adaptation_events', 'trading_positions']
                
                table_counts = {}
                for table in tables:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    table_counts[table] = count
                
                return {
                    "status": "healthy",
                    "connection_test": result == 1,
                    "table_counts": table_counts,
                    "pool_size": self.pool.get_size(),
                    "pool_max_size": self.pool.get_max_size()
                }
                
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }


# Global database manager instance
_db_manager: Optional[DatabaseManager] = None


async def get_database_manager(config: DatabaseConfig = None) -> DatabaseManager:
    """Get or create database manager instance"""
    global _db_manager
    
    if _db_manager is None:
        if config is None:
            from .production_config import get_production_config
            prod_config = get_production_config()
            config = prod_config.database
        
        _db_manager = DatabaseManager(config)
        await _db_manager.initialize()
    
    return _db_manager


async def close_database_manager() -> None:
    """Close database manager"""
    global _db_manager
    
    if _db_manager:
        await _db_manager.close()
        _db_manager = None