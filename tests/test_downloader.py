from unittest.mock import patch

from vdl.downloader import (
    Downloader,
    _parse_section,
    _print_upcoming,
    _remux_live_parts,
    kind,
    list_formats,
    probe,
)


def _dummy_hook(d):
    pass


def make_dl(**kwargs) -> Downloader:
    return Downloader(output_dir="/tmp/vdl_test", **kwargs)


class TestBuildYdlOpts:
    def test_audio_mp3_format(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp3", True, "bestaudio/best", "320", _dummy_hook)
        assert opts["format"] == "bestaudio/best"
        pp = opts["postprocessors"]
        extract = next(p for p in pp if p["key"] == "FFmpegExtractAudio")
        assert extract["preferredcodec"] == "mp3"
        assert extract["preferredquality"] == "320"

    def test_audio_flac_quality_zero(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("flac", True, "bestaudio/best", "320", _dummy_hook)
        extract = next(p for p in opts["postprocessors"] if p["key"] == "FFmpegExtractAudio")
        assert extract["preferredquality"] == "0"

    def test_audio_thumbnail_embedded_by_default(self):
        dl = make_dl(embed_thumbnail=True)
        opts = dl._build_ydl_opts("mp3", True, "bestaudio/best", "320", _dummy_hook)
        keys = [p["key"] for p in opts["postprocessors"]]
        assert "EmbedThumbnail" in keys
        assert opts.get("writethumbnail") is True

    def test_audio_no_thumbnail(self):
        dl = make_dl(embed_thumbnail=False)
        opts = dl._build_ydl_opts("mp3", True, "bestaudio/best", "320", _dummy_hook)
        keys = [p["key"] for p in opts["postprocessors"]]
        assert "EmbedThumbnail" not in keys

    def test_video_mp4_no_postprocessor(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["merge_output_format"] == "mp4"
        assert "postprocessors" not in opts

    def test_video_avi_has_convertor(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("avi", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["merge_output_format"] == "avi"
        keys = [p["key"] for p in opts.get("postprocessors", [])]
        assert "FFmpegVideoConvertor" in keys

    def test_playlist_flag_false(self):
        dl = make_dl(playlist=False)
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["noplaylist"] is True

    def test_playlist_flag_true(self):
        dl = make_dl(playlist=True)
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["noplaylist"] is False

    def test_output_dir_in_outtmpl(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert "/tmp/vdl_test" in opts["outtmpl"]

    def test_quiet_mode_enabled(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["quiet"] is True
        assert opts["no_warnings"] is True

    def test_custom_output_template(self):
        dl = make_dl(output_template="%(uploader)s - %(title)s.%(ext)s")
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert "%(uploader)s" in opts["outtmpl"]

    def test_sponsorblock_adds_postprocessors(self):
        dl = make_dl(sponsorblock=True)
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        keys = [p["key"] for p in opts.get("postprocessors", [])]
        assert "SponsorBlock" in keys
        assert "ModifyChapters" in keys

    def test_sponsorblock_off_by_default(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        keys = [p["key"] for p in opts.get("postprocessors", [])]
        assert "SponsorBlock" not in keys

    def test_subs_adds_options(self):
        dl = make_dl(subs=True, subs_lang="en")
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts.get("writesubtitles") is True
        assert "en" in opts.get("subtitleslangs", [])
        keys = [p["key"] for p in opts.get("postprocessors", [])]
        assert "FFmpegEmbedSubtitle" in keys

    def test_subs_off_by_default(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert "writesubtitles" not in opts

    def test_retries_default(self):
        dl = make_dl()
        assert dl.retries == 3

    def test_custom_retries(self):
        dl = make_dl(retries=5)
        assert dl.retries == 5


class TestMetadataOptions:
    def test_strip_metadata_audio_no_metadata_pp(self):
        dl = make_dl(strip_metadata=True)
        opts = dl._build_ydl_opts("mp3", True, "bestaudio/best", "320", _dummy_hook)
        keys = [p["key"] for p in opts["postprocessors"]]
        assert "FFmpegMetadata" not in keys
        assert "EmbedThumbnail" not in keys

    def test_default_audio_keeps_metadata_pp(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp3", True, "bestaudio/best", "320", _dummy_hook)
        keys = [p["key"] for p in opts["postprocessors"]]
        assert "FFmpegMetadata" in keys

    def test_strip_file_metadata_remux(self, tmp_path):
        from pathlib import Path
        from unittest.mock import patch

        from vdl.downloader import _strip_file_metadata

        f = tmp_path / "clip.mp4"
        f.write_bytes(b"data")

        def fake_run(cmd, **kwargs):
            # ffmpeg would write the output file: simulate it
            out = cmd[-1]
            Path(out).write_bytes(b"clean")

            class R:
                returncode = 0

            return R()

        with patch("vdl.downloader.subprocess.run", side_effect=fake_run) as run:
            _strip_file_metadata(f)

        args = run.call_args[0][0]
        assert "-map_metadata" in args and "-1" in args
        assert "-map_chapters" in args
        assert "+bitexact" in args
        assert f.read_bytes() == b"clean"

    def test_strip_metadata_drops_thumbnail_even_if_enabled(self):
        dl = make_dl(embed_thumbnail=True, strip_metadata=True)
        opts = dl._build_ydl_opts("mp3", True, "bestaudio/best", "320", _dummy_hook)
        assert opts.get("writethumbnail") is not True
        keys = [p["key"] for p in opts["postprocessors"]]
        assert "EmbedThumbnail" not in keys

    def test_custom_title_in_outtmpl(self):
        dl = make_dl(custom_title="Mon Titre")
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["outtmpl"].endswith("Mon Titre.%(ext)s")
        assert "%(title)s" not in opts["outtmpl"]

    def test_custom_title_sanitized(self):
        dl = make_dl(custom_title="a/b:c")
        opts = dl._build_ydl_opts("mp3", True, "bestaudio/best", "320", _dummy_hook)
        assert opts["outtmpl"].endswith("a_b_c.%(ext)s")


class TestNewOrthogonalOptions:
    def test_cookies_from_browser_added(self):
        dl = make_dl(cookies_browser="chrome")
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["cookiesfrombrowser"] == ("chrome",)

    def test_no_cookies_by_default(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert "cookiesfrombrowser" not in opts

    def test_format_id_overrides_quality_selector(self):
        dl = make_dl(format_id="137+140")
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["format"] == "137+140"

    def test_no_format_id_uses_quality_selector(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["format"] == "bestvideo+bestaudio/best"

    def test_sections_add_download_ranges(self):
        dl = make_dl(sections=["00:10-00:20"])
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert "download_ranges" in opts
        assert opts["force_keyframes_at_cuts"] is True

    def test_no_sections_by_default(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert "download_ranges" not in opts

    def test_concurrent_fragments_default(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["concurrent_fragment_downloads"] == 4

    def test_concurrent_fragments_custom(self):
        dl = make_dl(concurrent_fragments=8)
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["concurrent_fragment_downloads"] == 8

    def test_aria2c_off_by_default(self):
        dl = make_dl()
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert "external_downloader" not in opts

    def test_aria2c_enabled(self):
        dl = make_dl(use_aria2c=True)
        opts = dl._build_ydl_opts("mp4", False, "bestvideo+bestaudio/best", "0", _dummy_hook)
        assert opts["external_downloader"] == {"default": "aria2c"}
        assert opts["external_downloader_args"]["aria2c"] == ["-x", "16", "-s", "16", "-k", "1M"]


class TestParseSection:
    def test_mmss_range(self):
        assert _parse_section("00:10-00:20") == (10.0, 20.0)

    def test_hhmmss_range(self):
        assert _parse_section("01:00:10-01:00:20") == (3610.0, 3620.0)

    def test_raw_seconds(self):
        assert _parse_section("*90-120") == (90.0, 120.0)


class TestKind:
    def test_video(self):
        assert kind({"title": "x"}) == "video"

    def test_playlist(self):
        assert kind({"entries": []}) == "playlist"

    def test_live(self):
        assert kind({"live_status": "is_live"}) == "live"

    def test_upcoming(self):
        assert kind({"live_status": "is_upcoming"}) == "upcoming"


class TestProbe:
    def test_returns_info(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            mock_cls.return_value.__enter__.return_value.extract_info.return_value = {"title": "x"}
            assert probe("https://example.com") == {"title": "x"}

    def test_returns_none_on_exception(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            mock_cls.return_value.__enter__.return_value.extract_info.side_effect = Exception("boom")
            assert probe("https://example.com") is None

    def test_single_sets_noplaylist(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            mock_cls.return_value.__enter__.return_value.extract_info.return_value = {}
            probe("https://example.com", single=True)
        assert mock_cls.call_args[0][0]["noplaylist"] is True

    def test_default_sets_noplaylist(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            mock_cls.return_value.__enter__.return_value.extract_info.return_value = {}
            probe("https://example.com")
        assert mock_cls.call_args[0][0]["noplaylist"] is True

    def test_single_false_keeps_playlist(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            mock_cls.return_value.__enter__.return_value.extract_info.return_value = {}
            probe("https://example.com", single=False)
        assert mock_cls.call_args[0][0]["noplaylist"] is False


class TestPrintUpcoming:
    def test_with_timestamp(self, capsys):
        _print_upcoming({"release_timestamp": 4102444800})
        assert capsys.readouterr().out.strip() != ""

    def test_without_timestamp(self, capsys):
        _print_upcoming({})
        assert capsys.readouterr().out.strip() != ""


class TestRemuxLiveParts:
    def test_success(self, tmp_path):
        final = tmp_path / "Title.mp4"
        (tmp_path / "Title.f137.mp4").write_bytes(b"data")

        def fake_run(cmd, **kwargs):
            from pathlib import Path

            Path(cmd[-1]).write_bytes(b"merged")

            class R:
                returncode = 0

            return R()

        with patch("vdl.downloader.subprocess.run", side_effect=fake_run):
            assert _remux_live_parts(final) is True
        assert final.read_bytes() == b"merged"

    def test_no_fragments_found(self, tmp_path):
        assert _remux_live_parts(tmp_path / "Title.mp4") is False


class TestListFormats:
    def test_success_returns_0(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            mock_cls.return_value.__enter__.return_value.download.return_value = None
            assert list_formats("https://example.com") == 0

    def test_download_error_returns_1(self):
        import yt_dlp

        with patch("yt_dlp.YoutubeDL") as mock_cls:
            mock_cls.return_value.__enter__.return_value.download.side_effect = yt_dlp.utils.DownloadError("boom")
            assert list_formats("https://example.com") == 1


class TestLiveDownload:
    def test_probe_info_never_used_for_download(self):
        """The probe comes from another YoutubeDL instance: its URLs return 403.

        The info used for the download must always be re-extracted here.
        """
        probe_info = {"title": "Probe", "live_status": "not_live"}
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            ydl = mock_cls.return_value.__enter__.return_value
            ydl.prepare_filename.return_value = "/tmp/vdl_test/Video.mp4"
            ydl.extract_info.return_value = {"title": "Video", "live_status": "not_live"}
            ydl.process_ie_result.return_value = {"title": "Video"}
            dl = make_dl()
            result = dl.download(
                "https://example.com/video",
                "mp4",
                False,
                "bestvideo+bestaudio/best",
                "0",
                info=probe_info,
            )
        assert result.exit_code == 0
        ydl.extract_info.assert_called_once_with("https://example.com/video", download=False)
        assert ydl.process_ie_result.call_args[0][0] is not probe_info

    def test_is_live_sets_live_from_start_and_reextracts(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            ydl = mock_cls.return_value.__enter__.return_value
            ydl.params = {}
            ydl.extract_info.side_effect = [
                {"title": "Live", "live_status": "is_live"},
                {"title": "Live", "live_status": "is_live"},
            ]
            ydl.prepare_filename.return_value = "/tmp/vdl_test/Live.mp4"
            ydl.process_ie_result.return_value = {"title": "Live", "live_status": "is_live"}
            dl = make_dl()
            result = dl.download("https://example.com/live", "mp4", False, "bestvideo+bestaudio/best", "0")

        assert result.exit_code == 0
        assert ydl.params.get("live_from_start") is True
        assert ydl.extract_info.call_count == 2

    def test_no_live_from_start_when_disabled(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            ydl = mock_cls.return_value.__enter__.return_value
            ydl.params = {}
            ydl.extract_info.return_value = {"title": "Live", "live_status": "is_live"}
            ydl.prepare_filename.return_value = "/tmp/vdl_test/Live.mp4"
            ydl.process_ie_result.return_value = {"title": "Live", "live_status": "is_live"}
            dl = make_dl(live_from_start=False)
            result = dl.download("https://example.com/live", "mp4", False, "bestvideo+bestaudio/best", "0")

        assert result.exit_code == 0
        assert "live_from_start" not in ydl.params
        assert ydl.extract_info.call_count == 1

    def test_upcoming_short_circuits(self):
        with patch("yt_dlp.YoutubeDL") as mock_cls:
            ydl = mock_cls.return_value.__enter__.return_value
            ydl.extract_info.return_value = {
                "title": "Soon",
                "live_status": "is_upcoming",
                "release_timestamp": 4102444800,
            }
            dl = make_dl()
            result = dl.download("https://example.com/soon", "mp4", False, "bestvideo+bestaudio/best", "0")

        assert result.exit_code == 0
        ydl.process_ie_result.assert_not_called()

    def test_keyboard_interrupt_on_live_triggers_remux(self, tmp_path):
        with (
            patch("yt_dlp.YoutubeDL") as mock_cls,
            patch("vdl.downloader._remux_live_parts", return_value=True) as mock_remux,
        ):
            ydl = mock_cls.return_value.__enter__.return_value
            ydl.params = {}
            ydl.extract_info.return_value = {"title": "Live", "live_status": "is_live"}
            ydl.prepare_filename.return_value = str(tmp_path / "Live.mp4")
            ydl.process_ie_result.side_effect = KeyboardInterrupt
            dl = make_dl()
            result = dl.download("https://example.com/live", "mp4", False, "bestvideo+bestaudio/best", "0")

        assert result.exit_code == 0
        mock_remux.assert_called_once()

    def test_keyboard_interrupt_on_live_remux_failure_returns_130(self, tmp_path):
        with (
            patch("yt_dlp.YoutubeDL") as mock_cls,
            patch("vdl.downloader._remux_live_parts", return_value=False),
        ):
            ydl = mock_cls.return_value.__enter__.return_value
            ydl.params = {}
            ydl.extract_info.return_value = {"title": "Live", "live_status": "is_live"}
            ydl.prepare_filename.return_value = str(tmp_path / "Live.mp4")
            ydl.process_ie_result.side_effect = KeyboardInterrupt
            dl = make_dl()
            result = dl.download("https://example.com/live", "mp4", False, "bestvideo+bestaudio/best", "0")

        assert result.exit_code == 130
