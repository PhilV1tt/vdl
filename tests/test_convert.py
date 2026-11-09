from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vdl import presets
from vdl.convert import (
    _AUDIO_ENCODERS,
    AUDIO_KBPS,
    available_encoders,
    build_command,
    convert_files,
    convert_one,
    output_path,
    run_convert,
)

SRC = Path("/tmp/vdl_test/film.mkv")

FULL_ENCODERS = frozenset({"libmp3lame", "aac", "libvorbis", "libopus", "flac", "pcm_s16le", "libx264", "libvpx-vp9"})


@pytest.fixture(autouse=True)
def _encoders(monkeypatch):
    """Fixe la liste d'encodeurs : les tests ne doivent pas dependre du ffmpeg de la machine."""
    monkeypatch.setattr("vdl.convert.available_encoders", lambda: FULL_ENCODERS)


def _ffmpeg_ok(cmd: list[str], **_: object) -> MagicMock:
    """Simule ffmpeg : écrit le fichier de sortie (dernier argument)."""
    Path(cmd[-1]).write_bytes(b"audio")
    return MagicMock(returncode=0, stderr="")


def _convert_ok(src: Path, dst: Path, ext: str, quality: str) -> None:
    """Simule convert_one : écrit le fichier de sortie."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(b"audio")


class TestBuildCommand:
    def test_audio_drops_video_and_encodes_mp3(self):
        cmd = build_command(SRC, Path("/tmp/vdl_test/film.mp3"), "mp3", "320")
        assert cmd[:5] == ["ffmpeg", "-y", "-hide_banner", "-nostdin", "-i"]
        assert cmd[5] == str(SRC)
        assert cmd[6] == "-vn"
        assert cmd[7:] == ["-c:a", "libmp3lame", "-b:a", "320k", "/tmp/vdl_test/film.mp3"]

    def test_lossless_audio_ignores_bitrate(self):
        assert build_command(SRC, Path("out.flac"), "flac", "320")[7:] == ["-c:a", "flac", "out.flac"]

    def test_video_default_encodes_h264_aac_without_scaling(self):
        cmd = build_command(SRC, Path("out.mp4"), "mp4", "best")
        assert cmd[6:10] == ["-map", "0:v:0", "-map", "0:a:0?"]
        assert cmd[10:] == [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "out.mp4",
        ]

    def test_video_height_scales_width_to_even(self):
        cmd = build_command(SRC, Path("out.mov"), "mov", "1080")
        idx = cmd.index("-vf")
        assert cmd[idx + 1] == "scale=-2:1080"

    def test_webm_uses_vp9_opus(self):
        cmd = build_command(SRC, Path("out.webm"), "webm", "best")
        assert "libvpx-vp9" in cmd
        assert "libopus" in cmd
        assert "192k" in cmd

    def test_opus_bitrate_clamped_to_encoder_max(self):
        cmd = build_command(SRC, Path("out.opus"), "opus", "320")
        assert cmd[7:] == ["-c:a", "libopus", "-b:a", "256k", "out.opus"]

    def test_native_encoder_fallback_when_library_missing(self, monkeypatch):
        """Le build ffmpeg 9 de Homebrew n'a plus libvorbis : on encode avec celui de ffmpeg."""
        monkeypatch.setattr("vdl.convert.available_encoders", lambda: frozenset({"vorbis", "opus", "aac"}))
        assert build_command(SRC, Path("out.ogg"), "ogg", "320")[7:] == [
            "-c:a",
            "vorbis",
            "-strict",
            "-2",
            "-q:a",
            "3",
            "-ac",
            "2",
            "out.ogg",
        ]
        assert "libopus" not in build_command(SRC, Path("out.webm"), "webm", "best")

    def test_overwrites_without_prompting(self):
        assert "-y" in build_command(SRC, Path("out.mp3"), "mp3", "320")

    def test_unknown_ext_rejected(self):
        with pytest.raises(ValueError):
            build_command(SRC, Path("out.xyz"), "xyz", "320")


