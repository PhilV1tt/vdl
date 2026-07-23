"""Mémoire des derniers choix explicites. Chaîne : explicite > mémoire > config > défaut.

Le format est retenu séparément côté audio et côté vidéo (video_format / audio_format)
pour qu'un choix fait en vidéo ne déteigne jamais sur l'audio, et inversement.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATE_PATH = Path.home() / ".local" / "share" / "vdl" / "state.json"


def recall() -> dict[str, Any]:
    """Charge les derniers choix explicites, ou {} si aucun."""
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
    """Résout qualité/format/dossier : explicite > mémoire > config > défaut."""
    fmt_key = "audio_format" if is_audio else "video_format"
    resolved_quality = quality or state.get("quality") or cfg.default_quality or "best"
    resolved_ext = fmt or state.get(fmt_key) or cfg.default_format or ("mp3" if is_audio else "mp4")
    resolved_output = output or state.get("output") or cfg.output_dir
    return resolved_quality, resolved_ext, resolved_output


def remember(is_audio: bool, *, quality: str | None = None, fmt: str | None = None, output: str | None = None) -> None:
    """Mémorise uniquement les choix explicites de cette exécution (jamais les défauts résolus)."""
    if not any((quality, fmt, output)):
        return
    state = recall()
    if quality:
        state["quality"] = quality
    if fmt:
        state["audio_format" if is_audio else "video_format"] = fmt
    if output:
        state["output"] = output
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def reset() -> bool:
    """Supprime la mémoire. Retourne True si un fichier existait."""
    if STATE_PATH.exists():
        STATE_PATH.unlink()
        return True
    return False
