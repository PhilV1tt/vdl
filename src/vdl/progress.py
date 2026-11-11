from __future__ import annotations

import os
import shutil
import sys

from .i18n import t
from .tui import CYAN, GREEN, c

_LIVE_SPIN = ["◐", "◓", "◑", "◒"]


def _bar(pct: float, width: int = 20) -> str:
    filled = max(0, min(width, round(width * pct / 100)))
    return "█" * filled + "░" * (width - filled)


class ProgressPrinter:
    def __init__(self) -> None:
        self.title: str = ""
        self.total_bytes: int = 0
        self._active: bool = False
        self._spin: int = 0

    def update(self, pct: float, speed_bps: float = 0, eta_sec: int = 0) -> None:
        if not sys.stderr.isatty():
            if not self._active:
                print("Downloading…", file=sys.stderr)
            self._active = True
            return
        self._active = True
        self._spin = (self._spin + 1) % len(_LIVE_SPIN)
        cols = shutil.get_terminal_size((80, 20)).columns
        width = max(6, min(24, cols // 4))
        bar = _bar(pct, width)
        speed = f"  {speed_bps / 1024 / 1024:.1f} MiB/s" if speed_bps else ""
        eta = f"  reste {int(eta_sec) // 60:02d}:{int(eta_sec) % 60:02d}" if eta_sec and cols >= 60 else ""
        suffix = f"  {pct:5.1f}%{speed}{eta}"
        available = max(0, cols - width - len(suffix) - 9)
        title = self.title[:available]
        frame = "↓" if "VDL_REDUCED_MOTION" in os.environ else _LIVE_SPIN[self._spin]
        line = f"{c(frame, CYAN)} {title}  {c(bar, CYAN)}{suffix}"
        sys.stderr.write(f"\r{line}\033[K")
        sys.stderr.flush()

    def update_live(
        self, downloaded_bytes: int, frag_index: int | None, frag_count: int | None, speed_bps: float = 0
    ) -> None:
        """Indeterminate progress line (no known total, e.g. a live stream in progress)."""
        if not sys.stderr.isatty():
            if not self._active:
                print("Enregistrement en direct…", file=sys.stderr)
            self._active = True
            return
        self._active = True
        self._spin = (self._spin + 1) % len(_LIVE_SPIN)
        cols = shutil.get_terminal_size((80, 20)).columns
        spin = "●" if "VDL_REDUCED_MOTION" in os.environ else _LIVE_SPIN[self._spin]
        mib = downloaded_bytes / 1024 / 1024
        frag = f"  fragment {frag_index}" + (f"/{frag_count}" if frag_count else "") if frag_index else ""
        speed = f"  {speed_bps / 1024 / 1024:.1f} MiB/s" if speed_bps else ""
        suffix = f"  {mib:.1f} MiB{frag}{speed}"
        available = max(0, cols - len(suffix) - 6)
        line = f"{c(spin, CYAN)} {self.title[:available]}{suffix}"
        sys.stderr.write(f"\r{line}\033[K")
        sys.stderr.flush()

    def converting(self) -> None:
        self._active = True
        if not sys.stderr.isatty():
            print(t("converting"), file=sys.stderr)
            return
        sys.stderr.write(f"\r{c('◌', CYAN)} Assemblage / conversion…\033[K")
        sys.stderr.flush()

    def done(self, message: str = "") -> None:
        if self._active and sys.stderr.isatty():
            sys.stderr.write("\n")
            sys.stderr.flush()
        self._active = False
        if message:
            print(c(message, GREEN))
