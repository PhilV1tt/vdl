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

Colle un lien, vdl propose direct "Télécharger" avec la qualité et le format que tu as choisis la dernière fois. Entrée suffit. "Plutôt l'audio" bascule en un coup, et "Options…" ouvre qualité, format, dossier, extrait, sous-titres, SponsorBlock, métadonnées et cookies navigateur pour qui veut aller plus loin.

Sur une chaîne ou une playlist, vdl demande "toute la playlist" ou juste la vidéo précise. Sur un live en cours, il enregistre depuis le début (Ctrl-C pour arrêter à l'instant présent).

### Mode commande

```bash
vdl https://youtu.be/xxx                   # Vidéo MP4, meilleure qualité
vdl https://youtu.be/xxx -a                # Audio MP3
vdl https://youtu.be/xxx -a -f flac        # Audio FLAC
vdl https://youtu.be/xxx -q 1080           # Vidéo 1080p
vdl -m https://youtu.be/xxx                # MP3 + import Apple Music
vdl -b liens.txt                           # Télécharger une liste d'URLs
vdl https://youtu.be/xxx -s 12:00-14:30    # Juste cet extrait
vdl <live YouTube en cours>                # Enregistre depuis le début du live
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
| `-s DÉBUT-FIN` | Extrait, ex `12:00-14:30` (répétable) |
| `--cookies-from-browser NAVIGATEUR` | Cookies depuis chrome/safari/firefox/edge/brave (contenu privé/membres/âge) |
| `--live-from-start` / `--no-live-from-start` | Force ou désactive l'enregistrement d'un live depuis son début (défaut : auto-détecté) |
| `-F` / `--list-formats` | Lister les formats disponibles pour une URL |
| `--format-id ID` | Télécharger un format yt-dlp précis (voir `-F`) |
| `--subs [LANGUE]` | Sous-titres (langue optionnelle) |
| `--sponsorblock` / `--no-sponsorblock` | Force ou désactive SponsorBlock |
| `--list-sites` | Afficher les 1000+ sites supportés |

### Direct (live)

vdl détecte tout seul un live en cours et enregistre depuis son début. Il n'existe pas de moyen natif d'arrêter automatiquement "à l'instant présent" : Ctrl-C est le seul point d'arrêt, et vdl recolle alors les fragments déjà reçus en un fichier lisible.

Sur un live qui tourne en continu depuis longtemps (une caméra 24/7, par exemple), "depuis le début" peut représenter une quantité de données énorme. Vérifie que c'est bien ce que tu veux avant de lancer un enregistrement long, et laisse tourner le temps qu'il faut avant le Ctrl-C.

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

vdl retient automatiquement la dernière qualité, le dernier format (séparément pour
l'audio et la vidéo) et le dernier dossier utilisés, pour les proposer par défaut
la prochaine fois. `vdl config` affiche les valeurs effectives et leur origine
(mémoire ou config), `vdl config reset` oublie la mémoire.

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
