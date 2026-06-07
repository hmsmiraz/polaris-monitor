#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Polaris Monitor — Windows Worker Agent Installer

.DESCRIPTION
    Installs the Polaris Worker Agent on Windows 10/11 or Windows Server 2019/2022.
    Also installs Python (if needed), Windows Exporter, and NSSM for service management.

.PARAMETER MasterIP
    IP address of the Polaris Master server.

.PARAMETER Token
    Join token displayed by 'polaris-master token' on the master.

.PARAMETER MasterPort
    Master API port (default: 8000).

.PARAMETER ExporterPort
    Metrics exporter port (default: 9100).

.PARAMETER SkipExporter
    Skip Windows Exporter installation.

.PARAMETER SkipJoin
    Install files only — do not join master automatically.

.EXAMPLE
    .\install.ps1 -MasterIP 10.0.0.10 -Token abc123

.EXAMPLE
    .\install.ps1   # Interactive — prompts for master IP and token
#>

param(
    [string]$MasterIP     = "",
    [string]$Token        = "",
    [int]   $MasterPort   = 8000,
    [int]   $ExporterPort = 9100,
    [switch]$SkipExporter,
    [switch]$SkipJoin
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Constants ──────────────────────────────────────────────────────────────────
$PolarisHome   = "C:\Program Files\Polaris"
$AgentDir      = "$PolarisHome\worker-agent"
$ConfigDir     = "$env:ProgramData\Polaris"
$NssmUrl       = "https://nssm.cc/release/nssm-2.24.zip"
$NssmExe       = "$PolarisHome\nssm.exe"
$WinExporterVer = "0.25.1"
$WinExporterUrl = "https://github.com/prometheus-community/windows_exporter/releases/download/v$WinExporterVer/windows_exporter-$WinExporterVer-amd64.exe"
$WinExporterExe = "$PolarisHome\windows_exporter.exe"
$ScriptDir      = $PSScriptRoot

# ── Colour helpers ─────────────────────────────────────────────────────────────
function Write-Ok($msg)   { Write-Host "  [OK]  $msg" -ForegroundColor Green  }
function Write-Info($msg) { Write-Host "  [->]  $msg" -ForegroundColor Cyan   }
function Write-Warn($msg) { Write-Host "  [!]   $msg" -ForegroundColor Yellow }
function Write-Step($msg) { Write-Host "`n  >> $msg" -ForegroundColor Cyan -NoNewline; Write-Host "" }
function Write-Err($msg)  { Write-Host "  [X]  $msg" -ForegroundColor Red; exit 1 }

function Write-Banner {
    Write-Host ""
    Write-Host "  +----------------------------------------------+" -ForegroundColor Cyan
    Write-Host "  |  Polaris Monitor - Windows Agent Installer   |" -ForegroundColor Cyan
    Write-Host "  |  Windows 10/11 / Server 2019/2022            |" -ForegroundColor Cyan
    Write-Host "  +----------------------------------------------+" -ForegroundColor Cyan
    Write-Host ""
}

# ── Python Detection / Installation ───────────────────────────────────────────
function Get-PythonExe {
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $v = & $cmd --version 2>&1
            if ($v -match "Python 3\.(\d+)") {
                $minor = [int]$Matches[1]
                if ($minor -ge 9) {
                    Write-Ok "Found: $v ($cmd)"
                    return $cmd
                }
            }
        } catch { }
    }
    return $null
}

function Install-Python {
    Write-Info "Installing Python 3.11 via winget..."
    try {
        winget install --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements -h
        # Refresh PATH
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH", "User")
        Write-Ok "Python installed"
        return "python"
    } catch {
        Write-Warn "winget failed. Downloading Python installer directly..."
        $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
        $pyInstaller = "$env:TEMP\python-installer.exe"
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
        Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
        $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("PATH", "User")
        Write-Ok "Python installed"
        return "python"
    }
}

