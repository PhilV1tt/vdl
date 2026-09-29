"""Tests du mode interactif (questionary + probe mockés)."""

from unittest.mock import patch

import pytest

from vdl.config import VdlConfig
from vdl.downloader import DownloadResult
from vdl.interactive import _convert_flow, _download_flow, normalize_input, run_interactive

VIDEO_INFO = {"title": "Test Video", "duration": 120, "live_status": "not_live"}
LIVE_INFO = {"title": "Live Now", "live_status": "is_live"}
UPCOMING_INFO = {"title": "Soon", "live_status": "is_upcoming", "release_timestamp": 4102444800}
PLAYLIST_INFO = {"title": "My Playlist", "entries": [{"url": "a"}, {"url": "b"}]}


@pytest.fixture(autouse=True)
def _no_real_prefs_or_config(monkeypatch):
    """Config par défaut, mémoire vide, remember() en no-op : chaque test part d'un état neutre."""
    monkeypatch.setattr("vdl.interactive.load_config", lambda: VdlConfig())
    monkeypatch.setattr("vdl.prefs.recall", dict)
    monkeypatch.setattr("vdl.prefs.remember", lambda *a, **k: None)


class TestNormalizeInput:
    def test_passthrough_http(self):
        assert normalize_input("https://youtu.be/x") == "https://youtu.be/x"

    def test_handle_expands(self):
        assert normalize_input("@QOVESStudio") == "https://www.youtube.com/@QOVESStudio/videos"


