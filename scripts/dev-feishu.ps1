# Canonical local Feishu + Gateway bring-up for haitun-workspace.
# Do NOT invent ad-hoc POST /ais bodies - this script is the only allowed model id.
#
# Usage (from repo root, credentials already in env or .env loaded by your shell):
#   powershell -File scripts/dev-feishu.ps1
# Optional:
#   $env:GATEWAY_LISTEN = 'http://127.0.0.1:8765'
#   $env:PSI_FEISHU_APP_ID / $env:PSI_FEISHU_APP_SECRET must be set for both processes.

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Agent = Join-Path $RepoRoot 'examples\haitun-workspace'
$Listen = if ($env:GATEWAY_LISTEN) { $env:GATEWAY_LISTEN } else { 'http://127.0.0.1:8765' }
$AiId = 'feishu-default'
# Company proxy allowlist: deepseek-v4-flash | deepseek-v4-pro only.
# Never use deepseek-v4-flash-free (retired; upstream 400).
$Model = 'deepseek-v4-flash'
$BaseUrl = 'https://misakamikoto.genuineknowledge.cn'
# Proxy accepts the shared placeholder; override with a real key via env when needed.
$ApiKey = if ($env:PSI_MODEL_API_KEY) { $env:PSI_MODEL_API_KEY } else { 'haitun-default' }

if (-not $env:PSI_FEISHU_APP_ID -or -not $env:PSI_FEISHU_APP_SECRET) {
    Write-Error 'Set PSI_FEISHU_APP_ID and PSI_FEISHU_APP_SECRET before starting (Gateway + Channel both need them).'
}

# Same Gateway serves SPA + Feishu + OAuth relay. Feishu console redirect must be:
#   {PSI_OAUTH_CALLBACK_BASE}/oauth/callback
if (-not $env:PSI_OAUTH_CALLBACK_BASE) {
    $env:PSI_OAUTH_CALLBACK_BASE = $Listen
}

# The supervisor (AnDong) spawns a child Session and needs the Gateway to resolve its
# model binding. Its discovery order is PSI_GATEWAY_URL -> .psi/gateway.url ->
# 127.0.0.1:62720 / :8080. Our $Listen is none of those defaults, so without this the
# probe times out (1.5s x 2 defaults, twice per turn ~= 6s) and every turn records
# source=unavailable with no advice - the campaign still runs, just without adaptation.
if (-not $env:PSI_GATEWAY_URL) {
    $env:PSI_GATEWAY_URL = $Listen
}

Set-Location $RepoRoot

Write-Host "Starting Gateway on $Listen (agent=$Agent, feishu-ai-id=$AiId, oauth=$($env:PSI_OAUTH_CALLBACK_BASE))..."
# $Agent contains spaces (the repo path does), and -ArgumentList does NOT quote array
# elements for us: an unquoted path is split on every space and the CLI then reports
# "Unrecognized options: master, of, software, ...". So quote every path we pass.
$gwArgs = @(
    'run', 'psi-agent', 'gateway',
    '--listen', $Listen,
    '--browser',
    '--feishu-ai-id', $AiId,
    '--feishu-workspace-root', "`"$Agent`"",
    '--default-agent', "`"$Agent`"",
    '--verbose'
)
$gw = Start-Process -FilePath 'uv' -ArgumentList $gwArgs -PassThru -NoNewWindow `
    -WorkingDirectory $RepoRoot

$deadline = (Get-Date).AddSeconds(45)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $null = Invoke-RestMethod -Uri "$Listen/ais" -Method GET -TimeoutSec 2
        $ready = $true
        break
    } catch {
        Start-Sleep -Milliseconds 400
    }
}
if (-not $ready) {
    Write-Error "Gateway did not become ready at $Listen"
}

$ais = Invoke-RestMethod -Uri "$Listen/ais" -Method GET
$existing = @($ais | Where-Object { $_.id -eq $AiId })
if ($existing.Count -gt 0 -and $existing[0].model -ne $Model) {
    Write-Host "Replacing $AiId model $($existing[0].model) -> $Model"
    Invoke-RestMethod -Uri "$Listen/ais/$AiId" -Method DELETE | Out-Null
    $existing = @()
}
if ($existing.Count -eq 0) {
    Write-Host "POST /ais id=$AiId model=$Model"
    $body = @{
        id       = $AiId
        provider = 'openai'
        model    = $Model
        api_key  = $ApiKey
        base_url = $BaseUrl
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "$Listen/ais" -Method POST -Body $body -ContentType 'application/json' | Out-Null
} else {
    Write-Host "$AiId already OK (model=$($existing[0].model))"
}

# --session-socket is required by CLI but only used as fallback when --gateway-url routes fail.
$FallbackSocket = '\\.\pipe\psi\channels\fallback'
Write-Host "Starting Feishu channel (--gateway-url $Listen)..."
$chArgs = @(
    'run', 'psi-agent', 'channel', 'feishu',
    '--session-socket', "`"$FallbackSocket`"",
    '--gateway-url', $Listen,
    '--agent', "`"$Agent`"",
    '--require-mention',
    '--verbose'
)
$ch = Start-Process -FilePath 'uv' -ArgumentList $chArgs -PassThru -NoNewWindow `
    -WorkingDirectory $RepoRoot

Write-Host "Gateway pid=$($gw.Id)  Channel pid=$($ch.Id)"
Write-Host "Stop with: Stop-Process -Id $($gw.Id),$($ch.Id)"
Write-Host "Both processes stay attached to this console; Ctrl+C does not kill them - use Stop-Process."
