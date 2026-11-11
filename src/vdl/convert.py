"""Convert local files with ffmpeg: `vdl convert film.mkv -f mp3`.

Audio output: mp3 m4a aac flac wav ogg opus.  Video output: mp4 mkv webm avi mov.
Video encoding: h264 + aac, except webm which uses vp9 + opus.
Audio bitrate (`-q`): 320 kbps by default, capped at the encoder maximum.  Video height
(`-q`): unchanged by default. Existing files are kept.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import unquote, urlparse

from . import presets
from .i18n import t
from .tui import BOLD, DIM, Spinner, c, success_flash

AUDIO_KBPS: set[str] = {q["value"] for q in presets.AUDIO_QUALITIES}

# ext -> (ffmpeg encoders in order of preference, max accepted bitrate in kbps or None)
_AUDIO_ENCODERS: dict[str, tuple[tuple[str, ...], int | None]] = {
    "mp3": (("libmp3lame",), 320),
    "m4a": (("aac",), None),
    "aac": (("aac",), None),
    "ogg": (("libvorbis", "vorbis"), None),
    "opus": (("libopus", "opus"), 256),  # libopus refuse plus de 256
    "flac": (("flac",), None),
    "wav": (("pcm_s16le",), None),
}
_LOSSLESS = ("flac", "wav")
# native ffmpeg encoders: flagged experimental, they do not accept -b:a
_NATIVE = ("vorbis", "opus")
_PROGRESS_LINE = re.compile(r"^(size|frame)=")
_ENCODER_FLAGS = re.compile(r"^[VAS][A-Z.]{5}$")


def local_path(raw: str) -> Path:
    """Accept a quoted or shell-escaped path pasted from a file manager."""
    raw = raw.strip()
    if Path(raw).expanduser().is_file():
        return Path(raw).expanduser()
    if sys.platform != "win32":
        try:
            parts = shlex.split(raw)
        except ValueError:
            parts = []
        if len(parts) == 1:
            raw = parts[0]
    else:
        raw = raw.strip('"')
    if raw.startswith("file://"):
        raw = unquote(urlparse(raw).path)
    return Path(raw).expanduser()


def is_local_target(raw: str) -> bool:
    if raw.startswith(("http://", "https://", "@")):
        return False
    path = local_path(raw)
    return (
        path.is_file()
        or raw.startswith(("/", "./", "../", "~/", "file://"))
        or (path.suffix.lower().lstrip(".") in presets.ALL_EXTS | {"m4v", "m4b", "aiff", "aif", "wma", "wmv", "ts"})
    )


@lru_cache(maxsize=1)
def available_encoders() -> frozenset[str]:
    """Encoders of the installed ffmpeg binary (`ffmpeg -encoders`)."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    return frozenset(
        fields[1]
        for fields in (line.split() for line in out.splitlines())
        if len(fields) > 1 and _ENCODER_FLAGS.match(fields[0])
    )


def _pick_encoder(candidates: tuple[str, ...]) -> str:
    available = available_encoders()
    return next((c for c in candidates if c in available), candidates[0])


def _audio_args(ext: str, kbps: str) -> list[str]:
    candidates, cap = _AUDIO_ENCODERS[ext]
    if ext in _LOSSLESS:
        return ["-c:a", candidates[0]]
    codec = _pick_encoder(candidates)
    args = ["-c:a", codec]
    if codec in _NATIVE:
        # -ac 2: ffmpeg's vorbis encoder cannot handle mono
        return [*args, "-strict", "-2", "-q:a", "3"] + (["-ac", "2"] if codec == "vorbis" else [])
    return [*args, "-b:a", f"{min(int(kbps), cap) if cap else int(kbps)}k"]


def _video_args(ext: str, quality: str) -> list[str]:
    if ext == "webm":
        # vp9 is 10x slower than h264: keep -cpu-used 4 to stay within a few minutes
        args = ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-deadline", "good", "-cpu-used", "4"]
        audio_args = _audio_args("opus", "192")
    else:
        args = ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]
        audio_args = _audio_args("m4a", "192")
    if quality in presets.QUALITY_KEYS and quality != "best":
        args += ["-vf", f"scale=-2:{quality}"]  # -2 = even width, keeps the aspect ratio
    return [*args, *audio_args]


def build_command(src: Path, dst: Path, ext: str, quality: str) -> list[str]:
    if ext not in presets.ALL_EXTS:
        raise ValueError(f"format inconnu : {ext}")
    is_audio = ext in presets.AUDIO_EXTS
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-i", str(src)]
    # cover art is a video stream: do not keep it in an audio file
    cmd += ["-vn"] if is_audio else ["-map", "0:v:0", "-map", "0:a:0?"]
    cmd += _audio_args(ext, quality) if is_audio else _video_args(ext, quality)
    return [*cmd, str(dst)]


