# PowerShell script to test the Honeypot API
# Run: .\test-honeypot.ps1

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

Invoke-RestMethod -Uri "http://localhost:8000/honeypot" -Method Post -Headers $headers -Body $body
