# start_all.ps1 - Inicia todos os servicos do CPES
# Corner Pressure Elite System - Resolucao de conflito de portas

Write-Host "=== Iniciando Corner Pressure Elite System ===" -ForegroundColor Cyan

$basePath = "C:\Users\danew\Documents\CORNER PRESSURE ELITE"
$apiPath = "$basePath\corner-pressure-elite"
$dashPath = "$basePath\dashboard"

# 1. Verificar se WAHA esta rodando
Write-Host "`n[1/4] Verificando WAHA (porta 3000)..." -ForegroundColor Yellow
try {
    $null = docker info 2>&1
    $dockerOk = $true
} catch {
    $dockerOk = $false
}
if (-not $dockerOk) {
    Write-Host "Docker nao esta rodando. Inicie o Docker Desktop e execute novamente." -ForegroundColor Yellow
    Write-Host "Ou inicie o WAHA manualmente em outro terminal e pressione Enter para continuar..." -ForegroundColor Yellow
    Read-Host
} else {
    $wahaRunning = docker ps --filter "name=waha" --format "{{.Names}}" 2>$null
    if ($wahaRunning -ne "waha") {
        Write-Host "Iniciando WAHA na porta 3000..." -ForegroundColor Green
        docker run -d --name waha -p 3000:3000 -v ~/.waha:/app/.sessions devlikeapro/waha:latest
        Start-Sleep -Seconds 3
    } else {
        Write-Host "WAHA ja esta rodando" -ForegroundColor Green
    }
}

# 2. Iniciar FastAPI (backend)
Write-Host "`n[2/4] Iniciando FastAPI na porta 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$apiPath'; uvicorn api_server:app --host 127.0.0.1 --port 8000"
Start-Sleep -Seconds 5

# 3. Iniciar Dashboard (Next.js) na porta 3001
Write-Host "`n[3/4] Iniciando Dashboard na porta 3001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$dashPath'; npm run dev"
Start-Sleep -Seconds 10

# 4. Verificar todos os servicos
Write-Host "`n[4/4] Verificando servicos..." -ForegroundColor Yellow

# WAHA (3000) - usa raiz ou /api/sessions (sem /health)
try {
    $waha = Invoke-WebRequest -Uri "http://localhost:3000/" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK] WAHA (3000)" -ForegroundColor Green
} catch {
    Write-Host "[ERRO] WAHA (3000): $($_.Exception.Message)" -ForegroundColor Red
}

# FastAPI (8000)
try {
    $api = Invoke-RestMethod -Uri "http://localhost:8000/api/health" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK] FastAPI (8000)" -ForegroundColor Green
} catch {
    Write-Host "[ERRO] FastAPI (8000): $($_.Exception.Message)" -ForegroundColor Red
}

# Dashboard (3001)
try {
    $dash = Invoke-WebRequest -Uri "http://localhost:3001" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
    Write-Host "[OK] Dashboard (3001)" -ForegroundColor Green
} catch {
    Write-Host "[ERRO] Dashboard (3001): $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n=== Sistema Iniciado ===" -ForegroundColor Cyan
Write-Host "Dashboard: http://localhost:3001" -ForegroundColor White
Write-Host "API:       http://localhost:8000" -ForegroundColor White
Write-Host "WAHA:      http://localhost:3000" -ForegroundColor White
Write-Host "`nPressione qualquer tecla para iniciar o Monitor..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# 5. Iniciar Monitor
Write-Host "`nIniciando Monitor..." -ForegroundColor Yellow
Set-Location $apiPath
python monitor.py
