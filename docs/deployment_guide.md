# Adaptive Trading Bot Deployment Guide

This guide covers the deployment of the Adaptive Trading Bot to production environments.

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Python**: 3.8 or higher
- **Memory**: Minimum 4GB RAM, 8GB+ recommended
- **Storage**: Minimum 10GB free space
- **Database**: PostgreSQL 12+ (optional but recommended for production)

### Required Software

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv postgresql-client

# macOS (using Homebrew)
brew install python3 postgresql
```

### Environment Variables

Set the following environment variables before deployment:

```bash
# Trading API credentials
export KRAKEN_API_KEY="your_kraken_api_key"
export KRAKEN_API_SECRET="your_kraken_api_secret"

# Database credentials (if using PostgreSQL)
export DB_HOST="localhost"
export DB_PORT="5432"
export DB_NAME="adaptive_trading"
export DB_USER="trading_bot"
export DB_PASSWORD="your_secure_password"

# Optional: Custom configuration file path
export ADAPTIVE_BOT_CONFIG="config/production.json"
```

## Quick Deployment

### Automated Deployment

Use the provided deployment script for automated setup:

```bash
# Basic deployment
./scripts/deploy.sh

# Deployment with systemd service
./scripts/deploy.sh --systemd

# Skip database setup (if using external database)
./scripts/deploy.sh --skip-db
```

### Manual Deployment

If you prefer manual deployment:

1. **Clone and Setup**:
   ```bash
   git clone <repository_url>
   cd adaptive-trading-bot
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Create Configuration**:
   ```bash
   cp config/production.json.template config/production.json
   # Edit config/production.json with your settings
   ```

3. **Setup Database** (optional):
   ```bash
   # Create PostgreSQL database
   createdb adaptive_trading
   
   # Initialize schema
   python -c "
   import asyncio
   from bot.adaptive.database_setup import get_database_manager
   asyncio.run(get_database_manager().create_tables())
   "
   ```

4. **Start the Bot**:
   ```bash
   python -m bot.adaptive.adaptive_bot_main
   ```

## Configuration

### Production Configuration File

The bot uses a JSON configuration file for production settings. Copy the template and customize:

```bash
cp config/production.json.template config/production.json
```

Key configuration sections:

#### Safety Limits
```json
{
  "limits": {
    "max_position_size_usd": 1000.0,
    "max_daily_loss_usd": 500.0,
    "max_portfolio_risk": 0.02,
    "max_drawdown_percent": 5.0,
    "min_confidence_threshold": 0.7
  }
}
```

#### Database Configuration
```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "database": "adaptive_trading",
    "username": "trading_bot",
    "ssl_mode": "require"
  }
}
```

#### Logging Configuration
```json
{
  "logging": {
    "level": "INFO",
    "log_dir": "logs/production",
    "enable_file": true,
    "enable_console": false,
    "enable_syslog": true
  }
}
```

### Environment-Specific Settings

- **Development**: Set `"debug": true` and `"enable_live_trading": false`
- **Staging**: Use paper trading with production-like settings
- **Production**: Ensure `"debug": false` and carefully configure safety limits

## Database Setup

### PostgreSQL Installation

#### Ubuntu/Debian
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

#### macOS
```bash
brew install postgresql
brew services start postgresql
```

### Database Configuration

1. **Create Database User**:
   ```sql
   sudo -u postgres psql
   CREATE USER trading_bot WITH PASSWORD 'your_secure_password';
   CREATE DATABASE adaptive_trading OWNER trading_bot;
   GRANT ALL PRIVILEGES ON DATABASE adaptive_trading TO trading_bot;
   ```

2. **Configure Connection**:
   ```bash
   # Test connection
   psql -h localhost -U trading_bot -d adaptive_trading
   ```

3. **Initialize Schema**:
   The deployment script automatically creates the required tables, or run manually:
   ```bash
   python -c "
   import asyncio
   from bot.adaptive.database_setup import get_database_manager
   from bot.adaptive.production_config import get_production_config
   
   async def setup():
       config = get_production_config()
       db = await get_database_manager(config.database)
       await db.create_tables()
       await db.close()
   
   asyncio.run(setup())
   "
   ```

## Service Management

### Systemd Service (Linux)

The deployment script can create a systemd service:

```bash
./scripts/deploy.sh --systemd
```

Manual service management:

```bash
# Start service
sudo systemctl start adaptive-trading-bot

# Enable auto-start
sudo systemctl enable adaptive-trading-bot

# Check status
sudo systemctl status adaptive-trading-bot

# View logs
journalctl -u adaptive-trading-bot -f

# Stop service
sudo systemctl stop adaptive-trading-bot
```

### Process Management (Alternative)

Using screen or tmux for simple process management:

```bash
# Using screen
screen -S adaptive-bot
source .venv/bin/activate
python -m bot.adaptive.adaptive_bot_main
# Ctrl+A, D to detach

# Reattach later
screen -r adaptive-bot
```

## Monitoring and Logging

### Log Files

Production logs are stored in `logs/production/`:

- `adaptive_bot.log`: Main application log
- `errors.log`: Error-specific log
- `trades.log`: Trading activity log
- `performance.log`: Performance metrics log
- `adaptations.log`: System adaptation events

### Log Rotation

