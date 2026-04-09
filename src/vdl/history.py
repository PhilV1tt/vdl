from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .tui import BOLD, CYAN, DIM, GREEN, RED, RESET

_HISTORY_PATH = Path.home() / ".local" / "share" / "vdl" / "history.jsonl"


def log_download(
    url: str,
    title: str,
    fmt: str,
    output_path: str,
    status: str,
) -> None:
    _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "url": url,
        "title": title,
        "format": fmt,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "output_path": output_path,
        "status": status,
    }
    with _HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def show_history(n: int = 20) -> None:
    if not _HISTORY_PATH.exists():
        print("Aucun historique de telechargement.")
        return
    lines = _HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    recent = lines[-n:]
    print(f"{BOLD}Derniers {len(recent)} telechargements{RESET}\n")
    for line in reversed(recent):
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "?")[:19].replace("T", " ")
            is_ok = entry.get("status") == "ok"
            status = f"{GREEN}ok {RESET}" if is_ok else f"{RED}err{RESET}"
            fmt = f"{CYAN}[{entry.get('format', '?')}]{RESET}"
            title = entry.get("title", entry.get("url", "?"))
            print(f"  {status}  {DIM}{ts}{RESET}  {fmt}  {title}")
        except json.JSONDecodeError:
            continue
