"""Tests of the preferences memory (explicit > memory > config > default)."""

from vdl import prefs
from vdl.config import VdlConfig


def test_recall_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "STATE_PATH", tmp_path / "state.json")
    assert prefs.recall() == {}


def test_recall_corrupt_file_returns_empty(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setattr(prefs, "STATE_PATH", path)
    assert prefs.recall() == {}


def test_resolve_falls_back_to_config_default():
    cfg = VdlConfig(default_quality="720", default_format=None, output_dir="/tmp/out")
    quality, ext, out = prefs.resolve(None, None, None, False, {}, cfg)
    assert quality == "720"
    assert ext == "mp4"  # aucun default_format -> extension terminale audio-aware
    assert out == "/tmp/out"


def test_resolve_audio_terminal_fallback():
    cfg = VdlConfig(default_format=None)
    _, ext, _ = prefs.resolve(None, None, None, True, {}, cfg)
    assert ext == "mp3"


def test_resolve_explicit_wins_over_state_and_config():
    cfg = VdlConfig(default_quality="best")
    state = {"quality": "480"}
    quality, _, _ = prefs.resolve("1080", None, None, False, state, cfg)
    assert quality == "1080"


def test_resolve_state_wins_over_config():
    cfg = VdlConfig(default_quality="best")
    state = {"quality": "480"}
    quality, _, _ = prefs.resolve(None, None, None, False, state, cfg)
    assert quality == "480"


def test_resolve_format_namespaced_by_audio_video():
    cfg = VdlConfig(default_format=None)
    state = {"video_format": "mkv", "audio_format": "flac"}
    _, video_ext, _ = prefs.resolve(None, None, None, False, state, cfg)
    _, audio_ext, _ = prefs.resolve(None, None, None, True, state, cfg)
    assert video_ext == "mkv"
    assert audio_ext == "flac"


def test_remember_writes_only_explicit_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "STATE_PATH", tmp_path / "state.json")
    prefs.remember(False, quality="720", fmt=None, output=None)
    state = prefs.recall()
    assert state == {"mode": "video", "video_quality": "720"}


def test_remember_noop_when_nothing_explicit(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(prefs, "STATE_PATH", path)
    prefs.remember(False, quality=None, fmt=None, output=None)
    assert not path.exists()


def test_remember_namespaces_format_by_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "STATE_PATH", tmp_path / "state.json")
    prefs.remember(False, fmt="mp4")
    prefs.remember(True, fmt="flac")
    state = prefs.recall()
    assert state["video_format"] == "mp4"
    assert state["audio_format"] == "flac"


def test_remember_merges_into_existing_state(tmp_path, monkeypatch):
    monkeypatch.setattr(prefs, "STATE_PATH", tmp_path / "state.json")
    prefs.remember(False, quality="720")
    prefs.remember(False, output="/tmp/videos")
    state = prefs.recall()
    assert state["video_quality"] == "720"
    assert state["output"] == "/tmp/videos"


def test_reset_removes_file(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(prefs, "STATE_PATH", path)
    prefs.remember(False, quality="720")
    assert path.exists()
    assert prefs.reset() is True
    assert not path.exists()
    assert prefs.reset() is False