# ── NSSM (Service Manager) ─────────────────────────────────────────────────────
function Install-Nssm {
    if (Test-Path $NssmExe) { Write-Ok "NSSM already present"; return }
    Write-Info "Downloading NSSM (service manager)..."
    $zip = "$env:TEMP\nssm.zip"
    Invoke-WebRequest -Uri $NssmUrl -OutFile $zip -UseBasicParsing
    $extracted = "$env:TEMP\nssm-extracted"
    Expand-Archive -Path $zip -DestinationPath $extracted -Force
    $nssmBin = Get-ChildItem -Path $extracted -Filter "nssm.exe" -Recurse |
               Where-Object { $_.DirectoryName -like "*win64*" -or $_.DirectoryName -like "*64*" } |
               Select-Object -First 1
    if (-not $nssmBin) {
        $nssmBin = Get-ChildItem -Path $extracted -Filter "nssm.exe" -Recurse | Select-Object -First 1
    }
    Copy-Item $nssmBin.FullName -Destination $NssmExe -Force
    Write-Ok "NSSM installed: $NssmExe"
}

# ── Windows Exporter ───────────────────────────────────────────────────────────
function Install-WindowsExporter {
    if ($SkipExporter) { Write-Warn "Skipping Windows Exporter (--SkipExporter)"; return }

    Write-Info "Downloading Windows Exporter $WinExporterVer..."
    Invoke-WebRequest -Uri $WinExporterUrl -OutFile $WinExporterExe -UseBasicParsing
    Write-Ok "Windows Exporter downloaded"

    # Remove existing service if present
    $svc = Get-Service -Name "polaris-node-exporter" -ErrorAction SilentlyContinue
    if ($svc) { & $NssmExe stop  polaris-node-exporter 2>$null; & $NssmExe remove polaris-node-exporter confirm 2>$null }

    # Install as service via NSSM
    & $NssmExe install polaris-node-exporter $WinExporterExe
    & $NssmExe set polaris-node-exporter AppParameters "--web.listen-address=0.0.0.0:$ExporterPort --collectors.enabled=cpu,cs,logical_disk,net,os,system,time"
    & $NssmExe set polaris-node-exporter DisplayName "Polaris Node Exporter"
    & $NssmExe set polaris-node-exporter Start SERVICE_AUTO_START
    & $NssmExe start polaris-node-exporter

    Write-Ok "Windows Exporter service installed (port $ExporterPort)"
}

# ── Agent Service ──────────────────────────────────────────────────────────────
function Install-AgentService($pythonExe, $venvPython) {
    $svc = Get-Service -Name "polaris-agent" -ErrorAction SilentlyContinue
    if ($svc) { & $NssmExe stop polaris-agent 2>$null; & $NssmExe remove polaris-agent confirm 2>$null }

    & $NssmExe install polaris-agent $venvPython "$AgentDir\main.py"
    & $NssmExe set polaris-agent AppDirectory $AgentDir
    & $NssmExe set polaris-agent DisplayName  "Polaris Worker Agent"
    & $NssmExe set polaris-agent Description  "Polaris Monitor — Worker Node Agent"
    & $NssmExe set polaris-agent Start        SERVICE_AUTO_START
    & $NssmExe set polaris-agent AppStdout    "$env:ProgramData\Polaris\logs\agent.log"
    & $NssmExe set polaris-agent AppStderr    "$env:ProgramData\Polaris\logs\agent-error.log"
    Write-Ok "polaris-agent service installed"
}

# ── polaris.bat CLI Wrapper ────────────────────────────────────────────────────
function Write-CliWrapper($venvPython) {
    $cliWrapper = @"
@echo off
cd /d "$AgentDir"
"$venvPython" "$AgentDir\cli.py" %*
"@
    Set-Content -Path "$PolarisHome\polaris.bat" -Value $cliWrapper
    # Add to system PATH if not already there
    $syspath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    if ($syspath -notlike "*$PolarisHome*") {
        [System.Environment]::SetEnvironmentVariable("PATH", "$syspath;$PolarisHome", "Machine")
        $env:PATH = "$env:PATH;$PolarisHome"
        Write-Ok "Added $PolarisHome to system PATH"
    }
    Write-Ok "CLI wrapper installed: polaris"
}

