"""Tests du mode interactif (prompt-toolkit piloté par un pipe clavier, probe et Downloader mockés)."""

from unittest.mock import patch

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from vdl.config import VdlConfig
from vdl.downloader import DownloadResult
from vdl.interactive import _convert_flow, _download_flow, normalize_input, run_interactive

VIDEO_INFO = {"title": "Test Video", "duration": 120, "live_status": "not_live"}
LIVE_INFO = {"title": "Live Now", "live_status": "is_live"}
UPCOMING_INFO = {"title": "Soon", "live_status": "is_upcoming", "release_timestamp": 4102444800}
PLAYLIST_INFO = {"title": "My Playlist", "entries": [{"url": "a"}, {"url": "b"}]}
URL = "https://example.com/video"


@pytest.fixture(autouse=True)
def _no_real_prefs_or_config(monkeypatch):
    """Config par défaut, mémoire vide, remember() en no-op : chaque test part d'un état neutre."""
    monkeypatch.setattr("vdl.interactive.load_config", lambda: VdlConfig())
    monkeypatch.setattr("vdl.prefs.recall", dict)
    monkeypatch.setattr("vdl.prefs.remember", lambda *a, **k: None)


def run_flow(keys, info=VIDEO_INFO, exit_code=0, url=URL, **patches):
    """Envoie `keys` à l'écran unique et retourne (code de sortie, mock Downloader)."""
    with (
        create_pipe_input() as keyboard,
        create_app_session(input=keyboard, output=DummyOutput()),
        patch("vdl.interactive.probe", return_value=info),
        patch("vdl.interactive.Downloader") as downloader,
    ):
        downloader.return_value.download.return_value = DownloadResult(exit_code)
        keyboard.send_text(keys)
        rc = _download_flow(url)
    return rc, downloader


class TestNormalizeInput:
    def test_passthrough_http(self):
        assert normalize_input("https://youtu.be/x") == "https://youtu.be/x"

    def test_handle_expands(self):
        assert normalize_input("@QOVESStudio") == "https://www.youtube.com/@QOVESStudio/videos"


class TestDownloadFlowVideo:
    def test_probe_failure_returns_1(self):
        with patch("vdl.interactive.probe", return_value=None):
            assert _download_flow(URL) == 1

    @pytest.mark.parametrize(
        "keys, ext, is_audio, kbps",
        [("\r", "mp4", False, "0"), ("a", "mp3", True, "320"), ("\t\x1b[C\x1b[B\r", "m4a", True, "256")],
    )
    def test_choices_work_without_submenus(self, keys, ext, is_audio, kbps):
        with patch("vdl.interactive.confirm") as confirm, patch("vdl.interactive.select") as select:
            rc, downloader = run_flow(keys)
        assert rc == 0
        args = downloader.return_value.download.call_args.args
        assert args[1:3] == (ext, is_audio)
        assert args[4] == kbps
        confirm.assert_not_called()
        select.assert_not_called()

    def test_direct_video_key(self):
        rc, downloader = run_flow("\tv")
        assert rc == 0
        assert downloader.return_value.download.call_args.args[2] is False

    def test_cancel_downloads_nothing(self):
        rc, downloader = run_flow("\x03")
        assert rc == 0
        downloader.return_value.download.assert_not_called()

    def test_download_failure_returns_nonzero(self):
        rc, _ = run_flow("\r", exit_code=1)
        assert rc == 1


class TestOptionsScreen:
    def test_options_then_back_downloads(self):
        with patch("vdl.interactive.select", side_effect=["back"]):
            rc, downloader = run_flow("o")
        assert rc == 0
        assert downloader.return_value.download.call_args[0][2] is False

    def test_cancel_returns_to_screen_without_download(self):
        with patch("vdl.interactive.select", side_effect=["cancel"]):
            rc, downloader = run_flow("o\x03")
        assert rc == 0
        downloader.return_value.download.assert_not_called()

    def test_custom_title_via_metadata_row(self):
        with (
            patch("vdl.interactive.select", side_effect=["meta", "back"]),
            patch("vdl.interactive.confirm", return_value=False),  # nettoyer les métadonnées ? non
            patch("vdl.interactive.text", return_value="Mon Titre"),
        ):
            rc, downloader = run_flow("o")
        assert rc == 0
        assert downloader.call_args.kwargs["custom_title"] == "Mon Titre"

    def test_section_row_passed_to_downloader(self):
        with (
            patch("vdl.interactive.select", side_effect=["section", "back"]),
            patch("vdl.interactive.text", return_value="00:10-00:20"),
        ):
            rc, downloader = run_flow("o")
        assert rc == 0
        assert downloader.call_args.kwargs["sections"] == ["00:10-00:20"]


class TestPlaylistFlow:
    def test_whole_playlist(self):
        rc, downloader = run_flow("\r", info=PLAYLIST_INFO, url="https://www.youtube.com/playlist?list=PL123")
        assert rc == 0
        assert downloader.call_args.kwargs["playlist"] is True

    def test_video_in_combined_url_is_not_a_playlist(self):
        combined = "https://www.youtube.com/watch?v=abc&list=PL123"
        rc, downloader = run_flow("\r", info=VIDEO_INFO, url=combined)
        assert rc == 0
        assert downloader.call_args.kwargs["playlist"] is False

    def test_cancel(self):
        rc, downloader = run_flow("\x03", info=PLAYLIST_INFO, url="https://www.youtube.com/playlist?list=PL123")
        assert rc == 0
        downloader.return_value.download.assert_not_called()


