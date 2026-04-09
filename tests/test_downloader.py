from vdl.downloader import Downloader


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
