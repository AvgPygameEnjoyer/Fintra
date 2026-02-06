# Render Free Tier - Redis Initialization Workaround

Since Render's free tier doesn't support Shell access, we've created HTTP endpoints to initialize Redis and index the knowledge base.

## Quick Setup for Render Free Tier

### Step 1: Set Admin Key Environment Variable

Go to your Render Dashboard → Web Service → Environment

Add:
```
ADMIN_KEY=your-secure-random-key-here-change-this
```

**Generate a secure key:**
```bash
openssl rand -hex 32
```

Or use any random string (minimum 20 characters recommended)

### Step 2: Deploy Your Application

```bash
git add .
git commit -m "Add Redis admin endpoints for Render free tier"
git push origin main
```

### Step 3: Initialize Redis via HTTP Endpoint

After deployment is live (check the green "Live" badge), you have **3 options**:

#### Option A: Using Browser (Easiest)

Simply visit:
```
https://your-app.onrender.com/api/admin/init-redis?key=YOUR_ADMIN_KEY
```

Replace:
- `your-app.onrender.com` with your actual Render URL
- `YOUR_ADMIN_KEY` with the key you set in Step 1

**Expected Response:**
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "success": true,
  "steps": [
    {"step": 1, "action": "Initialize Redis connection", "status": "✅ Connected"},
    {"step": 2, "action": "Create vector search index", "status": "✅ Index ready"},
    {"step": 3, "action": "Index knowledge base documents", "status": "✅ Knowledge base indexed"},
    {"step": 4, "action": "Verify index contents", "status": "✅ 12 documents indexed"}
  ],
  "stats": {
    "index_name": "fintra_knowledge",
    "document_count": 12,
    "vector_dimension": 384
  }
}
```

#### Option B: Using cURL

```bash
curl -X POST "https://your-app.onrender.com/api/admin/init-redis?key=YOUR_ADMIN_KEY"
```

#### Option C: Using Postman/HTTP Client

- **Method:** POST
- **URL:** `https://your-app.onrender.com/api/admin/init-redis`
- **Headers:** 
  - `X-Admin-Key: YOUR_ADMIN_KEY`

### Step 4: Verify Status

Check if everything is working:

**Browser:**
```
https://your-app.onrender.com/api/admin/redis-status
```

**cURL:**
```bash
curl "https://your-app.onrender.com/api/admin/redis-status"
```

**Expected Response:**
```json
{
  "timestamp": "2024-01-15T10:30:00",
  "redis_available": true,
  "redis_connected": true,
  "rag_ready": true,
  "knowledge_base": {
    "index_name": "fintra_knowledge",
    "document_count": 12,
    "vector_dimension": 384
  }
}
```

## What These Endpoints Do

### `/api/admin/init-redis`

**Purpose:** Initialize Redis connection and index knowledge base

**Security:** 
- Requires `ADMIN_KEY` environment variable
- Requires `key` parameter matching ADMIN_KEY
- Logs unauthorized attempts

**Process:**
1. Connect to Redis
2. Create vector search index
3. Run `scripts/index_knowledge.py`
4. Verify documents are indexed

**Time:** Takes 30-60 seconds (model downloads on first run)

### `/api/admin/redis-status`

**Purpose:** Check current Redis and RAG status

**Security:** No authentication required (read-only status check)

**Returns:**
- Redis connection status
- RAG engine status
- Document count in knowledge base

## Troubleshooting

### "ADMIN_KEY not configured"

**Cause:** Environment variable not set

**Fix:**
1. Go to Render Dashboard → Environment
2. Add `ADMIN_KEY=your-secret-key`
3. Deploy again (Manual Deploy → Clear Build Cache)

### "Unauthorized"

**Cause:** Wrong admin key provided

**Fix:**
1. Check your Render environment variables
2. Use the exact key from `ADMIN_KEY`
3. Case-sensitive!

### "Redis connection failed"

**Cause:** Redis service not ready or misconfigured

