# Memory Optimization Guide for Render Free Tier

## Current Memory Optimizations Applied

### 1. Gunicorn Configuration
- **Workers**: 1 (minimal)
- **Threads**: 2 (for concurrency without extra processes)
- **Max Requests**: 100 (recycles workers to free memory)
- **Worker Class**: gthread (memory efficient)
- **Worker Tmp Dir**: /dev/shm (uses RAM instead of disk)

### 2. Disabled Heavy Services
The following memory-intensive services are now disabled:
- ❌ RAG (Retrieval-Augmented Generation) - loads ML models (~100-500MB)
- ❌ Redis-based knowledge base indexing
- ❌ Background initialization threads

These services were using 200-500MB+ of RAM and are not essential for core functionality.

### 3. Environment Variables Set
```bash
PYTHONDONTWRITEBYTECODE=1  # Don't write .pyc files
PYTHONUNBUFFERED=1         # Unbuffered output
MPLBACKEND=Agg            # Non-interactive matplotlib backend
```

## Memory Usage Breakdown

| Component | Memory Usage |
|-----------|-------------|
| Flask/Gunicorn | ~50-100MB |
| Database (SQLAlchemy) | ~50-100MB |
| yfinance/pandas | ~100-200MB |
| **Total Core App** | **~200-400MB** |
| RAG/Embeddings | ~200-500MB ❌ DISABLED |
| Redis operations | ~50-100MB ❌ DISABLED |

## What Still Works

✅ User authentication (OAuth/JWT)
✅ Portfolio management
✅ Stock data fetching (yfinance)
✅ Technical analysis (RSI, MACD, etc.)
✅ Backtesting
✅ Chatbot (without RAG knowledge base)
✅ All chart visualizations

## What's Limited

⚠️ Chatbot responses won't use knowledge base (RAG disabled)
⚠️ No chat response caching (Redis optional)
⚠️ No rate limiting (Redis optional)

## To Re-enable Full Features (Paid Tier)

If you upgrade to Render's Starter plan ($7/month) with 1GB RAM:

1. Remove the comment from `init_services_background()` in app.py
2. Set environment variable: `ENABLE_RAG=true`
3. Deploy

## Monitoring Memory

Check memory usage in Render Dashboard:
1. Go to your Web Service
2. Click "Metrics" tab
3. Look for "Memory Usage"

If memory exceeds 90%, the app will restart automatically.

## Additional Optimizations (If Still Having Issues)

1. **Disable Monte Carlo** (uses random sampling):
   - Comment out `initializeMonteCarlo()` in main.js

2. **Reduce pandas memory**:
   - Use `dtype` optimization in data loading
   - Limit data frames to essential columns

3. **Lazy load heavy modules**:
   - Already implemented for RAG/Redis
   - Can extend to other heavy imports

4. **Use lighter ML models**:
   - Currently tries FastEmbed first (10MB)
   - Falls back to sentence-transformers (100MB+) if needed

## Free Tier Limits

Render Free Tier:
- **RAM**: 512MB
- **CPU**: Shared
- **Disk**: Ephemeral (resets on deploy)
- **Uptime**: Spins down after 15 min inactivity

With current optimizations, the app uses ~300-400MB RAM, leaving headroom.

## Troubleshooting Memory Issues

If you still see "Out of Memory" errors:

1. **Check logs**: `Render Dashboard → Logs`
2. **Look for**: "MemoryError", "Killed process", "OOM"
3. **Common culprits**:
   - Large data downloads from yfinance
   - Too many concurrent requests
   - Memory leaks in long-running workers

4. **Quick fixes**:
   - Restart the service
   - Reduce `max-requests` in gunicorn config
   - Disable more features temporarily

## Future Improvements

For production with more memory:

1. Use Redis Cloud for caching
2. Enable RAG with knowledge base
3. Add rate limiting
4. Implement request queuing
5. Use CDN for static assets