The deployment script sets up automatic log rotation:

```bash
# Manual log rotation setup
sudo tee /etc/logrotate.d/adaptive-trading-bot <<EOF
/path/to/bot/logs/production/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 user user
}
EOF
```

### Health Monitoring

The bot includes built-in health monitoring:

1. **Health Check Endpoint**: Available if web interface is enabled
2. **Performance Monitoring**: Automatic performance degradation detection
3. **System Resource Monitoring**: CPU, memory, and disk usage tracking

### Alerting

Configure alerting in the production configuration:

```json
{
  "monitoring": {
    "enable_email_alerts": true,
    "enable_slack_alerts": false,
    "alert_cooldown_minutes": 30,
    "cpu_usage_threshold": 80.0,
    "memory_usage_threshold": 85.0
  }
}
```

## Security Considerations

### API Key Security

1. **Environment Variables**: Store API keys in environment variables, not config files
2. **Key Rotation**: Enable automatic API key rotation if supported
3. **Permissions**: Use minimal required API permissions

### System Security

1. **User Permissions**: Run the bot as a non-root user
2. **File Permissions**: Restrict access to configuration and log files
3. **Network Security**: Use firewall rules to limit network access
4. **Database Security**: Use SSL connections and strong passwords

### Configuration Security

```json
{
  "security": {
    "enable_api_key_rotation": true,
    "enable_request_signing": true,
    "enable_ip_whitelist": true,
    "allowed_ips": ["your.server.ip"],
    "enable_audit_logging": true
  }
}
```

## Backup and Recovery

### Automated Backups

The bot can automatically backup its state:

```json
{
  "enable_state_backup": true,
  "backup_interval_hours": 6,
  "backup_retention_days": 30
}
```

### Manual Backup

```bash
# Backup configuration
cp config/production.json backups/config-$(date +%Y%m%d).json

# Backup database
pg_dump -h localhost -U trading_bot adaptive_trading > backups/db-$(date +%Y%m%d).sql

# Backup logs
tar -czf backups/logs-$(date +%Y%m%d).tar.gz logs/
```

### Recovery Procedures

1. **Configuration Recovery**: Restore from backup configuration file
2. **Database Recovery**: Restore from PostgreSQL dump
3. **State Recovery**: The bot automatically recovers from the last saved state

## Performance Optimization

### System Optimization

1. **CPU**: Enable parallel processing in configuration
2. **Memory**: Adjust cache settings and connection pool sizes
3. **I/O**: Use SSD storage for database and logs
4. **Network**: Ensure low-latency connection to trading APIs

### Configuration Tuning

```json
{
  "enable_caching": true,
  "cache_ttl_seconds": 300,
  "enable_parallel_processing": true,
  "max_worker_threads": 4,
  "database": {
    "connection_pool_size": 10,
    "max_overflow": 20
  }
}
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Check database credentials and connectivity
   - Verify PostgreSQL service is running
   - Check firewall settings

2. **API Connection Issues**:
   - Verify API keys are correct and have required permissions
   - Check network connectivity to trading APIs
   - Review rate limiting settings

3. **Permission Errors**:
   - Ensure bot user has write access to log directories
   - Check file permissions on configuration files

4. **Memory Issues**:
   - Monitor memory usage and adjust cache settings
   - Consider increasing system memory
   - Review database connection pool settings

### Debug Mode

Enable debug mode for troubleshooting:

```json
{
  "debug": true,
  "logging": {
    "level": "DEBUG",
    "enable_console": true
  }
}
```

### Log Analysis

```bash
# Check for errors
grep -i error logs/production/adaptive_bot.log

# Monitor real-time logs
tail -f logs/production/adaptive_bot.log

# Check system resource usage
grep -i "resource" logs/production/adaptive_bot.log
```

## Validation and Testing

### Deployment Validation

Run the deployment validation tests:

```bash
python -m pytest tests/deployment/test_production_deployment.py -v
```

### Paper Trading Validation

Before enabling live trading:

1. Set `"enable_live_trading": false` in configuration
2. Run the bot in paper trading mode for at least 24 hours
3. Monitor performance and system stability
4. Review logs for any errors or warnings

### Gradual Rollout

1. **Start Small**: Begin with minimal position sizes
2. **Monitor Closely**: Watch performance and system metrics
3. **Gradual Increase**: Slowly increase position sizes and risk limits
4. **Full Production**: Enable full production settings after validation

## Maintenance

### Regular Maintenance Tasks

1. **Log Rotation**: Ensure logs are rotated and archived
2. **Database Cleanup**: Remove old data to manage database size
3. **Performance Review**: Regular review of trading performance
4. **Security Updates**: Keep system and dependencies updated
5. **Backup Verification**: Regularly test backup and recovery procedures

### Update Procedures

1. **Backup Current State**: Always backup before updates
2. **Test in Staging**: Test updates in staging environment first
3. **Gradual Rollout**: Deploy updates gradually
4. **Monitor Post-Update**: Closely monitor after updates

## Support and Documentation

- **Logs**: Check application logs for detailed error information
- **Configuration**: Review configuration documentation
- **API Documentation**: Refer to trading API documentation
- **Community**: Check project issues and discussions

For additional support, refer to the troubleshooting guide and API documentation.