# PowerShell startup script for Voice Pipeline Agent with Audio Analysis

# Function to cleanup processes on exit
function Cleanup {
    Write-Host "Shutting down services..." -ForegroundColor Yellow
    if ($AudioServerProcess) {
        Stop-Process -Id $AudioServerProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($AgentProcess) {
        Stop-Process -Id $AgentProcess.Id -Force -ErrorAction SilentlyContinue
    }
    exit 0
}

# Function to check if port is in use
function Test-Port {
    param([int]$Port)
    $connection = New-Object System.Net.Sockets.TcpClient
    try {
        $connection.Connect("127.0.0.1", $Port)
        $connection.Close()
        return $true
    }
    catch {
        return $false
    }
}

# Set up signal handlers
$null = Register-EngineEvent PowerShell.Exiting -Action { Cleanup }
try {
    $null = [Console]::CancelKeyPress.Add({ Cleanup })
} catch {
    # Handle case where Console is not available
}

Write-Host "Starting Voice Pipeline Agent with Audio Analysis..." -ForegroundColor Green

# Check if port 8000 is already in use
if (Test-Port -Port 8000) {
    Write-Host "Port 8000 is already in use. Attempting to free it..." -ForegroundColor Yellow
    
    # Try to find and kill processes using port 8000
    $processIds = netstat -ano | findstr :8000 | ForEach-Object { ($_ -split '\s+')[-1] } | Where-Object { $_ -match '^\d+$' } | Sort-Object -Unique
    
    if ($processIds) {
        foreach ($pid in $processIds) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped process $pid using port 8000" -ForegroundColor Yellow
            }
            catch {
                Write-Host "Could not stop process $pid" -ForegroundColor Red
            }
        }
        Start-Sleep -Seconds 2
    }
}

# Create audio-analysis directory if it doesn't exist
if (-not (Test-Path "audio-analysis")) {
    New-Item -ItemType Directory -Path "audio-analysis" | Out-Null
}

# Start the simplified audio analysis server in the background
Write-Host "Starting audio analysis server on port 8000..." -ForegroundColor Cyan
$AudioServerProcess = Start-Process -FilePath "python" -ArgumentList "audio_analysis_server_simple.py" -PassThru -NoNewWindow

# Wait a moment for the server to start
Start-Sleep -Seconds 3

# Check if audio server is running
if ($AudioServerProcess -and !$AudioServerProcess.HasExited) {
    Write-Host "Audio analysis server started successfully (PID: $($AudioServerProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "Failed to start audio analysis server" -ForegroundColor Red
    exit 1
}

# Test the server
Write-Host "Testing audio analysis server..." -ForegroundColor Cyan
$TestResult = python test_audio_server.py
if ($LASTEXITCODE -eq 0) {
    Write-Host "Audio analysis server test passed!" -ForegroundColor Green
} else {
    Write-Host "Audio analysis server test failed!" -ForegroundColor Red
}

# Start the voice agent
Write-Host "Starting voice pipeline agent..." -ForegroundColor Cyan
$AgentProcess = Start-Process -FilePath "python" -ArgumentList "agent.py", "dev" -PassThru -NoNewWindow

Write-Host "Both services are running. Press Ctrl+C to stop." -ForegroundColor Green
Write-Host "Audio Analysis Server: http://localhost:8000" -ForegroundColor Gray
Write-Host "Voice Agent: Running with LiveKit integration" -ForegroundColor Gray

# Wait for processes to finish
try {
    while (!$AgentProcess.HasExited -and !$AudioServerProcess.HasExited) {
        Start-Sleep -Seconds 1
    }
} finally {
    Cleanup
}
