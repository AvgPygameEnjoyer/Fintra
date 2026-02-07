#!/bin/bash
# Startup script for Render.com with memory optimization

echo "🚀 Starting Fintra with memory optimizations..."
echo "💾 Available memory: $(free -h 2>/dev/null | grep Mem | awk '{print $7}' || echo 'unknown')"

# Set Python memory optimization environment variables
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# Disable matplotlib backend to save memory
export MPLBACKEND=Agg

# Run gunicorn with memory-efficient settings
exec gunicorn app:app \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 2 \
    --timeout 120 \
    --max-requests 100 \
    --max-requests-jitter 20 \
    --worker-class gthread \
    --worker-tmp-dir /dev/shm \
    --log-level info \
    --access-logfile - \
    --error-logfile -
