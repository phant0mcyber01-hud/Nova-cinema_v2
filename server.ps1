# Nova Cinema как постоянный сервер на этом компьютере.
#
#   powershell -ExecutionPolicy Bypass -File server.ps1           запустить
#   powershell -ExecutionPolicy Bypass -File server.ps1 -Stop     остановить
#   powershell -ExecutionPolicy Bypass -File server.ps1 -Status   что сейчас живо
#
# Отличие от serve.ps1: тот запускает три окна для показа, а этот работает без
# окон и присматривает за процессами. Если API, бот или туннель падают — поднимает
# заново. Если Cloudflare выдал новый адрес — вписывает его в .env и перезапускает
# API и бота, чтобы Telegram открывал рабочую ссылку.
#
# Чего скрипт не может: разбудить уснувший компьютер. Спящий ноутбук — это
# выключенный сервер. Настройка крышки и сна — в параметрах питания Windows.

param(
    [switch]$Stop,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$logs = Join-Path $root "logs"
$state = Join-Path $logs "server-state.json"
$tunnelLog = Join-Path $logs "cloudflared.log"

New-Item -ItemType Directory -Force -Path $logs | Out-Null

function Write-Line($text, $color = "Gray") {
    $stamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$stamp] $text" -ForegroundColor $color
    Add-Content -Path (Join-Path $logs "server.log") -Value "[$stamp] $text" -Encoding UTF8
}

function Get-State {
    if (Test-Path $state) { return Get-Content $state -Raw -Encoding UTF8 | ConvertFrom-Json }
    return $null
}

function Save-State($api, $bot, $tunnel, $url) {
    @{ api = $api; bot = $bot; tunnel = $tunnel; url = $url } |
        ConvertTo-Json | Set-Content -Path $state -Encoding UTF8
}

function Test-Alive($processId) {
    if (-not $processId) { return $false }
    $null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)
}

function Stop-All {
    $saved = Get-State
    if ($saved) {
        foreach ($processId in @($saved.api, $saved.bot, $saved.tunnel)) {
            if (Test-Alive $processId) {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    # Всё, что могло остаться от предыдущих запусков. Забытый bot.py — это не
    # мусор, а второй опрашивающий: Telegram отдаёт обновления одному из них, и
    # кнопку меню перетирает тот, кто стартовал последним.
    Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*bot.py*" -or $_.CommandLine -like "*uvicorn*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Remove-Item $state -ErrorAction SilentlyContinue

    # И сам присмотр — иначе он через пятнадцать секунд поднимет всё обратно,
    # а второй запуск скрипта начнёт спорить с первым за один и тот же порт.
    Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
        Where-Object { $_.CommandLine -like "*server.ps1*" -and $_.ProcessId -ne $PID } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

    Write-Line "остановлено" "Yellow"
}

if ($Stop) { Stop-All; exit 0 }

if ($Status) {
    $saved = Get-State
    if (-not $saved) { Write-Host "не запущен"; exit 0 }
    Write-Host "адрес   : $($saved.url)"
    Write-Host "API     : $(if (Test-Alive $saved.api) { 'работает' } else { 'упал' })"
    Write-Host "бот     : $(if (Test-Alive $saved.bot) { 'работает' } else { 'упал' })"
    Write-Host "туннель : $(if (Test-Alive $saved.tunnel) { 'работает' } else { 'упал' })"
    exit 0
}

if (-not (Test-Path $python)) { Write-Line "нет $python" "Red"; exit 1 }
if (-not (Test-Path $cloudflared)) { Write-Line "нет cloudflared" "Red"; exit 1 }

function Start-Hidden($file, $arguments, $workingDirectory, $name) {
    # Без перенаправления вывод скрытого процесса пропадает: бот падал молча, и
    # понять почему было нельзя.
    $out = Join-Path $logs "$name.out.log"
    $err = Join-Path $logs "$name.err.log"
    (Start-Process -FilePath $file -ArgumentList $arguments -WorkingDirectory $workingDirectory `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err).Id
}

function Start-Tunnel {
    Remove-Item $tunnelLog -ErrorAction SilentlyContinue
    # Путь к проекту содержит пробелы и тире, а Start-Process не заключает
    # аргументы в кавычки сам — поэтому не --logfile, а перенаправление потока.
    # Адрес быстрого туннеля Cloudflare печатает именно в stderr.
    $processId = (Start-Process -FilePath $cloudflared `
        -ArgumentList @("tunnel", "--url", "http://localhost:8000", "--no-autoupdate", "--protocol", "http2") `
        -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -RedirectStandardError $tunnelLog).Id
    foreach ($attempt in 1..80) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $tunnelLog) {
            $found = Select-String -Path $tunnelLog -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" `
                -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) {
                $candidate = $found.Matches[0].Value
                # Адрес печатается раньше, чем поднимается соединение с краем
                # сети. Ждём, пока он начнёт отвечать, иначе присмотр решит,
                # что туннель мёртв, и убьёт его на середине подключения.
                foreach ($probe in 1..40) {
                    try {
                        Invoke-WebRequest -Uri "$candidate/api/settings" -TimeoutSec 5 -UseBasicParsing | Out-Null
                        return @{ id = $processId; url = $candidate; ready = $true }
                    } catch { Start-Sleep -Milliseconds 1500 }
                }
                return @{ id = $processId; url = $candidate; ready = $false }
            }
        }
    }
    return @{ id = $processId; url = $null; ready = $false }
}

function Set-PublicUrl($url) {
    $envPath = Join-Path $root ".env"
    $lines = Get-Content $envPath -Encoding UTF8 | ForEach-Object {
        if ($_ -like "WEBAPP_URL=*") { "WEBAPP_URL=$url" }
        elseif ($_ -like "CORS_ORIGINS=*") { "CORS_ORIGINS=$url" }
        else { $_ }
    }
    # Set-Content -Encoding UTF8 в Windows PowerShell 5.1 ставит BOM, а он
    # прилипает к первому ключу: BOT_TOKEN превращается в ﻿BOT_TOKEN,
    # и бот падает с «Token is invalid». Пишем без BOM.
    [System.IO.File]::WriteAllLines($envPath, $lines, (New-Object System.Text.UTF8Encoding($false)))
}

function Wait-Api {
    foreach ($attempt in 1..60) {
        try {
            Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/settings" -TimeoutSec 2 -UseBasicParsing | Out-Null
            return $true
        } catch { Start-Sleep -Milliseconds 500 }
    }
    return $false
}

function Find-Process($pattern) {
    $found = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -like $pattern } |
        Select-Object -First 1
    if ($found) { return $found.ProcessId }
    return $null
}

