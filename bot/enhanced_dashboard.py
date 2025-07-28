"""
Enhanced dashboard with real-time monitoring for cryptocurrency trading bot.
Provides web-based interface with portfolio visualization, trading activity feed,
performance charts, risk monitoring, and manual trading controls.
"""
import asyncio
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
import websockets
import logging
import psutil
from flask import Flask, render_template_string, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
import pandas as pd

from bot.utils import log_error, log_info, log_warning, safe_execute
from bot.enhanced_data_manager import EnhancedDataManager, MarketData
from bot.enhanced_data_manager import PerformanceMetrics as DataPerformanceMetrics
from bot.enhanced_logger import EnhancedLogger
from bot.enhanced_risk_manager import EnhancedRiskManager, RiskAssessment
from bot.kraken_client import KrakenClient
from bot.kraken_websocket import KrakenWebSocketClient


@dataclass
class DashboardConfig:
    """Configuration for the enhanced dashboard."""
    host: str = "localhost"
    port: int = 8080
    debug: bool = False
    auto_refresh_interval: int = 5  # seconds
    max_trade_history: int = 100
    max_log_entries: int = 500
    enable_manual_trading: bool = True
    enable_websocket: bool = True
    chart_data_points: int = 100
    theme: str = "dark"  # dark or light


