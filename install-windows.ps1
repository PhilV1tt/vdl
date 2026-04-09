# vdl — Installateur Windows
# Usage : powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/PhilV1tt/vdl/main/install-windows.ps1 | iex"

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗"
Write-Host "║   Installation de vdl                    ║"
Write-Host "╚══════════════════════════════════════════╝"
Write-Host ""

# ── Fonctions utilitaires ──────────────────────────────────────────────────

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

function Install-Winget-Package($id, $label) {
    Write-Host "→ Installation de $label..."
    winget install --id $id --silent --accept-package-agreements --accept-source-agreements
}

# ── 1. winget ─────────────────────────────────────────────────────────────

if (-not (Test-Command "winget")) {
    Write-Host "❌ winget n'est pas disponible." -ForegroundColor Red
    Write-Host "   Installe 'App Installer' depuis le Microsoft Store et relance ce script."
    exit 1
}
Write-Host "✓ winget disponible"

# ── 2. Python ─────────────────────────────────────────────────────────────

if (-not (Test-Command "python")) {
    Install-Winget-Package "Python.Python.3.12" "Python 3.12"
    # Recharger le PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Host "✓ Python déjà installé"
}

# ── 3. ffmpeg ─────────────────────────────────────────────────────────────

if (-not (Test-Command "ffmpeg")) {
    Install-Winget-Package "Gyan.FFmpeg" "ffmpeg"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
                [System.Environment]::GetEnvironmentVariable("Path", "User")
} else {
    Write-Host "✓ ffmpeg déjà installé"
}

# ── 4. pipx ───────────────────────────────────────────────────────────────

if (-not (Test-Command "pipx")) {
    Write-Host "→ Installation de pipx..."
    python -m pip install --user pipx
    python -m pipx ensurepath
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
} else {
    Write-Host "✓ pipx déjà installé"
}

# ── 5. vdl ────────────────────────────────────────────────────────────────

Write-Host "→ Installation de vdl..."
pipx install "git+https://github.com/PhilV1tt/vdl.git"

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗"
Write-Host "║   ✅  vdl est installé !                 ║"
Write-Host "╚══════════════════════════════════════════╝"
Write-Host ""
Write-Host "  Utilisation :"
Write-Host "    vdl                        → mode interactif (navigation flèches)"
Write-Host "    vdl https://youtu.be/xxx   → télécharger une vidéo"
Write-Host "    vdl https://... --audio    → extraire l'audio en MP3"
Write-Host "    vdl search ""lofi hip hop"" → rechercher sur YouTube"
Write-Host ""
Write-Host "  ⚠  Ouvre un nouveau terminal si la commande vdl n'est pas reconnue."
Write-Host ""
