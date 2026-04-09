"""Helpers TUI basés sur questionary — navigation clavier cross-platform."""

from __future__ import annotations

import sys

# ── Support ANSI Windows ───────────────────────────────────────────────────


def enable_ansi_windows() -> None:
    """Active les codes ANSI dans le terminal Windows (VTP)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import ctypes.wintypes

        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = ctypes.wintypes.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass


# ── Style questionary ──────────────────────────────────────────────────────

try:
    from questionary import Style as _QStyle

    _STYLE: _QStyle | None = _QStyle(
        [
            ("qmark", "fg:#5f87ff bold"),
            ("question", "bold"),
            ("answer", "fg:#5fffaf bold"),
            ("pointer", "fg:#5f87ff bold"),
            ("highlighted", "fg:#5f87ff bold"),
            ("selected", "fg:#5fffaf"),
            ("separator", "fg:#444444"),
            ("instruction", "fg:#888888"),
        ]
    )
except ImportError:
    _STYLE = None


# ── Wrappers publics ───────────────────────────────────────────────────────


def select(
    message: str,
    choices: list[str] | list[dict[str, str]],
    default: str | None = None,
) -> str | None:
    """Menu avec navigation flèches. Retourne la valeur choisie ou None si annulé."""
    try:
        import questionary

        result: str | None = questionary.select(message, choices=choices, default=default, style=_STYLE).ask()
        return result
    except (ImportError, KeyboardInterrupt):
        return None


def text(message: str, default: str = "") -> str | None:
    """Saisie texte avec historique clavier. Retourne None si annulé."""
    try:
        import questionary

        result: str | None = questionary.text(message, default=default, style=_STYLE).ask()
        return result
    except (ImportError, KeyboardInterrupt):
        return None


def confirm(message: str, default: bool = True) -> bool:
    """Confirmation oui/non. Retourne True si oui."""
    try:
        import questionary

        result: bool | None = questionary.confirm(message, default=default, style=_STYLE).ask()
        return bool(result) if result is not None else False
    except (ImportError, KeyboardInterrupt):
        return False


def autocomplete(message: str, choices: list[str], default: str = "") -> str | None:
    """Saisie avec autocomplétion. Retourne None si annulé."""
    try:
        import questionary

        result: str | None = questionary.autocomplete(message, choices=choices, default=default, style=_STYLE).ask()
        return result
    except (ImportError, KeyboardInterrupt):
        return None


def is_available() -> bool:
    """Retourne True si questionary est installé."""
    try:
        import questionary  # noqa: F401

        return True
    except ImportError:
        return False
