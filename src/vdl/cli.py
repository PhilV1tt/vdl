from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from urllib.parse import urlparse

from . import __version__, prefs, presets
from .config import VdlConfig
from .downloader import Downloader
from .links import is_channel_target, normalize_channel_url


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
  vdl <live YouTube en cours>           enregistre depuis le début du live
  vdl @QOVESStudio --links              liste les liens d'une chaîne (rien téléchargé)
  vdl @QOVESStudio --links | vdl -b -   liste puis télécharge toute la chaîne
  vdl -b liens.txt                      télécharger une liste d'URLs
  vdl -m https://youtu.be/xxx           MP3 + import Apple Music
  vdl convert film.mkv -f mp3           convertir un fichier local (mp3, flac, 1080p…)
  vdl film.mov -f mp3                   convertir directement, sans sous-commande
  vdl search "lofi hip hop"             rechercher sur YouTube
  vdl config                            préférences effectives et leur origine
  vdl                                   mode interactif (flèches)

Réglages avancés (sous-titres, SponsorBlock, miniature, template de nom) :
  ~/.config/vdl/config.toml   —   voir le README.
""",
    )
    p.add_argument("url", nargs="?", help="Lien à télécharger ou fichier local à convertir")
    p.add_argument("files", nargs="*", help="Autres fichiers locaux à convertir")
    p.add_argument("-a", "--audio", action="store_true", help="Extraire l'audio (MP3 par défaut)")
    p.add_argument(
        "-q",
        "--quality",
        default=None,
        metavar="Q",
        help="best | 2160 | 1440 | 1080 | 720 | 480 | 360  (défaut: dernier choix, sinon best)",
    )
    p.add_argument(
        "-f",
        "--format",
        metavar="FMT",
        help="mp3 m4a wav flac ogg aac opus  |  mp4 mkv webm avi mov",
    )
    p.add_argument("-o", "--output", metavar="DOSSIER", help="Dossier pour cette commande uniquement")
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

    adv = p.add_argument_group("avance")
    adv.add_argument(
        "-s",
        "--section",
        action="append",
        metavar="DEBUT-FIN",
        help="Extrait, ex 12:00-14:30 (repetable ; *DEBUT-FIN = secondes brutes)",
    )
    adv.add_argument(
        "--cookies-from-browser",
        metavar="NAVIGATEUR",
        help="chrome | safari | firefox | edge | brave (contenu prive/membres/age)",
    )
    adv.add_argument(
        "--live-from-start",
        dest="live_from_start",
        action="store_true",
        default=None,
        help="Force l'enregistrement d'un live depuis son debut (defaut : auto-detecte)",
    )
    adv.add_argument(
        "--no-live-from-start",
        dest="live_from_start",
        action="store_false",
        help="Desactive l'enregistrement depuis le debut, meme si le live est detecte",
    )
    adv.add_argument("-F", "--list-formats", action="store_true", help="Lister les formats disponibles et quitter")
    adv.add_argument("--format-id", metavar="ID", help="Telecharger un format yt-dlp precis (voir -F)")
    adv.add_argument(
        "--subs",
        nargs="?",
        const="",
        default=None,
        metavar="LANG",
        help="Telecharger les sous-titres (langue optionnelle, defaut config)",
    )
    adv.add_argument(
        "--sponsorblock", dest="sponsorblock", action="store_true", default=None, help="Coupe les segments sponsor"
    )
    adv.add_argument("--no-sponsorblock", dest="sponsorblock", action="store_false", help="Desactive SponsorBlock")

    meta = p.add_argument_group("autres")
    meta.add_argument("--history", action="store_true", help="Afficher l'historique")
    meta.add_argument("--list-sites", action="store_true", help="Sites supportes par yt-dlp")
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
    sys.exit(_search_flow(query=query, source="youtube" if query else None))


def _run_config(rest: list[str]) -> None:
    """Sous-commande : préférences effectives et leur origine, ou 'reset' pour les oublier."""
    from .config import _CONFIG_PATH, load_config

    if rest and rest[0] == "reset":
        removed = prefs.reset()
        print("Préférences mémorisées supprimées." if removed else "Rien à réinitialiser.")
        return

    cfg = load_config()
    state = prefs.recall()
    print(f"config    {_CONFIG_PATH}")
    print(f"mémoire   {prefs.STATE_PATH}")
    print()
    rows = [
        ("video_quality", state.get("video_quality") or state.get("quality"), cfg.default_quality),
        ("audio_quality", state.get("audio_quality"), "320"),
        (
            "video_format",
            state.get("video_format"),
            cfg.default_format if cfg.default_format in presets.VIDEO_EXTS else "mp4",
        ),
        (
            "audio_format",
            state.get("audio_format"),
            cfg.default_format if cfg.default_format in presets.AUDIO_EXTS else "mp3",
        ),
        ("output", state.get("output"), cfg.output_dir),
    ]
    for name, remembered, default in rows:
        value = remembered or default
        origin = "mémoire" if remembered else "config"
        print(f"  {name:<14} {value:<24} ({origin})")


def _build_downloader(
    args: argparse.Namespace,
    cfg: VdlConfig,
    *,
    output_dir: str,
    playlist: bool,
) -> Downloader:
    """Construit un Downloader à partir des args CLI, de la config, et du dossier/playlist déjà résolus."""
    subs_lang = args.subs if args.subs else cfg.subs_lang
    return Downloader(
        output_dir=output_dir,
        playlist=playlist,
        embed_thumbnail=cfg.embed_thumbnail,
        sponsorblock=args.sponsorblock if args.sponsorblock is not None else cfg.sponsorblock,
        subs=args.subs is not None or cfg.subs,
        subs_lang=subs_lang,
        output_template=cfg.output_template,
        retries=cfg.retries,
        live_from_start=args.live_from_start,
        sections=args.section,
        cookies_browser=args.cookies_from_browser,
        format_id=args.format_id,
        concurrent_fragments=cfg.concurrent_fragments,
        use_aria2c=cfg.aria2c,
    )


def main() -> None:
    # ── Init plateforme ────────────────────────────────────────────────────
    from .tui import enable_ansi_windows

    enable_ansi_windows()

    # ── Sous-commandes search / config ──────────────────────────────────────
    raw_args = sys.argv[1:]
    if raw_args and raw_args[0] == "search":
        query = " ".join(raw_args[1:])
        _run_search(query)
        return
    if raw_args and raw_args[0] == "config":
        _run_config(raw_args[1:])
        return
    if raw_args and raw_args[0] == "convert":
        if len(raw_args) == 1:
            from .interactive import _convert_flow

            if not sys.stdin.isatty():
                _make_parser().error("Indique un fichier : vdl convert film.mov -f mp3")
            _convert_flow()
            return
        from .convert import run_convert

        sys.exit(run_convert(raw_args[1:]))

    parser = _make_parser()
    args = parser.parse_intermixed_args()

    if args.url:
        from .convert import is_local_target, run_convert

        if is_local_target(args.url):
            unsupported = [
                key
                for key, value in vars(args).items()
                if value and key not in {"url", "files", "format", "quality", "output", "audio"}
            ]
            if unsupported:
                parser.error(f"Options réservées au téléchargement : {', '.join(unsupported)}")
            convert_args = [args.url, *args.files]
            for flag, value in (("-f", args.format), ("-q", args.quality), ("-o", args.output)):
                if value:
                    convert_args.extend([flag, value])
            sys.exit(run_convert(convert_args))
    if args.files:
        parser.error("Pour plusieurs liens, utilise vdl -b liens.txt")

    from .updater import start_update_check

    if not (args.links or args.list_formats):
        start_update_check(__version__)

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

    # ── Formats disponibles, sans télécharger ───────────────────────────────
    if args.list_formats:
        if not args.url:
            print("Précise une URL, ex : vdl <url> -F", file=sys.stderr)
            sys.exit(1)
        from .downloader import list_formats

        sys.exit(list_formats(normalize_channel_url(args.url.strip())))

    # ── Mode batch ──────────────────────────────────────────────────────────
    if args.batch_file:
        try:
            urls = _read_batch_file(args.batch_file)
        except OSError as e:
            print(f"Impossible de lire {args.batch_file} : {e}", file=sys.stderr)
            sys.exit(1)
        if not urls:
            print("Le fichier batch est vide.", file=sys.stderr)
            sys.exit(1)

        is_audio = args.audio or args.music or bool(args.format and args.format.lower() in presets.AUDIO_EXTS)
        state = prefs.recall()
        quality, ext, output_dir = prefs.resolve(args.quality, args.format, args.output, is_audio, state, cfg)
        ext = ext.lower()
        if ext not in (presets.AUDIO_EXTS if is_audio else presets.VIDEO_EXTS):
            parser.error(f"Format incompatible : {ext}")
        valid = [q["value"] for q in presets.AUDIO_QUALITIES] if is_audio else presets.QUALITY_KEYS
        if quality not in valid:
            parser.error(f"Qualité inconnue : {quality}. Valeurs : {', '.join(valid)}")
        quality_selector, audio_kbps = presets.build_quality_selector(is_audio, quality)
        dl = _build_downloader(args, cfg, output_dir=output_dir, playlist=args.playlist)

        ok = fail = 0
        for raw in urls:
            url = normalize_channel_url(raw)
            err = _validate_url(url)
            if err:
                print(f"URL ignoree ({err}) : {url}", file=sys.stderr)
                fail += 1
                continue
            result = dl.download(url, ext, is_audio, quality_selector, audio_kbps)
            if result.exit_code == 0:
                ok += 1
                if args.music and result.file_path:
                    from .music import music_pipeline

                    music_pipeline(result.file_path, result.info)
            else:
                fail += 1
        if ok:
            prefs.remember(is_audio, quality=args.quality, fmt=args.format)
        print(f"\n{ok} reussi(s), {fail} echoue(s)")
        _show_update_notification()
        sys.exit(0 if fail == 0 else 1)

    # ── Pas d'URL → mode interactif ────────────────────────────────────────
    if not args.url:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            parser.error("Indique un lien ou un fichier. Pour un flux de liens : vdl -b -")
        from .interactive import run_interactive

        run_interactive()
        _show_update_notification()
        return

    raw_url = args.url.strip()
    url = normalize_channel_url(raw_url)
    err = _validate_url(url)
    if err:
        print(err, file=sys.stderr)
        sys.exit(1)

    # Déterminer si c'est de l'audio (--music implique --audio ; un format audio aussi)
    is_audio = args.audio or args.music
    if not is_audio and args.format and args.format.lower() in presets.AUDIO_EXTS:
        is_audio = True

    state = prefs.recall()
    quality, ext, output_dir = prefs.resolve(args.quality, args.format, args.output, is_audio, state, cfg)
    ext = ext.lower()

    if ext not in (presets.AUDIO_EXTS if is_audio else presets.VIDEO_EXTS):
        print(
            f"Format incompatible : {ext}. Formats supportés : "
            f"{', '.join(sorted(presets.AUDIO_EXTS if is_audio else presets.VIDEO_EXTS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    valid = [q["value"] for q in presets.AUDIO_QUALITIES] if is_audio else presets.QUALITY_KEYS
    if quality not in valid:
        parser.error(f"Qualité inconnue : {quality}. Valeurs : {', '.join(valid)}")
    quality_selector, audio_kbps = presets.build_quality_selector(is_audio, quality)
    channel_mode = is_channel_target(raw_url)
    dl = _build_downloader(args, cfg, output_dir=output_dir, playlist=args.playlist or channel_mode)
    result = dl.download(url, ext, is_audio, quality_selector, audio_kbps)

    if result.exit_code == 0:
        prefs.remember(is_audio, quality=args.quality, fmt=args.format)

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
