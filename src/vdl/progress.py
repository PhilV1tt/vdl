from __future__ import annotations

import shutil
import sys

from .i18n import t

_CYAN = "\033[96m"
_GREEN = "\033[92m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _bar(pct: float, width: int = 20) -> str:
    filled = round(width * pct / 100)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _bar_colored(pct: float, width: int = 20) -> str:
    filled = round(width * pct / 100)
    filled = max(0, min(width, filled))
    return f"{_CYAN}{'█' * filled}{_DIM}{'░' * (width - filled)}{_RESET}"


class ProgressPrinter:
    def __init__(self) -> None:
        self.title: str = ""
        self.total_bytes: int = 0
        self._active: bool = False

    def update(self, pct: float, speed_bps: float = 0, eta_sec: int = 0) -> None:
        self._active = True
        cols = shutil.get_terminal_size((80, 20)).columns
        bar = _bar_colored(pct)
        speed_str = f"  {speed_bps / 1024 / 1024:.1f} MiB/s" if speed_bps else ""
        eta_str = f"  ETA {int(eta_sec) // 60:02d}:{int(eta_sec) % 60:02d}" if eta_sec else ""
        size_str = f"  {self.total_bytes / 1024 / 1024:.1f} MiB" if self.total_bytes else ""
        title = (self.title[:34] + "…") if len(self.title) > 35 else self.title
        line = f"\r{title}  [{bar}] {_CYAN}{pct:5.1f}%{_RESET}{_DIM}{size_str}{speed_str}{eta_str}{_RESET}"
        sys.stderr.write(line[: cols - 1] + "\033[K")
        sys.stderr.flush()

    def converting(self) -> None:
        self._active = True
        sys.stderr.write(f"\r{t('converting')}\033[K")
        sys.stderr.flush()

    def done(self, message: str = "") -> None:
        if self._active:
            sys.stderr.write("\n")
            sys.stderr.flush()
            self._active = False
        if message:
            print(message)