class TestAvailableEncoders:
    TABLE = """Encoders:
 V....D libx264              H.264
 A....D libmp3lame           MP3 (MPEG audio layer 3)
 A..X.D vorbis               Vorbis
 A....D aac                  AAC
      D some_noise_filter    noise
"""

    def test_keeps_only_encoder_lines(self):
        with patch("vdl.convert.subprocess.run", return_value=MagicMock(returncode=0, stdout=self.TABLE)):
            available_encoders.cache_clear()
            assert available_encoders() == frozenset({"libx264", "libmp3lame", "vorbis", "aac"})
        available_encoders.cache_clear()


class TestOutputPath:
    def test_next_to_source_by_default(self):
        assert output_path(Path("/a/b/film.mkv"), "mp3", None) == Path("/a/b/film.mp3")

    def test_output_dir_overrides(self):
        assert output_path(Path("/a/b/film.mkv"), "mp4", "~/Music") == Path.home() / "Music" / "film.mp4"


class TestConvertOne:
    def test_success_creates_file(self, tmp_path):
        src = tmp_path / "in.mkv"
        src.write_bytes(b"\x00")
        dst = tmp_path / "out.mp3"
        with patch("vdl.convert.subprocess.run", side_effect=_ffmpeg_ok):
            convert_one(src, dst, "mp3", "320")
        assert dst.read_bytes() == b"audio"

    def test_missing_output_dir_is_created(self, tmp_path):
        src = tmp_path / "in.mkv"
        src.write_bytes(b"\x00")
        dst = tmp_path / "sub" / "out.mp3"
        with patch("vdl.convert.subprocess.run", side_effect=_ffmpeg_ok):
            convert_one(src, dst, "mp3", "320")
        assert dst.exists()

    def test_failure_raises_with_ffmpeg_tail(self, tmp_path):
        src = tmp_path / "in.mkv"
        src.write_bytes(b"\x00")
        dst = tmp_path / "out.mp3"
        done = MagicMock(
            returncode=1, stderr="[mp4 @ 0x1] moov atom not found\nInvalid data found when processing input\n"
        )
        with patch("vdl.convert.subprocess.run", return_value=done), pytest.raises(RuntimeError, match="Invalid data"):
            convert_one(src, dst, "mp3", "320")
        assert not dst.exists()
        assert list(tmp_path.glob(".vdl-*")) == []  # temp folder cleaned up

    def test_success_without_output_counts_as_failure(self, tmp_path):
        src = tmp_path / "in.mkv"
        src.write_bytes(b"\x00")
        with (
            patch("vdl.convert.subprocess.run", return_value=MagicMock(returncode=0, stderr="")),
            pytest.raises(RuntimeError),
        ):
            convert_one(src, tmp_path / "out.mp3", "mp3", "320")

    def test_partial_output_removed_on_interrupt(self, tmp_path):
        src = tmp_path / "in.mkv"
        src.write_bytes(b"\x00")
        dst = tmp_path / "out.mp3"
        with patch("vdl.convert.subprocess.run", side_effect=KeyboardInterrupt), pytest.raises(KeyboardInterrupt):
            convert_one(src, dst, "mp3", "320")
        assert not dst.exists()
        assert list(tmp_path.glob(".vdl-*")) == []

    def test_existing_output_is_kept_and_refused(self, tmp_path):
        src = tmp_path / "in.mkv"
        src.write_bytes(b"\x00")
        dst = tmp_path / "out.mp3"
        dst.write_bytes(b"existing")
        with patch("vdl.convert.subprocess.run") as run, pytest.raises(RuntimeError, match="existe déjà"):
            convert_one(src, dst, "mp3", "320")
        run.assert_not_called()
        assert dst.read_bytes() == b"existing"


