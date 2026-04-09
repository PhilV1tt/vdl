from __future__ import annotations

import logging
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .i18n import t
from .tui import BOLD, DIM, RESET, YELLOW, Spinner, c, success_flash

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
    ) -> None:
        self.output_dir = output_dir
        self.playlist = playlist
        self.embed_thumbnail = embed_thumbnail
        self.sponsorblock = sponsorblock
        self.subs = subs
        self.subs_lang = subs_lang
        self.output_template = output_template
        self.retries = retries

    def _build_ydl_opts(
        self,
        ext: str,
        is_audio: bool,
        quality_selector: str,
        audio_kbps: str,
        progress_hook: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "format": quality_selector,
            "outtmpl": str(Path(self.output_dir) / self.output_template),
            "progress_hooks": [progress_hook],
            "noplaylist": not self.playlist,
            "quiet": True,
            "no_warnings": True,
        }

        # WAV doesn't support embedded thumbnails
        _THUMBNAIL_FORMATS = {"mp3", "m4a", "aac", "flac", "ogg", "opus"}

        if is_audio:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": ext,
                    "preferredquality": audio_kbps if ext == "mp3" else "0",
                },
                {"key": "FFmpegMetadata"},
            ]
            if self.embed_thumbnail and ext in _THUMBNAIL_FORMATS:
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
    ) -> DownloadResult:
        import time

        import yt_dlp

        from .progress import ProgressPrinter

        printer = ProgressPrinter()

        def progress_hook(d: dict[str, Any]) -> None:
            if d["status"] == "downloading":
                if not printer.title:
                    info = d.get("info_dict", {})
                    printer.title = info.get("title", "")
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                if total and not printer.total_bytes:
                    printer.total_bytes = total
                downloaded = d.get("downloaded_bytes", 0)
                pct = (downloaded / total * 85) if total > 0 else 0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0
                printer.update(pct, speed, eta)
            elif d["status"] == "finished":
                printer.converting()

        ydl_opts = self._build_ydl_opts(ext, is_audio, quality_selector, audio_kbps, progress_hook)

        _network_errors = ("Connection", "timed out", "HTTP Error 5", "Read timed out")

        for attempt in range(1, self.retries + 1):
            try:
                logger.info("Recuperation des infos pour %s", url)
                with Spinner(t("fetching")), yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info is None:
                        return DownloadResult(1)
                    _path_info = dict(info)
                    _path_info["ext"] = ext
                    final_path = Path(ydl.prepare_filename(_path_info))
                    title = info.get("title", "Video") or "Video"
                    printer.title = str(title)
                    duration = int(info.get("duration") or 0)
                    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else ""
                    print(f"{BOLD}{title}{RESET}" + (f"  {c(dur_str, DIM)}" if dur_str else ""))
                    print()
                    ydl.download([url])

                printer.done()
                success_flash(t("saved", path=self.output_dir))
                from .history import log_download

                log_download(url, str(title), ext, self.output_dir, "ok")
                return DownloadResult(0, final_path, info)

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
                print(f"\n{t('err_interrupted')}")
                return DownloadResult(130)

            except Exception as e:
                printer.done()
                print(f"Erreur : {e}", file=sys.stderr)
                return DownloadResult(1)

        return DownloadResult(1)
