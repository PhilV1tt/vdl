from __future__ import annotations

import logging
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .tui import BOLD, DIM, GREEN, RESET, YELLOW, c

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = str(Path.home() / "Downloads")


def check_deps() -> None:
    import importlib.util

    missing = []
    if importlib.util.find_spec("yt_dlp") is None:
        missing.append("yt-dlp  →  pip install yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg  →  brew install ffmpeg")
    if missing:
        print("Dependances manquantes :", file=sys.stderr)
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

        if is_audio:
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": ext,
                    "preferredquality": audio_kbps if ext == "mp3" else "0",
                },
                {"key": "FFmpegMetadata"},
            ]
            if self.embed_thumbnail:
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
    ) -> int:
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
                print(c("Recuperation des infos...", DIM))
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get("title", "Video")
                    printer.title = title
                    duration = int(info.get("duration") or 0)
                    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else ""
                    print(f"{BOLD}{title}{RESET}" + (f"  {c(dur_str, DIM)}" if dur_str else ""))
                    print()
                    ydl.download([url])

                printer.done(c(f"Sauvegarde dans {self.output_dir}/", GREEN))
                from .history import log_download

                log_download(url, title, ext, self.output_dir, "ok")
                return 0

            except yt_dlp.utils.DownloadError as e:
                msg = str(e)
                is_network = any(err in msg for err in _network_errors)
                if is_network and attempt < self.retries:
                    printer.done()
                    wait = 2**attempt
                    print(c(f"Erreur reseau. Nouvel essai {attempt}/{self.retries - 1} dans {wait}s...", YELLOW))
                    time.sleep(wait)
                    printer = ProgressPrinter()
                    continue
                printer.done()
                if "Unsupported URL" in msg:
                    print(f"Site non supporte par yt-dlp : {url}", file=sys.stderr)
                    print("  Lance `vdl --list-sites` pour voir les sites supportes.", file=sys.stderr)
                elif "Private video" in msg:
                    print("Video privee. Verifie l'URL ou tes permissions.", file=sys.stderr)
                elif "Video unavailable" in msg:
                    print("Video indisponible (supprimee ou restreinte geographiquement).", file=sys.stderr)
                elif "HTTP Error 429" in msg:
                    print("Trop de requetes (429). Attends quelques minutes avant de reessayer.", file=sys.stderr)
                elif "Unable to extract" in msg:
                    print("Impossible d'extraire. Essaie : yt-dlp -U", file=sys.stderr)
                else:
                    clean = msg.replace("ERROR: ", "").strip()
                    print(clean, file=sys.stderr)
                return 1

            except KeyboardInterrupt:
                printer.done()
                print("\nAnnule.")
                return 130

            except Exception as e:
                printer.done()
                print(f"Erreur : {e}", file=sys.stderr)
                return 1

        return 1
