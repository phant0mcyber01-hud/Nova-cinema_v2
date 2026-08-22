# Запуск демо-стенда Nova Cinema на этой машине.
#
#   powershell -ExecutionPolicy Bypass -File demo.ps1
#
# Поднимает API и фронтенд в отдельных окнах и печатает ссылки для входа.
# Закрыть демо — закрыть эти два окна.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Не найден $python — сначала создайте виртуальное окружение." -ForegroundColor Red
    exit 1
}

function Test-Port($port) {
    $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

if (Test-Port 8000) {
    Write-Host "Порт 8000 уже занят — считаю, что API запущен." -ForegroundColor Yellow
} else {
    Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $root
    Write-Host "API запускается на http://127.0.0.1:8000"
}

if (Test-Port 5173) {
    Write-Host "Порт 5173 уже занят — считаю, что фронтенд запущен." -ForegroundColor Yellow
} else {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
        -WorkingDirectory (Join-Path $root "frontend")
    Write-Host "Фронтенд запускается на http://localhost:5173"
}

Write-Host "Жду, пока поднимется API..."
$ready = $false
foreach ($attempt in 1..40) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/settings" -TimeoutSec 2 -UseBasicParsing | Out-Null
        $ready = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $ready) {
    Write-Host "API не ответил. Посмотрите, что пишет его окно." -ForegroundColor Red
    exit 1
}

Write-Host ""
& $python (Join-Path $root "demo_login.py")
Write-Host "Каталог без входа: http://localhost:5173" -ForegroundColor Cyan
