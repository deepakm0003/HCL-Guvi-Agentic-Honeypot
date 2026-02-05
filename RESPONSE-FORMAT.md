# API Response Format

## Expected JSON Format

The API **always** returns responses in this exact format:

```json
{
  "status": "success",
  "reply": "Why is my account being suspended?"
}
```

### Field Descriptions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | string | Yes | Either `"success"` or `"error"` |
| `reply` | string | Yes | The agent's response message |

### Examples

**Success Response:**
```json
{
  "status": "success",
  "reply": "Yaar, I'm really worried now. Which bank sent this message? I didn't receive any notification in my banking app."
}
```

**Error Response:**
```json
{
  "status": "error",
  "reply": "Invalid request format"
}
```

### Implementation

The response is implemented using Pydantic model `HoneypotResponse`:

```python
class HoneypotResponse(BaseModel):
    status: Literal["success", "error"]
    reply: str
```

FastAPI automatically serializes this to JSON with the exact format shown above.

### Verification

Test the format:
```bash
curl -X POST https://YOUR-URL/honeypot \
  -H "x-api-key: your-key" \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"test","message":{"sender":"scammer","text":"test","timestamp":"2026-01-21T10:15:30Z"},"conversationHistory":[]}'
```

Expected response:
```json
{"status":"success","reply":"..."}
```
