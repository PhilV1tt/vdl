import sys
from pathlib import Path

import pytest

from vdl.cli import _read_batch_file, _validate_url


class TestValidateUrl:
    def test_valid_http(self):
        assert _validate_url("http://example.com/video") is None

    def test_valid_https(self):
        assert _validate_url("https://youtube.com/watch?v=123") is None

    def test_missing_scheme(self):
        assert _validate_url("example.com/video") is not None

    def test_ftp_scheme_rejected(self):
        assert _validate_url("ftp://example.com/video") is not None

    def test_no_netloc(self):
        assert _validate_url("https://") is not None

    def test_embedded_credentials_rejected(self):
        assert _validate_url("https://user:pass@example.com/video") is not None


class TestReadBatchFile:
    def test_reads_urls(self, tmp_path: Path):
        f = tmp_path / "urls.txt"
        f.write_text("https://example.com/1\nhttps://example.com/2\n")
        urls = _read_batch_file(str(f))
        assert urls == ["https://example.com/1", "https://example.com/2"]

    def test_skips_blank_lines(self, tmp_path: Path):
        f = tmp_path / "urls.txt"
        f.write_text("https://example.com/1\n\n  \nhttps://example.com/2\n")
        urls = _read_batch_file(str(f))
        assert len(urls) == 2

    def test_skips_comments(self, tmp_path: Path):
        f = tmp_path / "urls.txt"
        f.write_text("# commentaire\nhttps://example.com/1\n")
        urls = _read_batch_file(str(f))
        assert urls == ["https://example.com/1"]

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            _read_batch_file("/tmp/vdl_nonexistent_12345.txt")

    def test_strips_whitespace(self, tmp_path: Path):
        f = tmp_path / "urls.txt"
        f.write_text("  https://example.com/1  \n")
        urls = _read_batch_file(str(f))
        assert urls == ["https://example.com/1"]


class TestBatchMain:
    def test_batch_missing_file_exits_1(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "argv", ["vdl", "-b", str(tmp_path / "nonexistent.txt")])
        import vdl.downloader as dl_mod
        from vdl import cli

        monkeypatch.setattr(dl_mod, "check_deps", lambda: None)
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1

    def test_batch_empty_file_exits_1(self, monkeypatch, tmp_path):
        batch_file = tmp_path / "empty.txt"
        batch_file.write_text("# just a comment\n")
        monkeypatch.setattr(sys, "argv", ["vdl", "-b", str(batch_file)])
        import vdl.downloader as dl_mod
        from vdl import cli

        monkeypatch.setattr(dl_mod, "check_deps", lambda: None)
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 1
