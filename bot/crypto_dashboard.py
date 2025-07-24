"""
Crypto dashboard update module for the trading bot.

This module provides functionality to update HTML dashboards with
cryptocurrency trading metrics and performance data.

Functions:
    update_tech_dashboard: Update the technical admin dashboard with crypto metrics
    update_cfo_dashboard: Update the CFO dashboard with crypto financial metrics
    generate_crypto_metrics_report: Generate a JSON report of crypto metrics
"""
import os
import json
import datetime
from typing import Dict, Any, Optional, List
import re
from pathlib import Path

from bot.crypto_logger import CryptoLogger, global_crypto_logger


def update_tech_dashboard(dashboard_path: str, logger: Optional[CryptoLogger] = None) -> bool:
    """
    Update the technical admin dashboard with crypto metrics.
    
    Args:
        dashboard_path: Path to the dashboard HTML file
        logger: CryptoLogger instance to use (uses global instance if None)
        
    Returns:
        bool: True if update was successful
    """
    if logger is None:
        logger = global_crypto_logger
    
    try:
        # Read the dashboard HTML
        with open(dashboard_path, 'r') as f:
            html = f.read()
        
        # Get metrics data
        metrics = logger.get_performance_metrics()
        portfolio = logger.get_portfolio_summary()
        
        # Update system health metrics
        html = _update_system_health_metrics(html, metrics)
        
        # Update recent trades
        html = _update_recent_trades(html, logger.recent_crypto_trades)
        
        # Update crypto-specific metrics
        html = _add_crypto_metrics_panel(html, metrics, portfolio)
        
        # Write updated dashboard
        with open(dashboard_path, 'w') as f:
            f.write(html)
        
        return True
    
    except Exception as e:
        if logger:
            logger.log_error(e, "Failed to update tech dashboard")
        return False


def update_cfo_dashboard(dashboard_path: str, logger: Optional[CryptoLogger] = None) -> bool:
    """
    Update the CFO dashboard with crypto financial metrics.
    
    Args:
        dashboard_path: Path to the dashboard HTML file
        logger: CryptoLogger instance to use (uses global instance if None)
        
    Returns:
        bool: True if update was successful
    """
    if logger is None:
        logger = global_crypto_logger
    
    try:
        # Read the dashboard HTML
        with open(dashboard_path, 'r') as f:
            html = f.read()
        
        # Get metrics data
        metrics = logger.get_performance_metrics()
        portfolio = logger.get_portfolio_summary()
        
        # Update KPI metrics
        html = _update_cfo_kpi_metrics(html, portfolio)
        
        # Update financial summary
        html = _update_financial_summary(html, metrics, portfolio)
        
        # Write updated dashboard
        with open(dashboard_path, 'w') as f:
            f.write(html)
        
        return True
    
    except Exception as e:
        if logger:
            logger.log_error(e, "Failed to update CFO dashboard")
        return False


def generate_crypto_metrics_report(output_path: str, logger: Optional[CryptoLogger] = None) -> bool:
    """
    Generate a JSON report of crypto metrics.
    
    Args:
        output_path: Path to the output JSON file
        logger: CryptoLogger instance to use (uses global instance if None)
        
    Returns:
        bool: True if report generation was successful
    """
    if logger is None:
        logger = global_crypto_logger
    
    try:
        # Export metrics to JSON
        logger.export_metrics_to_json(output_path)
        return True
    
    except Exception as e:
        if logger:
            logger.log_error(e, "Failed to generate crypto metrics report")
        return False


def _update_system_health_metrics(html: str, metrics: Dict[str, Any]) -> str:
    """
    Update system health metrics in the tech dashboard.
    
    Args:
        html: Dashboard HTML
        metrics: Performance metrics
        
    Returns:
        str: Updated HTML
    """
    # Update API rate limit
    html = re.sub(
        r'<span class="metric-value">(\d+) / (\d+)</span>\s*</div>\s*<div class="metric">\s*<span>Last Heartbeat</span>',
        f'<span class="metric-value">{int(metrics["api_calls_per_minute"] * 10)} / 1000</span></div><div class="metric"><span>Last Heartbeat</span>',
        html
    )
    
    # Update error rate
    html = re.sub(
        r'<span class="metric-value">([\d.]+)%</span>',
        f'<span class="metric-value">{metrics["api_errors_rate"] * 100:.2f}%</span>',
        html
    )
    
    # Update API latency in a new metric
    if '<span>API Rate Limit</span>' in html and '<span>API Latency</span>' not in html:
        html = html.replace(
            '<span>API Rate Limit</span>',
            '<span>API Latency</span><span class="metric-value">{:.1f}ms</span></div><div class="metric"><span>API Rate Limit</span>'.format(
                metrics["avg_latency_ms"]
            )
        )
    
    return html


