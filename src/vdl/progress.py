from __future__ import annotations

import shutil
import sys

from .i18n import t
from .tui import CYAN, DIM, RESET

_GREEN = "\033[92m"
_LIVE_SPIN = ["◐", "◓", "◑", "◒"]


def _bar(pct: float, width: int = 20) -> str:
    filled = max(0, min(width, round(width * pct / 100)))
    return "█" * filled + "░" * (width - filled)


def _bar_colored(pct: float, width: int = 20) -> str:
    filled = max(0, min(width, round(width * pct / 100)))
    return f"{CYAN}{'█' * filled}{DIM}{'░' * (width - filled)}{RESET}"


class ProgressPrinter:
    def __init__(self) -> None:
        self.title: str = ""
        self.total_bytes: int = 0
        self._active: bool = False
        self._spin: int = 0

    def update(self, pct: float, speed_bps: float = 0, eta_sec: int = 0) -> None:
        self._active = True
        cols = shutil.get_terminal_size((80, 20)).columns
        bar = _bar_colored(pct)
        speed_str = f"  {speed_bps / 1024 / 1024:.1f} MiB/s" if speed_bps else ""
        eta_str = f"  ETA {int(eta_sec) // 60:02d}:{int(eta_sec) % 60:02d}" if eta_sec else ""
        size_str = f"  {self.total_bytes / 1024 / 1024:.1f} MiB" if self.total_bytes else ""
        title = (self.title[:34] + "…") if len(self.title) > 35 else self.title
        line = f"\r{title}  [{bar}] {CYAN}{pct:5.1f}%{RESET}{DIM}{size_str}{speed_str}{eta_str}{RESET}"
        sys.stderr.write(line[: cols - 1] + "\033[K")
        sys.stderr.flush()

    def update_live(
        self, downloaded_bytes: int, frag_index: int | None, frag_count: int | None, speed_bps: float = 0
    ) -> None:
        """Ligne de progression indéterminée (pas de total connu, ex : live en cours)."""
        self._active = True
        self._spin = (self._spin + 1) % len(_LIVE_SPIN)
        cols = shutil.get_terminal_size((80, 20)).columns
        spin = _LIVE_SPIN[self._spin]
        mib = downloaded_bytes / 1024 / 1024
        frag = f"  fragment {frag_index}" + (f"/{frag_count}" if frag_count else "") if frag_index else ""
        speed_str = f"  {speed_bps / 1024 / 1024:.1f} MiB/s" if speed_bps else ""
        title = (self.title[:34] + "…") if len(self.title) > 35 else self.title
        line = f"\r{title}  {CYAN}{spin}{RESET}  {mib:.1f} MiB{frag}{DIM}{speed_str}{RESET}"
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
