#!/bin/bash

# Adaptive Trading Bot Deployment Script
# This script handles the deployment of the adaptive trading bot to production

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DEPLOY_ENV="${DEPLOY_ENV:-production}"
CONFIG_FILE="${CONFIG_FILE:-config/production.json}"
LOG_FILE="/tmp/adaptive_bot_deploy.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons"
    fi
}

# Check system requirements
check_requirements() {
    log "Checking system requirements..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed"
    fi
    
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if [[ $(echo "$PYTHON_VERSION < 3.8" | bc -l) -eq 1 ]]; then
        error "Python 3.8 or higher is required. Found: $PYTHON_VERSION"
    fi
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        error "pip3 is required but not installed"
    fi
    
    # Check PostgreSQL client
    if ! command -v psql &> /dev/null; then
        warning "PostgreSQL client not found. Database operations may fail."
    fi
    
    # Check disk space (require at least 1GB free)
    AVAILABLE_SPACE=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    if [[ $AVAILABLE_SPACE -lt 1048576 ]]; then  # 1GB in KB
        error "Insufficient disk space. At least 1GB free space required."
    fi
    
    success "System requirements check passed"
}

# Setup virtual environment
setup_venv() {
    log "Setting up Python virtual environment..."
    
    cd "$PROJECT_ROOT"
    
    if [[ ! -d ".venv" ]]; then
        python3 -m venv .venv
        log "Created new virtual environment"
    else
        log "Using existing virtual environment"
    fi
    
    source .venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        success "Installed Python dependencies"
    else
        error "requirements.txt not found"
    fi
}

# Create necessary directories
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p "$PROJECT_ROOT/logs/production"
    mkdir -p "$PROJECT_ROOT/config"
    mkdir -p "$PROJECT_ROOT/data/backups"
    mkdir -p "$PROJECT_ROOT/data/cache"
    
    # Set appropriate permissions
    chmod 755 "$PROJECT_ROOT/logs"
    chmod 755 "$PROJECT_ROOT/config"
    chmod 755 "$PROJECT_ROOT/data"
    
    success "Created directory structure"
}

# Setup configuration
setup_config() {
    log "Setting up configuration..."
    
    CONFIG_PATH="$PROJECT_ROOT/$CONFIG_FILE"
    
    if [[ ! -f "$CONFIG_PATH" ]]; then
        log "Creating default production configuration..."
        
        # Create default config using Python
        cd "$PROJECT_ROOT"
        source .venv/bin/activate
        
        python3 -c "
from bot.adaptive.production_config import ProductionConfig
config = ProductionConfig()
config.save_to_file('$CONFIG_FILE')
print('Default configuration created')
"
        
        warning "Default configuration created at $CONFIG_FILE"
        warning "Please review and customize the configuration before starting the bot"
    else
        log "Using existing configuration at $CONFIG_PATH"
    fi
    
    # Validate configuration
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    
    python3 -c "
from bot.adaptive.production_config import ProductionConfig
try:
    config = ProductionConfig.from_file('$CONFIG_FILE')
    issues = config.validate()
    if issues:
        print('Configuration validation issues:')
        for issue in issues:
            print(f'  - {issue}')
        exit(1)
    else:
        print('Configuration validation passed')
except Exception as e:
    print(f'Configuration validation failed: {e}')
    exit(1)
"
    
    success "Configuration setup completed"
}

# Setup database
setup_database() {
    log "Setting up database..."
    
    # Check if database configuration is provided
    if [[ -z "$DB_HOST" ]] || [[ -z "$DB_NAME" ]] || [[ -z "$DB_USER" ]]; then
        warning "Database environment variables not set. Skipping database setup."
        warning "Please set DB_HOST, DB_NAME, DB_USER, and DB_PASSWORD before running the bot."
        return
    fi
    
    # Test database connection
    if command -v psql &> /dev/null; then
        log "Testing database connection..."
        
        export PGPASSWORD="$DB_PASSWORD"
        if psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" &> /dev/null; then
            success "Database connection successful"
        else
            error "Failed to connect to database. Please check your database configuration."
        fi
    fi
    
    # Initialize database schema
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    
    python3 -c "
import asyncio
from bot.adaptive.database_setup import get_database_manager
from bot.adaptive.production_config import get_production_config

async def setup_db():
    try:
        config = get_production_config()
        db_manager = await get_database_manager(config.database)
        await db_manager.create_tables()
        print('Database schema initialized successfully')
        await db_manager.close()
    except Exception as e:
        print(f'Database setup failed: {e}')
        exit(1)

asyncio.run(setup_db())
"
    
    success "Database setup completed"
}

