from vdl import presets


def test_audio_exts_non_empty():
    assert len(presets.AUDIO_EXTS) > 0


def test_video_exts_non_empty():
    assert len(presets.VIDEO_EXTS) > 0


def test_exts_are_disjoint():
    assert presets.AUDIO_EXTS.isdisjoint(presets.VIDEO_EXTS)


def test_all_exts_is_union():
    assert presets.ALL_EXTS == presets.AUDIO_EXTS | presets.VIDEO_EXTS


def test_video_quality_map_keys():
    expected_keys = {"best", "2160", "1440", "1080", "720", "480", "360"}
    assert set(presets.VIDEO_QUALITY_MAP.keys()) == expected_keys


def test_video_quality_map_matches_video_qualities():
    """VIDEO_QUALITY_MAP values must match VIDEO_QUALITIES values (same order)."""
    quality_values = [q["value"] for q in presets.VIDEO_QUALITIES]
    map_values = list(presets.VIDEO_QUALITY_MAP.values())
    assert map_values == quality_values


def test_audio_formats_have_ext_and_label():
    for fmt in presets.AUDIO_FORMATS:
        assert "ext" in fmt
        assert "label" in fmt


def test_video_formats_have_ext_and_label():
    for fmt in presets.VIDEO_FORMATS:
        assert "ext" in fmt
        assert "label" in fmt


def test_audio_exts_match_audio_formats():
    expected = {f["ext"] for f in presets.AUDIO_FORMATS}
    assert presets.AUDIO_EXTS == expected


def test_video_exts_match_video_formats():
    expected = {f["ext"] for f in presets.VIDEO_FORMATS}
    assert presets.VIDEO_EXTS == expected
