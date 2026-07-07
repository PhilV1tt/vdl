from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import __version__, presets
from .config import VdlConfig
from .downloader import Downloader


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vdl",
        description="Télécharge vidéos et audio depuis n'importe quel site (YouTube, Vimeo, TikTok, SoundCloud…)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Exemples :
  vdl https://youtu.be/xxx              vidéo MP4, meilleure qualité
  vdl https://youtu.be/xxx -a           audio MP3
  vdl https://youtu.be/xxx -q 720       vidéo 720p
  vdl @QOVESStudio --links              liste les liens d'une chaîne (rien téléchargé)
  vdl @QOVESStudio --links | vdl -b -   liste puis télécharge toute la chaîne
  vdl -b liens.txt                      télécharger une liste d'URLs
  vdl -m https://youtu.be/xxx           MP3 + import Apple Music
  vdl search "lofi hip hop"             rechercher sur YouTube
  vdl                                   mode interactif (flèches)

Réglages avancés (sous-titres, SponsorBlock, miniature, template de nom) :
  ~/.config/vdl/config.toml   —   voir le README.
""",
    )
    p.add_argument("url", nargs="?", help="URL, @chaîne, ou 'search' pour rechercher")
    p.add_argument("-a", "--audio", action="store_true", help="Extraire l'audio (MP3 par défaut)")
    p.add_argument(
        "-q",
        "--quality",
        default="best",
        metavar="Q",
        help="best | 2160 | 1440 | 1080 | 720 | 480 | 360  (défaut: best)",
    )
    p.add_argument(
        "-f",
        "--format",
        metavar="FMT",
        help="mp3 m4a wav flac ogg aac opus  |  mp4 mkv webm avi mov",
    )
    p.add_argument("-o", "--output", metavar="DOSSIER", help="Dossier de destination (défaut: ~/Downloads)")
    p.add_argument("-p", "--playlist", action="store_true", help="Autoriser les playlists / chaînes entières")
    p.add_argument(
        "-b",
        "--batch-file",
        metavar="FICHIER",
        help="Fichier d'URLs, une par ligne ('-' pour lire l'entrée standard)",
    )
    p.add_argument(
        "--links",
        action="store_true",
        help="Lister les liens d'une chaîne/playlist sur la sortie standard, sans télécharger",
    )
    p.add_argument("-m", "--music", action="store_true", help="Télécharger en MP3 et importer dans Apple Music")

    meta = p.add_argument_group("autres")
    meta.add_argument("--history", action="store_true", help="Afficher l'historique")
    meta.add_argument("--list-sites", action="store_true", help="Sites supportés par yt-dlp")
    meta.add_argument("--update", action="store_true", help="Mettre à jour vdl")
    meta.add_argument("--verbose", action="store_true", help="Logs de débogage")
    meta.add_argument("--version", action="version", version=f"vdl {__version__}")
    return p


def _list_sites() -> None:
    try:
        from yt_dlp.extractor import list_extractors

        names = [ie.IE_NAME for ie in list_extractors(age_limit=None) if not ie.IE_NAME.startswith("_")]
        print("\n".join(names))
        print(f"\n{len(names)} extracteurs supportés")
    except ImportError:
        from .i18n import t

        print(t("missing_deps") + " yt-dlp", file=sys.stderr)
        sys.exit(1)


def _do_update() -> None:
    from .updater import do_update

    do_update()


def _validate_url(url: str) -> str | None:
    """Retourne un message d'erreur si l'URL est invalide, None si OK."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "L'URL doit commencer par http:// ou https://"
    if not parsed.netloc:
        return "URL invalide : hôte manquant"
    if parsed.username or parsed.password:
        return "URL invalide : les credentials embarqués ne sont pas acceptés"
    return None


def _read_batch_file(path: str) -> list[str]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def _run_search(query: str) -> None:
    """Sous-commande : recherche interactive (délègue à interactive._search_flow)."""
    from .downloader import check_deps
    from .interactive import _search_flow

    check_deps()
    sys.exit(_search_flow())