# Setup systemd service (optional)
setup_systemd() {
    if [[ "$1" != "--systemd" ]]; then
        return
    fi
    
    log "Setting up systemd service..."
    
    SERVICE_FILE="/etc/systemd/system/adaptive-trading-bot.service"
    
    if [[ ! -f "$SERVICE_FILE" ]]; then
        log "Creating systemd service file..."
        
        sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Adaptive Trading Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$PROJECT_ROOT
Environment=PATH=$PROJECT_ROOT/.venv/bin
Environment=ADAPTIVE_BOT_CONFIG=$CONFIG_FILE
ExecStart=$PROJECT_ROOT/.venv/bin/python -m bot.adaptive.adaptive_bot_main
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=adaptive-trading-bot

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$PROJECT_ROOT/logs $PROJECT_ROOT/data

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable adaptive-trading-bot.service
        
        success "Systemd service created and enabled"
    else
        log "Systemd service already exists"
    fi
}

# Setup log rotation
setup_logrotate() {
    log "Setting up log rotation..."
    
    LOGROTATE_FILE="/etc/logrotate.d/adaptive-trading-bot"
    
    if [[ ! -f "$LOGROTATE_FILE" ]]; then
        sudo tee "$LOGROTATE_FILE" > /dev/null <<EOF
$PROJECT_ROOT/logs/production/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 $(whoami) $(whoami)
    postrotate
        # Send SIGUSR1 to reload logs if service is running
        systemctl is-active --quiet adaptive-trading-bot && systemctl reload adaptive-trading-bot || true
    endscript
}
EOF
        
        success "Log rotation configured"
    else
        log "Log rotation already configured"
    fi
}

# Run deployment validation
validate_deployment() {
    log "Running deployment validation..."
    
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    
    # Run validation script
    python3 -c "
import sys
sys.path.append('.')

from bot.adaptive.production_config import get_production_config
from bot.adaptive.database_setup import get_database_manager
import asyncio

async def validate():
    try:
        # Test configuration loading
        config = get_production_config()
        print('✓ Configuration loaded successfully')
        
        # Test database connection
        if config.database.host != 'localhost' or config.database.database:
            db_manager = await get_database_manager(config.database)
            health = await db_manager.health_check()
            if health['status'] == 'healthy':
                print('✓ Database connection healthy')
            else:
                print(f'✗ Database health check failed: {health.get(\"message\", \"Unknown error\")}')
                return False
            await db_manager.close()
        
        # Test imports
        from bot.adaptive.adaptive_bot_main import AdaptiveBotMain
        print('✓ Core modules import successfully')
        
        print('✓ All validation checks passed')
        return True
        
    except Exception as e:
        print(f'✗ Validation failed: {e}')
        return False

if not asyncio.run(validate()):
    exit(1)
"
    
    success "Deployment validation passed"
}

# Main deployment function
main() {
    log "Starting Adaptive Trading Bot deployment..."
    log "Environment: $DEPLOY_ENV"
    log "Project root: $PROJECT_ROOT"
    
    # Parse command line arguments
    SETUP_SYSTEMD=false
    SKIP_DB=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --systemd)
                SETUP_SYSTEMD=true
                shift
                ;;
            --skip-db)
                SKIP_DB=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --systemd    Setup systemd service"
                echo "  --skip-db    Skip database setup"
                echo "  --help       Show this help message"
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                ;;
        esac
    done
    
    # Run deployment steps
    check_root
    check_requirements
    setup_venv
    create_directories
    setup_config
    
    if [[ "$SKIP_DB" != true ]]; then
        setup_database
    fi
    
    if [[ "$SETUP_SYSTEMD" == true ]]; then
        setup_systemd --systemd
        setup_logrotate
    fi
    
    validate_deployment
    
    success "Deployment completed successfully!"
    
    echo ""
    echo "Next steps:"
    echo "1. Review and customize the configuration file: $CONFIG_FILE"
    echo "2. Set up environment variables for API keys and database credentials"
    echo "3. Test the bot in paper trading mode first"
    
    if [[ "$SETUP_SYSTEMD" == true ]]; then
        echo "4. Start the service: sudo systemctl start adaptive-trading-bot"
        echo "5. Check service status: sudo systemctl status adaptive-trading-bot"
        echo "6. View logs: journalctl -u adaptive-trading-bot -f"
    else
        echo "4. Start the bot manually: python -m bot.adaptive.adaptive_bot_main"
    fi
    
    echo ""
    echo "For more information, see the documentation in docs/"
}

# Run main function
main "$@"