# ── Virtual Environment ────────────────────────────────────────────────────────
function Setup-Venv($pythonExe) {
    Write-Info "Creating Python virtual environment..."
    & $pythonExe -m venv "$AgentDir\venv"
    $pip = "$AgentDir\venv\Scripts\pip.exe"
    & $pip install --quiet --upgrade pip
    & $pip install --quiet -r "$AgentDir\requirements.txt"
    Write-Ok "Python dependencies installed"
    return "$AgentDir\venv\Scripts\python.exe"
}

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
Write-Banner

# Validate source files
if (-not (Test-Path "$ScriptDir\worker-agent")) {
    Write-Err "worker-agent/ not found. Run install.ps1 from the repository root."
}

# ── Step 1: Python ─────────────────────────────────────────────────────────────
Write-Step "Step 1/5  Python"
$pythonExe = Get-PythonExe
if (-not $pythonExe) { $pythonExe = Install-Python }

# ── Step 2: Copy Files ─────────────────────────────────────────────────────────
Write-Step "Step 2/5  Installing Polaris Worker Agent"
New-Item -ItemType Directory -Path $PolarisHome, $AgentDir, "$ConfigDir\logs" -Force | Out-Null
Copy-Item "$ScriptDir\worker-agent\*" -Destination $AgentDir -Recurse -Force
Write-Ok "Files installed: $AgentDir"

$venvPython = Setup-Venv $pythonExe

# ── Step 3: NSSM ──────────────────────────────────────────────────────────────
Write-Step "Step 3/5  Service Manager (NSSM)"
Install-Nssm

# ── Step 4: Windows Exporter ──────────────────────────────────────────────────
Write-Step "Step 4/5  Windows Exporter"
Install-WindowsExporter

# ── Step 5: Agent Service + CLI ───────────────────────────────────────────────
Write-Step "Step 5/5  Agent Service & CLI"
Install-AgentService $pythonExe $venvPython
Write-CliWrapper $venvPython

# ── Interactive prompt if no args given ───────────────────────────────────────
if (-not $SkipJoin) {
    if ([string]::IsNullOrEmpty($MasterIP)) {
        Write-Host ""
        $MasterIP = Read-Host "  Enter Master IP address"
    }
    if ([string]::IsNullOrEmpty($Token)) {
        $Token = Read-Host "  Enter Join Token"
    }
}

# ── Join Master ────────────────────────────────────────────────────────────────
if (-not $SkipJoin -and -not [string]::IsNullOrEmpty($MasterIP) -and -not [string]::IsNullOrEmpty($Token)) {
    Write-Host ""
    Write-Info "Joining master $MasterIP:$MasterPort ..."
    & $venvPython "$AgentDir\cli.py" join `
        --master-ip   $MasterIP `
        --master-port $MasterPort `
        --token       $Token `
        --node-exporter-port $ExporterPort `
        --skip-install

    # Start the agent service
    & $NssmExe start polaris-agent 2>$null
} else {
    Write-Host ""
    Write-Warn "Installation complete. Join manually:"
    Write-Host ""
    Write-Host "    polaris join --master-ip <IP> --token <TOKEN>" -ForegroundColor White
    Write-Host ""
}

Write-Host ""
Write-Host "  +----------------------------------------------+" -ForegroundColor Green
Write-Host "  |  Polaris Agent installed successfully!       |" -ForegroundColor Green
Write-Host "  |                                              |" -ForegroundColor Green
Write-Host "  |  CLI command:  polaris                       |" -ForegroundColor Green
Write-Host "  |  Check status: polaris status                |" -ForegroundColor Green
Write-Host "  +----------------------------------------------+" -ForegroundColor Green
Write-Host ""
