#!/bin/bash
set -e

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   Installing vdl                         ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# 1. Homebrew
if ! command -v brew &>/dev/null; then
    echo "→ Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add brew to PATH on Apple Silicon Macs
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✓ Homebrew already installed"
fi

# 2. Python
if ! command -v python3 &>/dev/null; then
    echo "→ Installing Python..."
    brew install python
else
    echo "✓ Python already installed"
fi

# 3. ffmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "→ Installing ffmpeg..."
    brew install ffmpeg
else
    echo "✓ ffmpeg already installed"
fi

# 4. pipx
if ! command -v pipx &>/dev/null; then
    echo "→ Installing pipx..."
    brew install pipx
    pipx ensurepath
else
    echo "✓ pipx already installed"
fi

# 5. vdl
echo "→ Installing vdl..."
pipx install "git+https://github.com/PhilV1tt/vdl.git"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   ✅  vdl is installed!                  ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "  Usage:"
echo "    vdl                        → interactive mode (the easiest)"
echo "    vdl https://youtu.be/xxx   → download a video"
echo "    vdl https://... --audio    → extract the audio as MP3"
echo ""
echo "  Open a new Terminal if the vdl command is not found."
echo ""
