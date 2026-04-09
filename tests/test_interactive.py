"""Tests du mode interactif (questionary mocké)."""

from unittest.mock import patch

import pytest

from vdl import presets
from vdl.interactive import _download_flow, run_interactive


class TestDownloadFlow:
    """Tests pour _download_flow avec questionary mocké."""

    def _mock_tui(self, answers: list[object]) -> object:
        """Crée un mock qui retourne les réponses dans l'ordre."""
        it = iter(answers)

        def _next(*_a: object, **_kw: object) -> object:
            try:
                return next(it)
            except StopIteration:
                return None

        return _next

    def test_audio_flow_calls_downloader(self):
        ext = presets.AUDIO_FORMATS[0]["ext"]  # mp3
        kbps = presets.AUDIO_QUALITIES[0]["value"]  # 320
        # Réponses : type=audio, fmt=mp3, qualité=320, subs skipped, output par défaut, confirm=True
        with (
            patch("vdl.interactive.select", side_effect=["audio", ext, kbps]),
            patch("vdl.interactive.text", return_value=""),
            patch("vdl.interactive.confirm", side_effect=[True]),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = 0
            rc = _download_flow("https://example.com/audio")
        assert rc == 0
        mock_dl.return_value.download.assert_called_once()
        call_args = mock_dl.return_value.download.call_args[0]
        assert call_args[2] is True  # is_audio

    def test_video_flow_calls_downloader(self):
        ext = presets.VIDEO_FORMATS[0]["ext"]  # mp4
        quality = presets.VIDEO_QUALITIES[0]["value"]
        # type=video, fmt, quality, subs=False, sponsorblock=False, output, confirm
        with (
            patch("vdl.interactive.select", side_effect=["video", ext, quality]),
            patch("vdl.interactive.text", return_value=""),
            patch("vdl.interactive.confirm", side_effect=[False, False, True]),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = 0
            rc = _download_flow("https://example.com/video")
        assert rc == 0
        call_args = mock_dl.return_value.download.call_args[0]
        assert call_args[2] is False  # is_audio

    def test_cancel_on_type_selection(self):
        with patch("vdl.interactive.select", return_value=None):
            rc = _download_flow("https://example.com/video")
        assert rc == 0

    def test_cancel_on_confirmation(self):
        ext = presets.VIDEO_FORMATS[0]["ext"]
        quality = presets.VIDEO_QUALITIES[0]["value"]
        with (
            patch("vdl.interactive.select", side_effect=["video", ext, quality]),
            patch("vdl.interactive.text", return_value=""),
            patch("vdl.interactive.confirm", side_effect=[False, False, False]),
        ):
            rc = _download_flow("https://example.com")
        assert rc == 0

    def test_subs_enabled(self):
        ext = presets.VIDEO_FORMATS[0]["ext"]
        quality = presets.VIDEO_QUALITIES[0]["value"]
        with (
            patch("vdl.interactive.select", side_effect=["video", ext, quality]),
            patch("vdl.interactive.text", side_effect=["fr", ""]),
            patch("vdl.interactive.confirm", side_effect=[True, False, True]),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = 0
            _download_flow("https://example.com/video")
        dl_kwargs = mock_dl.call_args[1]
        assert dl_kwargs["subs"] is True
        assert dl_kwargs["subs_lang"] == "fr"

    def test_sponsorblock_enabled(self):
        ext = presets.VIDEO_FORMATS[0]["ext"]
        quality = presets.VIDEO_QUALITIES[0]["value"]
        with (
            patch("vdl.interactive.select", side_effect=["video", ext, quality]),
            patch("vdl.interactive.text", return_value=""),
            patch("vdl.interactive.confirm", side_effect=[False, True, True]),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = 0
            _download_flow("https://example.com/video")
        dl_kwargs = mock_dl.call_args[1]
        assert dl_kwargs["sponsorblock"] is True


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
        # Première iteration : download avec URL vide -> loop
        # Deuxième : quit
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
        calls = []
        with (
            patch("vdl.interactive.select", side_effect=["history", "quit"]),
            patch("vdl.interactive._history_flow", side_effect=lambda: calls.append(1)) as mock_hist,
            pytest.raises(SystemExit),
        ):
            run_interactive()
        mock_hist.assert_called_once()

    def test_download_action_with_valid_url(self):
        url = "https://example.com/video"
        ext = presets.VIDEO_FORMATS[0]["ext"]
        quality = presets.VIDEO_QUALITIES[0]["value"]
        # run_interactive → download → _download_flow → sys.exit(rc)
        with (
            patch("vdl.interactive.select", side_effect=["download", "video", ext, quality]),
            patch("vdl.interactive.text", side_effect=[url, ""]),
            patch("vdl.interactive.confirm", side_effect=[False, False, True]),
            patch("vdl.interactive.Downloader") as mock_dl,
        ):
            mock_dl.return_value.download.return_value = 0
            with pytest.raises(SystemExit) as exc:
                run_interactive()
        assert exc.value.code == 0


class TestTuiModule:
    def test_is_available_true(self):
        from vdl.tui import is_available

        assert is_available() is True  # questionary est installé

    def test_enable_ansi_no_error(self):
        from vdl.tui import enable_ansi_windows

        enable_ansi_windows()  # ne doit pas lever d'exception
