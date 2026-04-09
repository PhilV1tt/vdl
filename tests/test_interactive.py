from unittest.mock import patch

import pytest

from vdl import presets
from vdl.interactive import _pick, run_interactive


class TestPick:
    def _items(self):
        return [{"label": "MP3"}, {"label": "WAV"}, {"label": "FLAC"}]

    def test_default_selection(self):
        with patch("builtins.input", return_value=""):
            idx = _pick(self._items(), "label", default=1)
        assert idx == 0  # default=1 → index 0

    def test_valid_numeric_input(self):
        with patch("builtins.input", return_value="2"):
            idx = _pick(self._items(), "label", default=1)
        assert idx == 1

    def test_out_of_range_falls_back_to_default(self):
        with patch("builtins.input", return_value="99"):
            idx = _pick(self._items(), "label", default=1)
        assert idx == 0

    def test_non_numeric_falls_back_to_default(self):
        with patch("builtins.input", return_value="abc"):
            idx = _pick(self._items(), "label", default=1)
        assert idx == 0

    def test_first_item_default(self):
        with patch("builtins.input", return_value="1"):
            idx = _pick(self._items(), "label", default=1)
        assert idx == 0

    def test_last_item(self):
        with patch("builtins.input", return_value="3"):
            idx = _pick(self._items(), "label", default=1)
        assert idx == 2

    def test_zero_input_falls_back(self):
        with patch("builtins.input", return_value="0"):
            idx = _pick(self._items(), "label", default=1)
        assert idx == 0


class TestRunInteractive:
    def _inputs(self, *values):
        return iter(values)

    def test_empty_url_exits_1(self):
        with patch("builtins.input", side_effect=[""]), pytest.raises(SystemExit) as exc:
            run_interactive()
        assert exc.value.code == 1

    def test_invalid_url_exits_1(self):
        with patch("builtins.input", side_effect=["not-a-url"]), pytest.raises(SystemExit) as exc:
            run_interactive()
        assert exc.value.code == 1

    def test_keyboard_interrupt_on_url_exits_0(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt), pytest.raises(SystemExit) as exc:
            run_interactive()
        assert exc.value.code == 0

    def test_eof_on_url_exits_0(self):
        with patch("builtins.input", side_effect=EOFError), pytest.raises(SystemExit) as exc:
            run_interactive()
        assert exc.value.code == 0

    def test_cancel_at_confirmation_exits_0(self):
        url = "https://example.com/video"
        # url, type=v, format choice, quality choice, subs=N, output, confirm=n
        inputs = [url, "v", "1", "1", "N", "", "n"]
        with patch("builtins.input", side_effect=inputs), pytest.raises(SystemExit) as exc:
            run_interactive()
        assert exc.value.code == 0

    def test_video_download_calls_downloader(self):
        url = "https://example.com/video"
        inputs = [url, "v", "1", "1", "N", "", "O"]
        with (
            patch("builtins.input", side_effect=inputs),
            patch("vdl.interactive.Downloader") as mock_dl_cls,
        ):
            mock_dl_cls.return_value.download.return_value = 0
            with pytest.raises(SystemExit) as exc:
                run_interactive()
        assert exc.value.code == 0
        mock_dl_cls.return_value.download.assert_called_once()
        call_args = mock_dl_cls.return_value.download.call_args[0]
        assert call_args[0] == url
        assert call_args[2] is False  # is_audio = False

    def test_audio_download_calls_downloader(self):
        url = "https://example.com/audio"
        # url, type=a, format choice=1 (mp3), quality=1, output=default, confirm
        inputs = [url, "a", "1", "1", "", "O"]
        with (
            patch("builtins.input", side_effect=inputs),
            patch("vdl.interactive.Downloader") as mock_dl_cls,
        ):
            mock_dl_cls.return_value.download.return_value = 0
            with pytest.raises(SystemExit) as exc:
                run_interactive()
        assert exc.value.code == 0
        call_args = mock_dl_cls.return_value.download.call_args[0]
        assert call_args[2] is True  # is_audio = True
        assert call_args[1] == presets.AUDIO_FORMATS[0]["ext"]

    def test_subs_prompt_appears_for_video(self):
        url = "https://example.com/video"
        inputs = [url, "v", "1", "1", "o", "fr", "", "O"]
        with (
            patch("builtins.input", side_effect=inputs),
            patch("vdl.interactive.Downloader") as mock_dl_cls,
        ):
            mock_dl_cls.return_value.download.return_value = 0
            with pytest.raises(SystemExit):
                run_interactive()
        dl_kwargs = mock_dl_cls.call_args[1]
        assert dl_kwargs["subs"] is True
        assert dl_kwargs["subs_lang"] == "fr"