class TestConvertFiles:
    def test_missing_file_counts_as_failure(self, tmp_path, capsys):
        assert convert_files([str(tmp_path / "nope.mkv")], "mp3", "320", None) == 1
        assert "nope.mkv" in capsys.readouterr().err

    def test_mixed_batch_exit_code(self, tmp_path, capsys):
        good = tmp_path / "in.mkv"
        good.write_bytes(b"\x00")
        with patch("vdl.convert.convert_one", side_effect=_convert_ok) as conv:
            code = convert_files([str(good), str(tmp_path / "nope.mkv")], "mp3", "320", None)
        assert code == 1
        assert "1 reussi(s), 1 echoue(s)" in capsys.readouterr().out
        assert (tmp_path / "in.mp3").exists()
        assert conv.call_count == 1

    def test_output_dir_used_for_every_file(self, tmp_path):
        for name in ("a.mkv", "b.mkv"):
            (tmp_path / name).write_bytes(b"\x00")
        out = tmp_path / "out"
        with patch("vdl.convert.convert_one", side_effect=_convert_ok):
            code = convert_files([str(tmp_path / "a.mkv"), str(tmp_path / "b.mkv")], "mp3", "320", str(out))
        assert code == 0
        assert sorted(p.name for p in out.iterdir()) == ["a.mp3", "b.mp3"]

    def test_conversion_error_is_reported(self, tmp_path, capsys):
        good = tmp_path / "in.mkv"
        good.write_bytes(b"\x00")
        with patch("vdl.convert.convert_one", side_effect=RuntimeError("boom")):
            assert convert_files([str(good)], "mp3", "320", None) == 1
        assert "boom" in capsys.readouterr().err


def _run(argv: list[str], state: dict[str, str] | None = None) -> int:
    from vdl.config import VdlConfig

    with (
        patch("vdl.downloader.check_deps"),
        patch("vdl.config.load_config", return_value=VdlConfig()),
        patch("vdl.prefs.recall", return_value=state or {}),
    ):
        return run_convert(argv)


class TestRunConvert:
    def test_defaults_to_mp3_320(self):
        with patch("vdl.convert.convert_files", return_value=0) as cf:
            _run(["film.mkv"])
        assert cf.call_args[0][1:] == ("mp3", "320", None)

    def test_remembers_last_audio_format(self):
        with patch("vdl.convert.convert_files", return_value=0) as cf:
            _run(["film.mkv"], {"audio_format": "flac"})
        assert cf.call_args[0][1] == "flac"

    def test_video_target_defaults_to_best(self):
        with patch("vdl.convert.convert_files", return_value=0) as cf:
            _run(["film.mkv", "-f", "mp4"])
        assert cf.call_args[0][1:] == ("mp4", "best", None)

    def test_files_and_output_dir_passed_through(self):
        with patch("vdl.convert.convert_files", return_value=0) as cf:
            _run(["a.mkv", "b.mkv", "-f", "mp3", "-o", "/tmp/out"])
        assert cf.call_args[0][0] == ["a.mkv", "b.mkv"]
        assert cf.call_args[0][3] == "/tmp/out"

    def test_unknown_format_exits_1(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _run(["film.mkv", "-f", "xyz"])
        assert exc.value.code == 1
        assert "xyz" in capsys.readouterr().err

    def test_leading_dot_in_format(self):
        with patch("vdl.convert.convert_files", return_value=0) as cf:
            _run(["film.mkv", "-f", ".wav"])
        assert cf.call_args[0][1] == "wav"

    def test_video_height_accepted(self):
        with patch("vdl.convert.convert_files", return_value=0) as cf:
            _run(["film.mkv", "-f", "mkv", "-q", "720"])
        assert cf.call_args[0][2] == "720"

    def test_unknown_quality_exits_1(self, capsys):
        with pytest.raises(SystemExit) as exc:
            _run(["film.mkv", "-f", "mp3", "-q", "9999"])
        assert exc.value.code == 1
        assert "9999" in capsys.readouterr().err

    def test_audio_bitrate_cannot_be_a_height(self):
        with pytest.raises(SystemExit) as exc:
            _run(["film.mkv", "-f", "mp3", "-q", "1080"])
        assert exc.value.code == 1

    def test_keyboard_interrupt_returns_130(self, capsys):
        with patch("vdl.convert.convert_files", side_effect=KeyboardInterrupt):
            assert _run(["film.mkv"]) == 130


def test_audio_kbps_comes_from_presets():
    assert {q["value"] for q in presets.AUDIO_QUALITIES} == AUDIO_KBPS


def test_every_preset_format_has_an_encoder():
    assert set(presets.AUDIO_EXTS) == set(_AUDIO_ENCODERS)
    for ext in presets.VIDEO_EXTS:
        codec = "libvpx-vp9" if ext == "webm" else "libx264"
        assert codec in build_command(SRC, Path("o.mp4"), ext, "best")
