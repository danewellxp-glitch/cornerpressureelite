# kill_all.ps1 - Encerra todos os servicos do CPES
# Frontend, Backend, Robo, WAHA

Write-Host "=== Encerrando servicos CPES ===" -ForegroundColor Cyan

function Kill-Port {
    param([int]$Port)
    $lines = netstat -ano | Select-String ":$Port\s+.*LISTENING"
    foreach ($line in $lines) {
        $parts = $line -split '\s+'
        $procId = $parts[-1]
        if ($procId -match '^\d+$') {
            taskkill /F /PID $procId 2>$null | Out-Null
            Write-Host "Porta ${Port} (PID $procId): encerrado" -ForegroundColor Yellow
        }
    }
    if (-not $lines) { Write-Host "Porta ${Port}: nada rodando" -ForegroundColor Gray }
}

# Frontend (3001)
Kill-Port -Port 3001

# WAHA (3000)
Kill-Port -Port 3000

# Backend FastAPI (8000)
Kill-Port -Port 8000

# Python (main.py, monitor.py)
$pyProcs = Get-Process -Name python -ErrorAction SilentlyContinue
if ($pyProcs) {
    foreach ($p in $pyProcs) {
        taskkill /F /PID $p.Id 2>$null | Out-Null
        Write-Host "Python (PID $($p.Id)): encerrado" -ForegroundColor Yellow
    }
} else {
    Write-Host "Python: nada rodando" -ForegroundColor Gray
}

# Docker WAHA
try {
    $waha = docker ps -q --filter "name=waha" 2>$null
    if ($waha) {
        docker stop waha 2>$null | Out-Null
        Write-Host "Docker WAHA: encerrado" -ForegroundColor Yellow
    } else {
        Write-Host "Docker WAHA: nao rodando" -ForegroundColor Gray
    }
} catch {
    Write-Host "Docker: nao disponivel" -ForegroundColor Gray
}

Write-Host "`n=== Servicos encerrados ===" -ForegroundColor Cyan
Write-Host "Banco SQLite (data/cpes.db): arquivo mantido - nao requer processo" -ForegroundColor Gray
