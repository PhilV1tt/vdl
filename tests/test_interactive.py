"""Tests du mode interactif (questionary mocké)."""

from unittest.mock import patch

import pytest

from vdl.downloader import DownloadResult
from vdl.interactive import _download_flow, run_interactive


class TestDownloadFlow:
    """Tests pour _download_flow avec questionary mocké."""

    def test_audio_downloads_mp3(self):
        with (
            patch("vdl.interactive.select", return_value="audio"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://example.com/audio")
        assert rc == 0
        call_args = mock_dl.return_value.download.call_args[0]
        assert call_args[1] == "mp3"  # ext
        assert call_args[2] is True  # is_audio

    def test_video_downloads_mp4(self):
        with (
            patch("vdl.interactive.select", return_value="video"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://example.com/video")
        assert rc == 0
        call_args = mock_dl.return_value.download.call_args[0]
        assert call_args[1] == "mp4"  # ext
        assert call_args[2] is False  # is_audio

    def test_cancel_on_type_selection(self):
        with patch("vdl.interactive.select", return_value=None):
            rc = _download_flow("https://example.com/video")
        assert rc == 0

    def test_download_failure_returns_nonzero(self):
        with (
            patch("vdl.interactive.select", return_value="video"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(1)
            rc = _download_flow("https://example.com/video")
        assert rc == 1

    def test_audio_confirms_apple_music_on_macos(self, tmp_path):
        import sys

        if sys.platform != "darwin":
            return
        f = tmp_path / "song.mp3"
        f.write_bytes(b"")
        with (
            patch("vdl.interactive.select", return_value="audio"),
            patch("vdl.interactive.confirm", return_value=True),
            patch("vdl.interactive.Downloader") as mock_dl,
            patch("vdl.music.music_pipeline") as mock_pipeline,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0, f, {"title": "Song"})
            rc = _download_flow("https://example.com/song")
        assert rc == 0
        mock_pipeline.assert_called_once()


class TestRunInteractive:
    def test_quit_action_exits_0(self):
        with patch("vdl.interactive.select", return_value="quit"), pytest.raises(SystemExit) as exc:
            run_interactive()
        assert exc.value.code == 0

    def test_none_action_exits_0(self):
        with patch("vdl.interactive.select", return_value=None), pytest.raises(SystemExit) as exc:
            run_interactive()
        assert exc.value.code == 0

    def test_empty_url_loops_back(self):
        with (
            patch("vdl.interactive.select", side_effect=["download", "quit"]),
            patch("vdl.interactive.text", return_value=""),
            pytest.raises(SystemExit) as exc,
        ):
            run_interactive()
        assert exc.value.code == 0

    def test_invalid_url_loops_back(self):
        with (
            patch("vdl.interactive.select", side_effect=["download", "quit"]),
            patch("vdl.interactive.text", return_value="not-a-url"),
            pytest.raises(SystemExit) as exc,
        ):
            run_interactive()
        assert exc.value.code == 0

    def test_history_action(self):
        with (
            patch("vdl.interactive.select", side_effect=["history", "quit"]),
            patch("vdl.interactive._history_flow") as mock_hist,
            pytest.raises(SystemExit),
        ):
            run_interactive()
        mock_hist.assert_called_once()

    def test_download_then_returns_to_menu(self):
        """Après un téléchargement, on revient au menu."""
        url = "https://example.com/video"
        with (
            patch("vdl.interactive.select", side_effect=["download", "video", "quit"]),
            patch("vdl.interactive.text", return_value=url),
            patch("vdl.interactive.Downloader") as mock_dl,
            pytest.raises(SystemExit) as exc,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            run_interactive()
        assert exc.value.code == 0

    def test_search_action(self):
        with (
            patch("vdl.interactive.select", side_effect=["search", "quit"]),
            patch("vdl.interactive._search_flow", return_value=0) as mock_search,
            pytest.raises(SystemExit),
        ):
            run_interactive()
        mock_search.assert_called_once()


class TestTuiModule:
    def test_is_available_true(self):
        from vdl.tui import is_available

        assert is_available() is True

    def test_enable_ansi_no_error(self):
        from vdl.tui import enable_ansi_windows

        enable_ansi_windows()  # ne doit pas lever d'exception
