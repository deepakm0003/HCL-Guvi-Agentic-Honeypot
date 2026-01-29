# Agentic Honeypot API - Deployment Guide

## 1. Multi-Turn Test (Local)

Test a full conversation with follow-up messages:

```powershell
.\test-multiturn.ps1
```

This sends 5 scammer messages in sequence with the same session. The agent responds to each, and the conversation history is preserved between turns.

---

## 2. Deploy to Railway

### Step 1: Create Railway Account
- Go to [railway.app](https://railway.app) and sign up (GitHub login works).

### Step 2: New Project
1. Click **New Project**
2. Choose **Deploy from GitHub repo** (connect your repo first)
3. Or choose **Empty Project** and deploy with Railway CLI

### Step 3: Configure
1. Railway will auto-detect the Dockerfile
2. Go to **Variables** and add:
   - `API_KEY` = your secret key (e.g. `my-secret-honeypot-key-0003`)
   - `OPENAI_API_KEY` = your OpenAI key
   - `REDIS_URL` = optional (uses in-memory if not set)

### Step 4: Deploy
- Railway builds and deploys automatically
- Your API URL: `https://your-app-name.up.railway.app`

### Step 5: Test
```powershell
Invoke-RestMethod -Uri "https://YOUR-RAILWAY-URL/honeypot" -Method Post -Headers @{"x-api-key"="my-secret-honeypot-key-0003"; "Content-Type"="application/json"} -Body '{"sessionId":"test-123","message":{"sender":"scammer","text":"Your bank account will be blocked today.","timestamp":"2026-01-21T10:15:30Z"},"conversationHistory":[],"metadata":{"channel":"SMS","language":"English","locale":"IN"}}'
```

---

## 3. Deploy to Render

### Step 1: Create Render Account
- Go to [render.com](https://render.com) and sign up.

### Step 2: New Web Service
1. Click **New** → **Web Service**
2. Connect your GitHub repo
3. Configure:
   - **Name:** honeypot-api
   - **Runtime:** Docker
   - **Dockerfile Path:** `./Dockerfile`
   - **Instance Type:** Free (or paid for better performance)

### Step 3: Environment Variables
Add in **Environment** tab:
- `API_KEY` = your secret key
- `OPENAI_API_KEY` = your OpenAI key
- `REDIS_URL` = optional (leave empty for in-memory)

### Step 4: Deploy
- Render builds and deploys
- Your API URL: `https://honeypot-api.onrender.com` (or similar)

### Step 5: Health Check
- Render uses `/health` for health checks
- Free tier may sleep after inactivity; first request may be slow

---

## 4. Deploy with Docker (Self-Hosted)

### Build and Run Locally
```bash
docker build -t honeypot-api .
docker run -p 8000:8000 -e API_KEY=your-key -e OPENAI_API_KEY=sk-your-key honeypot-api
```

### With .env file
```bash
docker run -p 8000:8000 --env-file .env honeypot-api
```

---

## 5. Register with GUVI Hackathon

1. **Get your public API URL** (from Railway, Render, or your server)
   - Example: `https://honeypot-api.onrender.com`

2. **Ensure your endpoint is reachable**
   - GUVI will send POST requests to: `https://YOUR-URL/honeypot`
   - Headers required: `x-api-key`, `Content-Type: application/json`

3. **Submit to hackathon**
   - Use the hackathon portal to register your API URL
   - Use the same `API_KEY` you configured (GUVI may need it for evaluation)

4. **Callback is automatic**
   - When engagement ends, your API sends results to:
   - `https://hackathon.guvi.in/api/updateHoneyPotFinalResult`
   - No extra setup needed

---

## Quick Reference

| Platform | URL After Deploy | Notes |
|----------|------------------|-------|
| Railway | `https://xxx.up.railway.app` | Auto HTTPS |
| Render | `https://xxx.onrender.com` | Free tier sleeps |
| Docker | `http://YOUR-SERVER-IP:8000` | Need reverse proxy for HTTPS |

---

## Troubleshooting

- **401 Unauthorized:** Check `x-api-key` header matches `API_KEY` env var
- **500 Error:** Check `OPENAI_API_KEY` is valid and has credits
- **Slow first request (Render):** Free tier cold start; wait ~30 seconds
- **Redis errors:** App falls back to in-memory; sessions won't persist across restarts