class TestDownloadFlowVideo:
    def test_probe_failure_returns_1(self):
        with patch("vdl.interactive.probe", return_value=None):
            rc = _download_flow("https://example.com/video")
        assert rc == 1

    def test_quick_download_uses_video_defaults(self):
        with (
            patch("vdl.interactive.probe", return_value=VIDEO_INFO),
            patch("vdl.interactive.select", return_value="download"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://example.com/video")
        assert rc == 0
        call_args = mock_dl.return_value.download.call_args[0]
        assert call_args[1] == "mp4"  # ext
        assert call_args[2] is False  # is_audio

    def test_audio_instead(self):
        with (
            patch("vdl.interactive.probe", return_value=VIDEO_INFO),
            patch("vdl.interactive.select", return_value="audio"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://example.com/video")
        assert rc == 0
        call_args = mock_dl.return_value.download.call_args[0]
        assert call_args[1] == "mp3"
        assert call_args[2] is True

    def test_cancel_on_quick_screen(self):
        with (
            patch("vdl.interactive.probe", return_value=VIDEO_INFO),
            patch("vdl.interactive.select", return_value=None),
        ):
            rc = _download_flow("https://example.com/video")
        assert rc == 0

    def test_download_failure_returns_nonzero(self):
        with (
            patch("vdl.interactive.probe", return_value=VIDEO_INFO),
            patch("vdl.interactive.select", return_value="download"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(1)
            rc = _download_flow("https://example.com/video")
        assert rc == 1


class TestOptionsScreen:
    def test_options_then_back_downloads(self):
        with (
            patch("vdl.interactive.probe", return_value=VIDEO_INFO),
            patch("vdl.interactive.select", side_effect=["options", "back"]),
            patch("vdl.interactive.confirm", return_value=False),  # "audio ?" -> non
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://example.com/video")
        assert rc == 0
        assert mock_dl.return_value.download.call_args[0][2] is False

    def test_custom_title_via_metadata_row(self):
        with (
            patch("vdl.interactive.probe", return_value=VIDEO_INFO),
            patch("vdl.interactive.select", side_effect=["options", "meta", "back"]),
            patch("vdl.interactive.confirm", side_effect=[False, False]),  # audio ? non ; nettoyer ? non
            patch("vdl.interactive.text", return_value="Mon Titre"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://example.com/video")
        assert rc == 0
        assert mock_dl.call_args.kwargs["custom_title"] == "Mon Titre"

    def test_section_row_passed_to_downloader(self):
        with (
            patch("vdl.interactive.probe", return_value=VIDEO_INFO),
            patch("vdl.interactive.select", side_effect=["options", "section", "back"]),
            patch("vdl.interactive.confirm", return_value=False),  # audio ?
            patch("vdl.interactive.text", return_value="00:10-00:20"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://example.com/video")
        assert rc == 0
        assert mock_dl.call_args.kwargs["sections"] == ["00:10-00:20"]


class TestPlaylistFlow:
    def test_whole_playlist(self):
        with (
            patch("vdl.interactive.probe", return_value=PLAYLIST_INFO),
            patch("vdl.interactive.select", return_value="all"),
            patch("vdl.interactive.confirm", return_value=False),  # audio ?
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://www.youtube.com/playlist?list=PL123")
        assert rc == 0
        assert mock_dl.call_args.kwargs["playlist"] is True

    def test_single_video_within_combined_url(self):
        combined_url = "https://www.youtube.com/watch?v=abc&list=PL123"
        with (
            patch("vdl.interactive.probe", side_effect=[PLAYLIST_INFO, VIDEO_INFO]),
            patch("vdl.interactive.select", side_effect=["one", "download"]),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow(combined_url)
        assert rc == 0

    def test_back_cancels(self):
        with (
            patch("vdl.interactive.probe", return_value=PLAYLIST_INFO),
            patch("vdl.interactive.select", return_value="back"),
        ):
            rc = _download_flow("https://www.youtube.com/playlist?list=PL123")
        assert rc == 0


class TestLiveFlow:
    def test_live_quick_screen_records_from_start(self):
        with (
            patch("vdl.interactive.probe", return_value=LIVE_INFO),
            patch("vdl.interactive.select", return_value="download"),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = DownloadResult(0)
            rc = _download_flow("https://www.youtube.com/watch?v=live123")
        assert rc == 0
        assert mock_dl.return_value.download.call_args.kwargs["info"] is LIVE_INFO

    def test_upcoming_short_circuits_without_download(self, capsys):
        with patch("vdl.interactive.probe", return_value=UPCOMING_INFO):
            rc = _download_flow("https://www.youtube.com/watch?v=soon")
        assert rc == 0
        assert capsys.readouterr().out.strip() != ""


class TestConvertFlow:
    def test_audio_conversion(self):
        from vdl.i18n import t

        with (
            patch("vdl.interactive.text", return_value=" /tmp/film.mkv "),
            patch("vdl.interactive.select", side_effect=[t("opt_audio"), "MP3", "320 kbps (max)"]),
            patch("vdl.convert.convert_files", return_value=0) as cf,
        ):
            _convert_flow()
        assert cf.call_args[0] == (["/tmp/film.mkv"], "mp3", "320", None)

    def test_video_conversion_picks_a_height_not_a_selector(self):
        from vdl.i18n import t

        with (
            patch("vdl.interactive.text", return_value="/tmp/film.mkv"),
            patch("vdl.interactive.select", side_effect=[t("opt_video"), "MP4", "1080p"]),
            patch("vdl.convert.convert_files", return_value=0) as cf,
        ):
            _convert_flow()
        assert cf.call_args[0] == (["/tmp/film.mkv"], "mp4", "1080", None)

    def test_empty_path_converts_nothing(self):
        with (
            patch("vdl.interactive.text", return_value="  "),
            patch("vdl.convert.convert_files") as cf,
        ):
            _convert_flow()
        cf.assert_not_called()

    def test_cancel_on_format_converts_nothing(self):
        from vdl.i18n import t

        with (
            patch("vdl.interactive.text", return_value="/tmp/film.mkv"),
            patch("vdl.interactive.select", side_effect=[t("opt_audio"), None]),
            patch("vdl.convert.convert_files") as cf,
        ):
            _convert_flow()
        cf.assert_not_called()


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

    def test_download_then_empty_queue_returns_to_menu(self):
        with (
            patch("vdl.interactive.select", side_effect=["download", "quit"]),
            patch("vdl.interactive.text", side_effect=["https://example.com/video", ""]),
            patch("vdl.interactive._download_flow", return_value=0) as mock_flow,
            pytest.raises(SystemExit) as exc,
        ):
            run_interactive()
        assert exc.value.code == 0
        mock_flow.assert_called_once_with("https://example.com/video")

    def test_queue_downloads_a_second_link(self):
        with (
            patch("vdl.interactive.select", side_effect=["download", "quit"]),
            patch("vdl.interactive.text", side_effect=["https://example.com/1", "https://example.com/2", ""]),
            patch("vdl.interactive._download_flow", return_value=0) as mock_flow,
            pytest.raises(SystemExit),
        ):
            run_interactive()
        assert mock_flow.call_count == 2

    def test_history_action(self):
        with (
            patch("vdl.interactive.select", side_effect=["history", "quit"]),
            patch("vdl.interactive._history_flow") as mock_hist,
            pytest.raises(SystemExit),
        ):
            run_interactive()
        mock_hist.assert_called_once()

    def test_search_action(self):
        with (
            patch("vdl.interactive.select", side_effect=["search", "quit"]),
            patch("vdl.interactive._search_flow", return_value=0) as mock_search,
            pytest.raises(SystemExit),
        ):
            run_interactive()
        mock_search.assert_called_once()

    def test_convert_action(self):
        with (
            patch("vdl.interactive.select", side_effect=["convert", "quit"]),
            patch("vdl.interactive._convert_flow") as mock_convert,
            pytest.raises(SystemExit),
        ):
            run_interactive()
        mock_convert.assert_called_once()


class TestTuiModule:
    def test_is_available_true(self):
        from vdl.tui import is_available

        assert is_available() is True

    def test_enable_ansi_no_error(self):
        from vdl.tui import enable_ansi_windows

        enable_ansi_windows()  # ne doit pas lever d'exception
