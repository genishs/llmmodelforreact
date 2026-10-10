# opencode-setup.ps1 - install opencode on Windows and point it at the halo-ubuntu llama-server
#
#   Run via opencode-setup.bat (double-click), or:
#     powershell -NoProfile -ExecutionPolicy Bypass -File .\opencode-setup.ps1
#
#   What it does (safe to re-run):
#     1. ask for the API key once (stored in user env LLM_KEY, shared with llmchat.bat)
#     2. check the server is reachable
#     3. download a pinned opencode release from GitHub and verify its sha256
#     4. install to %LOCALAPPDATA%\Programs\opencode and add it to the user PATH
#     5. write the opencode config (existing config is backed up, never silently replaced)
#
#   NOTE: keep this file ASCII-only. It is downloaded and executed; non-ASCII text risks encoding breakage.
param(
  [string]$Url = $(if ($env:LLM_URL) { $env:LLM_URL } else { "http://192.168.234.209:8080" }),
  [string]$Version = "v1.18.35"
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Step($m) { Write-Host "`n== $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "   OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "   !!  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "   XX  $m" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 1. API key
Step "1/5 API key"
$key = [Environment]::GetEnvironmentVariable("LLM_KEY", "User")
if (-not $key) { $key = $env:LLM_KEY }
if (-not $key) {
  $key = Read-Host "   Enter API key (from LLM_*.txt on halo-ubuntu)"
  if (-not $key) { Fail "No key entered." }
}
[Environment]::SetEnvironmentVariable("LLM_KEY", $key, "User"); $env:LLM_KEY = $key
Ok "LLM_KEY saved to user environment"

# ---------------------------------------------------------------- 2. server
Step "2/5 Server $Url"
try { Invoke-WebRequest "$Url/health" -UseBasicParsing -TimeoutSec 5 | Out-Null; Ok "server is up" }
catch { Warn "server not reachable now (installing anyway). On halo-ubuntu: ~/llm.sh start cn lan" }
try {
  $m = Invoke-RestMethod "$Url/v1/models" -Headers @{ Authorization = "Bearer $key" } -TimeoutSec 10
  $modelId = $m.data[0].id; Ok "API key accepted, model = $modelId"
} catch {
  if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { Fail "API key rejected (401). Re-run and enter the correct key: setx LLM_KEY `"`" then run again." }
  $modelId = "cn"; Warn "could not query models; assuming model id 'cn'"
}

# ---------------------------------------------------------------- 3. download + verify
Step "3/5 Download opencode $Version"
$repo = "anomalyco/opencode"
$rel = Invoke-RestMethod "https://api.github.com/repos/$repo/releases/tags/$Version" -Headers @{ "User-Agent" = "opencode-setup" }
$tmp = Join-Path $env:TEMP "opencode-setup"; New-Item -ItemType Directory -Force $tmp | Out-Null
$dest = Join-Path $env:LOCALAPPDATA "Programs\opencode"

function Install-Variant($name) {
  $asset = $rel.assets | Where-Object { $_.name -eq $name } | Select-Object -First 1
  if (-not $asset) { Fail "asset $name not found in $Version" }
  $zip = Join-Path $tmp $name
  Write-Host "   downloading $name ($([math]::Round($asset.size/1MB)) MB) ..."
  Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
  if ($asset.digest -and $asset.digest -like "sha256:*") {
    $want = $asset.digest.Substring(7).ToLower()
    $got = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if ($got -ne $want) { Fail "sha256 mismatch for $name (got $got, want $want)" }
    Ok "sha256 verified"
  } else { Warn "release has no published digest; skipped hash check" }
  if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
  New-Item -ItemType Directory -Force $dest | Out-Null
  Expand-Archive $zip -DestinationPath $dest -Force
  $exe = Get-ChildItem $dest -Recurse -Filter "opencode.exe" | Select-Object -First 1
  if (-not $exe) { Fail "opencode.exe not found after extract" }
  return $exe.FullName
}

$exe = Install-Variant "opencode-windows-x64.zip"
$ver = & $exe --version 2>$null
if ($LASTEXITCODE -ne 0 -or -not $ver) {
  Warn "x64 build did not run (older CPU without AVX2?). Trying baseline build."
  $exe = Install-Variant "opencode-windows-x64-baseline.zip"
  $ver = & $exe --version 2>$null
  if (-not $ver) { Fail "opencode does not run on this PC" }
}
Ok "opencode $ver -> $exe"

# ---------------------------------------------------------------- 4. PATH
Step "4/5 PATH"
$bin = Split-Path $exe
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($userPath -split ";") -notcontains $bin) {
  [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $bin), "User")
  Ok "added $bin to user PATH (new terminals will see it)"
} else { Ok "already on PATH" }
$env:Path += ";$bin"

# ---------------------------------------------------------------- 5. config
Step "5/5 Config"
$cfgDir = Join-Path $env:USERPROFILE ".config\opencode"
$cfg = Join-Path $cfgDir "opencode.json"
New-Item -ItemType Directory -Force $cfgDir | Out-Null
if (Test-Path $cfg) {
  $bak = "$cfg.bak-" + (Get-Date -Format "yyyyMMdd-HHmmss")
  Copy-Item $cfg $bak; Warn "existing config backed up to $bak"
}
# permission: opencode allows every edit/command WITHOUT asking by default -> force "ask".
# share: disabled so work code is never uploaded to a share link.
$json = @"
{
  "`$schema": "https://opencode.ai/config.json",
  "provider": {
    "halo": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "halo-ubuntu llama-server",
      "options": {
        "baseURL": "$Url/v1",
        "apiKey": "{env:LLM_KEY}"
      },
      "models": {
        "$modelId": {
          "name": "Qwen3-Coder-Next (halo, local)",
          "limit": { "context": 65536, "output": 8192 }
        }
      }
    }
  },
  "model": "halo/$modelId",
  "small_model": "halo/$modelId",
  "share": "disabled",
  "permission": {
    "edit": "ask",
    "bash": "ask"
  }
}
"@
[IO.File]::WriteAllText($cfg, $json, (New-Object Text.UTF8Encoding($false)))
[Environment]::SetEnvironmentVariable("OPENCODE_CONFIG", $cfg, "User"); $env:OPENCODE_CONFIG = $cfg
Ok "wrote $cfg (OPENCODE_CONFIG set)"

Write-Host "`n================ DONE ================" -ForegroundColor Green
Write-Host " 1. Open a NEW terminal (Windows Terminal recommended)"
Write-Host " 2. cd into a project folder   e.g.  cd C:\work\my-app"
Write-Host " 3. run:  opencode"
Write-Host ""
Write-Host " File edits and shell commands will ask before running."
Write-Host " Try it first on a throwaway folder."
Write-Host "======================================"
