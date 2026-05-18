param(
    [switch]$AppendV1,
    [Parameter(ValueFromRemainingArguments = $true)]
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

if (-not (Test-Path -LiteralPath $configPath)) {
    Fail "Codex config.toml not found: $configPath"
}
if (-not (Test-Path -LiteralPath $authPath)) {
    Fail "Codex auth.json not found: $authPath"
}
if (-not (Test-Path -LiteralPath $enginePath)) {
    Fail "System imagegen CLI not found: $enginePath"
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
if ($AppendV1 -and -not ($baseUrl.TrimEnd("/") -match "/v1$")) {
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

Write-Host "Using OPENAI_BASE_URL: $baseUrl"
Write-Host "Using OPENAI_API_KEY: <set>"

$pythonExe = $env:IMAGE_GEN_PYTHON
if (-not $pythonExe) {
    $pythonExe = "python"
}

& $pythonExe $enginePath @ImageGenArgs
exit $LASTEXITCODE
