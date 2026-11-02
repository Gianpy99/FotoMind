<#
.SYNOPSIS
    Run the Docker checks in the Pi development space (~/apps/fotomind). No Docker on the PC.

.DESCRIPTION
    Copies the current working tree (tracked + untracked, not git-ignored) to
    ~/apps/fotomind/src on the Pi, then:
      default       docker build --target test  (same gate as Jenkins)
      -Integration  also runs the DB integration tests in that image against fotomind_test
      -Run          builds the runtime image and starts the dev container (fotomind-dev)
                    on the Pi at 127.0.0.1:18097 (open it with: ssh -L 18097:127.0.0.1:18097 ...)
      -Stop         stops and removes the dev container

    Secrets live only in ~/apps/fotomind/.env on the Pi (create it from
    deployment/raspberry-pi/dev.env.example); this script never reads or sends them.
    Never touches the production container (fotomind) or image (fotomind:latest).
#>
param(
    [switch]$Integration,
    [switch]$Run,
    [switch]$Stop,
    [string]$PiHost = "192.168.1.129",
    [string]$PiUser = "g99trading"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Target = "$PiUser@$PiHost"
$Remote = "apps/fotomind"   # relative to the Pi user's home

function Invoke-Pi([string]$Script) {
    # Windows PowerShell re-adds CRLF when piping to native commands, so ship the script as
    # base64 (LF-only) and decode it on the Pi.
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Script.Replace("`r`n", "`n"))
    $b64 = [Convert]::ToBase64String($bytes)
    # Remote tools write progress to stderr; only the exit code decides failure.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        ssh -o BatchMode=yes $Target "echo $b64 | base64 -d | bash" 2>&1 | ForEach-Object { "$_" }
    }
    finally {
        $ErrorActionPreference = $previous
    }
    if ($LASTEXITCODE -ne 0) { throw "Remote step failed (exit $LASTEXITCODE)" }
}

if ($Stop) {
    Invoke-Pi "set -e; cd ~/$Remote/src && docker-compose -p fotomind-dev down"
    return
}

Push-Location $Root
try {
    $list = New-TemporaryFile
    $archive = Join-Path ([System.IO.Path]::GetTempPath()) "fotomind-src.tar.gz"
    git ls-files --cached --others --exclude-standard |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Set-Content -Encoding ascii $list
    tar -czf $archive -T $list
    if ($LASTEXITCODE -ne 0) { throw "tar failed" }
    Write-Host "==> Uploading working tree to ${Target}:~/$Remote/src" -ForegroundColor Cyan
    ssh -o BatchMode=yes $Target "mkdir -p ~/$Remote"
    scp -q $archive "${Target}:$Remote/src.tar.gz"
    if ($LASTEXITCODE -ne 0) { throw "scp failed" }
}
finally {
    Remove-Item $list, $archive -ErrorAction SilentlyContinue
    Pop-Location
}

$prepare = @"
set -e
cd ~/$Remote
rm -rf src && mkdir src && tar -xzf src.tar.gz -C src && rm src.tar.gz
[ -f .env ] && ln -sf ../.env src/.env || true
cd src
"@

Write-Host "==> docker build --target test (on the Pi)" -ForegroundColor Cyan
Invoke-Pi "$prepare`ndocker build --target test -t fotomind:dev-test ."

if ($Integration) {
    Write-Host "==> Integration tests against fotomind_test (on the Pi)" -ForegroundColor Cyan
    Invoke-Pi @"
set -e
cd ~/$Remote
[ -f .env ] || { echo 'Missing ~/$Remote/.env (see deployment/raspberry-pi/dev.env.example)'; exit 1; }
docker run --rm --env-file .env fotomind:dev-test pytest -q -m integration -rs
"@
}

if ($Run) {
    Write-Host "==> Starting dev container fotomind-dev on the Pi (127.0.0.1:18097)" -ForegroundColor Cyan
    Invoke-Pi @"
set -e
cd ~/$Remote/src
[ -f .env ] || { echo 'Missing ~/$Remote/.env (see deployment/raspberry-pi/dev.env.example)'; exit 1; }
docker-compose -p fotomind-dev up -d --build
for i in `$(seq 1 20); do
  if curl -fsS http://127.0.0.1:18097/health; then echo; exit 0; fi
  sleep 3
done
docker-compose -p fotomind-dev logs --tail 50
exit 1
"@
    Write-Host "Open it from the PC:  ssh -L 18097:127.0.0.1:18097 $Target   then http://localhost:18097"
}
