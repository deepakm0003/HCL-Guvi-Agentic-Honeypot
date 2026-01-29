# Multi-turn conversation test for Honeypot API
# Simulates a full scam conversation with follow-up messages
# Run: .\test-multiturn.ps1
# Or test deployed API: .\test-multiturn.ps1 -BaseUrl "https://your-app.onrender.com"

param(
    [string]$BaseUrl = "http://localhost:8000"
)

$baseUrl = "$BaseUrl/honeypot"
$headers = @{
    "x-api-key"    = "my-secret-honeypot-key-0003"
    "Content-Type" = "application/json"
}

$sessionId = "test-multiturn-$(Get-Date -Format 'HHmmss')"
$conversationHistory = @()

# Scammer messages to simulate (in order)
$scammerMessages = @(
    "Your bank account will be blocked today. Verify immediately.",
    "Share your UPI ID to avoid account suspension.",
    "Click this link to verify: https://fake-bank-verify.com/secure",
    "Send OTP to 9876543210 for verification.",
    "Your account XXXX-XXXX-1234 needs KYC update."
)

Write-Host "=== Multi-Turn Honeypot Test ===" -ForegroundColor Cyan
Write-Host "Session ID: $sessionId`n" -ForegroundColor Gray

foreach ($i in 0..($scammerMessages.Count - 1)) {
    $scammerText = $scammerMessages[$i]
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

    # Build conversation history for this turn
    $historyForRequest = @()
    foreach ($h in $conversationHistory) {
        $historyForRequest += @{
            sender    = $h.sender
            text      = $h.text
            timestamp = $h.timestamp
        }
    }

    $body = @{
        sessionId           = $sessionId
        message             = @{
            sender    = "scammer"
            text      = $scammerText
            timestamp = $timestamp
        }
        conversationHistory = $historyForRequest
        metadata            = @{
            channel  = "SMS"
            language = "English"
            locale   = "IN"
        }
    } | ConvertTo-Json -Depth 5

    Write-Host "[Turn $($i + 1)] Scammer: $scammerText" -ForegroundColor Red

    try {
        $response = Invoke-RestMethod -Uri $baseUrl -Method Post -Headers $headers -Body $body
        Write-Host "[Turn $($i + 1)] Agent:  $($response.reply)" -ForegroundColor Green
        Write-Host ""

        # Add to conversation history for next turn
        $conversationHistory += @{ sender = "scammer"; text = $scammerText; timestamp = $timestamp }
        $conversationHistory += @{ sender = "user"; text = $response.reply; timestamp = $timestamp }
    }
    catch {
        Write-Host "Error: $_" -ForegroundColor Yellow
        break
    }

    Start-Sleep -Milliseconds 500
}

Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host "Check server logs for callback to GUVI (if lifecycle conditions met)." -ForegroundColor Gray
