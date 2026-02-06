# Render.com Deployment Guide

This guide covers deploying Fintra with Redis on Render.com

## Quick Start for Render

### 1. Create Redis Service on Render

**Via Render Dashboard:**
1. Go to your Render Dashboard
2. Click "New +" → "Redis"
3. Name: `fintra-redis`
4. Region: Same as your web service (e.g., Oregon)
5. Plan: Free (or paid for production)
6. Click "Create"

**Via Blueprint (render.yaml):**
The `render.yaml` already includes Redis configuration. Just push to Git and Render will create both services.

### 2. Update render.yaml

The render.yaml has been updated to include Redis:

```yaml
services:
  - type: web
    name: stock-dashboard
    region: oregon
    plan: free
    runtime: python
    buildCommand: "./build.sh"
    startCommand: "gunicorn app:app --bind 0.0.0.0:10000 --workers 1 --timeout 120"
    envVars:
      - key: PYTHON_VERSION
        value: "3.12.4"
      - key: REDIS_HOST
        fromService:
          type: redis
          name: fintra-redis
          property: host
      - key: REDIS_PORT
        fromService:
          type: redis
          name: fintra-redis
          property: port
      - key: REDIS_PASSWORD
        fromService:
          type: redis
          name: fintra-redis
          property: password

  - type: redis
    name: fintra-redis
    region: oregon
    plan: free
    ipAllowList: []
```

### 3. Set Environment Variables in Render Dashboard

Go to your Web Service → Environment → Add the following:

**Required Variables:**
```
FLASK_SECRET_KEY=your-super-secret-key-here
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GEMINI_API_KEY=your-gemini-api-key
ACCESS_TOKEN_JWT_SECRET=your-jwt-access-secret
REFRESH_TOKEN_JWT_SECRET=your-jwt-refresh-secret
DATABASE_URL=your-postgres-database-url
```

**Redis Variables (Auto-populated if using render.yaml):**
```
REDIS_HOST=red-xxxxxxxxxxxxxxxxxxxx (auto-filled by Render)
REDIS_PORT=6379 (auto-filled by Render)
REDIS_PASSWORD=xxxxxxxxxx (auto-filled by Render)
```

### 4. Build and Deploy

**Option A - Using Git Push:**
```bash
git add .
git commit -m "Add Redis and RAG support"
git push origin main
```

Render will automatically:
1. Create the Redis service
2. Deploy the web service
3. Connect them via internal network
4. Inject environment variables

**Option B - Manual Deploy:**
1. Go to Render Dashboard
2. Click "Manual Deploy" → "Clear Build Cache & Deploy"

### 5. Index Knowledge Base on Render

After deployment, you need to index the knowledge base:

**Via Render Shell:**
1. Go to your Web Service on Render Dashboard
2. Click "Shell" tab
3. Run:
```bash
cd /opt/render/project/src
python scripts/index_knowledge.py
```

**Or via SSH (if enabled):**
```bash
ssh user@host.render.com
cd /opt/render/project/src
python scripts/index_knowledge.py
```

Expected output:
```
============================================================
Fintra Knowledge Base Indexing
============================================================
✅ Successfully indexed: 12 documents
📊 Index Statistics:
  - Total documents: 12
  - Vector dimension: 384
```

## Render-Specific Configuration

### Redis Connection

Render Redis uses SSL/TLS encryption. The code automatically detects Render environment and enables SSL:

```python
# redis_client.py automatically handles this
if is_render:
    connection_params['ssl'] = True
    connection_params['ssl_cert_reqs'] = None
```

### Memory Considerations

**Free Tier Limits:**
- Redis: 100 MB memory
- Web Service: 512 MB RAM
- Build time: 15 minutes

**Optimization:**
- Knowledge base: ~5-10 MB
- Chat cache: Clears automatically after 1 hour
- Rate limiting: Minimal memory footprint

If you hit memory limits:
1. Upgrade to paid plan
2. Reduce cache TTL in `redis_client.py`
3. Limit knowledge base documents

### Monitoring on Render

**View Redis Metrics:**
1. Go to Redis service in Render Dashboard
2. Click "Metrics" tab
3. Monitor memory usage and connections

**View Logs:**
1. Web Service → Logs
2. Filter by "Redis" to see connection status

**Common Log Messages:**
```
✅ Redis connection established to red-xxx:6379
✅ RAG engine initialized successfully
✅ Successfully indexed: 12 documents
```

