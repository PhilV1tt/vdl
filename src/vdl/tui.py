"""Terminal helpers for the command-line mode: ANSI colors, spinner, success line."""

from __future__ import annotations

import itertools
import os
import sys
import threading
import time

# ── Support ANSI Windows ───────────────────────────────────────────────────


def enable_ansi_windows() -> None:
    """Enable ANSI codes and copy-paste in the Windows terminal."""
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
    return sys.stdout.isatty() and "NO_COLOR" not in os.environ


def c(text: str, code: str) -> str:
    """Wrap text in an ANSI color code if the terminal supports it."""
    if not _supports_color():
        return text
    return f"{code}{text}{RESET}"


# ── Animations ─────────────────────────────────────────────────────────────


def success_flash(message: str) -> None:
    """Print the completed operation once."""
    print(c(f"  ✓  {message}", GREEN))


# ── Spinner ────────────────────────────────────────────────────────────────

_SPIN_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Spinner:
    """Animated spinner, used as a context manager."""

    def __init__(self, message: str) -> None:
        self._message = message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self) -> None:
        started = time.monotonic()
        for frame in itertools.cycle(_SPIN_FRAMES):
            if self._stop.is_set():
                break
            elapsed = time.monotonic() - started
            if "VDL_REDUCED_MOTION" in os.environ:
                frame = "·"
            timer = f"  {elapsed:.0f}s" if elapsed >= 2 else ""
            sys.stderr.write(f"\r{c(frame, CYAN)} {self._message}{timer}")
            sys.stderr.flush()
            self._stop.wait(0.08)
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()

    def __enter__(self) -> Spinner:
        if sys.stderr.isatty():
            self._thread.start()
        else:
            print(self._message, file=sys.stderr)
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        if self._thread.ident is not None:
            self._thread.join(timeout=1)
