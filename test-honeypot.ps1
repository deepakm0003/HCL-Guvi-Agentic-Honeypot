# PowerShell script to test the Honeypot API
# Run: .\test-honeypot.ps1
# Or test production: .\test-honeypot.ps1 -BaseUrl "https://honeypot-api-production.up.railway.app"

param(
    [string]$BaseUrl = "http://localhost:8000"
)

$headers = @{
    "x-api-key"     = "my-secret-honeypot-key-0003"
    "Content-Type"  = "application/json"
}

$body = @{
    sessionId = "test-123"
    message = @{
        sender    = "scammer"
        text     = "Your bank account will be blocked today. Verify immediately."
        timestamp = "2026-01-21T10:15:30Z"
    }
    conversationHistory = @()
    metadata = @{
        channel  = "SMS"
        language = "English"
        locale   = "IN"
    }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "$BaseUrl/honeypot" -Method Post -Headers $headers -Body $body
