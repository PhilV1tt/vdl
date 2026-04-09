# vdl — Téléchargeur universel de vidéos

Fait avec amour pour Julien, qui voulait juste télécharger ses vidéos sans prise de tête.

Télécharge des vidéos et de l'audio depuis YouTube, Vimeo, TikTok, SoundCloud et [1000+ autres sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Installation (Mac)

Colle cette commande dans le Terminal et appuie sur Entrée :

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/PhilV1tt/VideoDownloader/main/install-mac.sh)
```

C'est tout. Le script installe tout automatiquement.

## Utilisation

### Mode interactif (le plus simple)

Lance simplement :

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
pipx upgrade vdl
```

## Désinstallation

```bash
pipx uninstall vdl
```
