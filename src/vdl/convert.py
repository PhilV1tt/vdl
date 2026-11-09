"""Conversion de fichiers locaux avec ffmpeg : `vdl convert film.mkv -f mp3`.

Sortie audio : mp3 m4a aac flac wav ogg opus.  Sortie vidéo : mp4 mkv webm avi mov.
Encodage vidéo : h264 + aac, sauf webm en vp9 + opus.
Débit audio (`-q`) : 320 kbps par défaut, ramené au maximum de l'encodeur.  Hauteur vidéo
(`-q`) : inchangée par défaut. Les fichiers existants sont conservés.
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

# ext -> (encodeurs ffmpeg par ordre de preference, debit max accepte en kbps ou None)
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
# encodeurs natifs ffmpeg : marques experimentaux, ils ne prennent pas -b:a
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
    """Encodeurs du binaire ffmpeg installé (`ffmpeg -encoders`)."""
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
        # -ac 2 : l'encodeur vorbis de ffmpeg ne sait pas gerer le mono
        return [*args, "-strict", "-2", "-q:a", "3"] + (["-ac", "2"] if codec == "vorbis" else [])
    return [*args, "-b:a", f"{min(int(kbps), cap) if cap else int(kbps)}k"]


def _video_args(ext: str, quality: str) -> list[str]:
    if ext == "webm":
        # vp9 est 10x plus lent que h264 : on garde -cpu-used 4 pour rester sous quelques minutes
        args = ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-deadline", "good", "-cpu-used", "4"]
        audio_args = _audio_args("opus", "192")
    else:
        args = ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]
        audio_args = _audio_args("m4a", "192")
    if quality in presets.QUALITY_KEYS and quality != "best":
        args += ["-vf", f"scale=-2:{quality}"]  # -2 = largeur paire, garde le ratio
    return [*args, *audio_args]


def build_command(src: Path, dst: Path, ext: str, quality: str) -> list[str]:
    if ext not in presets.ALL_EXTS:
        raise ValueError(f"format inconnu : {ext}")
    is_audio = ext in presets.AUDIO_EXTS
    cmd = ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-i", str(src)]
    # une pochette d'album est un flux vidéo : on ne le garde pas dans un fichier audio
    cmd += ["-vn"] if is_audio else ["-map", "0:v:0", "-map", "0:a:0?"]
    cmd += _audio_args(ext, quality) if is_audio else _video_args(ext, quality)
    return [*cmd, str(dst)]


def _ffmpeg_error(stderr: str, returncode: int) -> str:
    lines = [line for line in stderr.splitlines() if line.strip() and not _PROGRESS_LINE.match(line)]
    return " | ".join(lines[-2:]) or f"ffmpeg a retourne {returncode}"


def convert_one(src: Path, dst: Path, ext: str, quality: str) -> None:
    """Convertit un fichier ; lève RuntimeError avec la fin de la sortie ffmpeg en cas d'échec."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.resolve() == dst.resolve():
        raise RuntimeError(f"La sortie ne peut pas remplacer la source : {src}")
    if dst.exists():
        raise RuntimeError(f"Le fichier de sortie existe déjà : {dst}")
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
    """Convertit chaque fichier, un par un. Retourne 0 si tous ont réussi."""
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
        description="Convertit un fichier video/audio local vers un autre format video/audio (ffmpeg)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Exemples :
  vdl convert film.mkv -f mp3          audio MP3 320 kbps
  vdl convert a.wav -f flac           audio FLAC sans perte
  vdl convert reel.mov -f mp4 -q 1080  video MP4 ramenee a 1080p
  vdl convert *.mp4 -f mp3 -o ~/Music  plusieurs fichiers, dossier de sortie

Formats audio : mp3 m4a aac flac wav ogg opus
Formats video : mp4 mkv webm avi mov
""",
    )
    p.add_argument("files", nargs="+", help="Fichier(s) a convertir")
    p.add_argument("-f", "--format", metavar="FMT", help="Format de sortie (defaut: mp3, ou le dernier choix audio)")
    p.add_argument(
        "-q", "--quality", metavar="Q", help="Video : 2160 1440 1080 720 480 360  |  Audio : 320 256 192 128"
    )
    p.add_argument("-o", "--output", metavar="DOSSIER", help="Dossier de sortie (defaut: a cote de la source)")
    return p


def resolve_format_and_quality(args: argparse.Namespace) -> tuple[str, str]:
    """Résout (format, qualité) et valide les deux. Lève SystemExit si l'un est inconnu."""
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
    """Point d'entree du sous-commande `vdl convert`."""
    import shutil

    args = _make_parser().parse_intermixed_args(argv)
    ext, quality = resolve_format_and_quality(args)
    if not shutil.which("ffmpeg"):
        print("ffmpeg est nécessaire pour convertir. Installation : brew install ffmpeg (macOS).", file=sys.stderr)
        return 1
    try:
        return convert_files(args.files, ext, quality, args.output)
    except KeyboardInterrupt:
        print(f"\n{t('err_interrupted')}")
        return 130