## Troubleshooting Render Deployment

### Issue: "Redis connection failed"

**Cause:** Environment variables not set

**Solution:**
1. Check Redis service is created
2. Verify env vars in Dashboard
3. REDIS_HOST should start with "red-"

### Issue: "ModuleNotFoundError: No module named 'redis'"

**Cause:** Dependencies not installed

**Solution:**
1. Check build.sh runs successfully
2. Verify requirements.txt includes redis packages
3. Trigger manual deploy with "Clear Build Cache"

### Issue: "Knowledge base indexing fails"

**Cause:** Redis not ready or model download issue

**Solution:**
1. Wait for Redis to be fully provisioned (2-3 minutes)
2. Run indexing script manually via Shell
3. Check logs for model download errors

### Issue: "SSL connection error"

**Cause:** SSL certificate verification

**Solution:**
The code already handles this by setting `ssl_cert_reqs=None` for Render's internal network. If you still see errors:

```python
# In redis_client.py, modify connection_params:
connection_params['ssl_cert_reqs'] = 'none'  # Use string 'none' if None doesn't work
```

### Issue: "Rate limiting not working"

**Cause:** Redis not connected

**Check:**
```python
# In Render Shell
python -c "from redis_client import redis_client; print(redis_client.is_connected())"
```

Should print: `True`

## Production Considerations

### 1. Upgrade Redis Plan

For production with high traffic:
- Upgrade to "Starter" ($10/month) or higher
- Provides persistence and higher memory
- Better for chat history storage

### 2. Database Persistence

Free Redis tier doesn't persist data. On restart:
- Knowledge base needs re-indexing
- Chat cache is cleared
- Rate limits reset

**Solution:**
Add to your startup code or create a startup script:
```python
# In app.py or startup hook
if os.getenv('RENDER'):
    # Re-index on startup
    os.system('python scripts/index_knowledge.py &')
```

### 3. Health Checks

Add to render.yaml:
```yaml
healthCheckPath: /health
```

Create health endpoint in routes.py that checks Redis:
```python
@api.route('/health')
def health():
    redis_status = redis_client.is_connected() if REDIS_AVAILABLE else False
    return jsonify(
        status="healthy",
        redis=redis_status,
        timestamp=datetime.now().isoformat()
    ), 200 if redis_status else 503
```

### 4. Backup Strategy

Since free tier doesn't persist:
- Keep knowledge_base/ in Git
- Re-index on every deployment (add to build.sh)
- Or upgrade to paid Redis for persistence

**Add to build.sh:**
```bash
#!/usr/bin/env bash
set -o errexit

pip install --upgrade pip
pip install -r requirements.txt

# Index knowledge base (for Render's ephemeral Redis)
python scripts/index_knowledge.py || echo "Indexing skipped (Redis not ready)"
```

## Cost Estimate

**Free Tier (Development):**
- Web Service: $0
- Redis: $0
- Total: $0/month

**Starter Tier (Production):**
- Web Service: $7/month
- Redis Starter: $10/month
- Total: $17/month

**With 2GB Redis (High Traffic):**
- Web Service: $7/month
- Redis 2GB: $35/month
- Total: $42/month

## Render Dashboard Checklist

Before going live:

- [ ] Redis service created and "Live"
- [ ] Environment variables set
- [ ] Build successful (green checkmark)
- [ ] Knowledge base indexed
- [ ] Health check endpoint working
- [ ] Rate limiting tested
- [ ] Chat responses cached
- [ ] RAG retrieval working

## Testing on Render

**Test 1: Basic Chat**
1. Open your deployed app
2. Send: "hi"
3. Should get: "Hey there! 👋"

**Test 2: RAG Search**
1. Send: "What is RSI?"
2. Check response includes RSI explanation
3. Check sources are listed

**Test 3: Rate Limiting**
1. Send 31 messages quickly
2. 31st should return: "Rate limit exceeded"

**Test 4: Caching**
1. Send: "What is MACD?"
2. Wait for response
3. Send same message again
4. Should be instant (cached)

## Support

**Render Documentation:**
- Redis on Render: https://render.com/docs/redis
- Environment Variables: https://render.com/docs/environment-variables
- Blueprint Spec: https://render.com/docs/blueprint-spec

**Fintra Issues:**
Check logs in Render Dashboard → Web Service → Logs

---

**Deployment Status:** Ready for Render 🚀
