from unittest.mock import MagicMock, patch

from vdl.links import extract_links, is_channel_target, normalize_channel_url


class TestNormalizeChannelUrl:
    def test_bare_handle(self):
        assert normalize_channel_url("@QOVESStudio") == "https://www.youtube.com/@QOVESStudio/videos"

    def test_channel_url_gets_videos_tab(self):
        assert (
            normalize_channel_url("https://www.youtube.com/@QOVESStudio")
            == "https://www.youtube.com/@QOVESStudio/videos"
        )

    def test_channel_id_url_gets_videos_tab(self):
        assert (
            normalize_channel_url("https://www.youtube.com/channel/UC123")
            == "https://www.youtube.com/channel/UC123/videos"
        )

    def test_existing_tab_untouched(self):
        url = "https://www.youtube.com/@QOVESStudio/shorts"
        assert normalize_channel_url(url) == url

    def test_playlist_untouched(self):
        url = "https://www.youtube.com/playlist?list=PL123"
        assert normalize_channel_url(url) == url

    def test_bare_domain_gets_scheme(self):
        assert normalize_channel_url("youtube.com/@x").startswith("https://")

    def test_trailing_slash(self):
        assert (
            normalize_channel_url("https://www.youtube.com/@x/")
            == "https://www.youtube.com/@x/videos"
        )


class TestIsChannelTarget:
    def test_bare_handle(self):
        assert is_channel_target("@QOVESStudio") is True

    def test_channel_page_without_tab(self):
        assert is_channel_target("https://www.youtube.com/@QOVESStudio") is True

    def test_watch_url_is_not_channel(self):
        assert is_channel_target("https://www.youtube.com/watch?v=abc123") is False

    def test_playlist_url_is_not_channel(self):
        assert is_channel_target("https://www.youtube.com/playlist?list=PL123") is False

    def test_combined_video_and_list_is_not_channel(self):
        assert is_channel_target("https://www.youtube.com/watch?v=abc&list=PL123") is False

    def test_non_youtube_domain_is_not_channel(self):
        assert is_channel_target("https://vimeo.com/12345") is False


def _fake_ydl(info):
    m = MagicMock()
    m.return_value.__enter__.return_value.extract_info.return_value = info
    return m


class TestExtractLinks:
    def test_returns_entry_urls(self):
        info = {"entries": [{"url": "https://youtu.be/1"}, {"url": "https://youtu.be/2"}, None]}
        with patch("yt_dlp.YoutubeDL", _fake_ydl(info)):
            assert extract_links("@x") == ["https://youtu.be/1", "https://youtu.be/2"]

    def test_falls_back_to_webpage_url(self):
        info = {"entries": [{"webpage_url": "https://youtu.be/a"}]}
        with patch("yt_dlp.YoutubeDL", _fake_ydl(info)):
            assert extract_links("@x") == ["https://youtu.be/a"]

    def test_single_video(self):
        info = {"webpage_url": "https://youtu.be/solo"}
        with patch("yt_dlp.YoutubeDL", _fake_ydl(info)):
            assert extract_links("https://youtu.be/solo") == ["https://youtu.be/solo"]

    def test_empty_info(self):
        with patch("yt_dlp.YoutubeDL", _fake_ydl(None)):
            assert extract_links("@x") == []
