from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .i18n import t
from .tui import BOLD, DIM, RED, RESET, YELLOW, Spinner, c, success_flash

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    exit_code: int
    file_path: Path | None = None
    info: dict[str, Any] = field(default_factory=dict)


DEFAULT_OUTPUT = str(Path.home() / "Downloads")

_ERROR_PATTERNS: list[tuple[str, str]] = [
    ("Unsupported URL", "err_unsupported"),
    ("Private video", "err_private"),
    ("Video unavailable", "err_unavailable"),
    ("HTTP Error 429", "err_429"),
    ("Unable to extract", "err_extract"),
    ("This live event will begin", "err_upcoming"),
]


def _print_error(msg: str, url: str = "") -> None:
    for pattern, key in _ERROR_PATTERNS:
        if pattern in msg:
            print(t(key, url=url) if key == "err_unsupported" else t(key), file=sys.stderr)
            if key == "err_unsupported":
                print(t("err_unsupported_hint"), file=sys.stderr)
            return
    print(msg.replace("ERROR: ", "").strip(), file=sys.stderr)


def check_deps() -> None:
    import importlib.util

    missing = []
    if importlib.util.find_spec("yt_dlp") is None:
        missing.append("yt-dlp  →  pip install yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg  →  brew install ffmpeg")
    if missing:
        print(t("missing_deps"), file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        sys.exit(1)


_BAD_TITLE = re.compile(r'[\\/:*?"<>|%]')


def _sanitize_title(title: str) -> str:
    cleaned = _BAD_TITLE.sub("_", title).strip()
    return cleaned or "video"


def _strip_file_metadata(path: Path) -> None:
    """Retire metadonnees globales et chapitres du fichier final, remux ffmpeg sans reencodage."""
    if not path.exists():
        return
    tmp = path.with_name(path.stem + ".stripped" + path.suffix)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(path),
        "-map",
        "0",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-fflags",
        "+bitexact",
        "-c",
        "copy",
        str(tmp),
    ]
    try:
        done = subprocess.run(cmd, capture_output=True)
        if done.returncode == 0 and tmp.exists():
            tmp.replace(path)
        elif tmp.exists():
            tmp.unlink()
    except Exception:
        pass


def _remux_live_parts(final_path: Path) -> bool:
    """Best-effort : remuxe les fragments d'un live interrompu (Ctrl-C) en un fichier lisible."""
    import glob

    pattern = glob.escape(final_path.stem) + ".f*"
    parts = sorted(str(p) for p in final_path.parent.glob(pattern) if p.stat().st_size > 0)
    if not parts:
        return False
    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", p]
    cmd += ["-c", "copy", str(final_path)]
    try:
        done = subprocess.run(cmd, capture_output=True)
        return done.returncode == 0 and final_path.exists()
    except Exception:
        return False


