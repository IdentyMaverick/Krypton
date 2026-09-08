# Krypton Windows 11 setup engine
# Reads bundle.json next to this script and installs every selected app.

[CmdletBinding()]
param(
    [string]$ProfilePath = "",
    [switch]$SkipTweaks
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

function Get-KryptonRoot {
    if ($PSScriptRoot) { return $PSScriptRoot }
    return Split-Path -Parent $MyInvocation.MyCommand.Path
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Step {
    param([string]$Message, [string]$Color = "Cyan")
    Write-Host "=> $Message" -ForegroundColor $Color
}

function Write-Ok {
    param([string]$Message)
    Write-Host "   OK  $Message" -ForegroundColor Green
}

function Write-WarnStep {
    param([string]$Message)
    Write-Host "   !!  $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "   XX  $Message" -ForegroundColor Red
}

function Get-WindowsBuild {
    try {
        return [int](Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuildNumber
    } catch {
        return 0
    }
}

function Test-WingetPresent {
    return [bool](Get-Command winget -ErrorAction SilentlyContinue)
}

function Install-WingetPackage {
    param([string]$PackageId, [string]$DisplayName)
    Write-Step "Installing $DisplayName ($PackageId)"
    $list = & winget list --id $PackageId -e --accept-source-agreements 2>$null
    if ($LASTEXITCODE -eq 0 -and $list -match [regex]::Escape($PackageId)) {
        Write-Ok "$DisplayName is already installed"
        return $true
    }
    & winget install --id $PackageId -e --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "$DisplayName installed"
        return $true
    }
    Write-Fail "winget could not install $DisplayName (exit $LASTEXITCODE)"
    return $false
}

function Get-PropertyValue {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-InstallerPathFromUrl {
    param([string]$Url, [string]$FileName)
    if ($FileName) { return $FileName }
    $uri = [Uri]$Url
    $leaf = [IO.Path]::GetFileName($uri.AbsolutePath)
    if (-not $leaf) { $leaf = "installer.exe" }
    return $leaf
}

function Install-UrlPackage {
    param(
        [string]$DisplayName,
        [string]$Url,
        [string]$SilentArgs,
        [string]$FileName
    )
    if ($Url -notmatch '^https://') {
        Write-Fail "Refusing non-https installer for $DisplayName"
        return $false
    }
    $work = Join-Path $env:TEMP ("krypton-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Path $work | Out-Null
    try {
        $leaf = Get-InstallerPathFromUrl -Url $Url -FileName $FileName
        $outFile = Join-Path $work $leaf
        Write-Step "Downloading $DisplayName"
        Invoke-WebRequest -Uri $Url -OutFile $outFile -UseBasicParsing
        return Install-LocalPackage -DisplayName $DisplayName -Path $outFile -SilentArgs $SilentArgs
    } catch {
        Write-Fail "Download failed for $DisplayName : $($_.Exception.Message)"
        return $false
    } finally {
        Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
    }
}

function Install-LocalPackage {
    param(
        [string]$DisplayName,
        [string]$Path,
        [string]$SilentArgs
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        Write-Fail "Installer not found for $DisplayName : $Path"
        return $false
    }
    Write-Step "Running installer for $DisplayName"
    $extension = [IO.Path]::GetExtension($Path).ToLowerInvariant()
    try {
        if ($extension -eq ".msi") {
            $msiArgs = @("/i", $Path, "/qn", "/norestart")
            if ($SilentArgs) { $msiArgs = @("/i", $Path) + ($SilentArgs -split " ") }
            $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $msiArgs -Wait -PassThru
        } else {
            $argList = @()
            if ($SilentArgs) { $argList = $SilentArgs -split " " }
            $process = Start-Process -FilePath $Path -ArgumentList $argList -Wait -PassThru
        }
        if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010) {
            Write-Ok "$DisplayName installed"
            return $true
        }
        Write-Fail "$DisplayName installer exited $($process.ExitCode)"
        return $false
    } catch {
        Write-Fail "Installer failed for $DisplayName : $($_.Exception.Message)"
        return $false
    }
}

function Set-RegistryDword {
    param([string]$Path, [string]$Name, [int]$Value)
    if (-not (Test-Path $Path)) {
        New-Item -Path $Path -Force | Out-Null
    }
    New-ItemProperty -Path $Path -Name $Name -Value $Value -PropertyType DWord -Force | Out-Null
}

function Apply-Tweak {
    param([string]$TweakId)
    switch ($TweakId) {
        "show-file-extensions" {
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" "HideFileExt" 0
        }
        "show-hidden-files" {
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" "Hidden" 1
        }
        "dark-mode" {
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "AppsUseLightTheme" 0
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "SystemUsesLightTheme" 0
        }
        "explorer-this-pc" {
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" "LaunchTo" 1
        }
        "taskbar-left" {
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" "TaskbarAl" 0
        }
        "disable-widgets" {
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" "TaskbarDa" 0
        }
        "end-task-in-taskbar" {
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" "TaskbarDeveloperSettings" 1
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" "TaskbarEndTask" 1
        }
        "classic-context-menu" {
            $key = "HKCU:\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}\InprocServer32"
            New-Item -Path $key -Force | Out-Null
            Set-ItemProperty -Path $key -Name "(default)" -Value ""
        }
        "disable-bing-search" {
            Set-RegistryDword "HKCU:\Software\Policies\Microsoft\Windows\Explorer" "DisableSearchBoxSuggestions" 1
            Set-RegistryDword "HKCU:\Software\Microsoft\Windows\CurrentVersion\Search" "BingSearchEnabled" 0
        }
        "enable-long-paths" {
            Set-RegistryDword "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" "LongPathsEnabled" 1
        }
        "high-performance-power" {
            $scheme = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
            $output = & powercfg /setactive $scheme 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "High performance plan is not available on this PC. $output"
            }
        }
        default {
            throw "Unknown tweak $TweakId"
        }
    }
}

$root = Get-KryptonRoot
if (-not $ProfilePath) {
    $ProfilePath = Join-Path $root "bundle.json"
}

$logDir = Join-Path $env:LOCALAPPDATA "Krypton\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir ("setup-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")
Start-Transcript -Path $logFile -Append | Out-Null

$failed = 0
$succeeded = 0

try {
    Write-Host ""
    Write-Host "  Krypton  Windows 11 setup" -ForegroundColor Green
    Write-Host "  $ProfilePath" -ForegroundColor DarkGray
    Write-Host ""

    if (-not (Test-IsAdministrator)) {
        Write-Fail "Please run Install.cmd as administrator."
        exit 1
    }

    $build = Get-WindowsBuild
    if ($build -gt 0 -and $build -lt 22000) {
        Write-WarnStep "This bundle targets Windows 11 (build 22000+). Current build is $build."
    } else {
        Write-Ok "Windows build $build"
    }

    if (-not (Test-Path -LiteralPath $ProfilePath)) {
        Write-Fail "bundle.json was not found."
        exit 1
    }

    $bundle = Get-Content -LiteralPath $ProfilePath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Ok "Loaded bundle '$($bundle.name)'"

    if (-not (Test-WingetPresent)) {
        Write-Fail "winget is not available. Install App Installer from the Microsoft Store, then re-run."
        $failed += 1
    }

    foreach ($app in @($bundle.apps)) {
        $name = $app.name
        $ok = $false
        switch ($app.source) {
            "winget" {
                if (Test-WingetPresent) {
                    $ok = Install-WingetPackage -PackageId $app.package -DisplayName $name
                }
            }
            "url" {
                $ok = Install-UrlPackage -DisplayName $name -Url $app.url -SilentArgs (Get-PropertyValue $app "silentArgs") -FileName (Get-PropertyValue $app "fileName")
            }
            "local" {
                $localPath = Get-PropertyValue $app "path"
                if (-not $localPath) {
                    Write-Fail "Local path missing for $name"
                    $ok = $false
                    break
                }
                if (-not [IO.Path]::IsPathRooted($localPath)) {
                    $localPath = Join-Path $root $localPath
                }
                $ok = Install-LocalPackage -DisplayName $name -Path $localPath -SilentArgs (Get-PropertyValue $app "silentArgs")
            }
            default {
                Write-Fail "Unknown source for $name"
            }
        }
        if ($ok) { $succeeded += 1 } else { $failed += 1 }
    }

    if (-not $SkipTweaks) {
        foreach ($tweakId in @($bundle.tweaks)) {
            try {
                Write-Step "Applying $tweakId"
                Apply-Tweak -TweakId $tweakId
                Write-Ok $tweakId
                $succeeded += 1
            } catch {
                Write-Fail "Tweak $tweakId failed: $($_.Exception.Message)"
                $failed += 1
            }
        }
    }

    Write-Host ""
    Write-Host "  Done. Installed/applied: $succeeded   Failed: $failed" -ForegroundColor $(if ($failed -gt 0) { "Yellow" } else { "Green" })
    Write-Host "  Log: $logFile" -ForegroundColor DarkGray
    Write-Host "  Sign out or restart if Explorer or the taskbar look unchanged." -ForegroundColor DarkGray
    Write-Host ""
    if ($failed -gt 0) { exit 1 }
    exit 0
} finally {
    Stop-Transcript | Out-Null
}
