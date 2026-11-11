from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_CACHE_PATH = Path.home() / ".config" / "vdl" / "update_check.json"
_API_URL = "https://api.github.com/repos/PhilV1tt/vdl/releases/latest"
_YTDLP_CACHE_PATH = Path.home() / ".config" / "vdl" / "ytdlp_check.json"
_YTDLP_API_URL = "https://pypi.org/pypi/yt-dlp/json"
_PIP_TIMEOUT = 180  # seconds
_CHECK_INTERVAL_HOURS = 24
_FETCH_TIMEOUT = 3  # seconds

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
    """Start the update check in the background."""
    global _check_thread
    _check_thread = threading.Thread(target=_run_check, args=(current_version,), daemon=True)
    _check_thread.start()


def get_update_notification() -> str | None:
    """Return a message if an update is available (waits at most 0.5 s)."""
    if _check_thread is not None:
        _check_thread.join(timeout=0.5)
    if _latest_version:
        from .i18n import t

        return t("update_available", version=_latest_version)
    return None


def get_latest_version() -> str | None:
    """Return the latest version if it is newer than the current one."""
    if _check_thread is not None:
        _check_thread.join(timeout=0.5)
    return _latest_version


def do_update() -> None:
    """Update vdl with pipx or pip."""
    from .i18n import t

    pipx = "pipx"
    try:
        result = subprocess.run([pipx, "list"], capture_output=True, text=True)
        if "vdl" in result.stdout:
            print(f"→ {t('update_pipx')}", flush=True)
            try:
                subprocess.run([pipx, "upgrade", "vdl"], check=True)
            except subprocess.CalledProcessError as e:
                print(f"Update failed: {e}", file=sys.stderr)
                return
            upgrade_ytdlp()
            return
    except FileNotFoundError:
        pass
    print(f"→ {t('update_pip')}", flush=True)
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "vdl", "yt-dlp"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Update failed: {e}", file=sys.stderr)


def _installed_ytdlp_version() -> str | None:
    try:
        from yt_dlp.version import __version__
    except ImportError:
        return None
    return str(__version__)


def _latest_ytdlp_version() -> str | None:
    try:
        req = urllib.request.Request(_YTDLP_API_URL, headers={"User-Agent": "vdl-updater/1"})
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            return str(json.loads(resp.read())["info"]["version"])
    except Exception:
        return None


def _upgrade_commands() -> list[list[str]]:
    """Install commands to try, in order: pip (pipx, venv, system) then uv (uv tool, uv venv)."""
    pip = [sys.executable, "-m", "pip", "install", "--upgrade", "--quiet", "yt-dlp"]
    uv = shutil.which("uv")
    uv_cmd = [uv, "pip", "install", "--python", sys.executable, "--upgrade", "--quiet", "yt-dlp"] if uv else None
    has_pip = importlib.util.find_spec("pip") is not None
    # uv tool and uv-created venvs have no pip: try uv first
    cmds = [pip, uv_cmd] if has_pip else [uv_cmd, pip]
    return [c for c in cmds if c]


def upgrade_ytdlp() -> bool:
    """Upgrade yt-dlp in the environment that runs vdl (pipx, uv, venv or pip). Silent."""
    for cmd in _upgrade_commands():
        try:
            if subprocess.run(cmd, capture_output=True, timeout=_PIP_TIMEOUT).returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def auto_update_ytdlp() -> None:
    """At most once every 24 h: install the latest yt-dlp if the installed one is older.

    No output and no error: on failure (network, permissions) vdl keeps the installed version.
    Call before the first import of yt_dlp.
    """
    if os.environ.get("VDL_NO_AUTO_UPDATE"):
        return
    try:
        data = json.loads(_YTDLP_CACHE_PATH.read_text(encoding="utf-8"))
        elapsed_h = (datetime.now(tz=timezone.utc) - datetime.fromisoformat(data["last_check"])).total_seconds() / 3600
        if elapsed_h < _CHECK_INTERVAL_HOURS:
            return
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        pass
    current, latest = _installed_ytdlp_version(), _latest_ytdlp_version()
    if latest is None:
        return  # no network: retry on the next launch
    if current is not None and _parse_version(latest) > _parse_version(current) and not upgrade_ytdlp():
        return
    try:
        _YTDLP_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _YTDLP_CACHE_PATH.write_text(
            json.dumps({"last_check": datetime.now(tz=timezone.utc).isoformat()}), encoding="utf-8"
        )
    except OSError:
        pass
