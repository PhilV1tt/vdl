"""Module Apple Music / iTunes : lookup MusicBrainz, écriture tags, import."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from .i18n import t
from .tui import Spinner, success_flash


def _check_deps() -> bool:
    return (
        importlib.util.find_spec("mutagen") is not None
        and importlib.util.find_spec("musicbrainzngs") is not None
    )


def lookup_metadata(title: str, artist: str) -> dict[str, Any]:
    """Cherche les métadonnées sur MusicBrainz. Retourne dict vide si aucun match."""
    try:
        import musicbrainzngs

        musicbrainzngs.set_useragent("vdl", "0.5.0", "https://github.com/PhilV1tt/vdl")
        result = musicbrainzngs.search_recordings(query=title, artist=artist, limit=5)
        recordings = result.get("recording-list", [])
        if not recordings:
            return {}

        rec = recordings[0]
        meta: dict[str, Any] = {}
        meta["title"] = rec.get("title")

        artist_credits = rec.get("artist-credit", [])
        if artist_credits:
            first = artist_credits[0]
            if isinstance(first, dict):
                meta["artist"] = first.get("artist", {}).get("name")

        releases = rec.get("release-list", [])
        if releases:
            rel = releases[0]
            meta["album"] = rel.get("title")
            meta["year"] = (rel.get("date") or "")[:4] or None
            track_list = rel.get("medium-list", [{}])[0].get("track-list", [])
            if track_list:
                meta["track_number"] = track_list[0].get("number")

        return {k: v for k, v in meta.items() if v}
    except Exception:
        return {}


def write_tags(file_path: Path, metadata: dict[str, Any]) -> None:
    """Écrit les tags dans le fichier audio via mutagen."""
    if not metadata:
        return
    try:
        suffix = file_path.suffix.lower().lstrip(".")
        if suffix == "mp3":
            _write_mp3(file_path, metadata)
        elif suffix in ("m4a", "aac", "mp4"):
            _write_m4a(file_path, metadata)
        elif suffix in ("flac", "ogg", "opus"):
            _write_vorbis(file_path, metadata)
    except Exception:
        pass


def _write_mp3(file_path: Path, metadata: dict[str, Any]) -> None:
    from mutagen.id3 import ID3, TALB, TCOM, TCON, TDRC, TIT2, TPE1, TRCK, ID3NoHeaderError

    try:
        tags = ID3(str(file_path))
    except ID3NoHeaderError:
        tags = ID3()

    if "title" in metadata:
        tags["TIT2"] = TIT2(encoding=3, text=str(metadata["title"]))
    if "artist" in metadata:
        tags["TPE1"] = TPE1(encoding=3, text=str(metadata["artist"]))
    if "album" in metadata:
        tags["TALB"] = TALB(encoding=3, text=str(metadata["album"]))
    if "track_number" in metadata:
        tags["TRCK"] = TRCK(encoding=3, text=str(metadata["track_number"]))
    if "year" in metadata:
        tags["TDRC"] = TDRC(encoding=3, text=str(metadata["year"]))
    if "composer" in metadata:
        tags["TCOM"] = TCOM(encoding=3, text=str(metadata["composer"]))
    if "genre" in metadata:
        tags["TCON"] = TCON(encoding=3, text=str(metadata["genre"]))

    tags.save(str(file_path))


def _write_m4a(file_path: Path, metadata: dict[str, Any]) -> None:
    from mutagen.mp4 import MP4

    tags = MP4(str(file_path))
    if "title" in metadata:
        tags["\xa9nam"] = [str(metadata["title"])]
    if "artist" in metadata:
        tags["\xa9ART"] = [str(metadata["artist"])]
    if "album" in metadata:
        tags["\xa9alb"] = [str(metadata["album"])]
    if "year" in metadata:
        tags["\xa9day"] = [str(metadata["year"])]
    if "composer" in metadata:
        tags["\xa9wrt"] = [str(metadata["composer"])]
    if "genre" in metadata:
        tags["\xa9gen"] = [str(metadata["genre"])]
    if "track_number" in metadata:
        import contextlib

        with contextlib.suppress(ValueError, TypeError):
            tags["trkn"] = [(int(metadata["track_number"]), 0)]
    tags.save()


def _write_vorbis(file_path: Path, metadata: dict[str, Any]) -> None:
    from mutagen import File

    audio = File(str(file_path))
    if audio is None:
        return

    _MAP = {
        "title": "title",
        "artist": "artist",
        "album": "album",
        "track_number": "tracknumber",
        "year": "date",
        "composer": "composer",
        "genre": "genre",
    }
    for key, tag in _MAP.items():
        if key in metadata:
            audio[tag] = [str(metadata[key])]
    audio.save()


def import_to_music_app(file_path: Path) -> bool:
    """Importe le fichier dans Apple Music (macOS) ou iTunes (Windows)."""
    if sys.platform == "darwin":
        return _import_macos(file_path)
    if sys.platform == "win32":
        return _import_windows(file_path)
    print(t("music_skip_import"), file=sys.stderr)
    return False


def _import_macos(file_path: Path) -> bool:
    import subprocess

    abs_path = str(file_path.resolve())
    script = f'tell application "Music" to add POSIX file "{abs_path}"'
    try:
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False


def _import_windows(file_path: Path) -> bool:
    try:
        import win32com.client  # type: ignore[import-untyped]

        itunes = win32com.client.Dispatch("iTunes.Application")
        playlist = itunes.LibraryPlaylist
        playlist.AddFile(str(file_path.resolve()))
        return True
    except Exception:
        return False


def music_pipeline(file_path: Path | None, info: dict[str, Any]) -> None:
    """Orchestre lookup MusicBrainz → écriture tags → import Apple Music."""
    if file_path is None or not file_path.exists():
        return

    if not _check_deps():
        print(t("music_missing_deps"), file=sys.stderr)
        print("  pipx inject vdl mutagen musicbrainzngs", file=sys.stderr)
        print("  # ou : pip install 'vdl[music]'", file=sys.stderr)
        return

    title = str(info.get("title", "") or file_path.stem)
    artist = str(info.get("uploader", "") or "")

    print()
    with Spinner(t("music_lookup")):
        metadata = lookup_metadata(title, artist)

    if metadata:
        parts: list[str] = []
        if metadata.get("artist"):
            parts.append(str(metadata["artist"]))
        if metadata.get("album"):
            parts.append(str(metadata["album"]))
        print(t("music_lookup_found", info=" — ".join(parts) if parts else title))
    else:
        print(t("music_lookup_none"))

    write_tags(file_path, metadata)
    if metadata:
        print(t("music_tagged"))

    print()
    with Spinner(t("music_importing")):
        ok = import_to_music_app(file_path)

    if ok:
        success_flash(t("music_imported"))
    elif sys.platform in ("darwin", "win32"):
        print(t("music_import_error"), file=sys.stderr)
