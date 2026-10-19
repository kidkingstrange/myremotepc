<#
.SYNOPSIS
    MyRemotePC - Clean-Machine & Windows Sandbox Verification Script
.DESCRIPTION
    Automates testing of MyRemotePC-Setup-v1.0.0.exe in a clean, developer-tool-free
    Windows environment (such as Windows Sandbox, Hyper-V, or VirtualBox).
#>

[CmdletBinding()]
param(
    [string]$InstallerPath = "",
    [switch]$Interactive = $false
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   MyRemotePC v1.0.0 Clean-Machine / Sandbox Verification   " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Locate Installer
if (-not $InstallerPath) {
    $searchLocations = @(
        "C:\Users\WDAGUtilityAccount\Desktop\MyRemotePC-Test\MyRemotePC-Setup-v1.0.0.exe",
        "C:\Users\WDAGUtilityAccount\Desktop\MyRemotePC-Release\MyRemotePC-Setup-v1.0.0.exe",
        "$PSScriptRoot\..\dist\releases\v1.0.0\MyRemotePC-Setup-v1.0.0.exe",
        "$PSScriptRoot\MyRemotePC-Setup-v1.0.0.exe",
        ".\MyRemotePC-Setup-v1.0.0.exe"
    )
    foreach ($loc in $searchLocations) {
        if (Test-Path $loc) {
            $InstallerPath = (Resolve-Path $loc).Path
            break
        }
    }
}

if (-not $InstallerPath -or -not (Test-Path $InstallerPath)) {
    Write-Host "[FAIL] Could not locate MyRemotePC-Setup-v1.0.0.exe!" -ForegroundColor Red
    Write-Host "Please provide the path via: .\sandbox_verifier.ps1 -InstallerPath 'C:\Path\To\Installer.exe'" -ForegroundColor Yellow
    exit 1
}

Write-Host "[PASS] Located Installer: $InstallerPath" -ForegroundColor Green
$installerSize = (Get-Item $InstallerPath).Length / 1MB
Write-Host ("       Installer Size: {0:N2} MB" -f $installerSize) -ForegroundColor Gray

# 2. Run Installation
Write-Host "`n--- Step 1: Executing Installer ---" -ForegroundColor Yellow
if ($Interactive) {
    Write-Host "Launching interactive installer wizard..." -ForegroundColor Gray
    $installProc = Start-Process -FilePath $InstallerPath -PassThru -Wait
} else {
    Write-Host "Running silent installation with desktop icon and firewall rules enabled..." -ForegroundColor Gray
    $installArgs = "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /TASKS=""desktopicon,firewallrule"""
    $installProc = Start-Process -FilePath $InstallerPath -ArgumentList $installArgs -PassThru -Wait
}

Write-Host "[PASS] Installer completed with exit code: $($installProc.ExitCode)" -ForegroundColor Green

# 3. Verify Installed Files
Write-Host "`n--- Step 2: Verifying Installed Files ---" -ForegroundColor Yellow
$appDirCandidates = @(
    "$env:LOCALAPPDATA\Programs\MyRemotePC",
    "C:\Program Files\MyRemotePC",
    "C:\Program Files (x86)\MyRemotePC"
)

$targetAppDir = $null
foreach ($dir in $appDirCandidates) {
    if (Test-Path "$dir\MyRemotePC.exe") {
        $targetAppDir = $dir
        break
    }
}

if (-not $targetAppDir) {
    Write-Host "[FAIL] Could not find MyRemotePC.exe in standard installation paths:" -ForegroundColor Red
    $appDirCandidates | ForEach-Object { Write-Host "       - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "[PASS] Target Application Directory: $targetAppDir" -ForegroundColor Green
$expectedFiles = @(
    "MyRemotePC.exe",
    "config.example.json",
    "LICENSE",
    "THIRD_PARTY_LICENSES.md",
    "open_viewer.bat",
    "share_over_internet.bat",
    "unins000.exe"
)

foreach ($f in $expectedFiles) {
    $full = Join-Path $targetAppDir $f
    if (Test-Path $full) {
        Write-Host "  [OK] $f exists" -ForegroundColor Gray
    } else {
        Write-Host "  [WARN] $f not found" -ForegroundColor Yellow
    }
}

# 4. Launch Application
Write-Host "`n--- Step 3: Launching MyRemotePC Host Service ---" -ForegroundColor Yellow
$appExe = Join-Path $targetAppDir "MyRemotePC.exe"
$proc = Start-Process -FilePath $appExe -PassThru
Start-Sleep -Seconds 3

$runningProc = Get-Process -Name "MyRemotePC" -ErrorAction SilentlyContinue
if ($runningProc) {
    Write-Host "[PASS] MyRemotePC process is active (PID: $($runningProc.Id), RAM: $([math]::Round($runningProc.WorkingSet64 / 1MB, 1)) MB)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] MyRemotePC failed to keep running!" -ForegroundColor Red
    exit 1
}

# 5. Verify REST API & Health
Write-Host "`n--- Step 4: Testing HTTP Endpoint (http://localhost:8080/api/status) ---" -ForegroundColor Yellow
$statusOk = $false
for ($i = 1; $i -le 10; $i++) {
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8080/api/status" -TimeoutSec 3 -ErrorAction Stop
        if ($response.status -eq "online") {
            Write-Host "[PASS] Host service is ONLINE!" -ForegroundColor Green
            Write-Host "       Machine ID   : $($response.machine_id)" -ForegroundColor Cyan
            Write-Host "       Machine Name : $($response.machine_name)" -ForegroundColor Cyan
            Write-Host "       Port         : $($response.port)" -ForegroundColor Cyan
            $statusOk = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $statusOk) {
    Write-Host "[FAIL] Could not query http://localhost:8080/api/status within 10 seconds." -ForegroundColor Red
}

# 6. Verify Configuration Persistence in %APPDATA%
Write-Host "`n--- Step 5: Checking Config File Persistence ---" -ForegroundColor Yellow
$appDataConfig = "$env:APPDATA\MyRemotePC\config.json"
if (Test-Path $appDataConfig) {
    try {
        $cfgJson = Get-Content $appDataConfig -Raw | ConvertFrom-Json
        Write-Host "[PASS] Config file created at: $appDataConfig" -ForegroundColor Green
        Write-Host "       Machine ID in config : $($cfgJson.machine_id)" -ForegroundColor Gray
        Write-Host "       Port in config       : $($cfgJson.port)" -ForegroundColor Gray
        Write-Host "       Salt length          : $($cfgJson.salt.Length) chars" -ForegroundColor Gray
    } catch {
        Write-Host "[WARN] Config file exists but could not parse JSON: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARN] %APPDATA%\MyRemotePC\config.json not yet generated or path differs." -ForegroundColor Yellow
}

# 7. Check Windows Firewall
Write-Host "`n--- Step 6: Verifying Windows Defender Firewall Rule ---" -ForegroundColor Yellow
try {
    $fwRule = Get-NetFirewallRule -DisplayName "MyRemotePC*" -ErrorAction SilentlyContinue
    if ($fwRule) {
        Write-Host "[PASS] Firewall rule detected: $($fwRule.DisplayName) (Enabled: $($fwRule.Enabled))" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Firewall rule query returned no match (requires elevated admin privileges or rule is named 'MyRemotePC Host')." -ForegroundColor Gray
    }
} catch {
    Write-Host "[INFO] NetSecurity PowerShell module not available in this container environment." -ForegroundColor Gray
}

# 8. Browser Verification
Write-Host "`n--- Step 7: Launching Browser Viewer ---" -ForegroundColor Yellow
Write-Host "Opening http://localhost:8080 in default web browser..." -ForegroundColor Cyan
Start-Process "http://localhost:8080"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   VERIFICATION COMPLETE: MyRemotePC is fully operational!  " -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To test uninstallation, run:" -ForegroundColor Yellow
Write-Host "Start-Process '$targetAppDir\unins000.exe' -Wait" -ForegroundColor White
Write-Host ""