def _update_recent_trades(html: str, trades: List[Any]) -> str:
    """
    Update recent trades in the tech dashboard.
    
    Args:
        html: Dashboard HTML
        trades: Recent trades
        
    Returns:
        str: Updated HTML
    """
    if not trades:
        return html
    
    # Find the trades section
    trades_section_match = re.search(r'<div class="panel-header">\s*<span class="panel-title">Recent Trades.*?<div class="trade-entry">', html, re.DOTALL)
    if not trades_section_match:
        return html
    
    # Start of trades section
    trades_start = trades_section_match.end() - len('<div class="trade-entry">')
    
    # Find end of trades section
    trades_end_match = re.search(r'</div>\s*</div>\s*<!-- Configuration -->', html[trades_start:], re.DOTALL)
    if not trades_end_match:
        return html
    
    trades_end = trades_start + trades_end_match.start()
    
    # Generate new trades HTML
    new_trades_html = ""
    for trade in reversed(trades[-10:]):  # Last 10 trades, most recent first
        # Calculate profit/loss class
        profit_class = "trade-profit" if trade.side == "BUY" else "trade-loss"
        
        # Format timestamp
        timestamp = trade.timestamp.strftime("%H:%M:%S")
        
        # Format trade HTML
        trade_html = f"""
        <div class="trade-entry">
            <div>
                <div>{trade.base_currency}/{trade.quote_currency} {trade.side} {trade.quantity:.8f} @ ${trade.price:.2f}</div>
                <div style="font-size: 10px; color: #7d8590;">{timestamp}</div>
            </div>
            <div class="{profit_class}">Fees: ${trade.fees:.2f}</div>
        </div>
        """
        new_trades_html += trade_html
    
    # Replace trades section
    return html[:trades_start] + new_trades_html + html[trades_end:]


def _add_crypto_metrics_panel(html: str, metrics: Dict[str, Any], portfolio: Dict[str, Any]) -> str:
    """
    Add a crypto metrics panel to the tech dashboard.
    
    Args:
        html: Dashboard HTML
        metrics: Performance metrics
        portfolio: Portfolio summary
        
    Returns:
        str: Updated HTML
    """
    # Check if crypto panel already exists
    if "Crypto Metrics" in html:
        return _update_crypto_metrics_panel(html, metrics, portfolio)
    
    # Find the database panel
    db_panel_match = re.search(r'<div class="panel full-width">\s*<div class="panel-header">\s*<span class="panel-title">Database & Infrastructure</span>', html)
    if not db_panel_match:
        return html
    
    # Insert crypto panel before database panel
    insert_point = db_panel_match.start()
    
    # Create crypto metrics panel
    crypto_panel = f"""
    <div class="panel full-width">
        <div class="panel-header">
            <span class="panel-title">Crypto Trading Metrics</span>
            <button class="btn">Export Metrics</button>
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;">
            <div>
                <div class="metric">
                    <span>Portfolio Value</span>
                    <span class="metric-value">${portfolio["total_usd_value"]:.2f}</span>
                </div>
                <div class="metric">
                    <span>API Calls/min</span>
                    <span class="metric-value">{metrics["api_calls_per_minute"]:.1f}</span>
                </div>
            </div>
            <div>
                <div class="metric">
                    <span>WebSocket Msgs/min</span>
                    <span class="metric-value">{metrics["websocket_messages_per_minute"]:.1f}</span>
                </div>
                <div class="metric">
                    <span>WebSocket Error Rate</span>
                    <span class="metric-value">{metrics["websocket_error_rate"]*100:.2f}%</span>
                </div>
            </div>
            <div>
                <div class="metric">
                    <span>Trades/min</span>
                    <span class="metric-value">{metrics["trades_per_minute"]:.2f}</span>
                </div>
                <div class="metric">
                    <span>Avg Trade Size</span>
                    <span class="metric-value">${metrics["avg_trade_size_usd"]:.2f}</span>
                </div>
            </div>
            <div>
                <div class="metric">
                    <span>Rate Limit Hits</span>
                    <span class="metric-value">{metrics["rate_limit_hits"]}</span>
                </div>
                <div class="metric">
                    <span>API Error Rate</span>
                    <span class="metric-value">{metrics["api_errors_rate"]*100:.2f}%</span>
                </div>
            </div>
        </div>
    </div>
    """
    
    return html[:insert_point] + crypto_panel + html[insert_point:]


