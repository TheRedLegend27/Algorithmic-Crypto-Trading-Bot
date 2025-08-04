#!/usr/bin/env python3
"""
Simple web dashboard for the Adaptive Trading Bot.
Provides a web interface to monitor bot status and activity.
"""
from flask import Flask, render_template_string, jsonify
import json
import subprocess
from datetime import datetime
import threading
import time

app = Flask(__name__)

# Global variables to store bot data
bot_data = {
    'status': 'Unknown',
    'stats': {},
    'recent_logs': [],
    'last_update': None
}

def get_bot_status():
    """Check if the bot process is running."""
    try:
        result = subprocess.run(['pgrep', '-f', 'run_adaptive_bot.py'], 
                              capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except:
        return False

def get_recent_logs(lines=30):
    """Get recent log entries."""
    try:
        with open('adaptive_bot.log', 'r') as f:
            log_lines = f.readlines()
            return log_lines[-lines:] if log_lines else []
    except FileNotFoundError:
        return ["Log file not found. Bot may not be running."]

def parse_log_stats(log_lines):
    """Parse log lines to extract key statistics."""
    stats = {
        'cycles': 0,
        'signals': 0,
        'trades': 0,
        'errors': 0,
        'last_cycle': 'N/A',
        'regime': 'Unknown',
        'strategies_active': 0,
        'paper_trading': True,
        'trading_pairs': ['XBTUSD', 'ETHUSD'],
        'initial_capital': 10000.0
    }
    
    for line in log_lines:
        if 'Cycle #' in line:
            stats['cycles'] += 1
            if '- ' in line:
                stats['last_cycle'] = line.split('- ')[-1].strip()
        elif 'signal' in line.lower() and 'generated' in line.lower():
            stats['signals'] += 1
        elif 'trade' in line.lower() and ('executed' in line.lower() or 'placed' in line.lower()):
            stats['trades'] += 1
        elif 'ERROR' in line:
            stats['errors'] += 1
        elif 'regime' in line.lower() and 'detected' in line.lower():
            if 'BULLISH' in line:
                stats['regime'] = 'BULLISH'
            elif 'BEARISH' in line:
                stats['regime'] = 'BEARISH'
            elif 'NEUTRAL' in line:
                stats['regime'] = 'NEUTRAL'
        elif 'strategies' in line.lower() and 'initialized' in line.lower():
            words = line.split()
            for i, word in enumerate(words):
                if word.isdigit() and i < len(words) - 1 and 'strategies' in words[i+1]:
                    stats['strategies_active'] = int(word)
    
    return stats

def update_bot_data():
    """Update bot data in background."""
    global bot_data
    while True:
        try:
            bot_running = get_bot_status()
            bot_data['status'] = 'RUNNING' if bot_running else 'STOPPED'
            
            if bot_running:
                recent_logs = get_recent_logs(50)
                bot_data['stats'] = parse_log_stats(recent_logs)
                
                # Format recent logs for display
                formatted_logs = []
                for line in recent_logs[-15:]:
                    if any(keyword in line.lower() for keyword in 
                           ['cycle', 'signal', 'trade', 'regime', 'error', 'warning', 'info']):
                        if ' - ' in line:
                            parts = line.split(' - ')
                            if len(parts) >= 3:
                                timestamp = parts[0]
                                level = parts[2].split(' - ')[0] if ' - ' in parts[2] else 'INFO'
                                message = ' - '.join(parts[2].split(' - ')[1:]) if ' - ' in parts[2] else parts[2]
                                formatted_logs.append({
                                    'timestamp': timestamp[-8:],
                                    'level': level.strip(),
                                    'message': message.strip()
                                })
                
                bot_data['recent_logs'] = formatted_logs
            
            bot_data['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
        except Exception as e:
            print(f"Error updating bot data: {e}")
        
        time.sleep(5)

# Start background data update thread
data_thread = threading.Thread(target=update_bot_data, daemon=True)
data_thread.start()

@app.route('/')
def dashboard():
    """Main dashboard page."""
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Adaptive Trading Bot Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                min-height: 100vh;
            }
            .container { 
                max-width: 1200px; 
                margin: 0 auto; 
                background: rgba(255,255,255,0.1);
                border-radius: 15px;
                padding: 30px;
                backdrop-filter: blur(10px);
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            }
            .header { 
                text-align: center; 
                margin-bottom: 30px; 
                border-bottom: 2px solid rgba(255,255,255,0.3);
                padding-bottom: 20px;
            }
            .status-card, .stats-card, .logs-card { 
                background: rgba(255,255,255,0.15); 
                padding: 20px; 
                margin: 20px 0; 
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .status-running { color: #4CAF50; }
            .status-stopped { color: #f44336; }
            .stats-grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                gap: 15px; 
                margin-top: 15px;
            }
            .stat-item { 
                background: rgba(255,255,255,0.1); 
                padding: 15px; 
                border-radius: 8px; 
                text-align: center;
                border: 1px solid rgba(255,255,255,0.1);
            }
            .stat-value { 
                font-size: 24px; 
                font-weight: bold; 
                margin-bottom: 5px;
            }
            .stat-label { 
                font-size: 12px; 
                opacity: 0.8; 
                text-transform: uppercase;
            }
            .logs-container { 
                max-height: 400px; 
                overflow-y: auto; 
                background: rgba(0,0,0,0.3);
                border-radius: 8px;
                padding: 15px;
            }
            .log-entry { 
                margin: 8px 0; 
                padding: 8px; 
                border-left: 3px solid #4CAF50;
                background: rgba(255,255,255,0.05);
                border-radius: 4px;
                font-family: 'Courier New', monospace;
                font-size: 13px;
            }
            .log-error { border-left-color: #f44336; }
            .log-warning { border-left-color: #ff9800; }
            .refresh-info { 
                text-align: center; 
                margin-top: 20px; 
                opacity: 0.7;
                font-size: 14px;
            }
            .emoji { font-size: 1.2em; }
        </style>
        <script>
            function refreshPage() {
                location.reload();
            }
            // Auto-refresh every 10 seconds
            setInterval(refreshPage, 10000);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1><span class="emoji">🤖</span> Adaptive Trading Bot Dashboard</h1>
                <p>Real-time monitoring and status</p>
            </div>
            
            <div class="status-card">
                <h2><span class="emoji">📊</span> Bot Status</h2>
                <p>Status: <span class="status-{{ 'running' if bot_data.status == 'RUNNING' else 'stopped' }}">
                    {{ '🟢 ' + bot_data.status if bot_data.status == 'RUNNING' else '🔴 ' + bot_data.status }}
                </span></p>
                <p>Last Update: {{ bot_data.last_update or 'Never' }}</p>
            </div>
            
            {% if bot_data.status == 'RUNNING' %}
            <div class="stats-card">
                <h2><span class="emoji">📈</span> Trading Statistics</h2>
                <div class="stats-grid">
                    <div class="stat-item">
                        <div class="stat-value">{{ bot_data.stats.cycles or 0 }}</div>
                        <div class="stat-label">Trading Cycles</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{{ bot_data.stats.signals or 0 }}</div>
                        <div class="stat-label">Signals Generated</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{{ bot_data.stats.trades or 0 }}</div>
                        <div class="stat-label">Trades Executed</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{{ bot_data.stats.strategies_active or 0 }}</div>
                        <div class="stat-label">Active Strategies</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{{ bot_data.stats.regime or 'Unknown' }}</div>
                        <div class="stat-label">Market Regime</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">{{ bot_data.stats.errors or 0 }}</div>
                        <div class="stat-label">Errors</div>
                    </div>
                </div>
            </div>
            
            <div class="logs-card">
                <h2><span class="emoji">📋</span> Recent Activity</h2>
                <div class="logs-container">
                    {% for log in bot_data.recent_logs %}
                    <div class="log-entry {{ 'log-error' if 'ERROR' in log.level else 'log-warning' if 'WARNING' in log.level else '' }}">
                        <strong>{{ log.timestamp }}</strong> | {{ log.message }}
                    </div>
                    {% endfor %}
                    {% if not bot_data.recent_logs %}
                    <div class="log-entry">No recent activity...</div>
                    {% endif %}
                </div>
            </div>
            {% else %}
            <div class="stats-card">
                <h2><span class="emoji">❌</span> Bot Not Running</h2>
                <p>The trading bot is currently stopped.</p>
                <p><strong>To start the bot:</strong></p>
                <code>python3 run_adaptive_bot.py</code>
            </div>
            {% endif %}
            
            <div class="refresh-info">
                <p><span class="emoji">🔄</span> Page auto-refreshes every 10 seconds</p>
                <p><strong>Terminal Monitor:</strong> <code>python3 monitor_adaptive_bot.py</code></p>
            </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_template, bot_data=bot_data)

@app.route('/api/status')
def api_status():
    """API endpoint for bot status."""
    return jsonify(bot_data)

if __name__ == '__main__':
    print("🌐 Starting Adaptive Trading Bot Web Dashboard...")
    print("📱 Access dashboard at: http://localhost:5000")
    print("🔄 Dashboard updates every 10 seconds")
    print("💡 Press Ctrl+C to stop the dashboard")
    
    app.run(host='0.0.0.0', port=5000, debug=False)