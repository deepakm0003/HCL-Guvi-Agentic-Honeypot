# Honeypot API - GUVI Hackathon Registration

## API URL

```
https://honeypot-api-production.up.railway.app/honeypot
```

## Authentication

| Header | Value |
|--------|-------|
| `x-api-key` | `my-secret-honeypot-key-0003` |
| `Content-Type` | `application/json` |

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root - API info (no 404) |
| `/health` | GET | Health check |
| `/ready` | GET | Evaluation readiness (fast, no auth) |
| `/honeypot` | POST | Main honeypot API |

**Note:** Visit `https://honeypot-api-production.up.railway.app/` (root) or `/health` to verify the API is up. The base URL without path previously returned 404.

## GUVI Registration

When registering with the hackathon platform, provide:

- **API Endpoint:** `https://honeypot-api-production.up.railway.app/honeypot`
- **API Key:** `my-secret-honeypot-key-0003` (if required by the portal)

## Quick Test (PowerShell)

```powershell
# Single request
.\test-honeypot.ps1 -BaseUrl "https://honeypot-api-production.up.railway.app"

# Multi-turn conversation
.\test-multiturn.ps1 -BaseUrl "https://honeypot-api-production.up.railway.app"
```
