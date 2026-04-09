"""Tests pour le module de recherche."""

from unittest.mock import patch

from vdl.search import _fmt_duration, _fmt_views, format_result_label, search_videos


class TestFormatDuration:
    def test_none(self):
        assert _fmt_duration(None) == ""

    def test_zero(self):
        assert _fmt_duration(0) == ""

    def test_minutes_seconds(self):
        assert _fmt_duration(90) == "1:30"

    def test_hours(self):
        assert _fmt_duration(3661) == "1:01:01"

    def test_pad_seconds(self):
        assert _fmt_duration(65) == "1:05"


class TestFormatViews:
    def test_none(self):
        assert _fmt_views(None) == ""

    def test_zero(self):
        assert _fmt_views(0) == ""

    def test_thousands(self):
        assert "5K" in _fmt_views(5000)

    def test_millions(self):
        assert "M" in _fmt_views(2_500_000)

    def test_small(self):
        assert "999" in _fmt_views(999)


class TestFormatResultLabel:
    def test_basic_label(self):
        result = {"title": "Test Video", "duration": 120, "uploader": "TestUser", "view_count": 1000}
        label = format_result_label(result, 1)
        assert "Test Video" in label
        assert "2:00" in label

    def test_missing_fields(self):
        result = {"title": "Minimal", "duration": None, "uploader": "", "view_count": None}
        label = format_result_label(result, 1)
        assert "Minimal" in label


class TestSearchVideos:
    def test_returns_empty_on_error(self):
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__.return_value.extract_info.side_effect = Exception("Network error")
            results = search_videos("test query")
        assert results == []

    def test_parses_results(self):
        mock_entry = {
            "title": "Test Video",
            "url": "https://www.youtube.com/watch?v=abc123",
            "duration": 120,
            "uploader": "TestUser",
            "view_count": 1000,
        }
        mock_info = {"entries": [mock_entry]}

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__.return_value.extract_info.return_value = mock_info
            results = search_videos("test")

        assert len(results) == 1
        assert results[0]["title"] == "Test Video"
        assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"

    def test_skips_none_entries(self):
        mock_info = {"entries": [None, {"title": "Valid", "url": "https://example.com", "duration": 60}]}

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__.return_value.extract_info.return_value = mock_info
            results = search_videos("test")

        assert len(results) == 1
        assert results[0]["title"] == "Valid"

    def test_youtube_id_becomes_full_url(self):
        mock_entry = {
            "title": "Test",
            "url": "abc123",  # Juste l'ID, pas une URL complète
            "duration": 60,
        }
        mock_info = {"entries": [mock_entry]}

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__.return_value.extract_info.return_value = mock_info
            results = search_videos("test", source="youtube")

        assert "youtube.com" in str(results[0]["url"])

    def test_empty_entries(self):
        mock_info = {"entries": []}

        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__.return_value.extract_info.return_value = mock_info
            results = search_videos("test")

        assert results == []