function Read-EnvUrl {
    $line = Get-Content (Join-Path $root ".env") -Encoding UTF8 |
        Where-Object { $_ -like "WEBAPP_URL=*" } | Select-Object -First 1
    if ($line) { return $line.Substring(11).Trim() }
    return $null
}

# Если стенд уже работает и публичный адрес отвечает, трогать его незачем.
# Убить живой туннель ради нового со случайным именем значит сломать показ на
# ровном месте: адрес сменится, кнопка бота устареет, а новый туннель ещё не
# факт что встанет.
$adopted = $false
$existingUrl = Read-EnvUrl
if ($existingUrl -and $existingUrl -like "https://*") {
    try {
        Invoke-WebRequest -Uri "$existingUrl/api/settings" -TimeoutSec 12 -UseBasicParsing | Out-Null
        $api = Find-Process "*uvicorn*"
        $tunnelProcess = Get-Process cloudflared -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($api -and $tunnelProcess) {
            $url = $existingUrl
            $tunnel = @{ id = $tunnelProcess.Id; url = $url; ready = $true }
            $bot = Find-Process "*bot.py*"
            if (-not $bot) {
                $bot = Start-Hidden $python @("bot.py") $root "bot"
                Write-Line "бот не работал, запустил" "Yellow"
            }
            Save-State $api $bot $tunnel.id $url
            Write-Line "подхватываю уже работающее: $url" "Green"
            Write-Line "работает: API $api, бот $bot, туннель $($tunnel.id)" "Green"
            $adopted = $true
        }
    } catch {
        $adopted = $false
    }
}

if (-not $adopted) {

Stop-All

Write-Line "собираю фронтенд"
Push-Location (Join-Path $root "frontend")
cmd /c "npm run build" | Out-Null
Pop-Location
if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
    Write-Line "сборка не получилась" "Red"; exit 1
}

# API поднимается первым. Готовность туннеля проверяется запросом к
# /api/settings через него же — пока приложение не отвечает, проверять нечего,
# и туннель, который на самом деле работает, был бы признан мёртвым.
$api = Start-Hidden $python @("-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000") $root "api"
if (-not (Wait-Api)) { Write-Line "API не ответил" "Red"; exit 1 }

