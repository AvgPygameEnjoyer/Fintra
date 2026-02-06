# 🚀 Quick Deploy Checklist - Render Free Tier

## Step 1: Set Environment Variables

Go to Render Dashboard → Your Web Service → Environment

**Required Variables:**
```
ADMIN_KEY=your-secure-admin-key-here-change-this
FLASK_SECRET_KEY=your-flask-secret
GOOGLE_CLIENT_ID=your-google-id
GOOGLE_CLIENT_SECRET=your-google-secret
GEMINI_API_KEY=your-gemini-key
ACCESS_TOKEN_JWT_SECRET=your-jwt-access-secret
REFRESH_TOKEN_JWT_SECRET=your-jwt-refresh-secret
DATABASE_URL=your-postgres-url
```

## Step 2: Deploy

```bash
git add .
git commit -m "Add Redis RAG and admin endpoints"
git push origin main
```

## Step 3: Wait for "Live"

Wait for green "Live" badge in Render Dashboard (2-3 minutes)

## Step 4: Initialize Redis (No Shell Required!)

### Via Browser (Easiest):
Visit:
```
https://YOUR-APP.onrender.com/api/admin/init-redis?key=YOUR_ADMIN_KEY
```

### Via cURL:
```bash
curl -X POST "https://YOUR-APP.onrender.com/api/admin/init-redis?key=YOUR_ADMIN_KEY"
```

**Expected Output:**
```json
{
  "success": true,
  "steps": [
    {"step": 1, "status": "✅ Connected"},
    {"step": 2, "status": "✅ Index ready"},
    {"step": 3, "status": "✅ Knowledge base indexed"},
    {"step": 4, "status": "✅ 12 documents indexed"}
  ]
}
```

## Step 5: Verify

Visit:
```
https://YOUR-APP.onrender.com/api/admin/redis-status
```

**Should show:**
```json
{
  "redis_connected": true,
  "rag_ready": true,
  "knowledge_base": {"document_count": 12}
}
```

## Done! 🎉

Your chatbot now has:
- ✅ Redis caching
- ✅ Rate limiting (30/min)
- ✅ RAG knowledge retrieval
- ✅ Security protection

## Test It:
1. Open your app
2. Say "hi" → Should get friendly greeting
3. Ask "What is RSI?" → Should get accurate answer
4. Ask same question again → Should be instant (cached)

## Files Changed:
- ✅ `routes.py` - Added admin endpoints
- ✅ `redis_client.py` - SSL support for Render
- ✅ `render.yaml` - Redis service config
- ✅ `RENDER_FREE_TIER_SETUP.md` - Full guide

## Cost: $0/month

---

**Questions?** See `RENDER_FREE_TIER_SETUP.md` for detailed troubleshooting.