def _parse_timestamp(s: str) -> float:
    parts = [float(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, sec = parts[-3:]
    return h * 3600 + m * 60 + sec


def _parse_section(spec: str) -> tuple[float, float]:
    """Parse '12:00-14:30' ou '*90-120' (secondes brutes) en (debut, fin)."""
    raw = spec.startswith("*")
    body = spec[1:] if raw else spec
    start_s, end_s = body.split("-", 1)
    if raw:
        return float(start_s), float(end_s)
    return _parse_timestamp(start_s), _parse_timestamp(end_s)


def probe(url: str, *, single: bool = False) -> dict[str, Any] | None:
    """Extraction legere : dict complet pour une video seule, entrees a plat pour une playlist/chaine.

    single=True force noplaylist (utile pour cibler la video precise d'une URL video+playlist).
    """
    import yt_dlp

    opts: dict[str, Any] = {"extract_flat": "in_playlist", "quiet": True, "no_warnings": True}
    if single:
        opts["noplaylist"] = True
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            result: dict[str, Any] | None = ydl.extract_info(url, download=False)
            return result
    except Exception:
        return None


def kind(info: dict[str, Any]) -> str:
    """Classe un dict probe : video, playlist, live ou upcoming."""
    live_status = info.get("live_status")
    if live_status == "is_upcoming":
        return "upcoming"
    if live_status == "is_live":
        return "live"
    return "playlist" if info.get("entries") is not None else "video"


def _print_upcoming(info: dict[str, Any]) -> None:
    ts = info.get("release_timestamp")
    if ts:
        from datetime import datetime

        print(t("live_upcoming", when=datetime.fromtimestamp(ts).strftime("%H:%M")))
    else:
        print(t("err_upcoming"))


def list_formats(url: str) -> int:
    """Affiche les formats disponibles (ids yt-dlp) sans rien telecharger."""
    import yt_dlp

    opts: dict[str, Any] = {"listformats": True, "quiet": False, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        return 0
    except yt_dlp.utils.DownloadError as e:
        _print_error(str(e), url)
        return 1


class Downloader:
    def __init__(
        self,
        output_dir: str = DEFAULT_OUTPUT,
        playlist: bool = False,
        embed_thumbnail: bool = True,
        sponsorblock: bool = False,
        subs: bool = False,
        subs_lang: str = "fr",
        output_template: str = "%(title)s.%(ext)s",
        retries: int = 3,
        strip_metadata: bool = False,
        custom_title: str | None = None,
        live_from_start: bool | None = None,
        sections: list[str] | None = None,
        cookies_browser: str | None = None,
        format_id: str | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.playlist = playlist
        self.embed_thumbnail = embed_thumbnail
        self.sponsorblock = sponsorblock
        self.subs = subs
        self.subs_lang = subs_lang
        self.output_template = output_template
        self.retries = retries
        self.strip_metadata = strip_metadata
        self.custom_title = custom_title
        self.live_from_start = live_from_start
        self.sections = sections
        self.cookies_browser = cookies_browser
        self.format_id = format_id

    def _build_ydl_opts(
        self,
        ext: str,
        is_audio: bool,
        quality_selector: str,
        audio_kbps: str,
        progress_hook: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        template = self.output_template
        if self.custom_title:
            template = _sanitize_title(self.custom_title) + ".%(ext)s"
        opts: dict[str, Any] = {
            "format": self.format_id or quality_selector,
            "outtmpl": str(Path(self.output_dir) / template),
            "progress_hooks": [progress_hook],
            "noplaylist": not self.playlist,
            "quiet": True,
            "no_warnings": True,
        }

        if self.cookies_browser:
            opts["cookiesfrombrowser"] = (self.cookies_browser,)

        if self.sections:
            from yt_dlp.utils import download_range_func

            opts["download_ranges"] = download_range_func(None, [_parse_section(s) for s in self.sections])
            opts["force_keyframes_at_cuts"] = True

        # WAV doesn't support embedded thumbnails
        _THUMBNAIL_FORMATS = {"mp3", "m4a", "aac", "flac", "ogg", "opus"}

        if is_audio:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": ext,
                    "preferredquality": audio_kbps if ext == "mp3" else "0",
                },
            ]
            if not self.strip_metadata:
                opts["postprocessors"].append({"key": "FFmpegMetadata"})
            if self.embed_thumbnail and not self.strip_metadata and ext in _THUMBNAIL_FORMATS:
                opts["postprocessors"].append({"key": "EmbedThumbnail"})
                opts["writethumbnail"] = True
        else:
            opts["merge_output_format"] = ext
            postprocessors: list[dict[str, Any]] = []
            if ext not in ("mp4", "mkv", "webm"):
                postprocessors.append({"key": "FFmpegVideoConvertor", "preferedformat": ext})
            if self.subs:
                opts["writesubtitles"] = True
                opts["subtitleslangs"] = [self.subs_lang]
                opts["subtitlesformat"] = "srt"
                postprocessors.append({"key": "FFmpegEmbedSubtitle"})
            if postprocessors:
                opts["postprocessors"] = postprocessors

        if self.sponsorblock:
            sblock: list[dict[str, Any]] = opts.setdefault("postprocessors", [])
            sblock.extend(
                [
                    {"key": "SponsorBlock", "categories": ["sponsor"]},
                    {"key": "ModifyChapters", "remove_sponsor_segments": ["sponsor"]},
                ]
            )

        return opts

    def download(
        self,
        url: str,
        ext: str,
        is_audio: bool,
        quality_selector: str,
        audio_kbps: str = "320",
        info: dict[str, Any] | None = None,
    ) -> DownloadResult:
        import time

        import yt_dlp

        from .progress import ProgressPrinter

        printer = ProgressPrinter()
        probe_info = info
        final_path: Path | None = None
        title = ""
        is_live = False

        def progress_hook(d: dict[str, Any]) -> None:
            if d["status"] == "downloading":
                if not printer.title:
                    pinfo = d.get("info_dict", {})
                    printer.title = pinfo.get("title", "")
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total and not printer.total_bytes:
                    printer.total_bytes = total
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0
                if total:
                    printer.update(downloaded / total * 85, speed, d.get("eta") or 0)
                else:
                    printer.update_live(downloaded, d.get("fragment_index"), d.get("fragment_count"), speed)
            elif d["status"] == "finished":
                printer.converting()

        ydl_opts = self._build_ydl_opts(ext, is_audio, quality_selector, audio_kbps, progress_hook)

        _network_errors = ("Connection", "timed out", "HTTP Error 5", "Read timed out")

        for attempt in range(1, self.retries + 1):
            try:
                logger.info("Recuperation des infos pour %s", url)
                with Spinner(t("fetching")), yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if probe_info is not None:
                        current_info = probe_info
                        probe_info = None  # ne reutiliser le probe qu'une fois ; les reessais refetchent
                    else:
                        current_info = ydl.extract_info(url, download=False)
                    if current_info is None:
                        return DownloadResult(1)

                    live_status = current_info.get("live_status")
                    if live_status == "is_upcoming":
                        _print_upcoming(current_info)
                        return DownloadResult(0)

                    if live_status == "is_live" and self.live_from_start is not False:
                        # le flag doit etre pose avant l'extraction pour influencer le choix de format
                        ydl.params["live_from_start"] = True
                        current_info = ydl.extract_info(url, download=False)
                        if current_info is None:
                            return DownloadResult(1)

                    is_live = live_status == "is_live"

                    _path_info = dict(current_info)
                    _path_info["ext"] = ext
                    final_path = Path(ydl.prepare_filename(_path_info))
                    title = current_info.get("title", "Video") or "Video"
                    printer.title = str(title)

                    if is_live:
                        print(f"{BOLD}{title}{RESET}  {BOLD}{RED}● LIVE{RESET}")
                        print(c(t("live_recording"), YELLOW))
                    else:
                        duration = int(current_info.get("duration") or 0)
                        dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else ""
                        print(f"{BOLD}{title}{RESET}" + (f"  {c(dur_str, DIM)}" if dur_str else ""))
                    print()

                    info = ydl.process_ie_result(current_info, download=True)

                printer.done()
                assert final_path is not None
                if self.strip_metadata:
                    _strip_file_metadata(final_path)
                success_flash(t("saved", path=self.output_dir))
                from .history import log_download

                log_download(url, str(title), ext, self.output_dir, "ok")
                return DownloadResult(0, final_path, info or {})

            except yt_dlp.utils.DownloadError as e:
                msg = str(e)
                is_network = any(err in msg for err in _network_errors)
                if is_network and attempt < self.retries:
                    printer.done()
                    wait = 2**attempt
                    print(c(t("retry", attempt=attempt, max=self.retries - 1, wait=wait), YELLOW))
                    time.sleep(wait)
                    printer = ProgressPrinter()
                    continue
                printer.done()
                _print_error(msg, url)
                return DownloadResult(1)

            except KeyboardInterrupt:
                printer.done()
                if is_live and final_path is not None:
                    print(f"\n{t('live_finalizing')}")
                    if _remux_live_parts(final_path):
                        success_flash(t("live_finalized", name=final_path.name))
                        from .history import log_download

                        log_download(url, title or "Video", ext, self.output_dir, "ok")
                        return DownloadResult(0, final_path, info or {})
                    print(t("live_partial_kept", path=str(final_path.parent)))
                else:
                    print(f"\n{t('err_interrupted')}")
                return DownloadResult(130)

            except Exception as e:
                printer.done()
                print(f"Erreur : {e}", file=sys.stderr)
                return DownloadResult(1)

        return DownloadResult(1)
