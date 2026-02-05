# Deployment Checklist

## ✅ Pre-Deployment Checklist

- [x] Code pushed to GitHub
- [x] Dockerfile exists
- [x] requirements.txt exists
- [x] Environment variables ready

## 🚂 Railway Deployment

### Quick Steps:
1. Go to https://railway.app → Login with GitHub
2. New Project → Deploy from GitHub repo
3. Select: `deepakm0003/HCL-Guvi-Agentic-Honeypot`
4. Settings → Variables → Add:
   - `API_KEY` = `my-secret-honeypot-key-0003`
   - `OPENAI_API_KEY` = `sk-your-openai-api-key` (get from https://platform.openai.com/api-keys)
5. Wait for deploy (2-3 minutes)
6. Get URL from Settings → Domains
7. Test: `https://YOUR-APP.up.railway.app/health`

### Your Railway URL:
```
https://honeypot-api-production.up.railway.app
```

### GUVI Submission URL:
```
https://honeypot-api-production.up.railway.app/honeypot
```

---

## 🎨 Render Deployment

### Quick Steps:
1. Go to https://render.com → Sign up with GitHub
2. New → Web Service
3. Connect repo: `HCL-Guvi-Agentic-Honeypot`
4. Configure:
   - Name: `hcl-guvi-agentic-honeypot`
   - Runtime: `Docker`
   - Dockerfile Path: `./Dockerfile`
5. Environment → Add:
   - `API_KEY` = `my-secret-honeypot-key-0003`
   - `OPENAI_API_KEY` = `sk-your-openai-api-key` (get from https://platform.openai.com/api-keys)
6. Create Web Service
7. Wait for build (5-10 minutes)
8. Get URL from dashboard

### Your Render URL:
```
https://hcl-guvi-agentic-honeypot.onrender.com
```

### GUVI Submission URL:
```
https://hcl-guvi-agentic-honeypot.onrender.com/honeypot
```

---

## 🧪 Testing After Deployment

### Test Health Endpoint:
```powershell
curl https://YOUR-URL/health
```

Expected: `{"status":"ok","service":"honeypot"}`

### Test Honeypot Endpoint:
```powershell
curl -X POST https://YOUR-URL/honeypot `
  -H "x-api-key: my-secret-honeypot-key-0003" `
  -H "Content-Type: application/json" `
  -d '{
    "sessionId": "test-123",
    "message": {
      "sender": "scammer",
      "text": "Your bank account will be blocked today.",
      "timestamp": 1769776085000
    },
    "conversationHistory": []
  }'
```

Expected: `{"status":"success","reply":"..."}`

---

## 📝 GUVI Submission Details

### Required Fields:
- **API Endpoint URL**: `https://YOUR-URL/honeypot`
- **API Key**: `my-secret-honeypot-key-0003`

### Test Before Submitting:
✅ Health check returns 200  
✅ POST /honeypot returns `{"status":"success","reply":"..."}`  
✅ API key authentication works  
✅ Handles Unix timestamp format  

---

## 🔧 Troubleshooting

### Railway:
- **Build fails**: Check logs → Deployments → View logs
- **Environment vars not working**: Settings → Variables → Verify spelling
- **App not starting**: Check PORT env var (Railway sets automatically)

### Render:
- **Build fails**: Check build logs → Look for Python/pip errors
- **App sleeps**: Free tier sleeps after 15 min inactivity → First request may be slow
- **502 Bad Gateway**: Check if app is running → Logs → Restart if needed

---

## 🚀 Quick Deploy Commands

### Railway (via CLI):
```bash
npm i -g @railway/cli
railway login
railway link
railway up
```

### Render (via CLI):
```bash
npm i -g render-cli
render login
render deploy
```

---

## ✅ Final Checklist Before GUVI Submission

- [ ] API is deployed and accessible
- [ ] Health endpoint returns OK
- [ ] POST /honeypot returns correct format
- [ ] API key authentication works
- [ ] Tested with GUVI sample request
- [ ] URL is correct (include `/honeypot` path)
- [ ] Environment variables are set correctly
