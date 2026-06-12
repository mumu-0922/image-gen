[CmdletBinding(PositionalBinding = $false)]
param(
    [switch]$NoAppendV1,
    [switch]$UseUv,
    [int]$RequestTimeout = 600,
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]]$ImageGenArgs
)

$ErrorActionPreference = "Stop"

function Fail($message) {
    Write-Error $message
    exit 1
}

$codexHome = $env:CODEX_HOME
if (-not $codexHome) {
    $codexHome = Join-Path $HOME ".codex"
}

$configPath = Join-Path $codexHome "config.toml"
$authPath = Join-Path $codexHome "auth.json"
$enginePath = Join-Path $codexHome "skills\.system\imagegen\scripts\image_gen.py"
$timeoutWrapperPath = Join-Path $codexHome "skills\image-gen\scripts\imagegen_with_timeout.py"

if (-not (Test-Path -LiteralPath $configPath)) {
    Fail "Codex config.toml not found: $configPath"
}
if (-not (Test-Path -LiteralPath $authPath)) {
    Fail "Codex auth.json not found: $authPath"
}
if (-not (Test-Path -LiteralPath $enginePath)) {
    Fail "System imagegen CLI not found: $enginePath"
}
if (-not (Test-Path -LiteralPath $timeoutWrapperPath)) {
    Fail "Timeout wrapper not found: $timeoutWrapperPath"
}
if (-not $ImageGenArgs -or $ImageGenArgs.Count -eq 0) {
    Fail "Missing imagegen CLI arguments. Example: generate-batch --input .\references\relay-test.jsonl --out-dir .\output\imagegen-relay-test --dry-run"
}

$configRaw = Get-Content -LiteralPath $configPath -Raw
$baseUrlMatch = [regex]::Match($configRaw, '(?m)^\s*base_url\s*=\s*"([^"]+)"')
if (-not $baseUrlMatch.Success) {
    Fail "No base_url found in Codex config.toml"
}

$baseUrl = $baseUrlMatch.Groups[1].Value.Trim()
if (-not $NoAppendV1 -and -not ($baseUrl.TrimEnd("/") -match "/v1$")) {
    $baseUrl = $baseUrl.TrimEnd("/") + "/v1"
}

$auth = Get-Content -LiteralPath $authPath -Raw | ConvertFrom-Json
$apiKey = $auth.OPENAI_API_KEY
if (-not $apiKey) {
    $apiKey = $auth.api_key
}
if (-not $apiKey) {
    Fail "No OPENAI_API_KEY found in Codex auth.json"
}

$env:OPENAI_BASE_URL = $baseUrl
$env:OPENAI_API_KEY = $apiKey
$env:IMAGE_GEN_ENGINE = $enginePath
if (-not $env:IMAGE_GEN_REQUEST_TIMEOUT) {
    $env:IMAGE_GEN_REQUEST_TIMEOUT = [string]$RequestTimeout
}

Write-Host "Using OPENAI_BASE_URL: $baseUrl"
Write-Host "Using OPENAI_API_KEY: <set>"
Write-Host "Using IMAGE_GEN_REQUEST_TIMEOUT: $env:IMAGE_GEN_REQUEST_TIMEOUT"

$isDryRun = $false
foreach ($arg in $ImageGenArgs) {
    if ($arg -eq "--dry-run") {
        $isDryRun = $true
        break
    }
}

$uvExe = Join-Path $HOME ".local\bin\uv.exe"
if (-not $isDryRun -and ($UseUv -or (Test-Path -LiteralPath $uvExe))) {
    if (-not (Test-Path -LiteralPath $uvExe)) {
        Fail "uv.exe not found: $uvExe"
    }
    if (-not $env:UV_CACHE_DIR) {
        $env:UV_CACHE_DIR = Join-Path (Get-Location) ".uv-cache"
    }
    & $uvExe run --with openai --with pillow python $timeoutWrapperPath @ImageGenArgs
    exit $LASTEXITCODE
}

$pythonExe = $env:IMAGE_GEN_PYTHON
if (-not $pythonExe) {
    $pythonExe = "python"
}
& $pythonExe $timeoutWrapperPath @ImageGenArgs
exit $LASTEXITCODE
