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
        description="Download video and audio from any site (YouTube, Vimeo, TikTok, SoundCloud...)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  vdl https://youtu.be/xxx              MP4 video, best quality
  vdl https://youtu.be/xxx -a           MP3 audio
  vdl https://youtu.be/xxx -q 720       720p video
  vdl <ongoing YouTube live>            record the live from its start
  vdl @QOVESStudio --links              list a channel's links (nothing downloaded)
  vdl @QOVESStudio --links | vdl -b -   list, then download the whole channel
  vdl -b links.txt                      download a list of URLs
  vdl -m https://youtu.be/xxx           MP3 + Apple Music import
  vdl convert film.mkv -f mp3           convert a local file (mp3, flac, 1080p...)
  vdl film.mov -f mp3                   convert directly, no subcommand
  vdl search "lofi hip hop"             search YouTube
  vdl config                            effective preferences and where they come from
  vdl                                   interactive mode (arrow keys)

Advanced settings (subtitles, SponsorBlock, thumbnail, name template):
  ~/.config/vdl/config.toml   —   see the README.
""",
    )
    p.add_argument("url", nargs="?", help="Link to download or local file to convert")
    p.add_argument("files", nargs="*", help="More local files to convert")
    p.add_argument("-a", "--audio", action="store_true", help="Extract the audio (MP3 by default)")
    p.add_argument(
        "-q",
        "--quality",
        default=None,
        metavar="Q",
        help="best | 2160 | 1440 | 1080 | 720 | 480 | 360  (default: last choice, else best)",
    )
    p.add_argument(
        "-f",
        "--format",
        metavar="FMT",
        help="mp3 m4a wav flac ogg aac opus  |  mp4 mkv webm avi mov",
    )
    p.add_argument("-o", "--output", metavar="DIR", help="Folder for this command only")
    p.add_argument("-p", "--playlist", action="store_true", help="Allow whole playlists / channels")
    p.add_argument(
        "-b",
        "--batch-file",
        metavar="FILE",
        help="File of URLs, one per line ('-' reads standard input)",
    )
    p.add_argument(
        "--links",
        action="store_true",
        help="Print the links of a channel/playlist to standard output, without downloading",
    )
    p.add_argument("-m", "--music", action="store_true", help="Download as MP3 and import into Apple Music")

    adv = p.add_argument_group("advanced")
    adv.add_argument(
        "-s",
        "--section",
        action="append",
        metavar="START-END",
        help="Excerpt, e.g. 12:00-14:30 (repeatable; *START-END = raw seconds)",
    )
    adv.add_argument(
        "--cookies-from-browser",
        metavar="BROWSER",
        help="chrome | safari | firefox | edge | brave (private / members-only / age-restricted content)",
    )
    adv.add_argument(
        "--live-from-start",
        dest="live_from_start",
        action="store_true",
        default=None,
        help="Force recording a live stream from its start (default: auto-detected)",
    )
    adv.add_argument(
        "--no-live-from-start",
        dest="live_from_start",
        action="store_false",
        help="Disable recording from the start, even if the live stream is detected",
    )
    adv.add_argument("-F", "--list-formats", action="store_true", help="List the available formats and exit")
    adv.add_argument("--format-id", metavar="ID", help="Download a specific yt-dlp format (see -F)")
    adv.add_argument(
        "--subs",
        nargs="?",
        const="",
        default=None,
        metavar="LANG",
        help="Download subtitles (optional language, config default)",
    )
    adv.add_argument(
        "--sponsorblock", dest="sponsorblock", action="store_true", default=None, help="Cut sponsor segments"
    )
    adv.add_argument("--no-sponsorblock", dest="sponsorblock", action="store_false", help="Disable SponsorBlock")

    meta = p.add_argument_group("other")
    meta.add_argument("--history", action="store_true", help="Show the history")
    meta.add_argument("--list-sites", action="store_true", help="Sites supported by yt-dlp")
    meta.add_argument("--update", action="store_true", help="Update vdl and yt-dlp")
    meta.add_argument("--verbose", action="store_true", help="Debug logs")
    meta.add_argument("--version", action="version", version=f"vdl {__version__}")
    return p


def _list_sites() -> None:
    try:
        from yt_dlp.extractor import list_extractors

        names = [ie.IE_NAME for ie in list_extractors(age_limit=None) if not ie.IE_NAME.startswith("_")]
        print("\n".join(names))
        print(f"\n{len(names)} supported extractors")
    except ImportError:
        from .i18n import t

        print(t("missing_deps") + " yt-dlp", file=sys.stderr)
        sys.exit(1)


def _do_update() -> None:
    from .updater import do_update

    do_update()


def _validate_url(url: str) -> str | None:
    """Return an error message if the URL is invalid, None if it is fine."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return "L'URL doit commencer par http:// ou https://"
    if not parsed.netloc:
        return "Invalid URL: missing host"
    if parsed.username or parsed.password:
        return "Invalid URL: embedded credentials are not accepted"
    return None


def _read_batch_file(path: str) -> list[str]:
    text = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def _run_search(query: str) -> None:
    """Subcommand: interactive search (delegates to interactive._search_flow)."""
    from .downloader import check_deps
    from .interactive import _search_flow

    check_deps()
    sys.exit(_search_flow(query=query, source="youtube" if query else None))


