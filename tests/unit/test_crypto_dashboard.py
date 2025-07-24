"""
Unit tests for the crypto dashboard update module.
"""
import os
import unittest
from unittest.mock import patch, MagicMock
import datetime
import tempfile
import json
import shutil

from bot.crypto_logger import (
    CryptoLogger, CryptoTradeRecord, CryptoBalanceRecord, CryptoMetricsRecord
)
from bot.crypto_dashboard import (
    update_tech_dashboard, update_cfo_dashboard, generate_crypto_metrics_report,
    _update_system_health_metrics, _update_recent_trades, _add_crypto_metrics_panel,
    _update_crypto_metrics_panel, _update_cfo_kpi_metrics, _update_financial_summary
)


class TestCryptoDashboard(unittest.TestCase):
    """Test cases for the crypto dashboard update module."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()
        
        # Create a temporary log directory
        self.test_log_dir = os.path.join(self.test_dir, "logs")
        os.makedirs(self.test_log_dir, exist_ok=True)
        
        # Create logger with rich disabled for testing
        self.logger = CryptoLogger(
            log_dir=self.test_log_dir,
            use_rich=False,
            metrics_interval_seconds=1  # Short interval for testing
        )
        
        # Sample data for testing
        self.sample_crypto_trade = CryptoTradeRecord(
            order_id="test-order-123",
            symbol="BTC/USD",
            side="BUY",
            quantity=0.001,
            price=50000.0,
            timestamp=datetime.datetime.now(),
            status="FILLED",
            product_id="BTC-USD",
            base_currency="BTC",
            quote_currency="USD",
            fees=0.5,
            fee_currency="USD",
            network_fee=0.0,
            exchange_fee=0.5,
            trade_type="spot"
        )
        
        self.sample_balance = CryptoBalanceRecord(
            currency="BTC",
            available=0.001,
            hold=0.0,
            total=0.001,
            usd_value=50.0,
            timestamp=datetime.datetime.now()
        )
        
        # Add sample data to logger
        self.logger.log_crypto_trade(self.sample_crypto_trade)
        self.logger.log_balance_update(self.sample_balance)
        
        # Add ETH balance
        eth_balance = CryptoBalanceRecord(
            currency="ETH",
            available=0.02,
            hold=0.0,
            total=0.02,
            usd_value=30.0,
            timestamp=datetime.datetime.now()
        )
        self.logger.log_balance_update(eth_balance)
        
        # Add some metrics history
        metrics1 = CryptoMetricsRecord(
            timestamp=datetime.datetime.now(),
            api_calls=100,
            api_errors=2,
            api_latency_ms=50.0,
            websocket_messages=500,
            websocket_errors=1,
            trades_executed=5,
            trade_volume_usd=1000.0,
            rate_limit_hits=1
        )
        
        metrics2 = CryptoMetricsRecord(
            timestamp=datetime.datetime.now(),
            api_calls=150,
            api_errors=3,
            api_latency_ms=60.0,
            websocket_messages=600,
            websocket_errors=2,
            trades_executed=7,
            trade_volume_usd=1500.0,
            rate_limit_hits=2
        )
        
        self.logger.metrics_history = [metrics1, metrics2]
        self.logger.metrics_interval_seconds = 60  # 1 minute
        
        # Create sample dashboard files
        self.tech_dashboard_path = os.path.join(self.test_dir, "tech_dashboard.html")
        self.cfo_dashboard_path = os.path.join(self.test_dir, "cfo_dashboard.html")
        
        # Copy sample dashboard content
        with open(self.tech_dashboard_path, 'w') as f:
            f.write(self._get_sample_tech_dashboard())
        
        with open(self.cfo_dashboard_path, 'w') as f:
            f.write(self._get_sample_cfo_dashboard())
    
    def tearDown(self):
        """Clean up after each test."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)
    
    def _get_sample_tech_dashboard(self) -> str:
        """Get sample tech dashboard HTML."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Tech Admin Dashboard</title>
        </head>
        <body>
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">System Health</span>
                    <button class="btn">Refresh</button>
                </div>
                <div class="metric">
                    <span>API Rate Limit</span>
                    <span class="metric-value">847 / 1000</span>
                </div>
                <div class="metric">
                    <span>Last Heartbeat</span>
                    <span class="metric-value">2s ago</span>
                </div>
                <div class="metric">
                    <span>Error Rate (24h)</span>
                    <span class="metric-value">0.03%</span>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-header">
                    <span class="panel-title">Recent Trades (Last 10)</span>
                    <button class="btn">View All</button>
                </div>
                <div class="trade-entry">
                    <div>
                        <div>AAPL BUY 25 @ $178.45</div>
                        <div style="font-size: 10px; color: #7d8590;">14:23:45</div>
                    </div>
                    <div class="trade-profit">+$127.50</div>
                </div>
            </div>
            <!-- Configuration -->
            
            <div class="panel full-width">
                <div class="panel-header">
                    <span class="panel-title">Database & Infrastructure</span>
                    <button class="btn">Run Diagnostics</button>
                </div>
            </div>
        </body>
        </html>
        """
    
    def _get_sample_cfo_dashboard(self) -> str:
        """Get sample CFO dashboard HTML."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>CFO Dashboard</title>
        </head>
        <body>
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-title">Total Assets Under Management</div>
                    <div class="kpi-value">$2,847,392</div>
                    <div class="kpi-change positive">
                        ↗ +$127,483 (+4.69%) this month
                    </div>
                </div>
            </div>
            
            <!-- Main Content Grid -->
            <div class="panel">
                <div class="panel-header">
                    <h3 class="panel-title">Financial Summary</h3>
                </div>
                <div class="panel-content">
                    <div class="metric-row">
                        <span class="metric-label">Gross Profit (YTD)</span>
                        <span class="metric-value positive">$532,583</span>
                    </div>
                </div>
                
                <div class="alert alert-info">
                    💡 Q4 investor statements ready for review.
                </div>
            </div>
        </body>
        </html>
        """
    
    def test_update_tech_dashboard(self):
        """Test updating the tech dashboard."""
        # Update the dashboard
        result = update_tech_dashboard(self.tech_dashboard_path, self.logger)
        
        # Check that update was successful
        self.assertTrue(result)
        
        # Read updated dashboard
        with open(self.tech_dashboard_path, 'r') as f:
            updated_html = f.read()
        
        # Check that crypto metrics were added
        self.assertIn("Crypto Trading Metrics", updated_html)
        self.assertIn("Portfolio Value", updated_html)
        self.assertIn("API Calls/min", updated_html)
        
        # Check that system health metrics were updated
        self.assertIn("api_errors_rate", str(self.logger.get_performance_metrics()))
        error_rate = self.logger.get_performance_metrics()["api_errors_rate"] * 100
        self.assertIn(f"{error_rate:.2f}%", updated_html)
    
    def test_update_cfo_dashboard(self):
        """Test updating the CFO dashboard."""
        # Update the dashboard
        result = update_cfo_dashboard(self.cfo_dashboard_path, self.logger)
        
        # Check that update was successful
        self.assertTrue(result)
        
        # Read updated dashboard
        with open(self.cfo_dashboard_path, 'r') as f:
            updated_html = f.read()
        
        # Check that crypto allocation was added
        self.assertIn("Crypto Allocation", updated_html)
        
        # Check that financial summary was updated
        self.assertIn("Crypto Trading Volume", updated_html)
        self.assertIn("Crypto Trading Fees", updated_html)
    
    def test_generate_crypto_metrics_report(self):
        """Test generating a crypto metrics report."""
        # Generate report
        report_path = os.path.join(self.test_dir, "metrics_report.json")
        result = generate_crypto_metrics_report(report_path, self.logger)
        
        # Check that report generation was successful
        self.assertTrue(result)
        
        # Check that report file was created
        self.assertTrue(os.path.exists(report_path))
        
        # Check report contents
        with open(report_path, 'r') as f:
            report = json.load(f)
        
        self.assertIn("portfolio", report)
        self.assertIn("performance", report)
        self.assertIn("metrics_history", report)
    
    def test_update_system_health_metrics(self):
        """Test updating system health metrics."""
        # Get sample HTML
        html = self._get_sample_tech_dashboard()
        
        # Get metrics
        metrics = self.logger.get_performance_metrics()
        
        # Update metrics
        updated_html = _update_system_health_metrics(html, metrics)
        
        # Check that metrics were updated
        self.assertIn(f"{metrics['api_calls_per_minute'] * 10:.0f} / 1000", updated_html)
        self.assertIn(f"{metrics['api_errors_rate'] * 100:.2f}%", updated_html)
    
    def test_update_recent_trades(self):
        """Test updating recent trades."""
        # Get sample HTML
        html = self._get_sample_tech_dashboard()
        
        # Update trades
        updated_html = _update_recent_trades(html, [self.sample_crypto_trade])
        
        # Check that trades were updated
        self.assertIn("BTC/USD BUY", updated_html)
        self.assertIn("0.00100000", updated_html)
        self.assertIn("$50000.00", updated_html)
    
    def test_add_crypto_metrics_panel(self):
        """Test adding a crypto metrics panel."""
        # Get sample HTML
        html = self._get_sample_tech_dashboard()
        
        # Get metrics and portfolio
        metrics = self.logger.get_performance_metrics()
        portfolio = self.logger.get_portfolio_summary()
        
        # Add crypto metrics panel
        updated_html = _add_crypto_metrics_panel(html, metrics, portfolio)
        
        # Check that panel was added
        self.assertIn("Crypto Trading Metrics", updated_html)
        self.assertIn("Portfolio Value", updated_html)
        self.assertIn(f"${portfolio['total_usd_value']:.2f}", updated_html)
    
    def test_update_crypto_metrics_panel(self):
        """Test updating the crypto metrics panel."""
        # Get sample HTML with crypto panel
        html = self._get_sample_tech_dashboard()
        metrics = self.logger.get_performance_metrics()
        portfolio = self.logger.get_portfolio_summary()
        html = _add_crypto_metrics_panel(html, metrics, portfolio)
        
        # Update metrics and portfolio
        new_metrics = metrics.copy()
        new_metrics["api_calls_per_minute"] = 200.0
        new_portfolio = portfolio.copy()
        new_portfolio["total_usd_value"] = 100.0
        
        # Update crypto metrics panel
        updated_html = _update_crypto_metrics_panel(html, new_metrics, new_portfolio)
        
        # Check that panel was updated
        self.assertIn("$100.00", updated_html)
        self.assertIn("200.0", updated_html)
    
    def test_update_cfo_kpi_metrics(self):
        """Test updating CFO KPI metrics."""
        # Get sample HTML
        html = self._get_sample_cfo_dashboard()
        
        # Get portfolio
        portfolio = self.logger.get_portfolio_summary()
        
        # Update KPI metrics
        updated_html = _update_cfo_kpi_metrics(html, portfolio)
        
        # Check that metrics were updated
        self.assertIn(f"${portfolio['total_usd_value']:,.2f}", updated_html)
        self.assertIn("Crypto Allocation", updated_html)
        self.assertIn("BTC", updated_html)
        self.assertIn("ETH", updated_html)
    
    def test_update_financial_summary(self):
        """Test updating financial summary."""
        # Get sample HTML
        html = self._get_sample_cfo_dashboard()
        
        # Get metrics and portfolio
        metrics = self.logger.get_performance_metrics()
        portfolio = self.logger.get_portfolio_summary()
        
        # Update financial summary
        updated_html = _update_financial_summary(html, metrics, portfolio)
        
        # Check that summary was updated
        self.assertIn("Crypto Trading Volume", updated_html)
        self.assertIn("Crypto Trading Fees", updated_html)


if __name__ == "__main__":
    unittest.main()