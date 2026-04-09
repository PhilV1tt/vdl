from __future__ import annotations

import json
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_CACHE_PATH = Path.home() / ".config" / "vdl" / "update_check.json"
_API_URL = "https://api.github.com/repos/PhilV1tt/vdl/releases/latest"
_CHECK_INTERVAL_HOURS = 24
_FETCH_TIMEOUT = 3  # secondes

_check_thread: threading.Thread | None = None
_latest_version: str | None = None


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except ValueError:
        return (0,)


def _should_check() -> bool:
    if not _CACHE_PATH.exists():
        return True
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        last_check = datetime.fromisoformat(data["last_check"])
        elapsed_h = (datetime.now(tz=timezone.utc) - last_check).total_seconds() / 3600
        return elapsed_h >= _CHECK_INTERVAL_HOURS
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return True


def _load_cached_latest() -> str | None:
    try:
        data = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        value = data.get("latest")
        return str(value) if value else None
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def _fetch_latest_version() -> str | None:
    try:
        req = urllib.request.Request(
            _API_URL,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "vdl-updater/1"},
        )
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            return tag.lstrip("v") if tag else None
    except Exception:
        return None


def _save_cache(latest: str | None) -> None:
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(
            json.dumps(
                {
                    "last_check": datetime.now(tz=timezone.utc).isoformat(),
                    "latest": latest,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass


def _run_check(current: str) -> None:
    global _latest_version
    if _should_check():
        latest = _fetch_latest_version()
        _save_cache(latest)
    else:
        latest = _load_cached_latest()
    if latest and _parse_version(latest) > _parse_version(current):
        _latest_version = latest


def start_update_check(current_version: str) -> None:
    """Lance la vérification de mise à jour en arrière-plan."""
    global _check_thread
    _check_thread = threading.Thread(target=_run_check, args=(current_version,), daemon=True)
    _check_thread.start()


def get_update_notification() -> str | None:
    """Retourne un message si une mise à jour est disponible (attend max 0.5s)."""
    if _check_thread is not None:
        _check_thread.join(timeout=0.5)
    if _latest_version:
        from .i18n import t

        return t("update_available", version=_latest_version)
    return None


def get_latest_version() -> str | None:
    """Retourne la dernière version disponible si plus récente que l'actuelle."""
    if _check_thread is not None:
        _check_thread.join(timeout=0.5)
    return _latest_version


def do_update() -> None:
    """Lance la mise à jour via pipx ou pip."""
    import subprocess
    import sys

    from .i18n import t

    pipx = "pipx"
    try:
        result = subprocess.run([pipx, "list"], capture_output=True, text=True)
        if "vdl" in result.stdout:
            print(f"→ {t('update_pipx')}")
            try:
                subprocess.run([pipx, "upgrade", "vdl"], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Update failed: {e}", file=sys.stderr)
                return
            print(f"\n{t('update_yt_dlp')}")
            return
    except FileNotFoundError:
        pass
    print(f"→ {t('update_pip')}")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "vdl"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Update failed: {e}", file=sys.stderr)
