# vdl — Windows installer
# Usage: powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/PhilV1tt/vdl/main/install-windows.ps1 | iex"

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗"
Write-Host "║   Installing vdl                         ║"
Write-Host "╚══════════════════════════════════════════╝"
Write-Host ""

# ── Helper functions ──────────────────────────────────────────────────

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Install-Winget-Package($id, $label) {
    Write-Host "→ Installing $label..."
    winget install --id $id --silent --accept-package-agreements --accept-source-agreements
}

# ── 1. winget ─────────────────────────────────────────────────────────────

if (-not (Test-Command "winget")) {
    Write-Host "❌ winget is not available." -ForegroundColor Red
    Write-Host "   Install 'App Installer' from the Microsoft Store and run this script again."
    exit 1
}
Write-Host "✓ winget available"

# ── 2. Python ─────────────────────────────────────────────────────────────

if (-not (Test-Command "python")) {
    Install-Winget-Package "Python.Python.3.12" "Python 3.12"
    # Reload PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Host "✓ Python already installed"
}

# ── 3. ffmpeg ─────────────────────────────────────────────────────────────

if (-not (Test-Command "ffmpeg")) {
    Install-Winget-Package "Gyan.FFmpeg" "ffmpeg"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Host "✓ ffmpeg already installed"
}

# ── 4. pipx ───────────────────────────────────────────────────────────────

if (-not (Test-Command "pipx")) {
    Write-Host "→ Installing pipx..."
    python -m pip install --user pipx
    python -m pipx ensurepath
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
} else {
    Write-Host "✓ pipx already installed"
}

# ── 5. vdl ────────────────────────────────────────────────────────────────

Write-Host "→ Installing vdl..."
pipx install "git+https://github.com/PhilV1tt/vdl.git"

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗"
Write-Host "║   ✅  vdl is installed!                  ║"
Write-Host "╚══════════════════════════════════════════╝"
Write-Host ""
Write-Host "  Usage:"
Write-Host "    vdl                        → interactive mode (arrow-key navigation)"
Write-Host "    vdl https://youtu.be/xxx   → download a video"
Write-Host "    vdl https://... --audio    → extract the audio as MP3"
Write-Host "    vdl search ""lofi hip hop"" → search YouTube"
Write-Host ""
Write-Host "  ⚠  Open a new terminal if the vdl command is not recognized."
Write-Host ""
