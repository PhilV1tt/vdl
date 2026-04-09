from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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
        print("Aucun historique de téléchargement.")
        return
    lines = _HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    recent = lines[-n:]
    print(f"Derniers {len(recent)} téléchargements :\n")
    for line in reversed(recent):
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "?")[:19].replace("T", " ")
            status = "ok " if entry.get("status") == "ok" else "err"
            print(f"  {status}  {ts}  [{entry.get('format', '?')}]  {entry.get('title', entry.get('url', '?'))}")
        except json.JSONDecodeError:
            continue
