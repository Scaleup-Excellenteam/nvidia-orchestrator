#!/bin/sh
set -e

echo "Starting NVIDIA Orchestrator services..."

# Set Python path
export PYTHONPATH=/app/src:${PYTHONPATH}

# Wait for PostgreSQL to be ready (if configured)
if [ ! -z "$POSTGRES_URL" ]; then
    echo "Waiting for PostgreSQL..."
    for i in $(seq 1 30); do
        python -c "
import psycopg
import sys
import time
try:
    conn = psycopg.connect('$POSTGRES_URL')
    conn.close()
    print('PostgreSQL is ready!')
    sys.exit(0)
except Exception as e:
    print(f'Attempt {$i}/30: PostgreSQL not ready yet... {e}')
    time.sleep(2)
"
        if [ $? -eq 0 ]; then
            break
        fi
        if [ $i -eq 30 ]; then
            echo "PostgreSQL connection timeout after 60 seconds"
            echo "Continuing anyway (PostgreSQL features will be disabled)"
        fi
    done
fi

# Start the health monitor in the background
echo "Starting health monitor..."
python -m nvidia_orchestrator.monitoring.health_monitor &
MONITOR_PID=$!

# Start the API server
echo "Starting API server on port 8000..."
python -m nvidia_orchestrator.api.app

# If API exits, kill the monitor
kill $MONITOR_PID 2>/dev/null || true
