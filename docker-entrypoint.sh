#!/bin/bash
set -e

# ============================================================================
# ⚠️  SECURITY WARNINGS FOR PRODUCTION DEPLOYMENTS
# ============================================================================
# 1. JWT Keys: Ensure JWT_PRIVATE_KEY and JWT_PUBLIC_KEY are set in .env
# 2. Database Seeding: Set SEED_DATABASE=false in production to avoid default accounts
# 3. Database Password: Change default 'rootpassword' in production
# 4. Sample Admin Credentials: Change SAMPLE_ADMIN_* values if seeding is enabled
# ============================================================================

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
# ⚠️  SECURITY NOTE: Password is intentionally NOT logged to prevent exposure in logs

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
    # ⚠️  SECURITY NOTE: Error message may contain connection details
    # In production, consider using a more generic error message
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

# Run startup scripts (all scripts/ folder scripts)
# ============================================================================
# ⚠️  SECURITY WARNING
# ============================================================================
# Backward-compatible toggle:
# - SEED_DATABASE is the legacy flag used by docs/docker-compose to control whether startup scripts run.
# - RUN_STARTUP_SCRIPTS is the newer, explicit flag.
#
# If RUN_STARTUP_SCRIPTS is not set, it will default to SEED_DATABASE (default true).
# Some scripts may seed sample data with default credentials.
# For production: set SEED_DATABASE=false (legacy) or RUN_STARTUP_SCRIPTS=false (preferred).
# ============================================================================
RUN_STARTUP_SCRIPTS_EFFECTIVE="${RUN_STARTUP_SCRIPTS:-${SEED_DATABASE:-true}}"
if [ "${RUN_STARTUP_SCRIPTS_EFFECTIVE}" = "true" ]; then
    echo ""
    echo "=========================================="
    echo "Running startup scripts in ./scripts ..."
    echo "=========================================="

    # Run any .sql files in scripts/ (if present)
    for sql_file in scripts/*.sql; do
        if [ -f "$sql_file" ]; then
            echo "Running SQL script: ${sql_file}"
            python3 - "$sql_file" <<'PY'
import os
import sys
from pathlib import Path

import mysql.connector

sql_path = Path(sys.argv[1])
conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USERNAME", "root"),
    password=os.getenv("DB_PASSWORD", "root"),
    database=os.getenv("DB_NAME", "ressy"),
)
cur = conn.cursor()
sql = sql_path.read_text(encoding="utf-8")
statements = [s.strip() for s in sql.split(";") if s.strip()]
for stmt in statements:
    cur.execute(stmt)
conn.commit()
cur.close()
conn.close()
print(f"✅ Ran SQL script: {sql_path.name}")
PY
        fi
    done

    # Run all python scripts in scripts/ (excluding run_migrations.py)
    for py_file in $(ls -1 scripts/*.py | sort); do
        if [[ "$py_file" == "scripts/run_migrations.py" ]]; then
            continue
        fi
        echo "Running Python script: ${py_file}"
        python3 "$py_file"
    done
else
    echo "Skipping startup scripts (RUN_STARTUP_SCRIPTS=${RUN_STARTUP_SCRIPTS:-unset}, SEED_DATABASE=${SEED_DATABASE:-unset})"
fi

echo ""
echo "=========================================="
echo "Starting application..."
echo "=========================================="

# Execute the main command (uvicorn)
exec "$@"
