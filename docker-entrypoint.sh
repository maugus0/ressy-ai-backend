#!/bin/bash
set -e

echo "=========================================="
echo "RessyAI Backend - Docker Entrypoint"
echo "=========================================="

# Database configuration from environment variables
# Supports both DB_* and MYSQL_* naming conventions
DB_HOST="${DB_HOST:-${MYSQL_HOST:-db}}"
DB_PORT="${DB_PORT:-${MYSQL_PORT:-3306}}"
DB_NAME="${DB_NAME:-${MYSQL_DATABASE:-ressy}}"
DB_USERNAME="${DB_USERNAME:-${MYSQL_USER:-root}}"
DB_PASSWORD="${DB_PASSWORD:-${MYSQL_PASSWORD:-rootpassword}}"

echo "Database Configuration:"
echo "  Host: ${DB_HOST}"
echo "  Port: ${DB_PORT}"
echo "  Database: ${DB_NAME}"
echo "  User: ${DB_USERNAME}"

# Export variables for Python scripts
export DB_HOST DB_PORT DB_NAME DB_USERNAME DB_PASSWORD

# Wait for MySQL to be ready
echo ""
echo "Waiting for MySQL to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python3 -c "
import mysql.connector
import os
try:
    conn = mysql.connector.connect(
        host=os.environ.get('DB_HOST'),
        port=int(os.environ.get('DB_PORT', 3306)),
        user=os.environ.get('DB_USERNAME'),
        password=os.environ.get('DB_PASSWORD')
    )
    conn.close()
    exit(0)
except Exception as e:
    print(f'MySQL not ready: {e}')
    exit(1)
" 2>/dev/null; then
        echo "MySQL is ready!"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting for MySQL... (attempt $RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: MySQL did not become ready in time"
    exit 1
fi

# Run migrations
echo ""
echo "=========================================="
echo "Running database migrations..."
echo "=========================================="
python3 scripts/run_migrations.py

# Check if seeding is enabled
if [ "${SEED_DATABASE:-true}" = "true" ]; then
    echo ""
    echo "=========================================="
    echo "Seeding database with sample data..."
    echo "=========================================="
    
    # Add sample admins (creates roles, permissions, and admin users)
    python3 scripts/add_sample_admins.py
    
    # Add sample restaurant data (menu items, FAQs)
    python3 scripts/add_sample_data.py
    
    echo "Database seeding completed!"
else
    echo "Skipping database seeding (SEED_DATABASE=${SEED_DATABASE})"
fi

echo ""
echo "=========================================="
echo "Starting application..."
echo "=========================================="

# Execute the main command (uvicorn)
exec "$@"
