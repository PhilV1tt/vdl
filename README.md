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

Si tu réponds oui à "Personnaliser", vdl demande en plus un titre, s'il faut retirer toutes les métadonnées, et pour l'audio la pochette et l'artiste/album. Sinon il garde les réglages par défaut.

### Mode commande

```bash
vdl https://youtu.be/xxx                   # Vidéo MP4, meilleure qualité
vdl https://youtu.be/xxx -a                # Audio MP3
vdl https://youtu.be/xxx -a -f flac        # Audio FLAC
vdl https://youtu.be/xxx -q 1080           # Vidéo 1080p
vdl -m https://youtu.be/xxx                # MP3 + import Apple Music
vdl -b liens.txt                           # Télécharger une liste d'URLs
```

### Options

| Option | Description |
|--------|-------------|
| `-a` / `--audio` | Extraire l'audio (MP3 par défaut) |
| `-q QUALITÉ` | Qualité vidéo : `best`, `1080`, `720`, `480`, `360` |
| `-f FORMAT` | Format : `mp3`, `m4a`, `flac`, `wav`, `mp4`, `mkv`… |
| `-o DOSSIER` | Dossier de destination (défaut : `~/Downloads`) |
| `-p` / `--playlist` | Télécharger une playlist / chaîne entière |
| `-b FICHIER` | Fichier d'URLs, une par ligne (`-` = entrée standard) |
| `--links` | Lister les liens d'une chaîne/playlist, sans télécharger |
| `-m` / `--music` | MP3 + import dans Apple Music |
| `--list-sites` | Afficher les 1000+ sites supportés |

### Récupérer tous les liens d'une chaîne

`--links` sort une URL par ligne sur la sortie standard, sans rien télécharger.
Un `@handle` seul est complété automatiquement.

```bash
vdl @QOVESStudio --links                   # Affiche tous les liens de la chaîne
vdl @QOVESStudio --links > liens.txt        # Enregistre la liste (à trier/filtrer)
vdl -b liens.txt                            # Télécharge ce qu'on a gardé
vdl @QOVESStudio --links | vdl -b -         # Tout en une passe
```

### Réglages persistants

Les options moins courantes se règlent une fois dans `~/.config/vdl/config.toml`
(au lieu d'un flag à chaque commande) :

```toml
subs = true              # Télécharger et embarquer les sous-titres
subs_lang = "fr"         # Langue des sous-titres
sponsorblock = true      # Supprimer les segments SponsorBlock
embed_thumbnail = true   # Embarquer la miniature
output_template = "%(title)s.%(ext)s"
```

## Mise à jour

```bash
vdl --update
```

## Désinstallation

```bash
pipx uninstall vdl        # macOS / Linux
```
