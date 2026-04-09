import os
import sys
import shutil
from pathlib import Path

DEFAULT_OUTPUT = str(Path.home() / "Downloads")


def check_deps():
    missing = []
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        missing.append("yt-dlp  →  pip install yt-dlp")
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg  →  brew install ffmpeg")
    if missing:
        print("❌ Dépendances manquantes :", file=sys.stderr)
        for m in missing:
            print(f"   • {m}", file=sys.stderr)
        sys.exit(1)


class Downloader:
    def __init__(
        self,
        output_dir: str = DEFAULT_OUTPUT,
        playlist: bool = False,
        embed_thumbnail: bool = True,
    ):
        self.output_dir = output_dir
        self.playlist = playlist
        self.embed_thumbnail = embed_thumbnail

    def download(
        self,
        url: str,
        ext: str,
        is_audio: bool,
        quality_selector: str,
        audio_kbps: str = "320",
    ) -> int:
        import yt_dlp
        from .progress import ProgressPrinter

        printer = ProgressPrinter()

        def progress_hook(d):
            if d["status"] == "downloading":
                if not printer.title:
                    info = d.get("info_dict", {})
                    printer.title = info.get("title", "")
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                pct = (downloaded / total * 85) if total > 0 else 0
                speed = d.get("speed") or 0
                eta = d.get("eta") or 0
                printer.update(pct, speed, eta)
            elif d["status"] == "finished":
                printer.converting()

        ydl_opts: dict = {
            "format": quality_selector,
            "outtmpl": os.path.join(self.output_dir, "%(title)s.%(ext)s"),
            "progress_hooks": [progress_hook],
            "noplaylist": not self.playlist,
            "quiet": True,
            "no_warnings": True,
        }

        if is_audio:
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": ext,
                    "preferredquality": audio_kbps if ext == "mp3" else "0",
                },
                {"key": "FFmpegMetadata"},
            ]
            if self.embed_thumbnail:
                ydl_opts["postprocessors"].append({"key": "EmbedThumbnail"})
                ydl_opts["writethumbnail"] = True
        else:
            ydl_opts["merge_output_format"] = ext
            if ext not in ("mp4", "mkv", "webm"):
                ydl_opts["postprocessors"] = [
                    {"key": "FFmpegVideoConvertor", "preferedformat": ext},
                ]

        try:
            print("🔍 Récupération des infos...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Vidéo")
                printer.title = title
                duration = info.get("duration", 0)
                dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else ""
                print(f"📺 {title}" + (f"  ({dur_str})" if dur_str else ""))
                print()
                ydl.download([url])

            printer.done(f"✅  Sauvegardé dans {self.output_dir}/")
            return 0

        except yt_dlp.utils.DownloadError as e:
            printer.done()
            msg = str(e)
            if "Unsupported URL" in msg:
                print(f"❌  Site non supporté par yt-dlp : {url}", file=sys.stderr)
                print("   Lance `vdl --list-sites` pour voir les sites supportés.", file=sys.stderr)
            else:
                # strip the verbose yt-dlp prefix
                clean = msg.replace("ERROR: ", "").strip()
                print(f"❌  {clean}", file=sys.stderr)
            return 1

        except KeyboardInterrupt:
            printer.done()
            print("\n🛑  Annulé.")
            return 130

        except Exception as e:
            printer.done()
            print(f"❌  Erreur inattendue : {e}", file=sys.stderr)
            return 1
