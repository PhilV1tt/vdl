import sys
from unittest.mock import MagicMock, patch

import pytest

from vdl import presets
from vdl.cli import _make_parser, _validate_url


def test_parser_defaults():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com"])
    assert args.url == "https://example.com"
    assert args.audio is False
    assert args.video is False
    assert args.quality == "best"
    assert args.format is None
    assert args.playlist is False
    assert args.no_thumbnail is False
    assert args.verbose is False
    assert args.subs is False
    assert args.sponsorblock is False


def test_parser_audio_flag():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "-a"])
    assert args.audio is True


def test_parser_quality_flag():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "-q", "1080"])
    assert args.quality == "1080"


def test_parser_format_flag():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "-f", "mp3"])
    assert args.format == "mp3"


def test_parser_verbose_flag():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "--verbose"])
    assert args.verbose is True


def test_parser_no_url():
    parser = _make_parser()
    args = parser.parse_args([])
    assert args.url is None


def test_parser_subs_flag():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "--subs", "--subs-lang", "en"])
    assert args.subs is True
    assert args.subs_lang == "en"


def test_parser_sponsorblock_flag():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "--sponsorblock"])
    assert args.sponsorblock is True


def test_parser_batch_file_flag():
    parser = _make_parser()
    args = parser.parse_args(["-b", "urls.txt"])
    assert args.batch_file == "urls.txt"


def test_invalid_format_exits(monkeypatch):
    """Passing an unknown format must exit with code 1."""
    monkeypatch.setattr(sys, "argv", ["vdl", "-f", "xyz", "https://example.com"])

    import vdl.downloader as dl_mod
    from vdl import cli
    from vdl.config import VdlConfig

    monkeypatch.setattr(dl_mod, "check_deps", lambda: None)
    monkeypatch.setattr("vdl.config.load_config", lambda *a, **kw: VdlConfig())
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 1


def test_audio_auto_detected_from_format():
    """When -f is an audio extension without -a, is_audio should be True."""
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "-f", "mp3"])
    is_audio = args.audio
    if not is_audio and not args.video and args.format and args.format.lower() in presets.AUDIO_EXTS:
        is_audio = True
    assert is_audio is True


def test_video_format_does_not_trigger_audio():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "-f", "mp4"])
    is_audio = args.audio
    if not is_audio and not args.video and args.format and args.format.lower() in presets.AUDIO_EXTS:
        is_audio = True
    assert is_audio is False


class TestValidateUrl:
    def test_valid_https(self):
        assert _validate_url("https://youtube.com/watch?v=abc") is None

    def test_valid_http(self):
        assert _validate_url("http://example.com") is None

    def test_invalid_scheme(self):
        assert _validate_url("ftp://example.com") is not None

    def test_no_netloc(self):
        assert _validate_url("https://") is not None

    def test_with_credentials_rejected(self):
        assert _validate_url("https://user:pass@example.com") is not None


class TestListSites:
    def test_list_sites_prints_and_counts(self, capsys):
        from vdl.cli import _list_sites

        mock_ie1 = MagicMock()
        mock_ie1.IE_NAME = "youtube"
        mock_ie2 = MagicMock()
        mock_ie2.IE_NAME = "_hidden"
        mock_ie3 = MagicMock()
        mock_ie3.IE_NAME = "vimeo"

        with (
            patch("vdl.cli.list_extractors", return_value=[mock_ie1, mock_ie2, mock_ie3], create=True),
            patch("yt_dlp.extractor.list_extractors", return_value=[mock_ie1, mock_ie2, mock_ie3]),
        ):
            _list_sites()

        captured = capsys.readouterr()
        assert "youtube" in captured.out
        assert "vimeo" in captured.out
        assert "_hidden" not in captured.out
        assert "2 extracteurs" in captured.out


class TestCheckDeps:
    def test_passes_when_all_available(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/ffmpeg")
        import importlib.util
        from unittest.mock import MagicMock

        monkeypatch.setattr(importlib.util, "find_spec", lambda name: MagicMock())
        from vdl.downloader import check_deps

        check_deps()  # should not raise

    def test_fails_when_ffmpeg_missing(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda cmd: None)
        from vdl.downloader import check_deps

        with pytest.raises(SystemExit) as exc:
            check_deps()
        assert exc.value.code == 1
