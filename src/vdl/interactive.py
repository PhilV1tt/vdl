"""Interactive mode: a download queue under an input line that is always ready. Run: vdl

Pasting a link starts the download at once with the settings shown on screen, and the next
link can be pasted while it runs. Text that is not a link searches YouTube; a local file path
converts the file. Settings change only while the input line is empty: Tab audio/video,
up/down the format, left/right the quality. Finished items are printed above the screen.

prompt_toolkit draws the screen; yt-dlp and ffmpeg run in worker threads (MAX_PARALLEL).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.processors import BeforeInput
from prompt_toolkit.output import ColorDepth
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.shortcuts import print_formatted_text

from . import __version__, prefs, presets
from .config import load_config
from .convert import is_local_target, local_path
from .downloader import Cancelled, Downloader
from .links import is_channel_target, normalize_channel_url

MAX_PARALLEL = 3
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
LOSSLESS = ("flac", "wav")
QUIT_WINDOW = 3.0  # s to confirm quitting while items run


@dataclass
class Job:
    """One queued item: a URL to download or a local file to convert."""

    target: str
    is_audio: bool
    ext: str
    quality: str
    output_dir: str
    music: bool = False
    section: str | None = None
    title: str = ""
    status: str = "queued"  # queued, running, converting
    pct: float | None = None
    speed: float = 0.0  # bytes/s
    eta: int = 0  # s
    size: int = 0  # bytes received, when the total is unknown (live)
    cancel: threading.Event = field(default_factory=threading.Event)


@dataclass
class State:
    """Everything the screen shows. Workers write job fields; the UI thread reads them."""

    cfg: Any
    is_audio: bool = False
    video: dict[str, str] = field(default_factory=dict)  # {"ext", "quality"}
    audio: dict[str, str] = field(default_factory=dict)
    output_dir: str = ""
    music: bool = False
    jobs: list[Job] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)  # last search
    searching: str = ""
    notice: str = ""
    last_file: Path | None = None
    clipboard: str = ""
    seen: set[str] = field(default_factory=set)  # targets already queued this session
    folder_edit: bool = False
    quit_armed_at: float = -1e9  # monotonic s
    lock: threading.Lock = field(default_factory=threading.Lock)
    pool: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(MAX_PARALLEL))
    app: Application[None] | None = None

    @property
    def mode(self) -> dict[str, str]:
        return self.audio if self.is_audio else self.video

    def refresh(self) -> None:
        if self.app is not None:
            self.app.invalidate()


def new_state(cfg: Any) -> State:
    memory = prefs.recall()
    v_quality, v_ext, output = prefs.resolve(None, None, None, False, memory, cfg)
    a_quality, a_ext, _ = prefs.resolve(None, None, None, True, memory, cfg)
    return State(
        cfg=cfg,
        is_audio=memory.get("mode") == "audio",
        video={"ext": v_ext, "quality": v_quality},
        audio={"ext": a_ext, "quality": a_quality},
        output_dir=output,
        music=cfg.music,
    )


# ── What the input line means ───────────────────────────────────────────────


def classify(raw: str) -> str:
    """'command', 'file', 'url' or 'search'."""
    if raw.startswith("/") and " " not in raw and raw.count("/") == 1 and not local_path(raw).exists():
        return "command"
    if is_local_target(raw):
        return "file"
    if raw.startswith(("http://", "https://", "@")) or ("." in raw.split("/")[0] and " " not in raw):
        return "url"
    return "search"


def split_section(raw: str) -> tuple[str, str | None]:
    """'URL 12:00-14:30' -> ('URL', '12:00-14:30'): an excerpt typed after the link."""
    head, _, tail = raw.rpartition(" ")
    if head and "-" in tail and all(part.replace(":", "").replace(".", "").isdigit() for part in tail.split("-", 1)):
        return head.strip(), tail
    return raw, None


def clipboard_url() -> str:
    """The URL in the clipboard, or ''. macOS only (pbpaste is instant)."""
    if sys.platform != "darwin" or not shutil.which("pbpaste"):
        return ""
    try:
        text = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=1).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    return text if text.startswith(("http://", "https://")) and "\n" not in text and " " not in text else ""


# ── Queue and workers ───────────────────────────────────────────────────────


def enqueue(state: State, target: str, section: str | None = None) -> Job:
    """Queue `target` with the settings on screen and remember them for the next run."""
    mode = state.mode
    job = Job(
        target=target,
        is_audio=state.is_audio,
        ext=mode["ext"],
        quality=mode["quality"],
        output_dir=state.output_dir,
        music=state.music and state.is_audio,
        section=section,
        title=local_path(target).name if is_local_target(target) else "",
    )
    with state.lock:
        state.jobs.append(job)
        state.seen.add(target)
    prefs.remember(state.is_audio, quality=mode["quality"], fmt=mode["ext"], output=state.output_dir)
    state.pool.submit(run_job, state, job)
    state.refresh()
    return job


def run_job(state: State, job: Job) -> None:
    """Worker thread: run one job, then print its outcome above the screen."""
    job.status = "running"
    state.refresh()
    try:
        path, error = convert_job(job) if is_local_target(job.target) else download_job(state, job)
    except Exception as e:  # a worker must never die silently
        path, error = None, f"{type(e).__name__}: {e}"
    with state.lock:
        state.jobs.remove(job)
        if path is not None:
            state.last_file = path
    name = job.title or job.target
    if path is not None:
        size = f"{path.stat().st_size / 1e6:.1f} MB" if path.exists() else ""
        print_line([("fg:ansigreen", "  ✓ "), ("bold", name), ("", f"  {size}  "), ("fg:ansibrightblack", str(path))])
    elif not job.cancel.is_set():
        print_line([("fg:ansired", "  ✗ "), ("bold", name), ("", "  "), ("fg:ansired", error.replace("\n", " "))])
    state.refresh()


def download_job(state: State, job: Job) -> tuple[Path | None, str]:
    cfg = state.cfg
    url = normalize_channel_url(job.target)
    selector, kbps = presets.build_quality_selector(job.is_audio, job.quality)
    dl = Downloader(
        output_dir=job.output_dir,
        playlist=is_channel_target(job.target),
        embed_thumbnail=cfg.embed_thumbnail,
        sponsorblock=cfg.sponsorblock,
        subs=cfg.subs,
        subs_lang=cfg.subs_lang,
        output_template=cfg.output_template,
        retries=cfg.retries,
        sections=[job.section] if job.section else None,
        concurrent_fragments=cfg.concurrent_fragments,
        use_aria2c=cfg.aria2c,
    )

    def report(event: dict[str, Any]) -> None:
        if job.cancel.is_set():
            raise Cancelled
        if "title" in event:
            job.title = event["title"] + ("  ● LIVE" if event.get("live") else "")
        if "pct" in event:
            job.pct, job.speed, job.eta = event["pct"], event["speed"], int(event["eta"])
        if "bytes" in event:
            job.pct, job.size, job.speed = None, event["bytes"], event["speed"]
        if event.get("converting"):
            job.status = "converting"
        state.refresh()

    result = dl.download(url, job.ext, job.is_audio, selector, kbps, report=report)
    if result.exit_code != 0:
        return None, result.error or "download failed"
    if result.file_path is None:  # a playlist: several files, no single path
        return Path(job.output_dir), ""
    if job.music and result.file_path is not None:
        job.status = "converting"
        state.refresh()
        import_to_music(result.file_path, result.info)
    return result.file_path, ""


def convert_job(job: Job) -> tuple[Path | None, str]:
    from .convert import convert_one, output_path

    src = local_path(job.target)
    if not src.is_file():
        return None, f"no such file: {src}"
    dst = output_path(src, job.ext, None)
    job.status = "converting"
    try:
        convert_one(src, dst, job.ext, job.quality)
    except (RuntimeError, OSError) as e:
        return None, str(e)
    return dst, ""


def import_to_music(path: Path, info: dict[str, Any]) -> None:
    """Tag from MusicBrainz and add to Apple Music, silently (the screen owns the terminal)."""
    from .music import _auto_install_deps, import_to_music_app, lookup_metadata, write_tags

    if _auto_install_deps():
        title = str(info.get("title") or path.stem)
        write_tags(path, lookup_metadata(title, str(info.get("uploader") or "")))
    import_to_music_app(path)


def search(state: State, query: str) -> None:
    """Worker thread: YouTube search; results appear as a numbered list."""
    from .search import search_videos

    state.searching, state.results = query, []
    state.refresh()
    results = search_videos(query, n=9)
    state.searching, state.results = "", results
    state.notice = "" if results else f"No result for “{query}”."
    state.refresh()


def print_line(fragments: list[tuple[str, str]]) -> None:
    """Print above the screen (patch_stdout keeps the screen below)."""
    print_formatted_text(FormattedText(fragments))


def reveal(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(path)], check=False)
    elif sys.platform == "win32":
        subprocess.run(["explorer", f"/select,{path}"], check=False)
    else:
        subprocess.run(["xdg-open", str(path.parent)], check=False)


# ── Screen ──────────────────────────────────────────────────────────────────

ACCENT = "fg:ansicyan bold"
ACTIVE = "bg:ansicyan fg:ansiblack bold"
HINT = "fg:ansibrightblack"


def _fmt_eta(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def _choice_row(label: str, values: list[str], current: str, keys: str) -> list[tuple[str, str]]:
    row: list[tuple[str, str]] = [(HINT, f"  {label:<9}")]
    for value in values:
        row += [(ACTIVE if value == current else "", f" {value} "), ("", " ")]
    return [*row, (HINT, f"  {keys}\n")]


def render_settings(state: State) -> list[tuple[str, str]]:
    mode = state.mode
    out: list[tuple[str, str]] = [
        (ACCENT, "  vdl "),
        (HINT, f"{__version__}   "),
        (ACTIVE if not state.is_audio else HINT, " VIDEO "),
        ("", " "),
        (ACTIVE if state.is_audio else HINT, " AUDIO "),
        (HINT, "  Tab\n"),
    ]
    formats = [f["ext"] for f in (presets.AUDIO_FORMATS if state.is_audio else presets.VIDEO_FORMATS)]
    out += _choice_row("format", formats, mode["ext"], "↑↓")
    if state.is_audio and mode["ext"] in LOSSLESS:
        out += [(HINT, "  quality  "), ("", " lossless\n")]
    else:
        qualities = [q["value"] for q in presets.AUDIO_QUALITIES] if state.is_audio else presets.QUALITY_KEYS
        out += _choice_row("quality", qualities, mode["quality"], "←→")
    out += [(HINT, "  folder   "), ("", f" {state.output_dir.replace(str(Path.home()), '~')}"), (HINT, "  ^O")]
    if state.is_audio and sys.platform == "darwin":
        out += [
            (HINT, "   Apple Music "),
            (ACCENT if state.music else HINT, "on" if state.music else "off"),
            (HINT, " ^E"),
        ]
    return [*out, ("", "\n")]


def render_jobs(state: State) -> list[tuple[str, str]]:
    frame = "·" if "VDL_REDUCED_MOTION" in os.environ else SPIN[int(time.monotonic() * 10) % len(SPIN)]
    out: list[tuple[str, str]] = []
    with state.lock:
        jobs = list(state.jobs)
    width = shutil.get_terminal_size((80, 20)).columns
    for job in jobs:
        name = (job.title or job.target)[: max(10, width - 48)]
        if job.status == "queued":
            out += [(HINT, f"  · waiting  {name}\n")]
        elif job.status == "converting":
            out += [(ACCENT, f"  {frame} "), ("", f"{name}  "), (HINT, "converting…\n")]
        elif job.pct is None and job.size:
            out += [(ACCENT, f"  {frame} "), ("", f"{name}  {job.size / 1e6:.1f} MB  {job.speed / 1e6:.1f} MB/s\n")]
        elif job.pct is None:
            out += [(ACCENT, f"  {frame} "), ("", f"{name}  "), (HINT, "reading the link…\n")]
        else:
            filled = round(job.pct / 10)
            bar = "█" * filled + "░" * (10 - filled)
            out += [
                (ACCENT, f"  {frame} "),
                ("", f"{name}  "),
                (ACCENT, bar),
                ("", f" {job.pct:3.0f}%  {job.speed / 1e6:.1f} MB/s  {_fmt_eta(job.eta)}\n"),
            ]
    if state.searching:
        out += [(ACCENT, f"  {frame} "), ("", f"searching “{state.searching}”…\n")]
    from .search import _fmt_duration

    for i, result in enumerate(state.results[:9], 1):
        duration = _fmt_duration(result.get("duration"))  # type: ignore[arg-type]
        queued = result["url"] in state.seen
        out += [
            (ACCENT, f"  {i} "),
            (HINT if queued else "", f"{str(result.get('title', '?'))[: width - 24]}"),
            (HINT, f"  {duration}{'  ✓ queued' if queued else ''}\n"),
        ]
    if state.results:
        out += [(HINT, "  1-9 download (several allowed)   Esc close\n")]
    return out


def render_footer(state: State, text: str) -> list[tuple[str, str]]:
    if state.notice:
        return [("fg:ansiyellow", f"  {state.notice}")]
    if state.folder_edit:
        return [(HINT, "  ↵ save folder   Esc cancel")]
    if not text and state.clipboard and state.clipboard not in state.seen:
        return [(HINT, "  ↵ download the link in the clipboard  "), ("", state.clipboard[:60])]
    parts = "  paste a link · type to search · drop a file to convert"
    if state.last_file is not None:
        parts += " · ^R show last file"
    return [(HINT, parts + " · ^D quit")]


def build_app(state: State) -> Application[None]:
    buffer = Buffer(multiline=False)
    keys = KeyBindings()
    empty = Condition(lambda: not buffer.text and not state.folder_edit)

    def say(message: str) -> None:
        state.notice = message

    def submit(raw: str) -> None:
        raw = raw.strip()
        if not raw:
            url = clipboard_url()  # read again: it may have changed since startup
            if url and url not in state.seen:
                enqueue(state, url)
            return
        kind = classify(raw)
        if kind == "command":
            if raw in ("/q", "/quit"):
                request_quit(state.app)
            elif raw == "/history":
                from .history import show_history

                show_history()
            else:
                say("Commands: /history, /quit")
        elif kind == "file":
            enqueue(state, raw)
        elif kind == "url":
            target, section = split_section(raw)
            enqueue(state, target, section)
        else:
            threading.Thread(target=search, args=(state, raw), daemon=True).start()

    def request_quit(app: Application[None] | None) -> None:
        running = list(state.jobs)
        if running and time.monotonic() - state.quit_armed_at > QUIT_WINDOW:
            state.quit_armed_at = time.monotonic()
            say(f"{len(running)} item(s) in progress: press again to stop them and quit.")
            return
        for job in running:
            job.cancel.set()
        if app is not None:
            app.exit()

    @keys.add("enter")
    def _enter(event: KeyPressEvent) -> None:
        text = buffer.text
        buffer.reset()
        if state.folder_edit:
            state.folder_edit = False
            folder = str(Path(text.strip()).expanduser()) if text.strip() else state.output_dir
            state.output_dir = folder
            say(f"Folder: {folder}")
            return
        submit(text)

    @keys.add(Keys.BracketedPaste)
    def _paste(event: KeyPressEvent) -> None:
        """Pasting links on an empty line queues them at once, one per line."""
        lines = [line.strip() for line in event.data.replace("\r", "\n").split("\n") if line.strip()]
        if not buffer.text and not state.folder_edit and lines and all(classify(x) == "url" for x in lines):
            for line in lines:
                target, section = split_section(line)
                enqueue(state, target, section)
            return
        buffer.insert_text(event.data.replace("\r", " ").replace("\n", " "))

    @keys.add("tab", filter=empty)
    def _mode(event: KeyPressEvent) -> None:
        state.is_audio = not state.is_audio

    @keys.add("up", filter=empty)
    @keys.add("down", filter=empty)
    @keys.add("left", filter=empty)
    @keys.add("right", filter=empty)
    def _adjust(event: KeyPressEvent) -> None:
        key = event.key_sequence[-1].key
        mode = state.mode
        if key in (Keys.Up, Keys.Down):
            field_name = "ext"
            values = [f["ext"] for f in (presets.AUDIO_FORMATS if state.is_audio else presets.VIDEO_FORMATS)]
        else:
            if state.is_audio and mode["ext"] in LOSSLESS:
                return
            field_name = "quality"
            values = [q["value"] for q in presets.AUDIO_QUALITIES] if state.is_audio else presets.QUALITY_KEYS
        step = 1 if key in (Keys.Down, Keys.Right) else -1
        mode[field_name] = values[(values.index(mode[field_name]) + step) % len(values)]

    @keys.add("c-o")
    def _folder(event: KeyPressEvent) -> None:
        state.folder_edit = True
        buffer.text = state.output_dir
        buffer.cursor_position = len(buffer.text)

    @keys.add("c-e")
    def _music(event: KeyPressEvent) -> None:
        if state.is_audio and sys.platform == "darwin":
            state.music = not state.music

    @keys.add("c-r")
    def _reveal(event: KeyPressEvent) -> None:
        if state.last_file is not None:
            reveal(state.last_file)

    for digit in "123456789":

        @keys.add(digit, filter=empty & Condition(lambda: bool(state.results)))
        def _pick(event: KeyPressEvent) -> None:
            index = int(event.key_sequence[-1].key) - 1
            if index < len(state.results) and state.results[index]["url"] not in state.seen:
                enqueue(state, str(state.results[index]["url"]))

    @keys.add("escape", eager=True)
    def _escape(event: KeyPressEvent) -> None:
        if state.folder_edit:
            state.folder_edit = False
            buffer.reset()
        elif state.results:
            state.results = []
        else:
            buffer.reset()

    @keys.add("c-c")
    @keys.add("c-d")
    def _quit(event: KeyPressEvent) -> None:
        request_quit(event.app)

    prompt = Condition(lambda: state.folder_edit)
    layout = Layout(
        HSplit(
            [
                Window(FormattedTextControl(lambda: render_settings(state)), dont_extend_height=True),
                Window(FormattedTextControl(lambda: render_jobs(state)), dont_extend_height=True),
                Window(
                    BufferControl(
                        buffer,
                        input_processors=[BeforeInput(lambda: [(ACCENT, "  folder > " if prompt() else "  > ")])],
                    ),
                    height=1,
                ),
                Window(FormattedTextControl(lambda: render_footer(state, buffer.text)), height=1),
            ]
        ),
        focused_element=buffer,
    )
    app: Application[None] = Application(
        layout=layout,
        key_bindings=keys,
        refresh_interval=0.1,
        erase_when_done=True,
        color_depth=ColorDepth.DEPTH_1_BIT if "NO_COLOR" in os.environ else None,
    )

    def _clear_notice(_: Any) -> None:
        """Any key hides the one-shot notice; the quit confirmation lasts QUIT_WINDOW seconds."""
        if time.monotonic() - state.quit_armed_at > QUIT_WINDOW:
            state.notice = ""

    app.key_processor.before_key_press += _clear_notice
    return app


def run_interactive(initial: str | None = None) -> None:
    """Open the queue screen; `initial` is handled like a first line typed by the user."""
    state = new_state(load_config())
    state.clipboard = clipboard_url()
    state.app = build_app(state)
    if initial:
        state.app.pre_run_callables.append(lambda: _submit_initial(state, initial))
    with patch_stdout(raw=True):
        state.app.run()
    state.pool.shutdown(wait=True, cancel_futures=True)


def _submit_initial(state: State, raw: str) -> None:
    if classify(raw) == "search":
        threading.Thread(target=search, args=(state, raw), daemon=True).start()
    else:
        enqueue(state, raw)
