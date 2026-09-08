# Krypton designer host for Windows 11 (no Python required).
# Serves the designer UI and can export a setup zip.

[CmdletBinding()]
param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8787
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$designer = Join-Path $root "designer"
$catalog = Join-Path $root "catalog"
$engine = Join-Path $root "engine"

Add-Type -AssemblyName System.Net.HttpListener
Add-Type -AssemblyName System.Web

function Get-MimeType([string]$Path) {
    switch ([IO.Path]::GetExtension($Path).ToLowerInvariant()) {
        ".html" { "text/html; charset=utf-8" }
        ".css"  { "text/css; charset=utf-8" }
        ".js"   { "text/javascript; charset=utf-8" }
        ".json" { "application/json; charset=utf-8" }
        ".svg"  { "image/svg+xml" }
        ".png"  { "image/png" }
        default { "application/octet-stream" }
    }
}

function Read-JsonFile([string]$Path) {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

$appsDoc = Read-JsonFile (Join-Path $catalog "apps.json")
$tweaksDoc = Read-JsonFile (Join-Path $catalog "tweaks.json")
$presetsDoc = Read-JsonFile (Join-Path $catalog "presets.json")
$combinedCatalog = @{
    version    = $appsDoc.version
    categories = $appsDoc.categories
    apps       = $appsDoc.apps
    tweaks     = $tweaksDoc.tweaks
    presets    = $presetsDoc.presets
}

$prefix = "http://$HostAddress`:$Port/"
$listener = [System.Net.HttpListener]::new()
$listener.Prefixes.Add($prefix)
try {
    $listener.Start()
} catch {
    Write-Host "Could not bind $prefix. Is another Krypton window open?" -ForegroundColor Red
    throw
}

$url = $prefix
Write-Host "Krypton designer is running at $url" -ForegroundColor Green
Start-Process $url

function Send-Bytes($Response, [byte[]]$Bytes, [string]$ContentType, [int]$Status = 200, [string]$Disposition = $null) {
    $Response.StatusCode = $Status
    $Response.ContentType = $ContentType
    $Response.Headers["Cache-Control"] = "no-store"
    if ($Disposition) {
        $Response.Headers["Content-Disposition"] = $Disposition
    }
    $Response.ContentLength64 = $Bytes.Length
    $Response.OutputStream.Write($Bytes, 0, $Bytes.Length)
    $Response.OutputStream.Close()
}

function Send-Json($Response, $Object, [int]$Status = 200) {
    $json = $Object | ConvertTo-Json -Depth 12 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    Send-Bytes $Response $bytes "application/json; charset=utf-8" $Status
}

function Get-SafePath([string]$Root, [string]$Relative) {
    $combined = [IO.Path]::GetFullPath((Join-Path $Root $Relative))
    $rootFull = [IO.Path]::GetFullPath($Root)
    if (-not $combined.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
        return $null
    }
    return $combined
}

Write-Host "Press Ctrl+C to stop."
try {
    while ($listener.IsListening) {
        $context = $listener.GetContext()
        $request = $context.Request
        $response = $context.Response
        try {
            $path = [Uri]::UnescapeDataString($request.Url.AbsolutePath)
            if ($request.HttpMethod -eq "GET" -and $path -eq "/api/status") {
                Send-Json $response @{
                    ok         = $true
                    app        = "Krypton"
                    platform   = "win32"
                    windows    = $true
                    winget     = [bool](Get-Command winget -ErrorAction SilentlyContinue)
                    canInstall = $false
                    canExport  = $true
                    host       = "powershell"
                }
                continue
            }
            if ($request.HttpMethod -eq "GET" -and $path -eq "/api/catalog") {
                Send-Json $response $combinedCatalog
                continue
            }
            if ($request.HttpMethod -eq "GET") {
                if ($path -eq "/") { $path = "/index.html" }
                $relative = $path.TrimStart("/")
                if ($relative.StartsWith("catalog/")) {
                    $file = Get-SafePath $catalog $relative.Substring("catalog/".Length)
                } elseif ($relative.StartsWith("engine/")) {
                    $file = Get-SafePath $engine $relative.Substring("engine/".Length)
                } else {
                    $file = Get-SafePath $designer $relative
                }
                if (-not $file -or -not (Test-Path -LiteralPath $file)) {
                    Send-Bytes $response ([Text.Encoding]::UTF8.GetBytes("Not found")) "text/plain" 404
                    continue
                }
                $bytes = [IO.File]::ReadAllBytes($file)
                Send-Bytes $response $bytes (Get-MimeType $file)
                continue
            }
            Send-Json $response @{ ok = $false; error = "Use the Export button. Python is not required for browsing; run python -m krypton serve for zip export, or use the designer Export which downloads files in the browser." } 501
        } catch {
            try { Send-Json $response @{ ok = $false; error = $_.Exception.Message } 500 } catch { }
        }
    }
} finally {
    $listener.Stop()
    $listener.Close()
}
