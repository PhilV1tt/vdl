"""List the links of a channel or playlist without downloading."""

from __future__ import annotations

from typing import Any

_YOUTUBE_TABS = ("/videos", "/shorts", "/streams", "/playlists", "/featured", "/live")
_CHANNEL_MARKERS = ("/@", "/channel/", "/c/", "/user/")


def normalize_channel_url(target: str) -> str:
    """Normalize a channel/playlist input into a URL that yt-dlp can list.

    - '@handle'                     -> https://www.youtube.com/@handle/videos
    - 'youtube.com/@handle'         -> https://www.youtube.com/@handle/videos
    - URL already on a tab or playlist -> unchanged
    """
    target = target.strip()

    # bare @handle -> YouTube channel URL
    if target.startswith("@"):
        return f"https://www.youtube.com/{target}/videos"

    if not target.startswith(("http://", "https://")):
        target = "https://" + target

    lower = target.lower()
    is_youtube = "youtube.com" in lower or "youtu.be" in lower

    # YouTube channel page without a tab -> target the videos tab
    if (
        is_youtube
        and any(marker in lower for marker in _CHANNEL_MARKERS)
        and "list=" not in lower
        and not any(tab in lower for tab in _YOUTUBE_TABS)
    ):
        target = target.rstrip("/") + "/videos"

    return target


def is_channel_target(raw: str) -> bool:
    """True if the input points to a whole channel/playlist rather than a single video."""
    raw = raw.strip()
    if raw.startswith("@"):
        return True
    lower = raw.lower()
    if "youtube.com" not in lower and "youtu.be" not in lower:
        return False
    if "list=" in lower or "watch?v=" in lower or "youtu.be/" in lower:
        return False
    return any(marker in lower for marker in _CHANNEL_MARKERS) or any(tab in lower for tab in _YOUTUBE_TABS)


def extract_links(target: str) -> list[str]:
    """Return the URLs of all videos of a channel/playlist, downloading nothing."""
    import yt_dlp

    url = normalize_channel_url(target)
    opts: dict[str, Any] = {
        "extract_flat": "in_playlist",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        return []

    entries = info.get("entries")
    if entries is None:
        # Single video passed directly
        single = info.get("webpage_url") or info.get("url")
        return [single] if single else []

    urls: list[str] = []
    for entry in entries:
        if not entry:
            continue
        link = entry.get("url") or entry.get("webpage_url")
        if link:
            urls.append(link)
    return urls