**Fix:**
1. Check Redis service is "Live" in Render Dashboard
2. Verify `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` env vars
3. Wait 2-3 minutes after Redis creation (takes time to provision)

### "Knowledge base indexed: 0 documents"

**Cause:** Indexing script failed or documents not found

**Fix:**
1. Check that `knowledge_base/` folder exists in your repo
2. Verify JSON files are present
3. Check Render logs for specific errors

### Timeout Error

**Cause:** Model download taking too long on first run

**Fix:**
1. Retry the request (model is cached after first download)
2. Or increase timeout in the admin endpoint code

## Security Considerations

### 1. Keep ADMIN_KEY Secret
- Never commit it to Git
- Use a long, random string
- Rotate it periodically
- Don't share the full initialization URL

### 2. Rate Limiting
The admin endpoint is NOT rate-limited (by design for initialization). Consider adding rate limiting if concerned:

Add to `routes.py` admin endpoint:
```python
# Add rate limiting for admin endpoint
if not RateLimiter.is_allowed(request.remote_addr, 'admin', max_requests=5):
    return jsonify(error="Too many admin requests"), 429
```

### 3. IP Restriction (Advanced)
For extra security, restrict to your IP:
```python
allowed_ips = ['your-ip-address']
if request.remote_addr not in allowed_ips:
    return jsonify(error="IP not allowed"), 403
```

## Alternative: Auto-Initialization on Startup

If you prefer automatic initialization, modify `app.py`:

```python
# Add to app.py after Flask app creation
def init_services_on_startup():
    """Auto-initialize Redis on startup (Render free tier friendly)"""
    try:
        from init_services import init_services
        from scripts.index_knowledge import index_documents
        
        # Initialize Redis
        init_services()
        
        # Index knowledge base (with retry)
        for attempt in range(3):
            try:
                index_documents()
                break
            except Exception as e:
                if attempt < 2:
                    import time
                    time.sleep(10)  # Wait 10 seconds before retry
                else:
                    app.logger.error(f"Failed to index after 3 attempts: {e}")
    except Exception as e:
        app.logger.error(f"Startup initialization error: {e}")

# Call after app creation
with app.app_context():
    init_services_on_startup()
```

**Pros:**
- Fully automatic, no manual step needed
- Works on every deploy

**Cons:**
- Slows down app startup (30-60 seconds)
- May cause Render health checks to fail initially
- Model downloads on every deploy (free tier Redis is ephemeral)

## Monitoring

### Check Initialization Status

Add this to your application startup check:

```javascript
// In your frontend, check status on page load
fetch('/api/admin/redis-status')
  .then(res => res.json())
  .then(data => {
    if (!data.redis_connected || data.knowledge_base.document_count === 0) {
      console.warn('⚠️ Redis not initialized - Chatbot features limited');
      // Show notification to user
    }
  });
```

### Render Logs

View initialization logs:
1. Dashboard → Web Service → Logs
2. Filter by "admin" to see initialization attempts
3. Filter by "redis" to see connection status

## Complete Deployment Checklist

- [ ] Set `ADMIN_KEY` in Render environment variables
- [ ] Deploy application
- [ ] Wait for deployment to show "Live"
- [ ] Initialize Redis via: `https://your-app.onrender.com/api/admin/init-redis?key=YOUR_KEY`
- [ ] Verify with: `https://your-app.onrender.com/api/admin/redis-status`
- [ ] Test chatbot with: "What is RSI?"
- [ ] Check rate limiting (send 31 messages quickly)
- [ ] Check caching (ask same question twice)

## Cost

**Still $0/month** on Render free tier:
- Web Service: Free
- Redis: Free (100MB)
- Bandwidth: Free (100GB/month)

## Support

If initialization fails:
1. Check Render Dashboard Logs
2. Verify all environment variables are set
3. Ensure Redis service shows "Live"
4. Retry initialization (sometimes it just needs a second attempt)

---

**Ready to go!** Just set your ADMIN_KEY and deploy! 🚀
