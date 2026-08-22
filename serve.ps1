# Nova Cinema с этого ноутбука как с сервера.
#
#   powershell -ExecutionPolicy Bypass -File serve.ps1
#
# Собирает фронтенд, поднимает API (он же отдаёт Mini App), открывает публичный
# HTTPS-адрес через cloudflared, прописывает этот адрес в .env и запускает бота.
# Останов — закрыть открывшиеся окна.
#
# Адрес временный: при каждом перезапуске туннеля он другой, поэтому скрипт
# каждый раз переписывает WEBAPP_URL и CORS_ORIGINS.

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"

if (-not (Test-Path $python)) {
    Write-Host "Не найден $python" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $cloudflared)) {
    Write-Host "Не найден cloudflared: $cloudflared" -ForegroundColor Red
    exit 1
}

function Test-Port($port) {
    $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host "Собираю фронтенд..."
Push-Location (Join-Path $root "frontend")
cmd /c "npm run build" | Out-Null
Pop-Location
if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Write-Host "Сборка не получилась." -ForegroundColor Red
    exit 1
}

Write-Host "Поднимаю туннель..."
$log = Join-Path $env:TEMP "nova-cloudflared.log"
if (Test-Path $log) { Remove-Item $log -Force }
Start-Process -FilePath $cloudflared `
    -ArgumentList "tunnel", "--url", "http://localhost:8000", "--no-autoupdate", "--logfile", $log `
    -WindowStyle Minimized

$public = $null
foreach ($attempt in 1..60) {
    Start-Sleep -Milliseconds 500
    if (Test-Path $log) {
        $match = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($match) {
            $public = $match.Matches[0].Value
            break
        }
    }
}
if (-not $public) {
    Write-Host "Туннель не поднялся, смотрите $log" -ForegroundColor Red
    exit 1
}
Write-Host "Публичный адрес: $public" -ForegroundColor Green

# Бот отдаёт этот адрес Telegram, а браузер сверяет с ним CORS.
$envPath = Join-Path $root ".env"
$lines = Get-Content $envPath -Encoding UTF8
$lines = $lines | ForEach-Object {
    if ($_ -like "WEBAPP_URL=*") { "WEBAPP_URL=$public" }
    elseif ($_ -like "CORS_ORIGINS=*") { "CORS_ORIGINS=$public" }
    else { $_ }
}
[System.IO.File]::WriteAllLines($envPath, $lines, (New-Object System.Text.UTF8Encoding($false)))

if (Test-Port 8000) {
    Write-Host "Порт 8000 занят: остановите старый API, чтобы он перечитал адрес." -ForegroundColor Yellow
} else {
    Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000" `
        -WorkingDirectory $root
}

Write-Host "Жду API..."
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
    Write-Host "API не ответил." -ForegroundColor Red
    exit 1
}

Start-Process -FilePath $python -ArgumentList "bot.py" -WorkingDirectory $root
Write-Host "Бот запущен: @NOVA_CINEMA_searchbot"

$lan = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "Открывается:" -ForegroundColor Cyan
Write-Host "  в Telegram — кнопка меню бота @NOVA_CINEMA_searchbot"
Write-Host "  в браузере — $public"
if ($lan) { Write-Host "  в этой Wi-Fi сети — http://${lan}:8000" }
Write-Host ""
& $python (Join-Path $root "demo_login.py")