$tunnel = Start-Tunnel
if (-not $tunnel.url) { Write-Line "туннель не поднялся, смотрите $tunnelLog" "Red"; exit 1 }
$url = $tunnel.url
Set-PublicUrl $url
if ($tunnel.ready) { Write-Line "адрес: $url" "Green" }
else { Write-Line "адрес: $url (пока не отвечает, присмотр подождёт)" "Yellow" }

# Бот читает WEBAPP_URL при старте, поэтому запускается после того, как адрес
# записан в .env.
$bot = Start-Hidden $python @("bot.py") $root "bot"
Save-State $api $bot $tunnel.id $url
Write-Line "работает: API $api, бот $bot, туннель $($tunnel.id)" "Green"

}

Write-Line "закрывать это окно можно, процессы останутся"

# --- присмотр ---------------------------------------------------------------
$misses = 0
$botFailures = 0
$graceUntil = (Get-Date).AddSeconds(60)
while ($true) {
    Start-Sleep -Seconds 15

    # Живого процесса мало: cloudflared остаётся запущенным и после того, как
    # соединение с краем сети развалилось, и молча крутит переподключения — а
    # публичный адрес в это время не отвечает. Спрашиваем сам адрес.
    # Свежий адрес trycloudflare доступен не сразу: имени нужно разойтись по
    # сети. Пока идёт прогрев — не проверяем, иначе присмотр убьёт туннель,
    # который вот-вот заработает, поднимет следующий, и так по кругу с новым
    # адресом каждую минуту.
    if ((Get-Date) -lt $graceUntil) { continue }

    $reachable = $false
    if ($url) {
        try {
            Invoke-WebRequest -Uri "$url/api/settings" -TimeoutSec 12 -UseBasicParsing | Out-Null
            $reachable = $true
        } catch { $reachable = $false }
    }
    # Одна неудачная проверка — это может быть просто моргнувшая сеть. Туннель
    # пересоздаётся с новым адресом, а значит и с перезапуском бота, поэтому
    # цена ошибки высокая: ждём двух подряд.
    if ($reachable) { $misses = 0 } else { $misses = $misses + 1 }

    # Пересоздание меняет адрес и требует перезапуска бота — цена ошибки высокая:
    # терпим минуту молчания, прежде чем решить, что туннель мёртв.
    if ((-not (Test-Alive $tunnel.id)) -or ($misses -ge 4)) {
        $misses = 0
        Write-Line "адрес не отвечает, поднимаю туннель заново" "Yellow"
        if (Test-Alive $tunnel.id) { Stop-Process -Id $tunnel.id -Force -ErrorAction SilentlyContinue }
        $tunnel = Start-Tunnel
        if ($tunnel.url -and $tunnel.url -ne $url) {
            # Новый адрес: Telegram должен узнать о нём, иначе кнопка ведёт в никуда.
            $url = $tunnel.url
            Set-PublicUrl $url
            Write-Line "новый адрес: $url — перезапускаю API и бота" "Yellow"
            foreach ($processId in @($api, $bot)) {
                if (Test-Alive $processId) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue }
            }
            $api = Start-Hidden $python @("-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000") $root "api"
            Wait-Api | Out-Null
            $bot = Start-Hidden $python @("bot.py") $root "bot"
        }
        $graceUntil = (Get-Date).AddSeconds(120)
    }

    if (-not (Test-Alive $api)) {
        Write-Line "API упал, поднимаю заново" "Yellow"
        $api = Start-Hidden $python @("-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000") $root "api"
        Wait-Api | Out-Null
    }

    if (-not (Test-Alive $bot)) {
        # Если бот падает раз за разом — обычно потому, что связи нет вообще, —
        # поднимать его каждые пятнадцать секунд бессмысленно: каждый запуск
        # ещё и дёргает Telegram настройкой кнопки меню. Отступаем всё дальше,
        # максимум до пяти минут.
        $botFailures = $botFailures + 1
        if ($botFailures -le 3 -or ($botFailures % [Math]::Min(20, $botFailures * 2)) -eq 0) {
            Write-Line "бот не работает (попытка $botFailures), поднимаю заново" "Yellow"
            $bot = Start-Hidden $python @("bot.py") $root "bot"
        }
    } else {
        $botFailures = 0
    }

    Save-State $api $bot $tunnel.id $url
}
