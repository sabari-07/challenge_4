# AIgnition Startup Script for PowerShell

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  AIgnition - Revenue Forecasting Platform" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Blue
& .\venv\Scripts\Activate.ps1

# Check if dependencies are installed
if (-not (Test-Path "venv\Lib\site-packages\fastapi")) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Start backend (inherit current session environment so network/DNS settings are preserved)
Write-Host "Starting FastAPI backend..." -ForegroundColor Green
$backendCmd = "cd '$PWD'; .\venv\Scripts\Activate.ps1; python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -UseNewEnvironment:$false

# Wait for backend to be ready
Write-Host "Waiting for backend to be ready..." -ForegroundColor Blue
Start-Sleep -Seconds 5

# Check if frontend dependencies are installed
if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
}

# Start frontend (inherit current session environment)
Write-Host "Starting React frontend..." -ForegroundColor Green
$frontendCmd = "cd '$PWD\frontend'; npm run dev"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -UseNewEnvironment:$false

Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "  SUCCESS! AIgnition is starting!" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "  Two new PowerShell windows opened:" -ForegroundColor Yellow
Write-Host "    - Backend (port 8000)" -ForegroundColor Yellow
Write-Host "    - Frontend (port 3000)" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Close those windows to stop the services" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
