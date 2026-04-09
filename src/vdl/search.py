from __future__ import annotations

import sys


def _fmt_duration(seconds: int | float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


def _fmt_views(n: int | None) -> str:
    if not n:
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M vues"
    if n >= 1_000:
        return f"{n // 1_000}K vues"
    return f"{n} vues"


SOURCES = {
    "youtube": "ytsearch",
    "soundcloud": "scsearch",
}


def search_videos(query: str, source: str = "youtube", n: int = 10) -> list[dict[str, object]]:
    """Cherche des vidéos via yt-dlp et retourne une liste de résultats."""
    import yt_dlp

    prefix = SOURCES.get(source, "ytsearch")
    search_url = f"{prefix}{n}:{query}"

    opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
    except Exception as e:
        print(f"❌  Erreur lors de la recherche : {e}", file=sys.stderr)
        return []

    entries = info.get("entries", []) if info else []
    results = []
    for entry in entries:
        if not entry:
            continue
        entry_url = entry.get("url") or entry.get("webpage_url") or entry.get("id", "")
        # For flat extraction, url may be just the video ID
        if entry_url and not str(entry_url).startswith("http") and source == "youtube":
            entry_url = f"https://www.youtube.com/watch?v={entry_url}"
        results.append(
            {
                "title": entry.get("title", "?"),
                "url": entry_url,
                "duration": entry.get("duration"),
                "uploader": entry.get("uploader") or entry.get("channel", ""),
                "view_count": entry.get("view_count"),
            }
        )
    return results


def format_result_label(r: dict[str, object], idx: int) -> str:
    """Formate un résultat pour l'affichage dans le menu."""
    title = str(r.get("title", "?"))
    dur = _fmt_duration(r.get("duration"))  # type: ignore[arg-type]
    uploader = str(r.get("uploader", ""))
    views = _fmt_views(r.get("view_count"))  # type: ignore[arg-type]

    parts = [f"{idx}. {title}"]
    meta = "  ".join(filter(None, [dur, uploader, views]))
    if meta:
        parts.append(f"   {meta}")
    return "\n".join(parts)
