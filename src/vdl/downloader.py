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
    error: str = ""


class Cancelled(Exception):
    """Raised from a report callback to stop a running download."""


class _SilentLogger:
    """yt-dlp logger for the queue screen: nothing may write to the terminal under it."""

    def debug(self, msg: str) -> None:
        pass

    info = warning = error = debug


DEFAULT_OUTPUT = str(Path.home() / "Downloads")

_ERROR_PATTERNS: list[tuple[str, str]] = [
    ("Unsupported URL", "err_unsupported"),
    ("Private video", "err_private"),
    ("Video unavailable", "err_unavailable"),
    ("HTTP Error 429", "err_429"),
    ("Unable to extract", "err_extract"),
    ("This live event will begin", "err_upcoming"),
]


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def error_message(msg: str, url: str = "") -> str:
    """Turn a yt-dlp error into the user message (one or two lines)."""
    for pattern, key in _ERROR_PATTERNS:
        if pattern in msg:
            if key == "err_unsupported":
                return f"{t(key, url=url)}\n{t('err_unsupported_hint')}"
            return t(key)
    return _ANSI.sub("", msg).replace("ERROR: ", "").strip()


def _print_error(msg: str, url: str = "") -> None:
    print(error_message(msg, url), file=sys.stderr)


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
    """Strip global metadata and chapters from the final file with an ffmpeg remux, no re-encoding."""
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
    """Best effort: remux the fragments of an interrupted live stream (Ctrl-C) into a playable file."""
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
    """Parse '12:00-14:30' or '*90-120' (raw seconds) into (start, end)."""
    raw = spec.startswith("*")
    body = spec[1:] if raw else spec
    start_s, end_s = body.split("-", 1)
    if raw:
        return float(start_s), float(end_s)
    return _parse_timestamp(start_s), _parse_timestamp(end_s)


def upcoming_message(info: dict[str, Any]) -> str:
    ts = info.get("release_timestamp")
    if ts:
        from datetime import datetime

        return t("live_upcoming", when=datetime.fromtimestamp(ts).strftime("%H:%M"))
    return t("err_upcoming")


def list_formats(url: str) -> int:
    """Print the available formats (yt-dlp ids), downloading nothing."""
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
        concurrent_fragments: int = 4,
        use_aria2c: bool = False,
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
        self.concurrent_fragments = concurrent_fragments
        self.use_aria2c = use_aria2c

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
            "concurrent_fragment_downloads": self.concurrent_fragments,
        }

        if self.use_aria2c:
            opts["external_downloader"] = {"default": "aria2c"}
            opts["external_downloader_args"] = {"aria2c": ["-x", "16", "-s", "16", "-k", "1M"]}

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
        report: Callable[[dict[str, Any]], None] | None = None,
    ) -> DownloadResult:
        """Extract `url` once, then download it from the same YoutubeDL instance.

        Without `report`, progress and messages go to the terminal. With `report`, nothing is
        printed: report() receives {"title", "live"} once, then {"pct", "speed", "eta"} or
        {"bytes", "speed"} (live), {"converting": True}, {"retry": n}. It may raise Cancelled.
        """
        import contextlib
        import time

        import yt_dlp

        from .progress import ProgressPrinter

        quiet = report is not None
        printer = ProgressPrinter()
        final_path: Path | None = None
        title = ""
        is_live = False

        def progress_hook(d: dict[str, Any]) -> None:
            speed = d.get("speed") or 0
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                if report is not None:
                    if total:
                        report({"pct": downloaded / total * 100, "speed": speed, "eta": d.get("eta") or 0})
                    else:
                        report({"bytes": downloaded, "speed": speed})
                elif total:
                    printer.update(downloaded / total * 100, speed, d.get("eta") or 0)
                else:
                    printer.update_live(downloaded, d.get("fragment_index"), d.get("fragment_count"), speed)
            elif d["status"] == "finished":
                if report is not None:
                    report({"converting": True})
                else:
                    printer.converting()

        ydl_opts = self._build_ydl_opts(ext, is_audio, quality_selector, audio_kbps, progress_hook)
        if quiet:
            ydl_opts["logger"] = _SilentLogger()

        _network_errors = ("Connection", "timed out", "HTTP Error 5", "Read timed out")

        for attempt in range(1, self.retries + 1):
            try:
                logger.info("Fetching info for %s", url)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # the spinner covers extraction only, so it never overlaps the title line
                    with contextlib.nullcontext() if quiet else Spinner(t("fetching")):
                        current_info = ydl.extract_info(url, download=False)
                        if current_info is None:
                            return DownloadResult(1, error=t("err_extract"))
                        live_status = current_info.get("live_status")
                        if live_status == "is_live" and self.live_from_start is not False:
                            # must be set before extraction to influence the format choice
                            ydl.params["live_from_start"] = True
                            current_info = ydl.extract_info(url, download=False)
                            if current_info is None:
                                return DownloadResult(1, error=t("err_extract"))

                    if live_status == "is_upcoming":
                        message = upcoming_message(current_info)
                        if not quiet:
                            print(message)
                        return DownloadResult(0 if not quiet else 1, error=message if quiet else "")

                    is_live = live_status == "is_live"
                    path_info = dict(current_info)
                    path_info["ext"] = ext
                    final_path = Path(ydl.prepare_filename(path_info))
                    title = str(current_info.get("title") or "Video")
                    printer.title = title

                    if report is not None:
                        report({"title": title, "live": is_live})
                    elif is_live:
                        print(f"{BOLD}{title}{RESET}  {BOLD}{RED}● LIVE{RESET}")
                        print(c(t("live_recording"), YELLOW))
                    else:
                        duration = int(current_info.get("duration") or 0)
                        dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else ""
                        print(f"{BOLD}{title}{RESET}" + (f"  {c(dur_str, DIM)}" if dur_str else ""))

                    info = ydl.process_ie_result(current_info, download=True)

                printer.done()
                assert final_path is not None
                if self.strip_metadata:
                    _strip_file_metadata(final_path)
                if not quiet:
                    success_flash(t("saved_file", path=final_path))
                from .history import log_download

                log_download(url, title, ext, self.output_dir, "ok")
                return DownloadResult(0, final_path, info or {})

            except Cancelled:
                printer.done()
                return DownloadResult(130, error=t("err_interrupted"))

            except yt_dlp.utils.DownloadError as e:
                msg = str(e)
                is_network = any(err in msg for err in _network_errors)
                if is_network and attempt < self.retries:
                    printer.done()
                    wait = 2**attempt
                    if report is not None:
                        report({"retry": attempt})
                    else:
                        print(c(t("retry", attempt=attempt, max=self.retries - 1, wait=wait), YELLOW))
                    time.sleep(wait)
                    printer = ProgressPrinter()
                    continue
                printer.done()
                if not quiet:
                    _print_error(msg, url)
                return DownloadResult(1, error=error_message(msg, url))

            except KeyboardInterrupt:
                printer.done()
                if is_live and final_path is not None:
                    print(f"\n{t('live_finalizing')}")
                    if _remux_live_parts(final_path):
                        success_flash(t("live_finalized", name=final_path.name))
                        from .history import log_download

                        log_download(url, title or "Video", ext, self.output_dir, "ok")
                        return DownloadResult(0, final_path, {})
                    print(t("live_partial_kept", path=str(final_path.parent)))
                else:
                    print(f"\n{t('err_interrupted')}")
                return DownloadResult(130)

            except Exception as e:
                printer.done()
                if not quiet:
                    print(f"Error: {e}", file=sys.stderr)
                return DownloadResult(1, error=str(e))

        return DownloadResult(1)