class TestLiveFlow:
    def test_live_screen_records(self):
        rc, downloader = run_flow("\r", info=LIVE_INFO, url="https://www.youtube.com/watch?v=live123")
        assert rc == 0
        assert downloader.return_value.download.call_args.kwargs["info"] is LIVE_INFO

    def test_upcoming_short_circuits_without_download(self, capsys):
        rc, downloader = run_flow("", info=UPCOMING_INFO, url="https://www.youtube.com/watch?v=soon")
        assert rc == 0
        assert capsys.readouterr().out.strip() != ""
        downloader.return_value.download.assert_not_called()


class TestConvertFlow:
    def test_drop_path_then_choose_format(self, tmp_path):
        src = tmp_path / "my film.mkv"
        src.touch()
        with (
            patch("vdl.interactive.select", return_value="MP3"),
            patch("vdl.convert.run_convert", return_value=0) as convert,
        ):
            _convert_flow(str(src).replace(" ", "\\ "))  # chemin collé depuis le Finder
        convert.assert_called_once_with([str(src), "-f", "mp3"])

    def test_prompts_for_path_when_missing(self, tmp_path):
        src = tmp_path / "film.mkv"
        src.touch()
        with (
            patch("vdl.interactive.text", return_value=f" {src} "),
            patch("vdl.interactive.select", return_value="MP4"),
            patch("vdl.convert.run_convert", return_value=0) as convert,
        ):
            _convert_flow()
        convert.assert_called_once_with([str(src), "-f", "mp4"])

    def test_empty_path_converts_nothing(self):
        with (
            patch("vdl.interactive.text", return_value="  "),
            patch("vdl.convert.run_convert") as convert,
        ):
            _convert_flow()
        convert.assert_not_called()

    def test_missing_file_converts_nothing(self, tmp_path, capsys):
        with patch("vdl.convert.run_convert") as convert:
            _convert_flow(str(tmp_path / "nope.mkv"))
        convert.assert_not_called()
        assert "nope.mkv" in capsys.readouterr().err

    def test_cancel_on_format_converts_nothing(self, tmp_path):
        src = tmp_path / "film.mkv"
        src.touch()
        with (
            patch("vdl.interactive.select", return_value=None),
            patch("vdl.convert.run_convert") as convert,
        ):
            _convert_flow(str(src))
        convert.assert_not_called()


class TestRunInteractive:
    @pytest.mark.parametrize("answer", ["", "   ", None, "/quit"])
    def test_quit_returns(self, answer):
        with patch("vdl.interactive.text", return_value=answer):
            assert run_interactive() is None

    def test_url_starts_download_then_empty_quits(self):
        with (
            patch("vdl.interactive.text", side_effect=[URL, ""]),
            patch("vdl.interactive._download_flow", return_value=0) as flow,
        ):
            run_interactive()
        flow.assert_called_once_with(URL)

    def test_second_link_is_downloaded(self):
        with (
            patch("vdl.interactive.text", side_effect=["https://example.com/1", "https://example.com/2", ""]),
            patch("vdl.interactive._download_flow", return_value=0) as flow,
        ):
            run_interactive()
        assert flow.call_count == 2

    def test_history_command(self):
        with (
            patch("vdl.interactive.text", side_effect=["/history", ""]),
            patch("vdl.interactive._history_flow") as history,
        ):
            run_interactive()
        history.assert_called_once()

    def test_search_command(self):
        with (
            patch("vdl.interactive.text", side_effect=["/search", ""]),
            patch("vdl.interactive._search_flow", return_value=0) as search,
        ):
            run_interactive()
        search.assert_called_once_with(query="")

    def test_convert_command(self):
        with (
            patch("vdl.interactive.text", side_effect=["/convert", ""]),
            patch("vdl.interactive._convert_flow") as convert,
        ):
            run_interactive()
        convert.assert_called_once_with(None)

    def test_local_file_goes_to_convert(self, tmp_path):
        src = tmp_path / "film.mkv"
        src.touch()
        with (
            patch("vdl.interactive.text", side_effect=[str(src), ""]),
            patch("vdl.interactive._convert_flow") as convert,
        ):
            run_interactive()
        convert.assert_called_once_with(str(src))

    def test_unknown_command_is_reported(self, capsys):
        with patch("vdl.interactive.text", side_effect=["/nope", ""]):
            run_interactive()
        assert "Commande inconnue" in capsys.readouterr().err

    def test_text_search_keeps_query(self):
        with (
            patch("vdl.interactive.text", side_effect=["lofi hip hop", ""]),
            patch("vdl.interactive._search_flow", return_value=0) as flow,
        ):
            run_interactive()
        flow.assert_called_once_with(query="lofi hip hop", source="youtube")


class TestTuiModule:
    def test_is_available_true(self):
        from vdl.tui import is_available

        assert is_available() is True

    def test_enable_ansi_no_error(self):
        from vdl.tui import enable_ansi_windows

        enable_ansi_windows()  # ne doit pas lever d'exception
