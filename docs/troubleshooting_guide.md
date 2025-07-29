# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the Enhanced Kraken Trading Bot.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [API Connection Issues](#api-connection-issues)
3. [WebSocket Problems](#websocket-problems)
4. [Trading Execution Issues](#trading-execution-issues)
5. [Performance Problems](#performance-problems)
6. [Configuration Errors](#configuration-errors)
7. [Dashboard Issues](#dashboard-issues)
8. [Logging and Monitoring](#logging-and-monitoring)
9. [Emergency Procedures](#emergency-procedures)

## Quick Diagnostics

### Health Check Script

Run this script to quickly diagnose common issues:

```bash
# Run comprehensive health check
python -c "
from bot.kraken_client import KrakenClient
from bot.kraken_websocket import KrakenWebSocketClient
from bot.config import Config
import os

print('🔍 Running Health Check...')

# Check environment variables
required_vars = ['KRAKEN_API_KEY', 'KRAKEN_API_SECRET']
for var in required_vars:
    if os.getenv(var):
        print(f'✅ {var} is set')
    else:
        print(f'❌ {var} is missing')

# Test API connection
try:
    client = KrakenClient()
    balance = client.get_account_balance()
    print('✅ API connection successful')
except Exception as e:
    print(f'❌ API connection failed: {e}')

# Test configuration
try:
    config = Config()
    print('✅ Configuration loaded successfully')
except Exception as e:
    print(f'❌ Configuration error: {e}')

print('🏁 Health check complete')
"
```

### System Information

Check system requirements:

```bash
# Python version
python --version  # Should be 3.8+

# Memory usage
python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%')"

# Disk space
df -h .

# Network connectivity
ping -c 3 api.kraken.com
```

## API Connection Issues

### Error: "Invalid API Key or Signature"

**Symptoms**:
```
KrakenAPIError: Invalid key
```

**Causes & Solutions**:

1. **Incorrect API Credentials**
   ```bash
   # Verify credentials in .env file
   cat .env | grep KRAKEN_API
   
   # Test with curl
   curl -X POST https://api.kraken.com/0/private/Balance \
     -H "API-Key: YOUR_API_KEY" \
     -H "API-Sign: YOUR_SIGNATURE"
   ```

2. **API Key Permissions**
   - Log into Kraken → Security → API
   - Verify these permissions are enabled:
     - ✅ Query Funds
     - ✅ Query Open Orders & Trades
     - ✅ Create & Modify Orders
     - ✅ Cancel Orders
     - ✅ Access WebSockets API

3. **System Time Synchronization**
   ```bash
   # Check system time
   date
   
   # Sync time (macOS)
   sudo sntp -sS time.apple.com
   
   # Sync time (Linux)
   sudo ntpdate -s time.nist.gov
   ```

### Error: "Rate Limit Exceeded"

**Symptoms**:
```
KrakenAPIError: API rate limit exceeded
```

**Solutions**:

1. **Reduce Request Frequency**
   ```json
   {
     "api_settings": {
       "request_delay": 1.0,        // Increase delay between requests
       "max_requests_per_minute": 60, // Reduce request rate
       "burst_limit": 10            // Reduce burst requests
     }
   }
   ```

2. **Check for Multiple Bot Instances**
   ```bash
   # Find running bot processes
   ps aux | grep python | grep bot
   
   # Kill duplicate processes
   pkill -f "run_enhanced_bot.py"
   ```

3. **Implement Exponential Backoff**
   ```python
   # Already implemented in bot/kraken_client.py
   # Increase backoff parameters if needed
   BACKOFF_FACTOR = 2.0  # Increase from default
   MAX_RETRIES = 5       # Increase retry attempts
   ```

### Error: "Connection Timeout"

**Symptoms**:
```
requests.exceptions.ConnectTimeout: HTTPSConnectionPool
```

**Solutions**:

1. **Check Network Connectivity**
   ```bash
   # Test Kraken API connectivity
   curl -I https://api.kraken.com/0/public/Time
   
   # Check DNS resolution
   nslookup api.kraken.com
   ```

2. **Firewall Configuration**
   ```bash
   # Allow outbound HTTPS traffic
   # macOS: System Preferences → Security & Privacy → Firewall
   # Linux: Configure iptables or ufw
   ```

3. **Proxy Configuration**
   ```bash
   # If using proxy, set environment variables
   export https_proxy=http://proxy.company.com:8080
   export http_proxy=http://proxy.company.com:8080
   ```

## WebSocket Problems

### Error: "WebSocket Connection Failed"

**Symptoms**:
```
WebSocketException: Connection failed to ws://ws.kraken.com
```

**Solutions**:

1. **Check WebSocket URL**
   ```python
   # Verify correct WebSocket endpoints
   PUBLIC_WS_URL = "wss://ws.kraken.com"
   PRIVATE_WS_URL = "wss://ws-auth.kraken.com"
   ```

2. **Test WebSocket Connectivity**
   ```bash
   # Install wscat for testing
   npm install -g wscat
   
   # Test public WebSocket
   wscat -c wss://ws.kraken.com
   ```

3. **Increase Connection Timeout**
   ```json
   {
     "websocket_settings": {
       "connection_timeout": 30,     // Increase from default 10
       "ping_interval": 20,          // Increase ping frequency
       "ping_timeout": 10            // Increase ping timeout
     }
   }
   ```

### Error: "WebSocket Authentication Failed"

**Symptoms**:
```
WebSocketAuthError: Authentication failed
```

**Solutions**:

1. **Verify Private WebSocket Permissions**
   - Ensure API key has "Access WebSockets API" permission
   - Check that private subscriptions are properly authenticated

2. **Token Generation Issues**
   ```python
   # Debug token generation
   from bot.kraken_websocket import KrakenWebSocketClient
   
   client = KrakenWebSocketClient()
   token = client.get_websocket_token()
   print(f"Token: {token}")
   ```

### Error: "WebSocket Disconnects Frequently"

**Symptoms**:
```
WebSocket connection lost, attempting reconnect...
```

**Solutions**:

1. **Adjust Reconnection Settings**
   ```json
   {
     "websocket_reconnect_attempts": 10,  // Increase attempts
     "websocket_reconnect_delay": 5,      // Increase delay
     "exponential_backoff": true          // Enable backoff
   }
   ```

2. **Implement Connection Monitoring**
   ```python
   # Monitor connection health
   def monitor_websocket_health():
       if not ws_client.is_connected():
           ws_client.reconnect()
   ```

## Trading Execution Issues

### Error: "Insufficient Funds"

**Symptoms**:
```
KrakenAPIError: Insufficient funds
```

**Solutions**:

1. **Check Account Balance**
   ```python
   from bot.kraken_client import KrakenClient
   
   client = KrakenClient()
   balance = client.get_account_balance()
   print(f"Available balance: {balance}")
   ```

2. **Adjust Position Sizing**
   ```json
   {
     "risk": {
       "default_trade_amount_usd": 50.0,    // Reduce trade size
       "max_position_per_pair_usd": 200.0,  // Reduce max position
       "buffer_percentage": 0.05            // Keep 5% buffer
     }
   }
   ```

3. **Account for Fees**
   ```python
   # Include trading fees in calculations
   trade_amount = desired_amount * (1 + trading_fee)
   ```

### Error: "Invalid Order Parameters"

**Symptoms**:
```
KrakenAPIError: Invalid order parameters
```

**Solutions**:

1. **Validate Order Parameters**
   ```python
   # Check minimum order sizes
   min_order_sizes = {
       'XBTUSD': 0.0001,  # 0.0001 BTC minimum
       'ETHUSD': 0.001,   # 0.001 ETH minimum
   }
   ```

2. **Price Precision Issues**
   ```python
   # Round prices to correct precision
   price = round(price, pair_info['price_precision'])
   volume = round(volume, pair_info['volume_precision'])
   ```

### Error: "Order Rejected"

**Symptoms**:
```
Order rejected: Post-only order would execute immediately
```

**Solutions**:

1. **Adjust Order Types**
   ```json
   {
     "order_settings": {
       "default_order_type": "market",     // Use market orders
       "use_post_only": false,             // Disable post-only
       "price_buffer": 0.001               // Add price buffer
     }
   }
   ```

2. **Market Hours Check**
   ```python
   # Some pairs have trading restrictions
   def is_market_open(pair):
       # Check if pair is actively trading
       ticker = client.get_ticker_information(pair)
       return ticker['volume'] > 0
   ```

## Performance Problems

### High Memory Usage

**Symptoms**:
```
System running out of memory
Bot becoming slow or unresponsive
```

**Solutions**:

1. **Reduce Data Retention**
   ```json
   {
     "data_management": {
       "max_candles_in_memory": 1000,     // Reduce from default
       "cleanup_interval": 300,           // Clean up every 5 minutes
       "enable_data_compression": true    // Compress historical data
     }
   }
   ```

2. **Optimize Pandas Operations**
   ```python
   # Use more efficient data types
   df = df.astype({
       'volume': 'float32',    # Reduce precision
       'price': 'float32'      # Reduce precision
   })
   ```

3. **Implement Data Cleanup**
   ```python
   # Regular cleanup of old data
   def cleanup_old_data():
       cutoff_time = datetime.now() - timedelta(hours=24)
       data_manager.cleanup_data_before(cutoff_time)
   ```

### High CPU Usage

**Symptoms**:
```
CPU usage consistently above 80%
Bot responses becoming slow
```

**Solutions**:

1. **Reduce Calculation Frequency**
   ```json
   {
     "performance": {
       "indicator_calculation_interval": 60,  // Calculate every minute
       "strategy_evaluation_interval": 30,    // Evaluate every 30 seconds
       "reduce_precision": true               // Use lower precision math
     }
   }
   ```

2. **Optimize Strategy Calculations**
   ```python
   # Use vectorized operations
   import numpy as np
   
   # Instead of loops, use numpy operations
   returns = np.diff(np.log(prices))
   ```

### Slow Response Times

**Symptoms**:
```
Dashboard updates slowly
Trade execution delays
```

**Solutions**:

1. **Enable Caching**
   ```json
   {
     "caching": {
       "enable_price_cache": true,
       "cache_duration": 5,              // Cache for 5 seconds
       "enable_indicator_cache": true
     }
   }
   ```

2. **Optimize Database Operations**
   ```python
   # Use batch operations
   def batch_insert_trades(trades):
       # Insert multiple trades at once
       db.bulk_insert(trades)
   ```

## Configuration Errors

### Error: "Configuration File Not Found"

**Symptoms**:
```
FileNotFoundError: config_examples/enhanced_trading_config.json
```

**Solutions**:

1. **Create Configuration File**
   ```bash
   # Copy example configuration
   cp config_examples/enhanced_trading_config.json config/trading_config.json
   ```

2. **Set Configuration Path**
   ```bash
   export CONFIG_PATH=/path/to/your/config.json
   ```

### Error: "Invalid Configuration Format"

**Symptoms**:
```
JSONDecodeError: Expecting ',' delimiter
```

**Solutions**:

1. **Validate JSON Format**
   ```bash
   # Check JSON syntax
   python -m json.tool config/trading_config.json
   ```

2. **Use Configuration Validator**
   ```python
   from bot.config import validate_config
   
   try:
       validate_config('config/trading_config.json')
       print("✅ Configuration is valid")
   except Exception as e:
       print(f"❌ Configuration error: {e}")
   ```

## Dashboard Issues

### Error: "Dashboard Not Loading"

**Symptoms**:
```
Cannot connect to http://localhost:8080
```

**Solutions**:

1. **Check Dashboard Process**
   ```bash
   # Check if dashboard is running
   lsof -i :8080
   
   # Start dashboard manually
   python -m bot.enhanced_dashboard
   ```

2. **Port Conflicts**
   ```bash
   # Find process using port 8080
   lsof -i :8080
   
   # Use different port
   export DASHBOARD_PORT=8081
   ```

3. **Firewall Issues**
   ```bash
   # Allow local connections
   # macOS: System Preferences → Security & Privacy
   # Linux: sudo ufw allow 8080
   ```

### Error: "Dashboard Shows No Data"

**Symptoms**:
```
Dashboard loads but shows empty charts
```

**Solutions**:

1. **Check Data Flow**
   ```python
   # Verify data is being generated
   from bot.enhanced_data_manager import EnhancedDataManager
   
   dm = EnhancedDataManager()
   data = dm.get_latest_data('XBTUSD')
   print(f"Data points: {len(data)}")
   ```

2. **WebSocket Connection**
   ```python
   # Ensure WebSocket is feeding dashboard
   dashboard.update_market_data(latest_data)
   ```

## Logging and Monitoring

### Missing Log Files

**Symptoms**:
```
Log files not being created
No trading history available
```

**Solutions**:

1. **Check Log Directory Permissions**
   ```bash
   # Create logs directory
   mkdir -p logs
   chmod 755 logs
   ```

2. **Verify Logging Configuration**
   ```python
   import logging
   
   # Check logging setup
   logger = logging.getLogger('bot')
   print(f"Logger level: {logger.level}")
   print(f"Handlers: {logger.handlers}")
   ```

### Log Files Too Large

**Symptoms**:
```
Log files consuming too much disk space
System running out of storage
```

**Solutions**:

1. **Enable Log Rotation**
   ```json
   {
     "logging": {
       "enable_rotation": true,
       "max_file_size": "10MB",
       "backup_count": 5,
       "compress_old_logs": true
     }
   }
   ```

2. **Clean Old Logs**
   ```bash
   # Remove logs older than 30 days
   find logs/ -name "*.log" -mtime +30 -delete
   
   # Compress old logs
   gzip logs/*.log.1 logs/*.log.2
   ```

## Emergency Procedures

### Emergency Stop

If the bot is behaving unexpectedly:

```bash
# Immediate stop
pkill -f "run_enhanced_bot.py"

# Cancel all open orders (if needed)
python -c "
from bot.kraken_client import KrakenClient
client = KrakenClient()
orders = client.get_open_orders()
for order_id in orders:
    client.cancel_order(order_id)
    print(f'Cancelled order: {order_id}')
"
```

### Data Backup

Before making major changes:

```bash
# Backup configuration
cp -r config/ config_backup_$(date +%Y%m%d)/

# Backup logs
tar -czf logs_backup_$(date +%Y%m%d).tar.gz logs/

# Backup trading data
python -c "
from bot.enhanced_data_manager import EnhancedDataManager
dm = EnhancedDataManager()
dm.export_all_data('backup_$(date +%Y%m%d).json')
"
```

### Recovery Procedures

If the bot crashes or behaves unexpectedly:

1. **Stop All Processes**
   ```bash
   pkill -f python
   ```

2. **Check System Resources**
   ```bash
   top
   df -h
   free -m
   ```

3. **Review Recent Logs**
   ```bash
   tail -100 logs/enhanced_bot.log
   tail -100 logs/errors.log
   ```

4. **Restart with Safe Mode**
   ```bash
   python run_enhanced_bot.py --paper-trading --safe-mode
   ```

### Getting Help

If you can't resolve an issue:

1. **Collect Diagnostic Information**
   ```bash
   # System info
   python --version
   pip list > requirements_current.txt
   
   # Recent logs
   tail -200 logs/enhanced_bot.log > debug_logs.txt
   
   # Configuration (remove sensitive data)
   cat config/trading_config.json > debug_config.json
   ```

2. **Check Documentation**
   - Review setup guide
   - Check user guide for configuration
   - Look for similar issues in troubleshooting

3. **Community Support**
   - Search existing issues
   - Create detailed bug report
   - Include diagnostic information

---

**⚠️ Important**: Always test solutions in paper trading mode before applying to live trading. Keep backups of working configurations and never trade with money you cannot afford to lose.