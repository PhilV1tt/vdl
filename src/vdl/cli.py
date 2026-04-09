import argparse
import logging
import sys
from pathlib import Path

from . import __version__, presets


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vdl",
        description="Télécharge vidéos et audio depuis n'importe quel site (YouTube, Vimeo, TikTok, SoundCloud…)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Exemples :
  vdl https://youtu.be/xxx                      vidéo MP4, meilleure qualité
  vdl https://vimeo.com/xxx --audio             MP3 320 kbps
  vdl https://soundcloud.com/a/b -a -f opus     OPUS audio
  vdl https://twitch.tv/videos/xxx -q 720       vidéo 720p
  vdl                                           mode interactif (prompts)
""",
    )
    p.add_argument("url", nargs="?", help="URL de la vidéo/audio")
    p.add_argument("-a", "--audio", action="store_true", help="Extraire l'audio")
    p.add_argument("-v", "--video", action="store_true", help="Forcer le téléchargement vidéo")
    p.add_argument(
        "-q",
        "--quality",
        default="best",
        metavar="QUALITÉ",
        help="Qualité vidéo : best | 2160 | 1440 | 1080 | 720 | 480 | 360  (défaut: best)",
    )
    p.add_argument(
        "-f",
        "--format",
        metavar="FORMAT",
        help="Format de sortie : mp3 | m4a | wav | flac | ogg | aac | opus | mp4 | mkv | webm | avi | mov",
    )
    p.add_argument(
        "-o",
        "--output",
        metavar="DOSSIER",
        help="Dossier de destination (défaut: ~/Downloads)",
    )
    p.add_argument("-p", "--playlist", action="store_true", help="Autoriser le téléchargement de playlists entières")
    p.add_argument("--no-thumbnail", action="store_true", help="Ne pas embarquer la miniature dans le fichier")
    p.add_argument("--list-sites", action="store_true", help="Afficher les sites supportés par yt-dlp")
    p.add_argument("--verbose", action="store_true", help="Afficher les logs de débogage")
    p.add_argument("--version", action="version", version=f"vdl {__version__}")
    return p


def _list_sites() -> None:
    try:
        from yt_dlp.extractor import list_extractors

        ies = list_extractors(age_limit=None)
        count = 0
        for ie in ies:
            name = ie.IE_NAME
            if not name.startswith("_"):
                print(name)
                count += 1
        print(f"\n{count} extracteurs supportés")
    except ImportError:
        print("❌ yt-dlp non installé", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = _make_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

    if args.list_sites:
        _list_sites()
        return

    from .downloader import check_deps

    check_deps()

    # Pas d'URL → mode interactif
    if not args.url:
        from .interactive import run_interactive

        run_interactive()
        return

    url = args.url.strip()
    if not url.startswith(("http://", "https://")):
        print("❌ L'URL doit commencer par http:// ou https://", file=sys.stderr)
        sys.exit(1)

    # Déterminer si c'est de l'audio
    is_audio = args.audio
    if not is_audio and not args.video:
        # Si le format demandé est un format audio, activer le mode audio automatiquement
        if args.format and args.format.lower() in presets.AUDIO_EXTS:
            is_audio = True

    # Format de sortie
    ext = args.format.lower() if args.format else ("mp3" if is_audio else "mp4")

    # Valider le format
    if ext not in presets.ALL_EXTS:
        print(
            f"❌ Format inconnu : {ext}. Formats supportés : {', '.join(sorted(presets.ALL_EXTS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Sélecteur de qualité yt-dlp
    if is_audio:
        quality_selector = "bestaudio/best"
        audio_kbps = "320"
    else:
        quality_selector = presets.VIDEO_QUALITY_MAP.get(args.quality, "bestvideo+bestaudio/best")
        audio_kbps = "0"

    output = args.output or str(Path.home() / "Downloads")

    from .downloader import Downloader

    dl = Downloader(
        output_dir=output,
        playlist=args.playlist,
        embed_thumbnail=not args.no_thumbnail,
    )
    sys.exit(dl.download(url, ext, is_audio, quality_selector, audio_kbps))