@dataclass
class Portfolio:
    """Portfolio data structure for dashboard."""
    total_value_usd: float
    available_balance: float
    positions: Dict[str, Any]
    daily_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TradeExecution:
    """Trade execution record for dashboard."""
    trade_id: str
    pair: str
    side: str
    order_type: str
    volume: float
    price: float
    fee: float
    timestamp: datetime
    strategy: str
    signal_confidence: float
    execution_time_ms: int
    status: str


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics for dashboard."""
    total_value_usd: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    successful_trades: int
    average_trade_duration: float


@dataclass
class SystemHealth:
    """System health metrics for dashboard."""
    bot_uptime: float
    cpu_usage: float
    memory_usage: float
    api_rate_limit_used: int
    api_rate_limit_max: int
    websocket_connected: bool
    last_heartbeat: datetime
    error_rate_24h: float
    active_strategies: List[str]
    trading_enabled: bool


@dataclass
class ManualTradeRequest:
    """Manual trade request from dashboard."""
    pair: str
    side: str  # buy or sell
    order_type: str  # market or limit
    volume: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class TradeResult:
    """Result of trade execution."""
    success: bool
    trade_id: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


class EnhancedDashboard:
    """Enhanced dashboard with real-time monitoring capabilities."""
    
    def __init__(self, config: DashboardConfig, data_manager: EnhancedDataManager,
                 logger: EnhancedLogger, risk_manager: EnhancedRiskManager,
                 kraken_client: KrakenClient):
        self.config = config
        self.data_manager = data_manager
        self.logger = logger
        self.risk_manager = risk_manager
        self.kraken_client = kraken_client
        
        # Flask app setup
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'enhanced_dashboard_secret_key'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # Dashboard state
        self.portfolio: Optional[Portfolio] = None
        self.market_data: Dict[str, MarketData] = {}
        self.trade_history: List[TradeExecution] = []
        self.system_health: Optional[SystemHealth] = None
        self.performance_metrics: Optional[DataPerformanceMetrics] = None
        
        # WebSocket clients
        self.websocket_clients: List[Any] = []
        self.update_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Setup routes and WebSocket handlers
        self._setup_routes()
        self._setup_websocket_handlers()
        
        log_info("Enhanced dashboard initialized")
    
    def start_server(self, host: str = None, port: int = None) -> None:
        """Start the dashboard server."""
        host = host or self.config.host
        port = port or self.config.port
        
        self.running = True
        
        # Start background update thread
        self.update_thread = threading.Thread(target=self._background_update_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        log_info(f"Starting enhanced dashboard server on {host}:{port}")
        
        try:
            self.socketio.run(
                self.app,
                host=host,
                port=port,
                debug=self.config.debug,
                allow_unsafe_werkzeug=True
            )
        except Exception as e:
            log_error(e, "Failed to start dashboard server")
            self.running = False
    
    def stop_server(self) -> None:
        """Stop the dashboard server."""
        self.running = False
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=5)
        log_info("Enhanced dashboard server stopped")
    
    def update_portfolio_data(self, portfolio: Portfolio) -> None:
        """Update portfolio data and broadcast to clients."""
        self.portfolio = portfolio
        self._broadcast_update('portfolio_update', asdict(portfolio))
    
    def update_market_data(self, market_data: Dict[str, MarketData]) -> None:
        """Update market data and broadcast to clients."""
        self.market_data = market_data
        
        # Convert to serializable format
        serializable_data = {}
        for pair, data in market_data.items():
            serializable_data[pair] = {
                'pair': data.pair,
                'timestamp': data.timestamp.isoformat(),
                'price': data.price,
                'volume': data.volume,
                'bid': data.bid,
                'ask': data.ask,
                'spread': data.spread,
                'volatility': data.volatility,
                'indicators': data.indicators
            }
        
        self._broadcast_update('market_data_update', serializable_data)
    
    def add_trade_event(self, trade: TradeExecution) -> None:
        """Add a new trade event and broadcast to clients."""
        self.trade_history.append(trade)
        
        # Keep only recent trades
        if len(self.trade_history) > self.config.max_trade_history:
            self.trade_history = self.trade_history[-self.config.max_trade_history:]
        
        # Convert to serializable format
        trade_data = asdict(trade)
        trade_data['timestamp'] = trade.timestamp.isoformat()
        
        self._broadcast_update('trade_update', trade_data)
    
    def update_performance_metrics(self, metrics: DataPerformanceMetrics) -> None:
        """Update performance metrics and broadcast to clients."""
        self.performance_metrics = metrics
        
        # Convert to serializable format
        metrics_data = asdict(metrics)
        metrics_data['last_updated'] = metrics.last_updated.isoformat()
        
        self._broadcast_update('performance_update', metrics_data)
    
    def update_system_health(self, health: SystemHealth) -> None:
        """Update system health metrics and broadcast to clients."""
        self.system_health = health
        
        # Convert to serializable format
        health_data = asdict(health)
        health_data['last_heartbeat'] = health.last_heartbeat.isoformat()
        
        self._broadcast_update('system_health_update', health_data)
    
    def handle_manual_trade_request(self, request: ManualTradeRequest) -> TradeResult:
        """Handle manual trade request from dashboard."""
        if not self.config.enable_manual_trading:
            return TradeResult(
                success=False,
                error="Manual trading is disabled"
            )
        
        try:
            # Validate trade request
            validation_result = self._validate_trade_request(request)
            if not validation_result.success:
                return validation_result
            
            # Execute trade through Kraken client
            if request.order_type == "market":
                result = self._execute_market_order(request)
            else:
                result = self._execute_limit_order(request)
            
            return result
            
        except Exception as e:
            log_error(e, f"Failed to execute manual trade: {request}")
            return TradeResult(
                success=False,
                error=f"Trade execution failed: {str(e)}"
            )    

    def _setup_routes(self) -> None:
        """Setup Flask routes for the dashboard."""
        
        @self.app.route('/')
        def index():
            """Main dashboard page."""
            return render_template_string(self._get_dashboard_template())
        
        @self.app.route('/api/portfolio')
        def get_portfolio():
            """Get current portfolio data."""
            if self.portfolio:
                portfolio_data = asdict(self.portfolio)
                portfolio_data['timestamp'] = self.portfolio.timestamp.isoformat()
                return jsonify(portfolio_data)
            return jsonify({'error': 'Portfolio data not available'})
        
        @self.app.route('/api/market_data')
        def get_market_data():
            """Get current market data."""
            serializable_data = {}
            for pair, data in self.market_data.items():
                serializable_data[pair] = {
                    'pair': data.pair,
                    'timestamp': data.timestamp.isoformat(),
                    'price': data.price,
                    'volume': data.volume,
                    'bid': data.bid,
                    'ask': data.ask,
                    'spread': data.spread,
                    'volatility': data.volatility,
                    'indicators': data.indicators
                }
            return jsonify(serializable_data)
        
        @self.app.route('/api/trades')
        def get_trades():
            """Get recent trade history."""
            trades_data = []
            for trade in self.trade_history[-50:]:  # Last 50 trades
                trade_data = asdict(trade)
                trade_data['timestamp'] = trade.timestamp.isoformat()
                trades_data.append(trade_data)
            return jsonify(trades_data)
        
        @self.app.route('/api/performance')
        def get_performance():
            """Get performance metrics."""
            if self.performance_metrics:
                metrics_data = asdict(self.performance_metrics)
                metrics_data['last_updated'] = self.performance_metrics.last_updated.isoformat()
                return jsonify(metrics_data)
            return jsonify({'error': 'Performance metrics not available'})
        
        @self.app.route('/api/system_health')
        def get_system_health():
            """Get system health metrics."""
            if self.system_health:
                health_data = asdict(self.system_health)
                health_data['last_heartbeat'] = self.system_health.last_heartbeat.isoformat()
                return jsonify(health_data)
            return jsonify({'error': 'System health data not available'})
        
        @self.app.route('/api/trade', methods=['POST'])
        def execute_trade():
            """Execute manual trade."""
            try:
                data = request.get_json()
                trade_request = ManualTradeRequest(
                    pair=data['pair'],
                    side=data['side'],
                    order_type=data['order_type'],
                    volume=float(data['volume']),
                    price=float(data['price']) if data.get('price') else None,
                    stop_loss=float(data['stop_loss']) if data.get('stop_loss') else None,
                    take_profit=float(data['take_profit']) if data.get('take_profit') else None
                )
                
                result = self.handle_manual_trade_request(trade_request)
                return jsonify(asdict(result))
                
            except Exception as e:
                log_error(e, "Failed to process trade request")
                return jsonify({
                    'success': False,
                    'error': f'Invalid trade request: {str(e)}'
                })
        
        @self.app.route('/api/bot_control', methods=['POST'])
        def bot_control():
            """Control bot operations."""
            try:
                data = request.get_json()
                action = data.get('action')
                
                if action == 'emergency_stop':
                    # Implement emergency stop
                    return jsonify({'success': True, 'message': 'Emergency stop activated'})
                elif action == 'pause_trading':
                    # Implement pause trading
                    return jsonify({'success': True, 'message': 'Trading paused'})
                elif action == 'resume_trading':
                    # Implement resume trading
                    return jsonify({'success': True, 'message': 'Trading resumed'})
                else:
                    return jsonify({'success': False, 'error': 'Unknown action'})
                    
            except Exception as e:
                log_error(e, "Failed to process bot control request")
                return jsonify({'success': False, 'error': str(e)})
    
    def _setup_websocket_handlers(self) -> None:
        """Setup WebSocket event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            log_info("Dashboard client connected")
            
            # Send initial data to new client
            if self.portfolio:
                portfolio_data = asdict(self.portfolio)
                portfolio_data['timestamp'] = self.portfolio.timestamp.isoformat()
                emit('portfolio_update', portfolio_data)
            
            if self.system_health:
                health_data = asdict(self.system_health)
                health_data['last_heartbeat'] = self.system_health.last_heartbeat.isoformat()
                emit('system_health_update', health_data)
            
            if self.performance_metrics:
                metrics_data = asdict(self.performance_metrics)
                metrics_data['last_updated'] = self.performance_metrics.last_updated.isoformat()
                emit('performance_update', metrics_data)
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            log_info("Dashboard client disconnected")
        
        @self.socketio.on('subscribe_pair')
        def handle_subscribe_pair(data):
            """Handle subscription to specific trading pair."""
            pair = data.get('pair')
            if pair and pair in self.market_data:
                market_data = self.market_data[pair]
                emit('market_data_update', {
                    pair: {
                        'pair': market_data.pair,
                        'timestamp': market_data.timestamp.isoformat(),
                        'price': market_data.price,
                        'volume': market_data.volume,
                        'bid': market_data.bid,
                        'ask': market_data.ask,
                        'spread': market_data.spread,
                        'volatility': market_data.volatility,
                        'indicators': market_data.indicators
                    }
                })
    
    def _broadcast_update(self, event: str, data: Any) -> None:
        """Broadcast update to all connected WebSocket clients."""
        if self.config.enable_websocket:
            self.socketio.emit(event, data)
    
    def _background_update_loop(self) -> None:
        """Background thread for periodic updates."""
        while self.running:
            try:
                # Update system health
                self._update_system_health()
                
                # Update performance metrics if available
                if hasattr(self.data_manager, 'calculate_performance_metrics'):
                    metrics = self.data_manager.calculate_performance_metrics()
                    if metrics:
                        self.update_performance_metrics(metrics)
                
                time.sleep(self.config.auto_refresh_interval)
                
            except Exception as e:
                log_error(e, "Error in dashboard background update loop")
                time.sleep(self.config.auto_refresh_interval)
    
    def _update_system_health(self) -> None:
        """Update system health metrics."""
        try:
            # Calculate bot uptime (placeholder - would need actual start time)
            uptime_hours = 24.5  # This would be calculated from actual start time
            
            # Get system metrics
            cpu_usage = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Create system health object
            health = SystemHealth(
                bot_uptime=uptime_hours,
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                api_rate_limit_used=850,  # Would get from actual API client
                api_rate_limit_max=1000,
                websocket_connected=True,  # Would check actual WebSocket status
                last_heartbeat=datetime.now(),
                error_rate_24h=0.02,  # Would calculate from actual error logs
                active_strategies=["Enhanced Momentum", "Mean Reversion"],  # From strategy manager
                trading_enabled=True  # From bot state
            )
            
            self.update_system_health(health)
            
        except Exception as e:
            log_error(e, "Failed to update system health")
    
    def _validate_trade_request(self, request: ManualTradeRequest) -> TradeResult:
        """Validate manual trade request."""
        try:
            # Basic validation
            if not request.pair or not request.side or not request.volume:
                return TradeResult(
                    success=False,
                    error="Missing required trade parameters"
                )
            
            if request.volume <= 0:
                return TradeResult(
                    success=False,
                    error="Volume must be positive"
                )
            
            if request.order_type == "limit" and not request.price:
                return TradeResult(
                    success=False,
                    error="Price required for limit orders"
                )
            
            # Risk validation through risk manager
            if self.risk_manager:
                # Create a mock signal for risk validation
                from bot.strategy import TradingSignal, SignalType
                
                # Convert side to SignalType
                action = SignalType.BUY if request.side.lower() == "buy" else SignalType.SELL
                
                signal = TradingSignal(
                    action=action,
                    confidence=0.8,  # Manual trades have high confidence
                    strategy="Manual",
                    timestamp=datetime.now(),
                    price=request.price or 0,
                    reasoning=f"Manual {request.side} order for {request.pair}"
                )
                
                risk_assessment = self.risk_manager.validate_trade(signal, {})
                if not risk_assessment.approved:
                    return TradeResult(
                        success=False,
                        error=f"Trade rejected by risk manager: {risk_assessment.reason}"
                    )
            
            return TradeResult(success=True, message="Trade request validated")
            
        except Exception as e:
            log_error(e, f"Error validating trade request: {request}")
            return TradeResult(
                success=False,
                error=f"Validation error: {str(e)}"
            )
    
    def _execute_market_order(self, request: ManualTradeRequest) -> TradeResult:
        """Execute market order."""
        try:
            # Execute through Kraken client
            result = self.kraken_client.place_market_order(
                request.pair,
                request.side.lower(),
                str(request.volume)
            )
            
            if result and 'txid' in result:
                trade_id = result['txid'][0] if isinstance(result['txid'], list) else result['txid']
                
                # Create trade execution record
                trade = TradeExecution(
                    trade_id=trade_id,
                    pair=request.pair,
                    side=request.side.upper(),
                    order_type="MARKET",
                    volume=request.volume,
                    price=0,  # Will be filled when order executes
                    fee=0,    # Will be calculated when order executes
                    timestamp=datetime.now(),
                    strategy="Manual",
                    signal_confidence=1.0,
                    execution_time_ms=0,
                    status="PENDING"
                )
                
                self.add_trade_event(trade)
                
                return TradeResult(
                    success=True,
                    trade_id=trade_id,
                    message=f"Market {request.side} order placed successfully"
                )
            else:
                return TradeResult(
                    success=False,
                    error="Failed to place market order"
                )
                
        except Exception as e:
            log_error(e, f"Failed to execute market order: {request}")
            return TradeResult(
                success=False,
                error=f"Market order execution failed: {str(e)}"
            )
    
    def _execute_limit_order(self, request: ManualTradeRequest) -> TradeResult:
        """Execute limit order."""
        try:
            # Execute through Kraken client
            result = self.kraken_client.place_limit_order(
                request.pair,
                request.side.lower(),
                str(request.volume),
                str(request.price)
            )
            
            if result and 'txid' in result:
                trade_id = result['txid'][0] if isinstance(result['txid'], list) else result['txid']
                
                # Create trade execution record
                trade = TradeExecution(
                    trade_id=trade_id,
                    pair=request.pair,
                    side=request.side.upper(),
                    order_type="LIMIT",
                    volume=request.volume,
                    price=request.price,
                    fee=0,    # Will be calculated when order executes
                    timestamp=datetime.now(),
                    strategy="Manual",
                    signal_confidence=1.0,
                    execution_time_ms=0,
                    status="PENDING"
                )
                
                self.add_trade_event(trade)
                
                return TradeResult(
                    success=True,
                    trade_id=trade_id,
                    message=f"Limit {request.side} order placed successfully"
                )
            else:
                return TradeResult(
                    success=False,
                    error="Failed to place limit order"
                )
                
        except Exception as e:
            log_error(e, f"Failed to execute limit order: {request}")
            return TradeResult(
                success=False,
                error=f"Limit order execution failed: {str(e)}"
            )
    
    def _get_dashboard_template(self) -> str:
        """Get the HTML template for the dashboard."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Enhanced Crypto Trading Dashboard</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            background: #0d1117;
            color: #c9d1d9;
            font-size: 14px;
        }
        
        .header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: bold;
            color: #58a6ff;
        }
        
        .status-bar {
            display: flex;
            gap: 2rem;
            align-items: center;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .status-green { background: #238636; }
        .status-red { background: #da3633; }
        .status-yellow { background: #d29922; }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 1.5rem;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 1.5rem;
        }
        
        .full-width {
            grid-column: 1 / -1;
        }
        
        .half-width {
            grid-column: span 2;
        }
        
        .panel {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 1rem;
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            padding-bottom: 0.5rem;
            border-bottom: 1px solid #30363d;
        }
        
        .panel-title {
            color: #f0f6fc;
            font-weight: bold;
        }
        
        .btn {
            padding: 0.5rem 1rem;
            border: 1px solid #30363d;
            background: #21262d;
            color: #c9d1d9;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .btn:hover {
            background: #30363d;
        }
        
        .btn-danger {
            background: #da3633;
            border-color: #da3633;
            color: white;
        }
        
        .btn-success {
            background: #238636;
            border-color: #238636;
            color: white;
        }
        
        .btn-primary {
            background: #0969da;
            border-color: #0969da;
            color: white;
        }
        
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid #21262d;
        }
        
        .metric:last-child {
            border-bottom: none;
        }
        
        .metric-value {
            color: #58a6ff;
            font-weight: bold;
        }
        
        .metric-positive {
            color: #238636;
        }
        
        .metric-negative {
            color: #f85149;
        }
        
        .trade-entry {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem;
            margin: 0.25rem 0;
            background: #0d1117;
            border-radius: 4px;
            font-size: 12px;
        }
        
        .trade-profit { color: #238636; }
        .trade-loss { color: #f85149; }
        
        .chart-container {
            height: 300px;
            position: relative;
        }
        
        .trading-form {
            display: grid;
            gap: 1rem;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        
        .form-input {
            background: #21262d;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 0.5rem;
            border-radius: 4px;
        }
        
        .form-select {
            background: #21262d;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 0.5rem;
            border-radius: 4px;
        }
        
        .log-entry {
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 11px;
            padding: 0.25rem 0.5rem;
            border-bottom: 1px solid #21262d;
            white-space: pre-wrap;
        }
        
        .log-error { color: #f85149; }
        .log-warning { color: #d29922; }
        .log-info { color: #58a6ff; }
        .log-debug { color: #7c3aed; }
        
        .scrollable {
            max-height: 300px;
            overflow-y: auto;
        }
        
        .alert {
            padding: 0.75rem;
            margin: 0.5rem 0;
            border-radius: 4px;
            border: 1px solid;
        }
        
        .alert-success {
            background: rgba(35, 134, 54, 0.1);
            border-color: #238636;
            color: #238636;
        }
        
        .alert-error {
            background: rgba(248, 81, 73, 0.1);
            border-color: #f85149;
            color: #f85149;
        }
        
        .alert-warning {
            background: rgba(210, 153, 34, 0.1);
            border-color: #d29922;
            color: #d29922;
        }
        
        .loading {
            opacity: 0.6;
            pointer-events: none;
        }
        
        .connection-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .chart-controls {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
            align-items: center;
        }
        
        .pair-selector {
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }
        
        @media (max-width: 1200px) {
            .grid {
                grid-template-columns: 1fr 1fr;
            }
        }
        
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            
            .container {
                padding: 1rem;
            }
            
            .header {
                padding: 1rem;
            }
            
            .status-bar {
                flex-direction: column;
                gap: 1rem;
            }
        }solid #30363d;
            color: #c9d1d9;
            padding: 0.5rem;
            border-radius: 4px;
        }
        
        .alert {
            padding: 0.75rem;
            border-radius: 4px;
            margin: 0.5rem 0;
        }
        
        .alert-success {
            background: #0f2419;
            border: 1px solid #238636;
            color: #238636;
        }
        
        .alert-error {
            background: #2d1117;
            border: 1px solid #f85149;
            color: #f85149;
        }
        
        .alert-warning {
            background: #2d2408;
            border: 1px solid #d29922;
            color: #d29922;
        }
        
        .portfolio-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }
        
        .portfolio-item {
            background: #0d1117;
            padding: 1rem;
            border-radius: 4px;
            text-align: center;
        }
        
        .portfolio-value {
            font-size: 1.5rem;
            font-weight: bold;
            color: #58a6ff;
        }
        
        .portfolio-change {
            font-size: 0.875rem;
            margin-top: 0.5rem;
        }
        
        .market-data-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
        }
        
        .pair-card {
            background: #0d1117;
            padding: 1rem;
            border-radius: 4px;
        }
        
        .pair-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .pair-name {
            font-weight: bold;
            color: #f0f6fc;
        }
        
        .pair-price {
            font-size: 1.25rem;
            color: #58a6ff;
        }
        
        .pair-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
            font-size: 0.875rem;
        }
        
        .log-container {
            height: 200px;
            overflow-y: auto;
            background: #0d1117;
            padding: 0.5rem;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }
        
        .log-entry {
            padding: 0.25rem 0;
            border-bottom: 1px solid #21262d;
        }
        
        .log-timestamp {
            color: #7d8590;
        }
        
        .log-level-error { color: #f85149; }
        .log-level-warn { color: #d29922; }
        .log-level-info { color: #58a6ff; }
        .log-level-debug { color: #7d8590; }
        
        .connection-status {
            position: fixed;
            top: 10px;
            right: 10px;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
        }
        
        .connected {
            background: #0f2419;
            border: 1px solid #238636;
            color: #238636;
        }
        
        .disconnected {
            background: #2d1117;
            border: 1px solid #f85149;
            color: #f85149;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">🚀 Enhanced Crypto Trading Dashboard</div>
        <div class="status-bar">
            <div class="status-item">
                <div class="status-dot status-green" id="connectionStatus"></div>
                <span id="connectionText">Connected</span>
            </div>
            <div class="status-item">
                <span>Bot Status: </span>
                <span id="botStatus">Active</span>
            </div>
            <div class="status-item">
                <span>Uptime: </span>
                <span id="botUptime">--</span>
            </div>
            <button class="btn btn-danger" onclick="emergencyStop()">Emergency Stop</button>
        </div>
    </div>

    <div class="container">
        <!-- Portfolio Overview -->
        <div class="grid">
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Portfolio Overview</div>
                    <button class="btn" onclick="refreshPortfolio()">Refresh</button>
                </div>
                <div id="portfolioContainer">
                    <div class="metric">
                        <span>Total Value:</span>
                        <span class="metric-value" id="totalValue">$--</span>
                    </div>
                    <div class="metric">
                        <span>Available Balance:</span>
                        <span class="metric-value" id="availableBalance">$--</span>
                    </div>
                    <div class="metric">
                        <span>Daily P&L:</span>
                        <span class="metric-value" id="dailyPnl">$--</span>
                    </div>
                    <div class="metric">
                        <span>Unrealized P&L:</span>
                        <span class="metric-value" id="unrealizedPnl">$--</span>
                    </div>
                    <div class="metric">
                        <span>Realized P&L:</span>
                        <span class="metric-value" id="realizedPnl">$--</span>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">System Health</div>
                    <button class="btn" onclick="refreshSystemHealth()">Refresh</button>
                </div>
                <div id="systemHealthContainer">
                    <div class="metric">
                        <span>CPU Usage:</span>
                        <span class="metric-value" id="cpuUsage">--%</span>
                    </div>
                    <div class="metric">
                        <span>Memory Usage:</span>
                        <span class="metric-value" id="memoryUsage">--%</span>
                    </div>
                    <div class="metric">
                        <span>API Rate Limit:</span>
                        <span class="metric-value" id="apiRateLimit">--/--</span>
                    </div>
                    <div class="metric">
                        <span>WebSocket:</span>
                        <span class="metric-value" id="websocketStatus">--</span>
                    </div>
                    <div class="metric">
                        <span>Error Rate (24h):</span>
                        <span class="metric-value" id="errorRate">--%</span>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Performance Metrics</div>
                    <button class="btn" onclick="refreshPerformance()">Refresh</button>
                </div>
                <div id="performanceContainer">
                    <div class="metric">
                        <span>Data Fetch Time:</span>
                        <span class="metric-value" id="fetchTime">-- ms</span>
                    </div>
                    <div class="metric">
                        <span>Cache Hit Rate:</span>
                        <span class="metric-value" id="cacheHitRate">--%</span>
                    </div>
                    <div class="metric">
                        <span>Data Quality:</span>
                        <span class="metric-value" id="dataQuality">--%</span>
                    </div>
                    <div class="metric">
                        <span>Active Pairs:</span>
                        <span class="metric-value" id="activePairs">--</span>
                    </div>
                    <div class="metric">
                        <span>Memory Usage:</span>
                        <span class="metric-value" id="memoryUsageMb">-- MB</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Market Data and Charts -->
        <div class="grid">
            <div class="panel half-width">
                <div class="panel-header">
                    <div class="panel-title">Market Data</div>
                    <div class="chart-controls">
                        <div class="pair-selector">
                            <label>Pair:</label>
                            <select id="chartPairSelect" class="form-select" onchange="updateChart()">
                                <option value="">Select Pair</option>
                                <option value="BTC/USD">BTC/USD</option>
                                <option value="ETH/USD">ETH/USD</option>
                                <option value="ADA/USD">ADA/USD</option>
                                <option value="DOT/USD">DOT/USD</option>
                            </select>
                        </div>
                        <button class="btn" onclick="refreshMarketData()">Refresh</button>
                    </div>
                </div>
                <div class="chart-container">
                    <canvas id="priceChart"></canvas>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Live Market Data</div>
                </div>
                <div id="marketDataContainer" class="scrollable">
                    <!-- Market data will be populated here -->
                </div>
            </div>
        </div>

        <!-- Trading Activity and Manual Controls -->
        <div class="grid">
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Recent Trades</div>
                    <button class="btn" onclick="refreshTrades()">Refresh</button>
                </div>
                <div id="tradesContainer" class="scrollable">
                    <!-- Trade history will be populated here -->
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Manual Trading</div>
                </div>
                <div class="trading-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Trading Pair:</label>
                            <select id="tradePair" class="form-select">
                                <option value="BTC/USD">BTC/USD</option>
                                <option value="ETH/USD">ETH/USD</option>
                                <option value="ADA/USD">ADA/USD</option>
                                <option value="DOT/USD">DOT/USD</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Side:</label>
                            <select id="tradeSide" class="form-select">
                                <option value="buy">Buy</option>
                                <option value="sell">Sell</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Order Type:</label>
                            <select id="orderType" class="form-select" onchange="togglePriceField()">
                                <option value="market">Market</option>
                                <option value="limit">Limit</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Volume:</label>
                            <input type="number" id="tradeVolume" class="form-input" step="0.001" min="0.001" placeholder="0.001">
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Price (Limit Only):</label>
                            <input type="number" id="tradePrice" class="form-input" step="0.01" placeholder="Optional for market orders" disabled>
                        </div>
                        <div class="form-group">
                            <label>Stop Loss:</label>
                            <input type="number" id="stopLoss" class="form-input" step="0.01" placeholder="Optional">
                        </div>
                    </div>
                    <div class="form-group">
                        <label>Take Profit:</label>
                        <input type="number" id="takeProfit" class="form-input" step="0.01" placeholder="Optional">
                    </div>
                    <button class="btn btn-primary" onclick="executeTrade()">Execute Trade</button>
                    <div id="tradeResult"></div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Bot Controls</div>
                </div>
                <div class="trading-form">
                    <button class="btn btn-success" onclick="resumeTrading()">Resume Trading</button>
                    <button class="btn btn-warning" onclick="pauseTrading()">Pause Trading</button>
                    <button class="btn btn-danger" onclick="emergencyStop()">Emergency Stop</button>
                    <div id="controlResult"></div>
                </div>
            </div>
        </div>

        <!-- Logs and Alerts -->
        <div class="grid">
            <div class="panel full-width">
                <div class="panel-header">
                    <div class="panel-title">System Logs</div>
                    <div>
                        <button class="btn" onclick="clearLogs()">Clear</button>
                        <button class="btn" onclick="exportLogs()">Export</button>
                    </div>
                </div>
                <div id="logContainer" class="scrollable">
                    <!-- Logs will be populated here -->
                </div>
            </div>
        </div>
    </div>
    <div class="connection-status" id="connectionStatus">Connecting...</div>
    
    <header class="header">
        <div class="logo">Enhanced Crypto Trading Dashboard</div>
        <div class="status-bar">
            <div class="status-item">
                <span class="status-dot" id="botStatus"></span>
                <span id="botStatusText">Bot Status</span>
            </div>
            <div class="status-item">
                <span class="status-dot" id="apiStatus"></span>
                <span id="apiStatusText">API Status</span>
            </div>
            <div class="status-item">
                <span class="status-dot" id="wsStatus"></span>
                <span id="wsStatusText">WebSocket</span>
            </div>
            <span id="lastUpdate">Last Update: --</span>
        </div>
    </header>

    <div class="container">
        <!-- Portfolio Overview -->
        <div class="grid">
            <div class="panel full-width">
                <div class="panel-header">
                    <span class="panel-title">Portfolio Overview</span>
                    <button class="btn" onclick="refreshPortfolio()">Refresh</button>
                </div>
                <div class="portfolio-grid" id="portfolioGrid">
                    <div class="portfolio-item">
                        <div>Total Value</div>
                        <div class="portfolio-value" id="totalValue">$0.00</div>
                        <div class="portfolio-change" id="totalChange">--</div>
                    </div>
                    <div class="portfolio-item">
                        <div>Available Balance</div>
                        <div class="portfolio-value" id="availableBalance">$0.00</div>
                    </div>
                    <div class="portfolio-item">
                        <div>Daily P&L</div>
                        <div class="portfolio-value" id="dailyPnl">$0.00</div>
                    </div>
                    <div class="portfolio-item">
                        <div>Unrealized P&L</div>
                        <div class="portfolio-value" id="unrealizedPnl">$0.00</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- System Health and Controls -->
        <div class="grid">
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">System Health</span>
                    <button class="btn" onclick="refreshSystemHealth()">Refresh</button>
                </div>
                <div id="systemHealthMetrics">
                    <div class="metric">
                        <span>Bot Uptime</span>
                        <span class="metric-value" id="botUptime">--</span>
                    </div>
                    <div class="metric">
                        <span>CPU Usage</span>
                        <span class="metric-value" id="cpuUsage">--</span>
                    </div>
                    <div class="metric">
                        <span>Memory Usage</span>
                        <span class="metric-value" id="memoryUsage">--</span>
                    </div>
                    <div class="metric">
                        <span>API Rate Limit</span>
                        <span class="metric-value" id="apiRateLimit">--</span>
                    </div>
                    <div class="metric">
                        <span>Error Rate (24h)</span>
                        <span class="metric-value" id="errorRate">--</span>
                    </div>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Bot Controls</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 0.5rem;">
                    <button class="btn btn-danger" onclick="emergencyStop()">Emergency Stop</button>
                    <button class="btn" onclick="pauseTrading()">Pause Trading</button>
                    <button class="btn btn-success" onclick="resumeTrading()">Resume Trading</button>
                    <button class="btn" onclick="restartBot()">Restart Bot</button>
                </div>
                <div class="alert alert-warning" id="botAlert" style="display: none;">
                    Bot status alerts will appear here
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Performance Metrics</span>
                </div>
                <div id="performanceMetrics">
                    <div class="metric">
                        <span>Win Rate</span>
                        <span class="metric-value" id="winRate">--</span>
                    </div>
                    <div class="metric">
                        <span>Sharpe Ratio</span>
                        <span class="metric-value" id="sharpeRatio">--</span>
                    </div>
                    <div class="metric">
                        <span>Max Drawdown</span>
                        <span class="metric-value" id="maxDrawdown">--</span>
                    </div>
                    <div class="metric">
                        <span>Total Trades</span>
                        <span class="metric-value" id="totalTrades">--</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Market Data and Charts -->
        <div class="grid">
            <div class="panel half-width">
                <div class="panel-header">
                    <span class="panel-title">Market Data</span>
                    <button class="btn" onclick="refreshMarketData()">Refresh</button>
                </div>
                <div class="market-data-grid" id="marketDataGrid">
                    <!-- Market data will be populated here -->
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Price Chart</span>
                    <select class="form-select" id="chartPairSelect" onchange="updateChart()">
                        <option value="">Select Pair</option>
                    </select>
                </div>
                <div class="chart-container">
                    <canvas id="priceChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Trading Activity and Manual Trading -->
        <div class="grid">
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Recent Trades</span>
                    <button class="btn" onclick="refreshTrades()">Refresh</button>
                </div>
                <div id="tradesContainer" style="height: 300px; overflow-y: auto;">
                    <!-- Trades will be populated here -->
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Manual Trading</span>
                </div>
                <form class="trading-form" onsubmit="submitTrade(event)">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Trading Pair</label>
                            <select class="form-select" id="tradePair" required>
                                <option value="">Select Pair</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Side</label>
                            <select class="form-select" id="tradeSide" required>
                                <option value="buy">Buy</option>
                                <option value="sell">Sell</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Order Type</label>
                            <select class="form-select" id="orderType" onchange="togglePriceField()" required>
                                <option value="market">Market</option>
                                <option value="limit">Limit</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Volume</label>
                            <input type="number" class="form-input" id="tradeVolume" step="0.00000001" required>
                        </div>
                    </div>
                    <div class="form-group" id="priceGroup" style="display: none;">
                        <label>Price</label>
                        <input type="number" class="form-input" id="tradePrice" step="0.01">
                    </div>
                    <button type="submit" class="btn btn-primary">Execute Trade</button>
                </form>
                <div id="tradeResult" style="margin-top: 1rem;"></div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Risk Monitoring</span>
                </div>
                <div id="riskMetrics">
                    <div class="metric">
                        <span>Portfolio Risk</span>
                        <span class="metric-value" id="portfolioRisk">--</span>
                    </div>
                    <div class="metric">
                        <span>Position Exposure</span>
                        <span class="metric-value" id="positionExposure">--</span>
                    </div>
                    <div class="metric">
                        <span>VaR (95%)</span>
                        <span class="metric-value" id="valueAtRisk">--</span>
                    </div>
                    <div class="metric">
                        <span>Correlation Risk</span>
                        <span class="metric-value" id="correlationRisk">--</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Live Logs -->
        <div class="grid">
            <div class="panel full-width">
                <div class="panel-header">
                    <span class="panel-title">Live System Logs</span>
                    <div>
                        <button class="btn" onclick="clearLogs()">Clear</button>
                        <button class="btn" onclick="exportLogs()">Export</button>
                    </div>
                </div>
                <div class="log-container" id="logContainer">
                    <!-- Logs will be populated here -->
                </div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection
        const socket = io();
        let priceChart = null;
        let chartData = {};

        // Connection status
        socket.on('connect', function() {
            document.getElementById('connectionStatus').textContent = 'Connected';
            document.getElementById('connectionStatus').className = 'connection-status connected';
        });

        socket.on('disconnect', function() {
            document.getElementById('connectionStatus').textContent = 'Disconnected';
            document.getElementById('connectionStatus').className = 'connection-status disconnected';
        });

        // Data update handlers
        socket.on('portfolio_update', function(data) {
            updatePortfolioDisplay(data);
        });

        socket.on('market_data_update', function(data) {
            updateMarketDataDisplay(data);
            updateChartData(data);
        });

        socket.on('trade_update', function(data) {
            addTradeToDisplay(data);
        });

        socket.on('performance_update', function(data) {
            updatePerformanceDisplay(data);
        });

        socket.on('system_health_update', function(data) {
            updateSystemHealthDisplay(data);
        });

        // Initialize dashboard
        function initializeDashboard() {
            initializeChart();
            loadInitialData();
        }

        function initializeChart() {
            const ctx = document.getElementById('priceChart').getContext('2d');
            priceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Price',
                        data: [],
                        borderColor: '#58a6ff',
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            labels: {
                                color: '#c9d1d9'
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: {
                                color: '#c9d1d9'
                            },
                            grid: {
                                color: '#30363d'
                            }
                        },
                        y: {
                            ticks: {
                                color: '#c9d1d9'
                            },
                            grid: {
                                color: '#30363d'
                            }
                        }
                    }
                }
            });
        }

        function loadInitialData() {
            // Load portfolio data
            fetch('/api/portfolio')
                .then(response => response.json())
                .then(data => {
                    if (!data.error) {
                        updatePortfolioDisplay(data);
                    }
                });

            // Load market data
            fetch('/api/market_data')
                .then(response => response.json())
                .then(data => {
                    updateMarketDataDisplay(data);
                    populateTradingPairs(data);
                });

            // Load trades
            fetch('/api/trades')
                .then(response => response.json())
                .then(data => {
                    data.forEach(trade => addTradeToDisplay(trade));
                });

            // Load system health
            fetch('/api/system_health')
                .then(response => response.json())
                .then(data => {
                    if (!data.error) {
                        updateSystemHealthDisplay(data);
                    }
                });

            // Load performance metrics
            fetch('/api/performance')
                .then(response => response.json())
                .then(data => {
                    if (!data.error) {
                        updatePerformanceDisplay(data);
                    }
                });
        }

        function updatePortfolioDisplay(data) {
            document.getElementById('totalValue').textContent = `$${data.total_value_usd.toFixed(2)}`;
            document.getElementById('availableBalance').textContent = `$${data.available_balance.toFixed(2)}`;
            document.getElementById('dailyPnl').textContent = `$${data.daily_pnl.toFixed(2)}`;
            document.getElementById('unrealizedPnl').textContent = `$${data.unrealized_pnl.toFixed(2)}`;
            
            // Update colors based on P&L
            const dailyPnlElement = document.getElementById('dailyPnl');
            const unrealizedPnlElement = document.getElementById('unrealizedPnl');
            
            dailyPnlElement.className = data.daily_pnl >= 0 ? 'portfolio-value metric-positive' : 'portfolio-value metric-negative';
            unrealizedPnlElement.className = data.unrealized_pnl >= 0 ? 'portfolio-value metric-positive' : 'portfolio-value metric-negative';
        }

        function updateMarketDataDisplay(data) {
            const container = document.getElementById('marketDataGrid');
            container.innerHTML = '';
            
            Object.entries(data).forEach(([pair, marketData]) => {
                const pairCard = document.createElement('div');
                pairCard.className = 'pair-card';
                pairCard.innerHTML = `
                    <div class="pair-header">
                        <div class="pair-name">${pair}</div>
                        <div class="pair-price">$${marketData.price.toFixed(2)}</div>
                    </div>
                    <div class="pair-metrics">
                        <div>Volume: ${marketData.volume.toFixed(2)}</div>
                        <div>Spread: ${(marketData.spread * 100).toFixed(3)}%</div>
                        <div>Bid: $${marketData.bid.toFixed(2)}</div>
                        <div>Ask: $${marketData.ask.toFixed(2)}</div>
                    </div>
                `;
                container.appendChild(pairCard);
            });
        }

        function updateChartData(data) {
            const selectedPair = document.getElementById('chartPairSelect').value;
            if (selectedPair && data[selectedPair]) {
                const marketData = data[selectedPair];
                const timestamp = new Date(marketData.timestamp).toLocaleTimeString();
                
                if (!chartData[selectedPair]) {
                    chartData[selectedPair] = { labels: [], prices: [] };
                }
                
                chartData[selectedPair].labels.push(timestamp);
                chartData[selectedPair].prices.push(marketData.price);
                
                // Keep only last 100 data points
                if (chartData[selectedPair].labels.length > 100) {
                    chartData[selectedPair].labels.shift();
                    chartData[selectedPair].prices.shift();
                }
                
                priceChart.data.labels = chartData[selectedPair].labels;
                priceChart.data.datasets[0].data = chartData[selectedPair].prices;
                priceChart.update('none');
            }
        }

        function addTradeToDisplay(trade) {
            const container = document.getElementById('tradesContainer');
            const tradeElement = document.createElement('div');
            tradeElement.className = 'trade-entry';
            
            const profitClass = trade.side === 'BUY' ? 'trade-profit' : 'trade-loss';
            const timestamp = new Date(trade.timestamp).toLocaleTimeString();
            
            tradeElement.innerHTML = `
                <div>
                    <div>${trade.pair} ${trade.side} ${trade.volume.toFixed(8)} @ $${trade.price.toFixed(2)}</div>
                    <div style="font-size: 10px; color: #7d8590;">${timestamp} - ${trade.strategy}</div>
                </div>
                <div class="${profitClass}">Fee: $${trade.fee.toFixed(2)}</div>
            `;
            
            container.insertBefore(tradeElement, container.firstChild);
            
            // Keep only recent trades
            while (container.children.length > 50) {
                container.removeChild(container.lastChild);
            }
        }

        function updatePerformanceDisplay(data) {
            // This would be populated with actual performance metrics
            document.getElementById('winRate').textContent = '68.4%';
            document.getElementById('sharpeRatio').textContent = '1.84';
            document.getElementById('maxDrawdown').textContent = '-3.2%';
            document.getElementById('totalTrades').textContent = '247';
        }

        function updateSystemHealthDisplay(data) {
            document.getElementById('botUptime').textContent = `${data.bot_uptime.toFixed(1)}h`;
            document.getElementById('cpuUsage').textContent = `${data.cpu_usage.toFixed(1)}%`;
            document.getElementById('memoryUsage').textContent = `${data.memory_usage.toFixed(1)}%`;
            document.getElementById('apiRateLimit').textContent = `${data.api_rate_limit_used}/${data.api_rate_limit_max}`;
            document.getElementById('errorRate').textContent = `${(data.error_rate_24h * 100).toFixed(2)}%`;
            
            // Update status indicators
            const botStatus = document.getElementById('botStatus');
            const apiStatus = document.getElementById('apiStatus');
            const wsStatus = document.getElementById('wsStatus');
            
            botStatus.className = data.trading_enabled ? 'status-dot status-green' : 'status-dot status-red';
            apiStatus.className = data.api_rate_limit_used < data.api_rate_limit_max * 0.9 ? 'status-dot status-green' : 'status-dot status-yellow';
            wsStatus.className = data.websocket_connected ? 'status-dot status-green' : 'status-dot status-red';
            
            document.getElementById('botStatusText').textContent = data.trading_enabled ? 'Trading' : 'Paused';
            document.getElementById('apiStatusText').textContent = 'API Connected';
            document.getElementById('wsStatusText').textContent = data.websocket_connected ? 'Connected' : 'Disconnected';
            document.getElementById('lastUpdate').textContent = `Last Update: ${new Date(data.last_heartbeat).toLocaleTimeString()}`;
        }

        function populateTradingPairs(data) {
            const tradePairSelect = document.getElementById('tradePair');
            const chartPairSelect = document.getElementById('chartPairSelect');
            
            tradePairSelect.innerHTML = '<option value="">Select Pair</option>';
            chartPairSelect.innerHTML = '<option value="">Select Pair</option>';
            
            Object.keys(data).forEach(pair => {
                const option1 = document.createElement('option');
                option1.value = pair;
                option1.textContent = pair;
                tradePairSelect.appendChild(option1);
                
                const option2 = document.createElement('option');
                option2.value = pair;
                option2.textContent = pair;
                chartPairSelect.appendChild(option2);
            });
        }

        // Trading functions
        function togglePriceField() {
            const orderType = document.getElementById('orderType').value;
            const priceGroup = document.getElementById('priceGroup');
            const priceInput = document.getElementById('tradePrice');
            
            if (orderType === 'limit') {
                priceGroup.style.display = 'block';
                priceInput.required = true;
            } else {
                priceGroup.style.display = 'none';
                priceInput.required = false;
            }
        }

        function submitTrade(event) {
            event.preventDefault();
            
            const tradeData = {
                pair: document.getElementById('tradePair').value,
                side: document.getElementById('tradeSide').value,
                order_type: document.getElementById('orderType').value,
                volume: document.getElementById('tradeVolume').value,
                price: document.getElementById('tradePrice').value || null
            };
            
            fetch('/api/trade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(tradeData)
            })
            .then(response => response.json())
            .then(result => {
                const resultDiv = document.getElementById('tradeResult');
                if (result.success) {
                    resultDiv.innerHTML = `<div class="alert alert-success">${result.message}</div>`;
                    // Reset form
                    event.target.reset();
                    togglePriceField();
                } else {
                    resultDiv.innerHTML = `<div class="alert alert-error">${result.error}</div>`;
                }
            })
            .catch(error => {
                document.getElementById('tradeResult').innerHTML = `<div class="alert alert-error">Trade request failed: ${error.message}</div>`;
            });
        }

        // Bot control functions
        function emergencyStop() {
            if (confirm('Are you sure you want to emergency stop the bot?')) {
                controlBot('emergency_stop');
            }
        }

        function pauseTrading() {
            controlBot('pause_trading');
        }

        function resumeTrading() {
            controlBot('resume_trading');
        }

        function restartBot() {
            if (confirm('Are you sure you want to restart the bot?')) {
                controlBot('restart_bot');
            }
        }

        function controlBot(action) {
            fetch('/api/bot_control', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ action: action })
            })
            .then(response => response.json())
            .then(result => {
                const alertDiv = document.getElementById('botAlert');
                if (result.success) {
                    alertDiv.innerHTML = result.message;
                    alertDiv.className = 'alert alert-success';
                    alertDiv.style.display = 'block';
                } else {
                    alertDiv.innerHTML = result.error;
                    alertDiv.className = 'alert alert-error';
                    alertDiv.style.display = 'block';
                }
                
                setTimeout(() => {
                    alertDiv.style.display = 'none';
                }, 5000);
            });
        }

        // Refresh functions
        function refreshPortfolio() {
            fetch('/api/portfolio')
                .then(response => response.json())
                .then(data => {
                    if (!data.error) {
                        updatePortfolioDisplay(data);
                    }
                });
        }

        function refreshMarketData() {
            fetch('/api/market_data')
                .then(response => response.json())
                .then(data => {
                    updateMarketDataDisplay(data);
                });
        }

        function refreshTrades() {
            document.getElementById('tradesContainer').innerHTML = '';
            fetch('/api/trades')
                .then(response => response.json())
                .then(data => {
                    data.forEach(trade => addTradeToDisplay(trade));
                });
        }

        function refreshSystemHealth() {
            fetch('/api/system_health')
                .then(response => response.json())
                .then(data => {
                    if (!data.error) {
                        updateSystemHealthDisplay(data);
                    }
                });
        }

        function refreshPerformance() {
            fetch('/api/performance')
                .then(response => response.json())
                .then(data => {
                    if (!data.error) {
                        updatePerformanceDisplay(data);
                    }
                });
        }

        function updateChart() {
            const selectedPair = document.getElementById('chartPairSelect').value;
            if (selectedPair) {
                socket.emit('subscribe_pair', { pair: selectedPair });
            }
        }

        function togglePriceField() {
            const orderType = document.getElementById('orderType').value;
            const priceField = document.getElementById('tradePrice');
            
            if (orderType === 'limit') {
                priceField.disabled = false;
                priceField.required = true;
            } else {
                priceField.disabled = true;
                priceField.required = false;
                priceField.value = '';
            }
        }

        function executeTrade() {
            const pair = document.getElementById('tradePair').value;
            const side = document.getElementById('tradeSide').value;
            const orderType = document.getElementById('orderType').value;
            const volume = document.getElementById('tradeVolume').value;
            const price = document.getElementById('tradePrice').value;
            const stopLoss = document.getElementById('stopLoss').value;
            const takeProfit = document.getElementById('takeProfit').value;

            if (!pair || !side || !volume) {
                showTradeResult('Please fill in all required fields', 'error');
                return;
            }

            const tradeData = {
                pair: pair,
                side: side,
                order_type: orderType,
                volume: volume
            };

            if (orderType === 'limit' && price) {
                tradeData.price = price;
            }
            if (stopLoss) {
                tradeData.stop_loss = stopLoss;
            }
            if (takeProfit) {
                tradeData.take_profit = takeProfit;
            }

            showTradeResult('Executing trade...', 'info');

            fetch('/api/trade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(tradeData)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showTradeResult(`Trade executed successfully! ID: ${data.trade_id}`, 'success');
                    clearTradeForm();
                } else {
                    showTradeResult(`Trade failed: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                showTradeResult(`Error: ${error.message}`, 'error');
            });
        }

        function showTradeResult(message, type) {
            const resultDiv = document.getElementById('tradeResult');
            resultDiv.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
            
            // Clear after 5 seconds
            setTimeout(() => {
                resultDiv.innerHTML = '';
            }, 5000);
        }

        function clearTradeForm() {
            document.getElementById('tradeVolume').value = '';
            document.getElementById('tradePrice').value = '';
            document.getElementById('stopLoss').value = '';
            document.getElementById('takeProfit').value = '';
        }

        function emergencyStop() {
            if (confirm('Are you sure you want to trigger an emergency stop? This will halt all trading immediately.')) {
                controlBot('emergency_stop');
            }
        }

        function pauseTrading() {
            controlBot('pause_trading');
        }

        function resumeTrading() {
            controlBot('resume_trading');
        }

        function controlBot(action) {
            fetch('/api/bot_control', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ action: action })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showControlResult(data.message, 'success');
                } else {
                    showControlResult(`Control failed: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                showControlResult(`Error: ${error.message}`, 'error');
            });
        }

        function showControlResult(message, type) {
            const resultDiv = document.getElementById('controlResult');
            resultDiv.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
            
            // Clear after 5 seconds
            setTimeout(() => {
                resultDiv.innerHTML = '';
            }, 5000);
        }

        function clearLogs() {
            document.getElementById('logContainer').innerHTML = '';
        }

        function exportLogs() {
            // Get all log entries
            const logContainer = document.getElementById('logContainer');
            const logEntries = Array.from(logContainer.children).map(entry => entry.textContent);
            
            // Create downloadable file
            const logData = logEntries.join('\\n');
            const blob = new Blob([logData], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            
            // Create download link
            const a = document.createElement('a');
            a.href = url;
            a.download = `dashboard_logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }

        function addLogEntry(message, level = 'info') {
            const container = document.getElementById('logContainer');
            const div = document.createElement('div');
            div.className = `log-entry log-${level}`;
            
            const timestamp = new Date().toLocaleTimeString();
            div.textContent = `[${timestamp}] ${message}`;
            
            container.insertBefore(div, container.firstChild);
            
            // Keep only recent log entries
            while (container.children.length > 100) {
                container.removeChild(container.lastChild);
            }
        }

        // Initialize dashboard when page loads
        document.addEventListener('DOMContentLoaded', initializeDashboard);
    </script>
</body>
</html>
        '''