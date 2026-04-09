AUDIO_FORMATS = [
    {"label": "MP3",  "ext": "mp3"},
    {"label": "M4A",  "ext": "m4a"},
    {"label": "WAV",  "ext": "wav"},
    {"label": "FLAC", "ext": "flac"},
    {"label": "OGG",  "ext": "ogg"},
    {"label": "AAC",  "ext": "aac"},
    {"label": "OPUS", "ext": "opus"},
]

VIDEO_FORMATS = [
    {"label": "MP4",  "ext": "mp4"},
    {"label": "MKV",  "ext": "mkv"},
    {"label": "WEBM", "ext": "webm"},
    {"label": "AVI",  "ext": "avi"},
    {"label": "MOV",  "ext": "mov"},
]

VIDEO_QUALITIES = [
    {"label": "Meilleure qualité", "value": "bestvideo+bestaudio/best"},
    {"label": "4K (2160p)",        "value": "bestvideo[height<=2160]+bestaudio/best[height<=2160]"},
    {"label": "2K (1440p)",        "value": "bestvideo[height<=1440]+bestaudio/best[height<=1440]"},
    {"label": "1080p",             "value": "bestvideo[height<=1080]+bestaudio/best[height<=1080]"},
    {"label": "720p",              "value": "bestvideo[height<=720]+bestaudio/best[height<=720]"},
    {"label": "480p",              "value": "bestvideo[height<=480]+bestaudio/best[height<=480]"},
    {"label": "360p",              "value": "bestvideo[height<=360]+bestaudio/best[height<=360]"},
]

AUDIO_QUALITIES = [
    {"label": "320 kbps (max)", "value": "320"},
    {"label": "256 kbps",       "value": "256"},
    {"label": "192 kbps",       "value": "192"},
    {"label": "128 kbps",       "value": "128"},
]

VIDEO_QUALITY_MAP = {
    "best": "bestvideo+bestaudio/best",
    "2160": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
}

AUDIO_EXTS = {f["ext"] for f in AUDIO_FORMATS}
VIDEO_EXTS = {f["ext"] for f in VIDEO_FORMATS}