def _run_config(rest: list[str]) -> None:
    """Subcommand: effective preferences and where they come from, or 'reset' to forget them."""
    from .config import _CONFIG_PATH, load_config

    if rest and rest[0] == "reset":
        removed = prefs.reset()
        print("Remembered preferences deleted." if removed else "Nothing to reset.")
        return

    cfg = load_config()
    state = prefs.recall()
    print(f"config    {_CONFIG_PATH}")
    print(f"memory    {prefs.STATE_PATH}")
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
        origin = "memory" if remembered else "config"
        print(f"  {name:<14} {value:<24} ({origin})")


def _build_downloader(
    args: argparse.Namespace,
    cfg: VdlConfig,
    *,
    output_dir: str,
    playlist: bool,
) -> Downloader:
    """Build a Downloader from the CLI args, the config, and the already resolved folder/playlist."""
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
    # ── Platform init ────────────────────────────────────────────────────
    from .tui import enable_ansi_windows

    enable_ansi_windows()

    # ── Subcommands search / config ──────────────────────────────────────
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
                _make_parser().error("Give a file: vdl convert film.mov -f mp3")
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
                parser.error(f"Options that only apply to downloads : {', '.join(unsupported)}")
            convert_args = [args.url, *args.files]
            for flag, value in (("-f", args.format), ("-q", args.quality), ("-o", args.output)):
                if value:
                    convert_args.extend([flag, value])
            sys.exit(run_convert(convert_args))
    if args.files:
        parser.error("For several links, use vdl -b links.txt")

    from .updater import auto_update_ytdlp, start_update_check

    if not args.update:
        auto_update_ytdlp()
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

    # ── Link extraction (channel/playlist), no download ─────────
    if args.links:
        if not args.url:
            print("Give a channel or a playlist, e.g. vdl @channel --links", file=sys.stderr)
            sys.exit(1)
        from .links import extract_links

        try:
            urls = extract_links(args.url)
        except Exception as e:
            print(f"Extraction failed: {e}", file=sys.stderr)
            sys.exit(1)
        if not urls:
            print("No video found.", file=sys.stderr)
            sys.exit(1)
        print("\n".join(urls))
        return

    from .config import load_config
    from .downloader import check_deps

    check_deps()
    cfg = load_config()

    # ── Available formats, no download ───────────────────────────────
    if args.list_formats:
        if not args.url:
            print("Give a URL, e.g. vdl <url> -F", file=sys.stderr)
            sys.exit(1)
        from .downloader import list_formats

        sys.exit(list_formats(normalize_channel_url(args.url.strip())))

    # ── Batch mode ──────────────────────────────────────────────────────────
    if args.batch_file:
        try:
            urls = _read_batch_file(args.batch_file)
        except OSError as e:
            print(f"Cannot read {args.batch_file} : {e}", file=sys.stderr)
            sys.exit(1)
        if not urls:
            print("The batch file is empty.", file=sys.stderr)
            sys.exit(1)

        is_audio = args.audio or args.music or bool(args.format and args.format.lower() in presets.AUDIO_EXTS)
        state = prefs.recall()
        quality, ext, output_dir = prefs.resolve(args.quality, args.format, args.output, is_audio, state, cfg)
        ext = ext.lower()
        if ext not in (presets.AUDIO_EXTS if is_audio else presets.VIDEO_EXTS):
            parser.error(f"Incompatible format: {ext}")
        valid = [q["value"] for q in presets.AUDIO_QUALITIES] if is_audio else presets.QUALITY_KEYS
        if quality not in valid:
            parser.error(f"Unknown quality: {quality}. Values: {', '.join(valid)}")
        quality_selector, audio_kbps = presets.build_quality_selector(is_audio, quality)
        dl = _build_downloader(args, cfg, output_dir=output_dir, playlist=args.playlist)

        ok = fail = 0
        for raw in urls:
            url = normalize_channel_url(raw)
            err = _validate_url(url)
            if err:
                print(f"URL skipped ({err}) : {url}", file=sys.stderr)
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
        print(f"\n{ok} succeeded, {fail} failed")
        _show_update_notification()
        sys.exit(0 if fail == 0 else 1)

    # ── No URL → interactive mode ────────────────────────────────────────
    if not args.url:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            parser.error("Give a link or a file. To read links from a stream: vdl -b -")
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

    # Decide whether this is audio (--music implies --audio; so does an audio format)
    is_audio = args.audio or args.music
    if not is_audio and args.format and args.format.lower() in presets.AUDIO_EXTS:
        is_audio = True

    state = prefs.recall()
    quality, ext, output_dir = prefs.resolve(args.quality, args.format, args.output, is_audio, state, cfg)
    ext = ext.lower()

    if ext not in (presets.AUDIO_EXTS if is_audio else presets.VIDEO_EXTS):
        print(
            f"Incompatible format: {ext}. Supported formats: "
            f"{', '.join(sorted(presets.AUDIO_EXTS if is_audio else presets.VIDEO_EXTS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    valid = [q["value"] for q in presets.AUDIO_QUALITIES] if is_audio else presets.QUALITY_KEYS
    if quality not in valid:
        parser.error(f"Unknown quality: {quality}. Values: {', '.join(valid)}")
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
