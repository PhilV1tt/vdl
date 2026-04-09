import sys

import pytest

from vdl import presets
from vdl.cli import _make_parser


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


def test_invalid_format_exits(monkeypatch):
    """Passing an unknown format must exit with code 1."""
    monkeypatch.setattr(sys, "argv", ["vdl", "-f", "xyz", "https://example.com"])
    # Patch check_deps to avoid requiring yt-dlp + ffmpeg
    import vdl.cli as cli_module

    monkeypatch.setattr(cli_module, "__name__", "__main__")

    # Patch check_deps so it doesn't fail on missing deps
    import vdl.downloader as dl_mod
    from vdl import cli

    monkeypatch.setattr(dl_mod, "check_deps", lambda: None)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 1


def test_audio_auto_detected_from_format():
    """When -f is an audio extension without -a, is_audio should be True."""
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "-f", "mp3"])
    # Simulate the logic from main()
    is_audio = args.audio
    if not is_audio and not args.video:
        if args.format and args.format.lower() in presets.AUDIO_EXTS:
            is_audio = True
    assert is_audio is True


def test_video_format_does_not_trigger_audio():
    parser = _make_parser()
    args = parser.parse_args(["https://example.com", "-f", "mp4"])
    is_audio = args.audio
    if not is_audio and not args.video:
        if args.format and args.format.lower() in presets.AUDIO_EXTS:
            is_audio = True
    assert is_audio is False
