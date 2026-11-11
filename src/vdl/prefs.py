"""Memory of the last explicit choices. Precedence: explicit > memory > config > default.

The format is remembered separately for audio and video (video_format / audio_format),
so a video choice never leaks into audio, and the other way round.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import presets

STATE_PATH = Path.home() / ".local" / "share" / "vdl" / "state.json"


def recall() -> dict[str, Any]:
    """Load the last explicit choices, or {} if there are none."""
    if not STATE_PATH.exists():
        return {}
    try:
        loaded: dict[str, Any] = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return loaded
    except (json.JSONDecodeError, OSError):
        return {}


def resolve(
    quality: str | None,
    fmt: str | None,
    output: str | None,
    is_audio: bool,
    state: dict[str, Any],
    cfg: Any,
) -> tuple[str, str, str]:
    """Resolve quality, format and folder: explicit > memory > config > default."""
    fmt_key = "audio_format" if is_audio else "video_format"
    valid_quality = {q["value"] for q in presets.AUDIO_QUALITIES} if is_audio else presets.QUALITY_KEYS
    remembered = state.get("audio_quality" if is_audio else "video_quality") or state.get("quality")
    default = "320" if is_audio else "best"
    resolved_quality = quality or (remembered if remembered in valid_quality else None)
    resolved_quality = resolved_quality or (cfg.default_quality if cfg.default_quality in valid_quality else default)
    formats = presets.AUDIO_EXTS if is_audio else presets.VIDEO_EXTS
    configured = cfg.default_format if cfg.default_format in formats else None
    resolved_ext = fmt or state.get(fmt_key) or configured or ("mp3" if is_audio else "mp4")
    resolved_output = output or state.get("output") or cfg.output_dir
    return resolved_quality, resolved_ext, resolved_output


def remember(is_audio: bool, *, quality: str | None = None, fmt: str | None = None, output: str | None = None) -> None:
    """Remember only the explicit choices of this run (never resolved defaults)."""
    if not any((quality, fmt, output)):
        return
    state = recall()
    state["mode"] = "audio" if is_audio else "video"
    if quality:
        state["audio_quality" if is_audio else "video_quality"] = quality
    if fmt:
        state["audio_format" if is_audio else "video_format"] = fmt
    if output:
        state["output"] = output
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def reset() -> bool:
    """Delete the memory file. Return True if one existed."""
    if STATE_PATH.exists():
        STATE_PATH.unlink()
        return True
    return False
