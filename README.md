# Agentic Honeypot API

AI-powered honeypot system for scam detection and intelligence extraction. Detects scam messages, engages scammers via an autonomous AI agent, and extracts structured intelligence.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (create .env from .env.example)
# Required: API_KEY, OPENAI_API_KEY
# Optional: REDIS_URL (falls back to in-memory if unavailable)

# Run the server
python run.py
# Or: uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## API Usage

### Endpoint

```
POST /honeypot
```

### Headers

- `x-api-key`: Your secret API key (required)
- `Content-Type`: application/json

### Request Body

```json
{
  "sessionId": "wertyu-dfghj-ertyui",
  "message": {
    "sender": "scammer",
    "text": "Your bank account will be blocked today. Verify immediately.",
    "timestamp": "2026-01-21T10:15:30Z"
  },
  "conversationHistory": [],
  "metadata": {
    "channel": "SMS",
    "language": "English",
    "locale": "IN"
  }
}
```

### Response

```json
{
  "status": "success",
  "reply": "Why will my account be blocked?"
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| API_KEY | API authentication key | your-secret-api-key |
| OPENAI_API_KEY | OpenAI API key for LLM | (required for full features) |
| REDIS_URL | Redis connection URL | redis://localhost:6379/0 |
| REDIS_SESSION_TTL | Session TTL in seconds | 3600 |
| SCAM_CONFIDENCE_THRESHOLD | Scam detection threshold | 0.7 |

## Architecture

- **Detector**: Hybrid keyword + LLM scam detection
- **Agent**: Indian persona, multi-turn engagement
- **Memory**: Redis per-session (in-memory fallback)
- **Extractor**: LLM + regex intelligence extraction
- **Lifecycle**: Auto-end when 12 messages or 2+ intel items
- **Callback**: Sends final result to GUVI endpoint

## Project Structure

```
app/
├── main.py          # FastAPI app, /honeypot endpoint
├── config.py        # Settings
├── models.py        # Pydantic models
├── services/
│   ├── detector.py  # Scam detection
│   ├── agent.py     # AI agent
│   ├── memory.py    # Redis session memory
│   ├── extractor.py # Intelligence extraction
│   ├── lifecycle.py # Engagement lifecycle
│   └── callback.py  # GUVI callback
└── utils/
    ├── validators.py # Input validation
    └── logging.py   # Structured logging
```

## Testing

- **Single request:** `.\test-honeypot.ps1`
- **Multi-turn conversation:** `.\test-multiturn.ps1`
- **Deployed API:** `.\test-multiturn.ps1 -BaseUrl "https://your-app.onrender.com"`

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for Railway, Render, and Docker deployment instructions.
