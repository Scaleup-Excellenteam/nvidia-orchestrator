#!/bin/bash

# Wait for PostgreSQL to be ready using Python instead of pg_isready
echo "Waiting for PostgreSQL to be ready..."
python << 'EOF'
import time
import psycopg
import os

dsn = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@postgres:5432/orchestrator")
max_attempts = 30
attempt = 0

while attempt < max_attempts:
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                print("PostgreSQL is ready!")
                exit(0)
    except Exception as e:
        attempt += 1
        print(f"PostgreSQL is unavailable (attempt {attempt}/{max_attempts}) - sleeping")
        time.sleep(2)

print("PostgreSQL failed to become ready after maximum attempts")
exit(1)
EOF

if [ $? -ne 0 ]; then
    echo "Failed to connect to PostgreSQL, exiting"
    exit 1
fi

# Wait a bit more to ensure the database is fully initialized
sleep 5

# Start the application
echo "Starting Orchestrator API..."
exec uvicorn app:app --host 0.0.0.0 --port 8000
