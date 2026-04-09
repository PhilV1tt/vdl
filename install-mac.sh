#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Installation de vdl                    ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. Homebrew
if ! command -v brew &>/dev/null; then
    echo "→ Installation de Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Ajouter brew au PATH pour les Macs Apple Silicon
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✓ Homebrew déjà installé"
fi

# 2. Python
if ! command -v python3 &>/dev/null; then
    echo "→ Installation de Python..."
    brew install python
else
    echo "✓ Python déjà installé"
fi

# 3. ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "→ Installation de ffmpeg..."
    brew install ffmpeg
else
    echo "✓ ffmpeg déjà installé"
fi

# 4. pipx
if ! command -v pipx &>/dev/null; then
    echo "→ Installation de pipx..."
    brew install pipx
    pipx ensurepath
else
    echo "✓ pipx déjà installé"
fi

# 5. vdl
echo "→ Installation de vdl..."
pipx install "git+https://github.com/PhilV1tt/vdl.git"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅  vdl est installé !                 ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Utilisation :"
echo "    vdl                        → mode interactif (le plus simple)"
echo "    vdl https://youtu.be/xxx   → télécharger une vidéo"
echo "    vdl https://... --audio    → extraire l'audio en MP3"
echo ""
echo "  Relance un nouveau Terminal si la commande vdl n'est pas trouvée."
echo ""