def _update_crypto_metrics_panel(html: str, metrics: Dict[str, Any], portfolio: Dict[str, Any]) -> str:
    """
    Update the crypto metrics panel in the tech dashboard.
    
    Args:
        html: Dashboard HTML
        metrics: Performance metrics
        portfolio: Portfolio summary
        
    Returns:
        str: Updated HTML
    """
    # Update portfolio value
    html = re.sub(
        r'<span>Portfolio Value</span>\s*<span class="metric-value">\$[\d,.]+</span>',
        f'<span>Portfolio Value</span><span class="metric-value">${portfolio["total_usd_value"]:.2f}</span>',
        html
    )
    
    # Update API calls/min
    html = re.sub(
        r'<span>API Calls/min</span>\s*<span class="metric-value">[\d,.]+</span>',
        f'<span>API Calls/min</span><span class="metric-value">{metrics["api_calls_per_minute"]:.1f}</span>',
        html
    )
    
    # Update WebSocket msgs/min
    html = re.sub(
        r'<span>WebSocket Msgs/min</span>\s*<span class="metric-value">[\d,.]+</span>',
        f'<span>WebSocket Msgs/min</span><span class="metric-value">{metrics["websocket_messages_per_minute"]:.1f}</span>',
        html
    )
    
    # Update WebSocket error rate
    html = re.sub(
        r'<span>WebSocket Error Rate</span>\s*<span class="metric-value">[\d,.]+%</span>',
        f'<span>WebSocket Error Rate</span><span class="metric-value">{metrics["websocket_error_rate"]*100:.2f}%</span>',
        html
    )
    
    # Update trades/min
    html = re.sub(
        r'<span>Trades/min</span>\s*<span class="metric-value">[\d,.]+</span>',
        f'<span>Trades/min</span><span class="metric-value">{metrics["trades_per_minute"]:.2f}</span>',
        html
    )
    
    # Update avg trade size
    html = re.sub(
        r'<span>Avg Trade Size</span>\s*<span class="metric-value">\$[\d,.]+</span>',
        f'<span>Avg Trade Size</span><span class="metric-value">${metrics["avg_trade_size_usd"]:.2f}</span>',
        html
    )
    
    # Update rate limit hits
    html = re.sub(
        r'<span>Rate Limit Hits</span>\s*<span class="metric-value">[\d,.]+</span>',
        f'<span>Rate Limit Hits</span><span class="metric-value">{metrics["rate_limit_hits"]}</span>',
        html
    )
    
    # Update API error rate
    html = re.sub(
        r'<span>API Error Rate</span>\s*<span class="metric-value">[\d,.]+%</span>',
        f'<span>API Error Rate</span><span class="metric-value">{metrics["api_errors_rate"]*100:.2f}%</span>',
        html
    )
    
    return html


def _update_cfo_kpi_metrics(html: str, portfolio: Dict[str, Any]) -> str:
    """
    Update KPI metrics in the CFO dashboard.
    
    Args:
        html: Dashboard HTML
        portfolio: Portfolio summary
        
    Returns:
        str: Updated HTML
    """
    # Update total assets under management
    html = re.sub(
        r'<div class="kpi-title">Total Assets Under Management</div>\s*<div class="kpi-value">\$[\d,]+</div>',
        f'<div class="kpi-title">Total Assets Under Management</div><div class="kpi-value">${portfolio["total_usd_value"]:,.2f}</div>',
        html
    )
    
    # Add crypto allocation KPI if not present
    if "Crypto Allocation" not in html:
        # Find the KPI grid
        kpi_grid_match = re.search(r'<div class="kpi-grid">(.*?)</div>\s*<!-- Main Content Grid -->', html, re.DOTALL)
        if kpi_grid_match:
            kpi_grid = kpi_grid_match.group(1)
            
            # Create crypto allocation KPI
            crypto_kpi = f"""
            <div class="kpi-card">
                <div class="kpi-title">Crypto Allocation</div>
                <div class="kpi-value">{len(portfolio["balances"])} assets</div>
                <div class="kpi-change neutral">
                    {", ".join(portfolio["balances"].keys())}
                </div>
            </div>
            """
            
            # Add to KPI grid
            new_kpi_grid = kpi_grid + crypto_kpi
            html = html.replace(kpi_grid, new_kpi_grid)
    
    return html


def _update_financial_summary(html: str, metrics: Dict[str, Any], portfolio: Dict[str, Any]) -> str:
    """
    Update financial summary in the CFO dashboard.
    
    Args:
        html: Dashboard HTML
        metrics: Performance metrics
        portfolio: Portfolio summary
        
    Returns:
        str: Updated HTML
    """
    # Find the financial summary section
    summary_match = re.search(r'<h3 class="panel-title">Financial Summary</h3>.*?<div class="panel-content">(.*?)</div>', html, re.DOTALL)
    if not summary_match:
        return html
    
    # Add crypto trading metrics if not present
    if "Crypto Trading Volume" not in html:
        # Find the end of the financial summary
        summary_end_match = re.search(r'</div>\s*<div class="alert alert-info">', html)
        if summary_end_match:
            insert_point = summary_end_match.start()
            
            # Create crypto trading metrics
            crypto_metrics = f"""
            <div class="metric-row">
                <span class="metric-label">Crypto Trading Volume (24h)</span>
                <span class="metric-value">${metrics["avg_trade_size_usd"] * metrics["trades_per_minute"] * 60 * 24:.2f}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">Crypto Trading Fees (24h)</span>
                <span class="metric-value">${metrics["avg_trade_size_usd"] * metrics["trades_per_minute"] * 60 * 24 * 0.005:.2f}</span>
            </div>
            """
            
            html = html[:insert_point] + crypto_metrics + html[insert_point:]
    
    return html