def _build_downloader(args: argparse.Namespace, cfg: VdlConfig) -> Downloader:
    """Construit un Downloader à partir des args CLI et de la config."""
    return Downloader(
        output_dir=args.output or cfg.output_dir,
        playlist=args.playlist,
        embed_thumbnail=cfg.embed_thumbnail,
        sponsorblock=cfg.sponsorblock,
        subs=cfg.subs,
        subs_lang=cfg.subs_lang,
        output_template=cfg.output_template,
        retries=cfg.retries,
    )


def main() -> None:
    # ── Init plateforme ────────────────────────────────────────────────────
    from .tui import enable_ansi_windows

    enable_ansi_windows()

    # ── Sous-commande search ───────────────────────────────────────────────
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "search":
        query = " ".join(raw_args[1:])
        _run_search(query)
        return

    # ── Détection mise à jour (background) ────────────────────────────────
    from .updater import start_update_check

    start_update_check(__version__)

    parser = _make_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

    if args.list_sites:
        _list_sites()
        return

    if args.history:
        from .history import show_history

        show_history()
        return

    if args.update:
        _do_update()
        return

    # ── Extraction de liens (chaîne/playlist), sans téléchargement ─────────
    if args.links:
        if not args.url:
            print("Précise une chaîne ou une playlist, ex : vdl @chaine --links", file=sys.stderr)
            sys.exit(1)
        from .links import extract_links

        try:
            urls = extract_links(args.url)
        except Exception as e:
            print(f"Erreur d'extraction : {e}", file=sys.stderr)
            sys.exit(1)
        if not urls:
            print("Aucune vidéo trouvée.", file=sys.stderr)
            sys.exit(1)
        print("\n".join(urls))
        return

    from .config import load_config
    from .downloader import check_deps

    check_deps()
    cfg = load_config()

    # ── Mode batch ──────────────────────────────────────────────────────────
    if args.batch_file:
        try:
            urls = _read_batch_file(args.batch_file)
        except FileNotFoundError:
            print(f"Fichier introuvable : {args.batch_file}", file=sys.stderr)
            sys.exit(1)
        if not urls:
            print("Le fichier batch est vide.", file=sys.stderr)
            sys.exit(1)

        is_audio = args.audio
        ext = (args.format.lower() if args.format else None) or cfg.default_format or ("mp3" if is_audio else "mp4")
        quality_selector, audio_kbps = presets.build_quality_selector(is_audio, args.quality or cfg.default_quality)
        dl = _build_downloader(args, cfg)

        ok = fail = 0
        for url in urls:
            err = _validate_url(url)
            if err:
                print(f"URL ignoree ({err}) : {url}", file=sys.stderr)
                fail += 1
                continue
            result = dl.download(url, ext, is_audio, quality_selector, audio_kbps)  # type: ignore[union-attr]
            if result.exit_code == 0:
                ok += 1
            else:
                fail += 1
        print(f"\n{ok} reussi(s), {fail} echoue(s)")
        _show_update_notification()
        sys.exit(0 if fail == 0 else 1)

    # ── Pas d'URL → mode interactif ────────────────────────────────────────
    if not args.url:
        from .interactive import run_interactive

        run_interactive()
        _show_update_notification()
        return

    url = args.url.strip()
    err = _validate_url(url)
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    # Déterminer si c'est de l'audio (--music implique --audio ; un format audio aussi)
    is_audio = args.audio or args.music
    if not is_audio and args.format and args.format.lower() in presets.AUDIO_EXTS:
        is_audio = True

    ext = args.format.lower() if args.format else ("mp3" if is_audio else "mp4")

    if ext not in presets.ALL_EXTS:
        print(
            f"Format inconnu : {ext}. Formats supportes : {', '.join(sorted(presets.ALL_EXTS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    quality_selector, audio_kbps = presets.build_quality_selector(is_audio, args.quality)
    dl = _build_downloader(args, cfg)
    result = dl.download(url, ext, is_audio, quality_selector, audio_kbps)  # type: ignore[union-attr]

    if args.music and result.exit_code == 0 and result.file_path:
        from .music import music_pipeline

        music_pipeline(result.file_path, result.info)

    _show_update_notification()
    sys.exit(result.exit_code)


def _show_update_notification() -> None:
    from .updater import get_update_notification

    msg = get_update_notification()
    if msg:
        print(f"\n{msg}")
