"""Helpers TUI basés sur questionary - navigation clavier cross-platform."""

from __future__ import annotations

import itertools
import sys
import threading
import time

# ── Support ANSI Windows ───────────────────────────────────────────────────


def enable_ansi_windows() -> None:
    """Active les codes ANSI et le copier-coller dans le terminal Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        import ctypes.wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        # Enable ANSI escape codes on stdout
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle_out = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode_out = ctypes.wintypes.DWORD()
        if kernel32.GetConsoleMode(handle_out, ctypes.byref(mode_out)):
            kernel32.SetConsoleMode(handle_out, mode_out.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

        # Enable QuickEdit mode on stdin so Ctrl+V / right-click paste works in cmd.exe
        STD_INPUT_HANDLE = -10
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080
        handle_in = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        mode_in = ctypes.wintypes.DWORD()
        if kernel32.GetConsoleMode(handle_in, ctypes.byref(mode_in)):
            kernel32.SetConsoleMode(handle_in, mode_in.value | ENABLE_EXTENDED_FLAGS | ENABLE_QUICK_EDIT_MODE)
    except Exception:
        pass


# ── Couleurs ANSI ─────────────────────────────────────────────────────────

CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
WHITE = "\033[97m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(text: str, code: str) -> str:
    """Enveloppe text avec un code couleur ANSI si le terminal le supporte."""
    if not _supports_color():
        return text
    return f"{code}{text}{RESET}"


# ── Animations ─────────────────────────────────────────────────────────────


def clear_screen() -> None:
    """Efface le terminal (seulement si TTY)."""
    if _supports_color():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def type_print(text: str, prefix: str = "", delay: float = 0.025) -> None:
    """Effet machine à écrire. Dégradé vers plain print si pas TTY."""
    if not _supports_color():
        print(prefix + text)
        return
    if prefix:
        sys.stdout.write(prefix)
        sys.stdout.flush()
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def animate_separator(width: int = 44, color: str = "") -> None:
    """Trace une ligne ─ caractère par caractère."""
    col = color if color else DIM
    if not _supports_color():
        print(f"  {'─' * width}")
        return
    sys.stdout.write(f"  {col}")
    for _ in range(width):
        sys.stdout.write("─")
        sys.stdout.flush()
        time.sleep(0.004)
    sys.stdout.write(f"{RESET}\n")
    sys.stdout.flush()


def success_flash(message: str) -> None:
    """Affiche un message de succès avec un flash blanc → vert."""
    if not _supports_color():
        print(f"  ✓  {message}")
        return
    # Flash blanc vif d'abord
    sys.stdout.write(f"  {BOLD}{WHITE}✓  {message}{RESET}\n")
    sys.stdout.flush()
    time.sleep(0.12)
    # Remplacer par vert
    sys.stdout.write(f"\033[1A\r  {BOLD}{GREEN}✓  {message}{RESET}\n")
    sys.stdout.flush()


def fade_out(message: str, color: str = "") -> None:
    """Affiche un message qui s'estompe (bold → dim)."""
    col = color if color else CYAN
    if not _supports_color():
        print(f"  {message}")
        return
    sys.stdout.write(f"  {BOLD}{col}{message}{RESET}\n")
    sys.stdout.flush()
    time.sleep(0.15)
    sys.stdout.write(f"\033[1A\r  {DIM}{message}{RESET}\n")
    sys.stdout.flush()


# ── Spinner ────────────────────────────────────────────────────────────────

_SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Spinner:
    """Spinner animé à utiliser comme context manager."""

    def __init__(self, message: str) -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self) -> None:
        for frame in itertools.cycle(_SPIN_FRAMES):
            if self._stop.is_set():
                break
            sys.stderr.write(f"\r{CYAN}{frame}{RESET} {self._message}")
            sys.stderr.flush()
            time.sleep(0.08)
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def __enter__(self) -> Spinner:
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=1)


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
            ("separator", "fg:#666666"),
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
