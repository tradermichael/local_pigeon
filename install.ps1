# Local Pigeon Installer for Windows
# Usage: irm https://raw.githubusercontent.com/tradermichael/local_pigeon/main/install.ps1 | iex
# Or: .\install.ps1

$ErrorActionPreference = "Stop"

# Configuration
$InstallDir = "$env:USERPROFILE\.local_pigeon"
$VenvDir = "$InstallDir\venv"
$RepoUrl = "https://github.com/tradermichael/local_pigeon.git"
$MinPythonVersion = [Version]"3.10"

# Colors
function Write-Color {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

# Banner
Write-Host ""
Write-Color "  _                     _   ____  _                       " "Cyan"
Write-Color " | |    ___   ___ __ _| | |  _ \(_) __ _  ___  ___  _ __  " "Cyan"
Write-Color " | |   / _ \ / __/ _`  | | | |_) | |/ _`  |/ _ \/ _ \| '_ \ " "Cyan"
Write-Color " | |__| (_) | (_| (_| | | |  __/| | (_| |  __/ (_) | | | |" "Cyan"
Write-Color " |_____\___/ \___\__,_|_| |_|   |_|\__, |\___|\___/|_| |_|" "Cyan"
Write-Color "                                   |___/                  " "Cyan"
Write-Host ""
Write-Color "Local AI Agent with Discord/Telegram, Google Workspace & Payments" "White"
Write-Host "=================================================================="
Write-Host ""

# Check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Check if command exists
function Test-Command {
    param([string]$Command)
    return [bool](Get-Command $Command -ErrorAction SilentlyContinue)
}

# Get Python version
function Get-PythonVersion {
    try {
        $version = & python --version 2>&1
        if ($version -match "Python (\d+\.\d+)") {
            return [Version]$Matches[1]
        }
    } catch {}
    
    try {
        $version = & python3 --version 2>&1
        if ($version -match "Python (\d+\.\d+)") {
            return [Version]$Matches[1]
        }
    } catch {}
    
    return $null
}

# Check Python
function Test-Python {
    $version = Get-PythonVersion
    if ($version -and $version -ge $MinPythonVersion) {
        Write-Color "✓ Python $version found" "Green"
        return $true
    }
    return $false
}

# Install Python
function Install-Python {
    Write-Color "Installing Python..." "Yellow"
    
    # Try winget first
    if (Test-Command "winget") {
        Write-Host "Using winget to install Python..."
        winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        if (Test-Python) {
            return $true
        }
    }
    
    # Try scoop
    if (Test-Command "scoop") {
        Write-Host "Using scoop to install Python..."
        scoop install python
        if (Test-Python) {
            return $true
        }
    }
    
    # Manual download
    Write-Color "Downloading Python installer..." "Yellow"
    $installerUrl = "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe"
    $installerPath = "$env:TEMP\python-installer.exe"
    
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
    
    Write-Host "Running Python installer..."
    Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1" -Wait
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    Remove-Item $installerPath -ErrorAction SilentlyContinue
    
    return Test-Python
}

# Check Ollama
function Test-Ollama {
    if (Test-Command "ollama") {
        try {
            $version = & ollama --version 2>&1 | Select-Object -First 1
            Write-Color "✓ Ollama found: $version" "Green"
            return $true
        } catch {}
    }
    return $false
}

# Install Ollama
function Install-Ollama {
    Write-Color "Installing Ollama..." "Yellow"
    
    $installerUrl = "https://ollama.ai/download/OllamaSetup.exe"
    $installerPath = "$env:TEMP\OllamaSetup.exe"
    
    Write-Host "Downloading Ollama..."
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
    
    Write-Host "Running Ollama installer..."
    Start-Process -FilePath $installerPath -Wait
    
    Remove-Item $installerPath -ErrorAction SilentlyContinue
    
    # Refresh PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    Write-Color "✓ Ollama installed" "Green"
}

# Pull model
function Pull-Model {
    param([string]$Model = "llama3.2")
    
    Write-Color "Pulling model: $Model" "Cyan"
    Write-Host "This may take a while depending on your internet connection..."
    
    # Start Ollama if not running
    $ollamaProcess = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
    if (-not $ollamaProcess) {
        Write-Host "Starting Ollama service..."
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
    }
    
    & ollama pull $Model
    Write-Color "✓ Model $Model ready" "Green"
}

# Main installation
function Install-LocalPigeon {
    Write-Color "Step 1: Checking Python..." "Cyan"
    if (-not (Test-Python)) {
        $response = Read-Host "Python not found. Install it now? [Y/n]"
        if ($response -eq "" -or $response -match "^[Yy]") {
            if (-not (Install-Python)) {
                Write-Color "Failed to install Python. Please install Python $MinPythonVersion+ manually." "Red"
                exit 1
            }
        } else {
            Write-Color "Python is required. Please install Python $MinPythonVersion+ and try again." "Red"
            exit 1
        }
    }
    
    Write-Host ""
    Write-Color "Step 2: Checking Ollama..." "Cyan"
    if (-not (Test-Ollama)) {
        $response = Read-Host "Ollama not found. Install it now? [Y/n]"
        if ($response -eq "" -or $response -match "^[Yy]") {
            Install-Ollama
        } else {
            Write-Color "! Skipping Ollama installation. You'll need to install it manually." "Yellow"
        }
    }
    
    Write-Host ""
    Write-Color "Step 3: Creating installation directory..." "Cyan"
    if (-not (Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    }
    Write-Color "✓ Directory: $InstallDir" "Green"
    
    Write-Host ""
    Write-Color "Step 4: Cloning repository..." "Cyan"
    $repoDir = "$InstallDir\repo"
    if (Test-Path $repoDir) {
        Write-Host "Updating existing installation..."
        Push-Location $repoDir
        & git pull
        Pop-Location
    } else {
        & git clone $RepoUrl $repoDir
    }
    Write-Color "✓ Repository cloned" "Green"
    
    Write-Host ""
    Write-Color "Step 5: Creating virtual environment..." "Cyan"
    & python -m venv $VenvDir
    Write-Color "✓ Virtual environment created" "Green"
    
    Write-Host ""
    Write-Color "Step 6: Installing dependencies..." "Cyan"
    & "$VenvDir\Scripts\pip.exe" install --upgrade pip
    & "$VenvDir\Scripts\pip.exe" install -e $repoDir
    Write-Color "✓ Dependencies installed" "Green"
    
    Write-Host ""
    Write-Color "Step 6b: Installing Playwright browser..." "Cyan"
    & "$VenvDir\Scripts\playwright.exe" install chromium
    Write-Color "✓ Playwright Chromium installed" "Green"
    
    Write-Host ""
    Write-Color "Step 7: Setting up configuration..." "Cyan"
    $envFile = "$InstallDir\.env"
    if (-not (Test-Path $envFile)) {
        Copy-Item "$repoDir\.env.example" $envFile
        Write-Color "✓ Created .env file at $envFile" "Green"
    } else {
        Write-Color "! .env file already exists, keeping existing configuration" "Yellow"
    }
    
    $configFile = "$InstallDir\config.yaml"
    if (-not (Test-Path $configFile)) {
        Copy-Item "$repoDir\config.yaml" $configFile
        Write-Color "✓ Created config.yaml at $configFile" "Green"
    }
    
    Write-Host ""
    Write-Color "Step 8: Creating command wrapper..." "Cyan"
    
    # Create batch wrapper
    $wrapperPath = "$InstallDir\local-pigeon.cmd"
    @"
@echo off
call "$VenvDir\Scripts\activate.bat"
cd /d "$InstallDir"
local-pigeon %*
"@ | Set-Content $wrapperPath
    
    # Add to PATH
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*$InstallDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallDir", "User")
        $env:Path = "$env:Path;$InstallDir"
        Write-Color "✓ Added to PATH" "Green"
    }
    
    Write-Color "✓ Created command: local-pigeon" "Green"
    
    # Pull model if Ollama is installed
    Write-Host ""
    if (Test-Ollama) {
        $response = Read-Host "Pull default model (llama3.2)? [Y/n]"
        if ($response -eq "" -or $response -match "^[Yy]") {
            Pull-Model "llama3.2"
        }
    }
    
    Write-Host ""
    Write-Color "========================================" "Green"
    Write-Color "   Installation Complete!" "Green"
    Write-Color "========================================" "Green"
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host ""
    Write-Host "1. Open a NEW terminal (to refresh PATH)"
    Write-Host ""
    Write-Host "2. Configure your settings:"
    Write-Host "   notepad $InstallDir\.env"
    Write-Host ""
    Write-Host "3. Run the setup wizard:"
    Write-Host "   local-pigeon setup"
    Write-Host ""
    Write-Host "4. Start Local Pigeon:"
    Write-Host "   local-pigeon run"
    Write-Host ""
    Write-Host "For help: local-pigeon --help"
    Write-Host ""
}

# Check for git
if (-not (Test-Command "git")) {
    Write-Color "Git is required but not installed." "Red"
    Write-Host ""
    
    $response = Read-Host "Install Git using winget? [Y/n]"
    if ($response -eq "" -or $response -match "^[Yy]") {
        if (Test-Command "winget") {
            winget install Git.Git --accept-source-agreements --accept-package-agreements
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        } else {
            Write-Color "Please install Git manually from https://git-scm.com/download/win" "Yellow"
            exit 1
        }
    } else {
        Write-Color "Git is required. Please install it and try again." "Red"
        exit 1
    }
}

# Run installation
Install-LocalPigeon
