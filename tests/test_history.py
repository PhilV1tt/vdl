from pathlib import Path
from unittest.mock import patch

from vdl.history import log_download, show_history


class TestLogDownload:
    def test_creates_file(self, tmp_path: Path):
        history_file = tmp_path / "history.jsonl"
        with patch("vdl.history._HISTORY_PATH", history_file):
            log_download("https://example.com", "Test", "mp4", "/tmp", "ok")
        assert history_file.exists()

    def test_appends_entry(self, tmp_path: Path):
        history_file = tmp_path / "history.jsonl"
        with patch("vdl.history._HISTORY_PATH", history_file):
            log_download("https://example.com/1", "Video 1", "mp4", "/tmp", "ok")
            log_download("https://example.com/2", "Video 2", "mp3", "/tmp", "error")
        lines = history_file.read_text().strip().splitlines()
        assert len(lines) == 2

    def test_entry_fields(self, tmp_path: Path):
        import json

        history_file = tmp_path / "history.jsonl"
        with patch("vdl.history._HISTORY_PATH", history_file):
            log_download("https://example.com", "My Title", "mp4", "/videos", "ok")
        entry = json.loads(history_file.read_text().strip())
        assert entry["url"] == "https://example.com"
        assert entry["title"] == "My Title"
        assert entry["format"] == "mp4"
        assert entry["output_path"] == "/videos"
        assert entry["status"] == "ok"
        assert "timestamp" in entry


class TestShowHistory:
    def test_no_history_file(self, tmp_path: Path, capsys):
        with patch("vdl.history._HISTORY_PATH", tmp_path / "nonexistent.jsonl"):
            show_history()
        captured = capsys.readouterr()
        assert captured.out.strip() != ""

    def test_shows_entries(self, tmp_path: Path, capsys):
        history_file = tmp_path / "history.jsonl"
        with patch("vdl.history._HISTORY_PATH", history_file):
            log_download("https://example.com", "Test Video", "mp4", "/tmp", "ok")
            show_history()
        captured = capsys.readouterr()
        assert "Test Video" in captured.out
