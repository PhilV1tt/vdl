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

Colle un lien directement : vdl affiche les derniers réglages sur un seul écran.
Entrée télécharge, `a` lance l'audio, `v` la vidéo. Le dernier mode utilisé est retenu.
Tab bascule audio/vidéo ; les flèches gauche/droite changent la qualité et haut/bas le format.
`d` change le dossier, `e` l'extrait, `o` ouvre les options avancées. Échap revient à la saisie du lien.
Sur Mac, `m` télécharge l'audio puis l'importe dans Apple Music.
Le mode actif est surligné ; les réglages réagissent aux touches.
`NO_COLOR=1` désactive les couleurs, `VDL_REDUCED_MOTION=1` désactive les animations.
Glisse un fichier local dans le Terminal : vdl propose le format de conversion.
Tape du texte : vdl cherche sur YouTube. Entrée vide ou Ctrl-D quitte.

Les commandes `/convert`, `/search`, `/history` et `/quit` sont affichées au démarrage.
Les options avancées regroupent sous-titres, SponsorBlock, métadonnées et cookies.

Un lien vidéo cible cette vidéo, même si YouTube y ajoute une playlist ou une radio.
Pour tout télécharger, utilise `vdl URL --playlist`. Un lien de playlist seule ou de chaîne
utilise le même écran de réglages pour la playlist entière. Sur un live en cours, vdl enregistre
depuis le début (Ctrl-C pour arrêter à l'instant présent).

### Mode commande

```bash
vdl https://youtu.be/xxx                   # Vidéo MP4, meilleure qualité
vdl https://youtu.be/xxx -a                # Audio MP3
vdl https://youtu.be/xxx -a -f flac        # Audio FLAC
vdl https://youtu.be/xxx -q 1080           # Vidéo 1080p
vdl -m https://youtu.be/xxx                # MP3 + import Apple Music
vdl -b liens.txt                           # Télécharger une liste d'URLs
vdl convert film.mkv -f mp3                # Convertir un fichier local
vdl film.mov -f mp3                        # Conversion directe, sans sous-commande
vdl convert                               # Choisir un fichier puis un format
vdl https://youtu.be/xxx -s 12:00-14:30    # Juste cet extrait
vdl <live YouTube en cours>                # Enregistre depuis le début du live
```

### Convertir un fichier local

`convert` transforme un fichier déjà sur le disque, sans passer par un site. La sortie
porte le nom de la source ; `-o` change le dossier.
La sous-commande `convert` est facultative : `vdl film.mkv -f mp3` fonctionne aussi.
Sans argument, `vdl convert` demande un fichier et son format de sortie.

```bash
vdl convert film.mkv -f mp3             # MP3 320 kbps
vdl convert podcast.wav -f flac         # FLAC, sans perte
vdl convert reel.mov -f mp4 -q 1080     # MP4 ramené à 1080p
vdl convert *.mp4 -f mp3 -o ~/Music     # plusieurs fichiers d'un coup
```

| Option | Description |
|--------|-------------|
| `-f FORMAT` | Sortie : `mp3` `m4a` `aac` `flac` `wav` `ogg` `opus` (vidéo : `mp4` `mkv` `webm` `avi` `mov`) |
| `-q Q` | Audio : `320` `256` `192` `128` kbps.  Vidéo : hauteur `2160` `1440` `1080` `720` `480` `360` |
| `-o DOSSIER` | Dossier de sortie (défaut : à côté de la source) |

Sans `-f`, la sortie est le dernier format audio choisi, ou MP3. L'encodage est h264 + AAC,
VP9 + Opus pour WebM. Si le nom de sortie existe, vdl ajoute un suffixe (`film (1).mp3`).
La source est conservée, y compris pour une conversion vers le même format.
Un échec ne laisse pas de fichier partiel.

En mode interactif, colle un chemin ou utilise `/convert`.

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

vdl retient automatiquement la dernière qualité et le dernier format, séparément pour
l'audio et la vidéo. Le dossier choisi en mode interactif est également retenu
la prochaine fois. `vdl config` affiche les valeurs effectives et leur origine
(mémoire ou config), `vdl config reset` oublie la mémoire.

En ligne de commande, `-o` ne change le dossier que pour cette exécution.

Les options moins courantes se règlent une fois dans `~/.config/vdl/config.toml`
(au lieu d'un flag à chaque commande) :

```toml
subs = true              # Télécharger et embarquer les sous-titres
subs_lang = "fr"         # Langue des sous-titres
sponsorblock = true      # Supprimer les segments SponsorBlock
embed_thumbnail = true   # Embarquer la miniature
output_template = "%(title)s.%(ext)s"
concurrent_fragments = 4 # Fragments telechargés en parallèle (vidéos/lives longs)
aria2c = false           # Déléguer le téléchargement à aria2c (brew install aria2)
```

Sur les vidéos longues et les lives, vdl télécharge déjà 4 fragments en parallèle
par défaut (plus rapide qu'un fragment à la fois). Pour aller plus loin, installe
`aria2c` et passe `aria2c = true` : yt-dlp lui délègue le téléchargement, généralement
le plus rapide.

## Mise à jour

```bash
vdl --update
```

## Désinstallation

```bash
pipx uninstall vdl        # macOS / Linux
```
