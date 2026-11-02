<#
.SYNOPSIS
    Regenerate packages/api-client (openapi.json + schema.d.ts) from the FastAPI app.
#>
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& .\.venv\Scripts\fotomind-openapi.exe packages\api-client\openapi.json
if ($LASTEXITCODE -ne 0) { throw "OpenAPI export failed" }
npm run generate:api
if ($LASTEXITCODE -ne 0) { throw "Client generation failed" }
