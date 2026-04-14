AUDIO_FORMATS = [
    {"label": "MP3", "ext": "mp3"},
    {"label": "M4A", "ext": "m4a"},
    {"label": "WAV", "ext": "wav"},
    {"label": "FLAC", "ext": "flac"},
    {"label": "OGG", "ext": "ogg"},
    {"label": "AAC", "ext": "aac"},
    {"label": "OPUS", "ext": "opus"},
]

VIDEO_FORMATS = [
    {"label": "MP4", "ext": "mp4"},
    {"label": "MKV", "ext": "mkv"},
    {"label": "WEBM", "ext": "webm"},
    {"label": "AVI", "ext": "avi"},
    {"label": "MOV", "ext": "mov"},
]

VIDEO_QUALITIES = [
    {"label": "Meilleure qualité", "value": "bestvideo+bestaudio/best"},
    {"label": "4K (2160p)", "value": "bestvideo[height<=2160]+bestaudio/best[height<=2160]"},
    {"label": "2K (1440p)", "value": "bestvideo[height<=1440]+bestaudio/best[height<=1440]"},
    {"label": "1080p", "value": "bestvideo[height<=1080]+bestaudio/best[height<=1080]"},
    {"label": "720p", "value": "bestvideo[height<=720]+bestaudio/best[height<=720]"},
    {"label": "480p", "value": "bestvideo[height<=480]+bestaudio/best[height<=480]"},
    {"label": "360p", "value": "bestvideo[height<=360]+bestaudio/best[height<=360]"},
]

AUDIO_QUALITIES = [
    {"label": "320 kbps (max)", "value": "320"},
    {"label": "256 kbps", "value": "256"},
    {"label": "192 kbps", "value": "192"},
    {"label": "128 kbps", "value": "128"},
]

# Derived from VIDEO_QUALITIES - single source of truth
_QUALITY_KEYS = ["best", "2160", "1440", "1080", "720", "480", "360"]
VIDEO_QUALITY_MAP: dict[str, str] = {key: VIDEO_QUALITIES[i]["value"] for i, key in enumerate(_QUALITY_KEYS)}

AUDIO_EXTS: set[str] = {f["ext"] for f in AUDIO_FORMATS}
VIDEO_EXTS: set[str] = {f["ext"] for f in VIDEO_FORMATS}
ALL_EXTS: set[str] = AUDIO_EXTS | VIDEO_EXTS


def build_quality_selector(is_audio: bool, quality_key: str = "best") -> tuple[str, str]:
    """Retourne (quality_selector, audio_kbps) pour yt-dlp."""
    if is_audio:
        return "bestaudio/best", "320"
    return VIDEO_QUALITY_MAP.get(quality_key, "bestvideo+bestaudio/best"), "0"
