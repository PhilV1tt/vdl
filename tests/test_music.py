"""Tests for src/vdl/music.py."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vdl.music import import_to_music_app, lookup_metadata, music_pipeline, write_tags

# ── lookup_metadata ────────────────────────────────────────────────────────


def _fake_mb_result() -> dict:
    return {
        "recording-list": [
            {
                "title": "Bohemian Rhapsody",
                "artist-credit": [{"artist": {"name": "Queen"}}],
                "release-list": [
                    {
                        "title": "A Night at the Opera",
                        "date": "1975-11-21",
                        "medium-list": [{"track-list": [{"number": "11"}]}],
                    }
                ],
            }
        ]
    }


class TestLookupMetadata:
    def _mock_mb(self, return_value: dict | None = None, side_effect: Exception | None = None) -> MagicMock:
        mock = MagicMock()
        if side_effect:
            mock.search_recordings.side_effect = side_effect
        else:
            mock.search_recordings.return_value = return_value or _fake_mb_result()
        return mock

    def test_lookup_found(self):
        mock_mb = self._mock_mb()
        with patch.dict(sys.modules, {"musicbrainzngs": mock_mb}):
            meta = lookup_metadata("Bohemian Rhapsody", "Queen")
        assert meta["title"] == "Bohemian Rhapsody"
        assert meta["artist"] == "Queen"
        assert meta["album"] == "A Night at the Opera"
        assert meta["year"] == "1975"
        assert meta["track_number"] == "11"

    def test_lookup_no_match(self):
        mock_mb = self._mock_mb(return_value={"recording-list": []})
        with patch.dict(sys.modules, {"musicbrainzngs": mock_mb}):
            meta = lookup_metadata("unknown", "unknown")
        assert meta == {}

    def test_lookup_exception_returns_empty(self):
        mock_mb = self._mock_mb(side_effect=Exception("network error"))
        with patch.dict(sys.modules, {"musicbrainzngs": mock_mb}):
            meta = lookup_metadata("some song", "some artist")
        assert meta == {}

    def test_lookup_no_date_skips_year(self):
        result = _fake_mb_result()
        result["recording-list"][0]["release-list"][0]["date"] = ""
        mock_mb = self._mock_mb(return_value=result)
        with patch.dict(sys.modules, {"musicbrainzngs": mock_mb}):
            meta = lookup_metadata("Bohemian Rhapsody", "Queen")
        assert "year" not in meta


# ── write_tags ─────────────────────────────────────────────────────────────


class TestWriteTags:
    def test_write_tags_empty_does_nothing(self, tmp_path: Path):
        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"")
        write_tags(mp3, {})  # should not raise

    def test_write_tags_mp3(self, tmp_path: Path):
        pytest.importorskip("mutagen", reason="mutagen not installed")
        from mutagen.id3 import ID3

        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"")
        write_tags(mp3, {"title": "Test Song", "artist": "Test Artist", "album": "Test Album"})
        tags = ID3(str(mp3))
        assert str(tags["TIT2"]) == "Test Song"
        assert str(tags["TPE1"]) == "Test Artist"
        assert str(tags["TALB"]) == "Test Album"

    def test_write_tags_mp3_all_fields(self, tmp_path: Path):
        pytest.importorskip("mutagen", reason="mutagen not installed")
        from mutagen.id3 import ID3

        mp3 = tmp_path / "test.mp3"
        mp3.write_bytes(b"")
        write_tags(
            mp3,
            {
                "title": "Song",
                "artist": "Artist",
                "album": "Album",
                "track_number": "3",
                "year": "2020",
                "genre": "Rock",
                "composer": "Composer",
            },
        )
        tags = ID3(str(mp3))
        assert str(tags["TRCK"]) == "3"
        assert str(tags["TDRC"]) == "2020"
        assert str(tags["TCON"]) == "Rock"
        assert str(tags["TCOM"]) == "Composer"

    def test_write_tags_unknown_ext_no_crash(self, tmp_path: Path):
        f = tmp_path / "test.xyz"
        f.write_bytes(b"")
        write_tags(f, {"title": "Test"})  # should not raise


# ── import_to_music_app ────────────────────────────────────────────────────


class TestImportToMusicApp:
    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_import_macos_success(self, tmp_path: Path):
        f = tmp_path / "song.mp3"
        f.write_bytes(b"")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            assert import_to_music_app(f) is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "osascript"
        assert str(f.resolve()) in cmd[2]

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
    def test_import_macos_failure(self, tmp_path: Path):
        f = tmp_path / "song.mp3"
        f.write_bytes(b"")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            assert import_to_music_app(f) is False

    @pytest.mark.skipif(sys.platform != "linux", reason="non-apple platform only")
    def test_import_unsupported_platform(self, tmp_path: Path, capsys):
        f = tmp_path / "song.mp3"
        f.write_bytes(b"")
        result = import_to_music_app(f)
        assert result is False
        captured = capsys.readouterr()
        assert captured.err  # should print a skip message


# ── music_pipeline ─────────────────────────────────────────────────────────


class TestMusicPipeline:
    def test_pipeline_none_path(self):
        music_pipeline(None, {})  # should return immediately without error

    def test_pipeline_missing_file(self, tmp_path: Path):
        f = tmp_path / "nonexistent.mp3"
        music_pipeline(f, {})  # should return immediately without error

    def test_pipeline_missing_deps(self, tmp_path: Path):
        f = tmp_path / "song.mp3"
        f.write_bytes(b"")
        with patch("vdl.music._auto_install_deps", return_value=False):
            music_pipeline(f, {})  # should return without calling lookup

    def test_pipeline_success(self, tmp_path: Path):
        f = tmp_path / "song.mp3"
        f.write_bytes(b"")
        info = {"title": "Bohemian Rhapsody", "uploader": "Queen"}
        mb_meta = {"title": "Bohemian Rhapsody", "artist": "Queen"}
        with (
            patch("vdl.music._auto_install_deps", return_value=True),
            patch("vdl.music.lookup_metadata", return_value=mb_meta) as mock_lookup,
            patch("vdl.music.write_tags") as mock_tags,
            patch("vdl.music.import_to_music_app", return_value=True) as mock_import,
        ):
            music_pipeline(f, info)

        mock_lookup.assert_called_once_with("Bohemian Rhapsody", "Queen")
        mock_tags.assert_called_once_with(f, mb_meta)
        mock_import.assert_called_once_with(f)

    def test_pipeline_no_metadata(self, tmp_path: Path, capsys):
        f = tmp_path / "song.mp3"
        f.write_bytes(b"")
        with (
            patch("vdl.music._auto_install_deps", return_value=True),
            patch("vdl.music.lookup_metadata", return_value={}),
            patch("vdl.music.write_tags"),
            patch("vdl.music.import_to_music_app", return_value=False),
        ):
            music_pipeline(f, {"title": "Song", "uploader": "Artist"})
        out = capsys.readouterr().out
        assert "Aucune" in out or "No metadata" in out
