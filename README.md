# vdl - Téléchargeur universel de vidéos

Fait avec amour pour Julien :))))

Téléchargez des vidéos et de l'audio depuis YouTube, Vimeo, TikTok, SoundCloud et [1000+ autres sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Installation

### macOS

Collez cette commande dans le Terminal et appuyez sur Entrée :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/PhilV1tt/vdl/main/install-mac.sh)
```

### Linux

```bash
# 1. Installer pipx si pas déjà installé
sudo apt install pipx        # Debian/Ubuntu
sudo dnf install pipx        # Fedora
sudo pacman -S python-pipx   # Arch

pipx ensurepath

# 2. Installer ffmpeg
sudo apt install ffmpeg      # Debian/Ubuntu
sudo dnf install ffmpeg      # Fedora
sudo pacman -S ffmpeg        # Arch

# 3. Installer vdl
pipx install git+https://github.com/PhilV1tt/vdl.git
```

### Windows

Collez cette commande dans PowerShell (en tant qu'administrateur) :

```powershell
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/PhilV1tt/vdl/main/install-windows.ps1 | iex"
```

Le script installe automatiquement Python, ffmpeg et vdl via winget.

## Utilisation

### Mode interactif (le plus simple)

Lancez simplement :

```bash
vdl
```

Le programme pose des questions : lien, audio ou vidéo, format, qualité. Rien à mémoriser.

### Mode commande

```bash
vdl https://youtu.be/xxx                   # Vidéo MP4, meilleure qualité
vdl https://youtu.be/xxx --audio           # MP3 320 kbps
vdl https://youtu.be/xxx -a -f flac        # Audio FLAC
vdl https://youtu.be/xxx -q 1080           # Vidéo 1080p
vdl https://soundcloud.com/a/b -a          # Audio depuis SoundCloud
```

### Options

| Option | Description |
|--------|-------------|
| `-a` / `--audio` | Extraire l'audio |
| `-q QUALITÉ` | Qualité vidéo : `best`, `1080`, `720`, `480`, `360` |
| `-f FORMAT` | Format : `mp3`, `m4a`, `flac`, `wav`, `mp4`, `mkv`… |
| `-o DOSSIER` | Dossier de destination (défaut : `~/Downloads`) |
| `-p` / `--playlist` | Télécharger une playlist entière |
| `--list-sites` | Afficher les 1000+ sites supportés |

## Mise à jour

```bash
vdl --update
```

## Désinstallation

```bash
pipx uninstall vdl        # macOS / Linux
```