def _ffmpeg_error(stderr: str, returncode: int) -> str:
    lines = [line for line in stderr.splitlines() if line.strip() and not _PROGRESS_LINE.match(line)]
    return " | ".join(lines[-2:]) or f"ffmpeg returned {returncode}"


def convert_one(src: Path, dst: Path, ext: str, quality: str) -> None:
    """Convert one file; raise RuntimeError with the end of ffmpeg's output on failure."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        raise RuntimeError(f"The output cannot replace the source : {src}")
    if dst.exists():
        raise RuntimeError(f"The output file already exists : {dst}")
    with TemporaryDirectory(prefix=".vdl-", dir=dst.parent) as folder:
        partial = Path(folder) / dst.name
        done = subprocess.run(build_command(src, partial, ext, quality), capture_output=True, text=True)
        if done.returncode != 0 or not partial.is_file():
            raise RuntimeError(_ffmpeg_error(done.stderr, done.returncode))
        partial.replace(dst)


def output_path(src: Path, ext: str, output_dir: str | None) -> Path:
    folder = Path(output_dir).expanduser() if output_dir else src.parent
    dst = folder / f"{src.stem}.{ext}"
    index = 1
    while dst.exists() or dst.resolve() == src.resolve():
        dst = folder / f"{src.stem} ({index}).{ext}"
        index += 1
    return dst


def convert_files(files: list[str], ext: str, quality: str, output_dir: str | None) -> int:
    """Convert each file in turn. Return 0 if all succeeded."""
    ok = fail = 0
    for raw in files:
        src = local_path(raw)
        if not src.is_file():
            print(t("err_no_file", name=raw), file=sys.stderr)
            fail += 1
            continue
        dst = output_path(src, ext, output_dir)
        print(f"{c(src.name, BOLD)}  ->  {dst.name}  {c(f'[{ext.upper()} · {quality}]', DIM)}", flush=True)
        with Spinner(t("converting")):
            try:
                convert_one(src, dst, ext, quality)
            except (RuntimeError, OSError) as e:
                print(t("err_convert", msg=e), file=sys.stderr)
                fail += 1
                continue
        success_flash(f"{dst}  ({dst.stat().st_size / 1e6:.1f} Mo)")
        ok += 1
    if len(files) > 1:
        print(f"\n{ok} reussi(s), {fail} echoue(s)")
    return 0 if fail == 0 else 1


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vdl convert",
        description="Convert a local video/audio file to another video/audio format (ffmpeg)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  vdl convert film.mkv -f mp3          MP3 audio, 320 kbps
  vdl convert a.wav -f flac           lossless FLAC audio
  vdl convert reel.mov -f mp4 -q 1080  MP4 video scaled to 1080p
  vdl convert *.mp4 -f mp3 -o ~/Music  several files, output folder

Audio formats: mp3 m4a aac flac wav ogg opus
Video formats: mp4 mkv webm avi mov
""",
    )
    p.add_argument("files", nargs="+", help="File(s) to convert")
    p.add_argument("-f", "--format", metavar="FMT", help="Output format (default: mp3, or the last audio choice)")
    p.add_argument("-q", "--quality", metavar="Q", help="Video: 2160 1440 1080 720 480 360  |  Audio : 320 256 192 128")
    p.add_argument("-o", "--output", metavar="DIR", help="Output folder (default: next to the source)")
    return p


def resolve_format_and_quality(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve (format, quality) and validate both. Raise SystemExit if either is unknown."""
    from .config import load_config
    from .prefs import recall

    cfg = load_config()
    ext = (args.format or recall().get("audio_format") or cfg.default_format or "mp3").lower().lstrip(".")
    if ext not in presets.ALL_EXTS:
        print(t("err_format", fmt=ext, formats=", ".join(sorted(presets.ALL_EXTS))), file=sys.stderr)
        raise SystemExit(1)

    is_audio = ext in presets.AUDIO_EXTS
    quality = args.quality or ("320" if is_audio else "best")
    valid = AUDIO_KBPS if is_audio else presets.QUALITY_KEYS
    if quality not in valid:
        print(t("err_quality", q=quality, values=", ".join(valid)), file=sys.stderr)
        raise SystemExit(1)
    return ext, quality


def run_convert(argv: list[str]) -> int:
    """Entry point of the `vdl convert` subcommand."""
    import shutil

    args = _make_parser().parse_intermixed_args(argv)
    ext, quality = resolve_format_and_quality(args)
    if not shutil.which("ffmpeg"):
        print("ffmpeg is required to convert. Install it with: brew install ffmpeg (macOS).", file=sys.stderr)
        return 1
    try:
        return convert_files(args.files, ext, quality, args.output)
    except KeyboardInterrupt:
        print(f"\n{t('err_interrupted')}")
        return 130
