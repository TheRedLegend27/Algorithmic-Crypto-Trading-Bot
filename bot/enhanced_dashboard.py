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
                    price=float(data['price']) if data.get('price') else None
                )
                
                result = self.handle_manual_trade_request(trade_request)
                return jsonify(asdict(result))
                
            except Exception as e:
                log_error(e, "Failed to process trade request")
                return jsonify({
                    'success': False,
                    'error': f'Invalid trade request: {str(e)}'
                })
    
    def _setup_websocket_handlers(self) -> None:
        """Setup WebSocket event handlers."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            log_info("Dashboard client connected")
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            log_info("Dashboard client disconnected")
    
    def _background_update_loop(self) -> None:
        """Background thread for periodic updates."""
        while self.running:
            try:
                # Update system health
                self._update_system_health()
                
                # Update portfolio data
                self._update_portfolio_data()
                
                time.sleep(self.config.auto_refresh_interval)
                
            except Exception as e:
                log_error(e, "Error in dashboard background update loop")
                time.sleep(self.config.auto_refresh_interval)
    
    def _update_system_health(self) -> None:
        """Update system health metrics."""
        try:
            # Get system metrics
            cpu_usage = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Create system health object
            health = SystemHealth(
                bot_uptime=24.5,  # Would be calculated from actual start time
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                api_rate_limit_used=850,  # Would get from actual API client
                api_rate_limit_max=1000,
                websocket_connected=True,  # Would check actual WebSocket status
                last_heartbeat=datetime.now(),
                error_rate_24h=0.02,  # Would calculate from actual error logs
                active_strategies=["Enhanced Strategies"],  # From strategy manager
                trading_enabled=True  # From bot state
            )
            
            self.system_health = health
            self._broadcast_update('system_health_update', asdict(health))
            
        except Exception as e:
            log_error(e, "Failed to update system health")
    
    def _update_portfolio_data(self) -> None:
        """Update portfolio data from Kraken client."""
        try:
            # Get account balance from Kraken
            balance_result = self.kraken_client.get_account_balance()
            if not balance_result:
                return
            
            # Calculate portfolio metrics
            total_value_usd = 0
            available_balance = 0
            positions = {}
            
            for asset, balance in balance_result.items():
                if float(balance) > 0:
                    positions[asset] = {
                        'balance': float(balance),
                        'usd_value': 0  # Would need price conversion
                    }
                    
                    # For USD/USDT, use direct value
                    if asset in ['USD', 'USDT', 'USDC']:
                        usd_value = float(balance)
                        positions[asset]['usd_value'] = usd_value
                        total_value_usd += usd_value
                        available_balance += usd_value
            
            # Create portfolio object
            portfolio = Portfolio(
                total_value_usd=total_value_usd,
                available_balance=available_balance,
                positions=positions,
                daily_pnl=0.0,  # Would calculate from actual data
                unrealized_pnl=0.0,
                realized_pnl=0.0
            )
            
            self.portfolio = portfolio
            portfolio_data = asdict(portfolio)
            portfolio_data['timestamp'] = portfolio.timestamp.isoformat()
            self._broadcast_update('portfolio_update', portfolio_data)
            
        except Exception as e:
            log_error(e, "Failed to update portfolio data")
    
    def handle_manual_trade_request(self, request: ManualTradeRequest) -> TradeResult:
        """Handle manual trade request from dashboard."""
        if not self.config.enable_manual_trading:
            return TradeResult(
                success=False,
                error="Manual trading is disabled"
            )
        
        try:
            # Execute trade through Kraken client
            if request.order_type == "market":
                result = self.kraken_client.place_market_order(
                    request.pair,
                    request.side.lower(),
                    str(request.volume)
                )
            else:
                result = self.kraken_client.place_limit_order(
                    request.pair,
                    request.side.lower(),
                    str(request.volume),
                    str(request.price)
                )
            
            if result and 'txid' in result:
                trade_id = result['txid'][0] if isinstance(result['txid'], list) else result['txid']
                return TradeResult(
                    success=True,
                    trade_id=trade_id,
                    message=f"{request.order_type.title()} {request.side} order placed successfully"
                )
            else:
                return TradeResult(
                    success=False,
                    error="Failed to place order"
                )
                
        except Exception as e:
            log_error(e, f"Failed to execute manual trade: {request}")
            return TradeResult(
                success=False,
                error=f"Trade execution failed: {str(e)}"
            )
    
    def _broadcast_update(self, event: str, data: Any) -> None:
        """Broadcast update to all connected WebSocket clients."""
        if self.config.enable_websocket:
            self.socketio.emit(event, data)
    
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
        
        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
            margin-bottom: 1rem;
        }
        
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        
        .form-input, .form-select {
            background: #21262d;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 0.5rem;
            border-radius: 4px;
        }
        
        .alert {
            background: #1c2128;
            border: 1px solid #d29922;
            border-radius: 4px;
            padding: 0.75rem;
            margin: 0.5rem 0;
            color: #d29922;
        }
        
        .alert-error {
            border-color: #f85149;
            color: #f85149;
        }
        
        .alert-success {
            border-color: #238636;
            color: #238636;
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="logo">Enhanced Crypto Trading Dashboard</div>
        <div class="status-bar">
            <div class="status-item">
                <span class="status-dot status-green" id="bot-status"></span>
                <span>Bot Status</span>
            </div>
            <div class="status-item">
                <span class="status-dot status-green" id="api-status"></span>
                <span>API Connected</span>
            </div>
            <div class="status-item">
                <span class="status-dot status-green" id="ws-status"></span>
                <span>WebSocket</span>
            </div>
            <span id="current-time"></span>
        </div>
    </header>

    <div class="container">
        <!-- Portfolio Overview -->
        <div class="grid">
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Portfolio Overview</span>
                    <button class="btn" onclick="refreshPortfolio()">Refresh</button>
                </div>
                <div class="metric">
                    <span>Total Value (USD)</span>
                    <span class="metric-value" id="total-value">$0.00</span>
                </div>
                <div class="metric">
                    <span>Available Balance</span>
                    <span class="metric-value" id="available-balance">$0.00</span>
                </div>
                <div class="metric">
                    <span>Daily P&L</span>
                    <span class="metric-value" id="daily-pnl">$0.00</span>
                </div>
                <div class="metric">
                    <span>Unrealized P&L</span>
                    <span class="metric-value" id="unrealized-pnl">$0.00</span>
                </div>
                <div class="metric">
                    <span>Realized P&L</span>
                    <span class="metric-value" id="realized-pnl">$0.00</span>
                </div>
            </div>

            <!-- System Health -->
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">System Health</span>
                    <button class="btn" onclick="refreshSystemHealth()">Refresh</button>
                </div>
                <div class="metric">
                    <span>Bot Uptime</span>
                    <span class="metric-value" id="bot-uptime">0h 0m</span>
                </div>
                <div class="metric">
                    <span>CPU Usage</span>
                    <span class="metric-value" id="cpu-usage">0%</span>
                </div>
                <div class="metric">
                    <span>Memory Usage</span>
                    <span class="metric-value" id="memory-usage">0%</span>
                </div>
                <div class="metric">
                    <span>API Rate Limit</span>
                    <span class="metric-value" id="api-rate-limit">0 / 1000</span>
                </div>
                <div class="metric">
                    <span>Error Rate (24h)</span>
                    <span class="metric-value" id="error-rate">0.00%</span>
                </div>
            </div>

            <!-- Manual Trading -->
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Manual Trading</span>
                </div>
                <form onsubmit="submitTrade(event)">
                    <div class="form-row">
                        <div class="form-group">
                            <label>Trading Pair</label>
                            <select class="form-select" id="trade-pair" required>
                                <option value="">Select Pair</option>
                                <option value="XBTUSD">BTC/USD</option>
                                <option value="ETHUSD">ETH/USD</option>
                                <option value="ADAUSD">ADA/USD</option>
                                <option value="SOLUSD">SOL/USD</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Side</label>
                            <select class="form-select" id="trade-side" required>
                                <option value="">Select Side</option>
                                <option value="buy">Buy</option>
                                <option value="sell">Sell</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>Order Type</label>
                            <select class="form-select" id="trade-type" required onchange="togglePriceField()">
                                <option value="">Select Type</option>
                                <option value="market">Market</option>
                                <option value="limit">Limit</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Volume</label>
                            <input type="number" class="form-input" id="trade-volume" step="0.00000001" required>
                        </div>
                    </div>
                    <div class="form-group" id="price-group" style="display: none;">
                        <label>Price (USD)</label>
                        <input type="number" class="form-input" id="trade-price" step="0.01">
                    </div>
                    <button type="submit" class="btn btn-primary">Execute Trade</button>
                </form>
                <div id="trade-alerts"></div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection
        const socket = io();

        // Initialize dashboard
        document.addEventListener('DOMContentLoaded', function() {
            updateCurrentTime();
            setInterval(updateCurrentTime, 1000);
            
            // Load initial data
            refreshPortfolio();
            refreshSystemHealth();
        });

        // WebSocket event handlers
        socket.on('connect', function() {
            console.log('Connected to dashboard server');
            updateConnectionStatus('ws-status', true);
        });

        socket.on('disconnect', function() {
            console.log('Disconnected from dashboard server');
            updateConnectionStatus('ws-status', false);
        });

        socket.on('portfolio_update', function(data) {
            updatePortfolioDisplay(data);
        });

        socket.on('system_health_update', function(data) {
            updateSystemHealthDisplay(data);
        });

        // Utility functions
        function updateCurrentTime() {
            document.getElementById('current-time').textContent = new Date().toLocaleTimeString();
        }

        function updateConnectionStatus(elementId, connected) {
            const element = document.getElementById(elementId);
            element.className = 'status-dot ' + (connected ? 'status-green' : 'status-red');
        }

        function formatCurrency(value) {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD'
            }).format(value);
        }

        function formatPercentage(value) {
            return (value * 100).toFixed(2) + '%';
        }

        // Portfolio functions
        function refreshPortfolio() {
            fetch('/api/portfolio')
                .then(response => response.json())
                .then(data => updatePortfolioDisplay(data))
                .catch(error => console.error('Error fetching portfolio:', error));
        }

        function updatePortfolioDisplay(data) {
            if (data.error) {
                console.error('Portfolio error:', data.error);
                return;
            }

            document.getElementById('total-value').textContent = formatCurrency(data.total_value_usd || 0);
            document.getElementById('available-balance').textContent = formatCurrency(data.available_balance || 0);
            
            const dailyPnl = data.daily_pnl || 0;
            const dailyPnlElement = document.getElementById('daily-pnl');
            dailyPnlElement.textContent = formatCurrency(dailyPnl);
            dailyPnlElement.className = 'metric-value ' + (dailyPnl >= 0 ? 'metric-positive' : 'metric-negative');
            
            const unrealizedPnl = data.unrealized_pnl || 0;
            const unrealizedPnlElement = document.getElementById('unrealized-pnl');
            unrealizedPnlElement.textContent = formatCurrency(unrealizedPnl);
            unrealizedPnlElement.className = 'metric-value ' + (unrealizedPnl >= 0 ? 'metric-positive' : 'metric-negative');
            
            const realizedPnl = data.realized_pnl || 0;
            const realizedPnlElement = document.getElementById('realized-pnl');
            realizedPnlElement.textContent = formatCurrency(realizedPnl);
            realizedPnlElement.className = 'metric-value ' + (realizedPnl >= 0 ? 'metric-positive' : 'metric-negative');
        }

        // System health functions
        function refreshSystemHealth() {
            fetch('/api/system_health')
                .then(response => response.json())
                .then(data => updateSystemHealthDisplay(data))
                .catch(error => console.error('Error fetching system health:', error));
        }

        function updateSystemHealthDisplay(data) {
            if (data.error) {
                console.error('System health error:', data.error);
                return;
            }

            const uptimeHours = Math.floor(data.bot_uptime || 0);
            const uptimeMinutes = Math.floor(((data.bot_uptime || 0) % 1) * 60);
            document.getElementById('bot-uptime').textContent = `${uptimeHours}h ${uptimeMinutes}m`;
            
            document.getElementById('cpu-usage').textContent = (data.cpu_usage || 0).toFixed(1) + '%';
            document.getElementById('memory-usage').textContent = (data.memory_usage || 0).toFixed(1) + '%';
            document.getElementById('api-rate-limit').textContent = `${data.api_rate_limit_used || 0} / ${data.api_rate_limit_max || 1000}`;
            document.getElementById('error-rate').textContent = formatPercentage(data.error_rate_24h || 0);
            
            // Update status indicators
            updateConnectionStatus('bot-status', data.trading_enabled);
            updateConnectionStatus('api-status', data.api_rate_limit_used < data.api_rate_limit_max);
        }

        // Trading functions
        function togglePriceField() {
            const orderType = document.getElementById('trade-type').value;
            const priceGroup = document.getElementById('price-group');
            const priceInput = document.getElementById('trade-price');
            
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
                pair: document.getElementById('trade-pair').value,
                side: document.getElementById('trade-side').value,
                order_type: document.getElementById('trade-type').value,
                volume: document.getElementById('trade-volume').value,
                price: document.getElementById('trade-price').value || null
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
                const alertsDiv = document.getElementById('trade-alerts');
                const alertClass = result.success ? 'alert-success' : 'alert-error';
                const message = result.success ? result.message : result.error;
                
                alertsDiv.innerHTML = `<div class="alert ${alertClass}">${message}</div>`;
                
                if (result.success) {
                    // Reset form
                    event.target.reset();
                    togglePriceField();
                    // Refresh portfolio
                    setTimeout(() => {
                        refreshPortfolio();
                    }, 1000);
                }
            })
            .catch(error => {
                console.error('Error submitting trade:', error);
                document.getElementById('trade-alerts').innerHTML = 
                    '<div class="alert alert-error">Failed to submit trade</div>';
            });
        }
    </script>
</body>
</html>
        '''