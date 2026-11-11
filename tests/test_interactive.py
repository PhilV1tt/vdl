"""Queue screen tests: keys come through a prompt_toolkit pipe, Downloader and search are mocked."""

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from vdl.config import VdlConfig
from vdl.downloader import DownloadResult
from vdl.interactive import build_app, classify, enqueue, new_state, split_section

URL = "https://www.youtube.com/watch?v=abc"
PASTE = "\x1b[200~{}\x1b[201~"
CTRL_D, TAB, UP, DOWN, RIGHT = "\x04", "\t", "\x1b[A", "\x1b[B", "\x1b[C"


@pytest.fixture(autouse=True)
def _neutral(monkeypatch):
    """Empty memory, remember() recorded, no clipboard: every test starts from the same state."""
    monkeypatch.setattr("vdl.prefs.recall", dict)
    monkeypatch.setattr("vdl.interactive.clipboard_url", lambda: "")
    remembered = []
    monkeypatch.setattr("vdl.prefs.remember", lambda *a, **k: remembered.append((a, k)))
    return remembered


def quit_when_idle(state, keyboard):
    """Send Ctrl-D once the queue is empty, so quitting needs no confirmation."""

    def wait():
        time.sleep(0.2)  # let the keys already sent be handled
        while state.jobs:
            time.sleep(0.01)
        keyboard.send_text(CTRL_D)

    threading.Thread(target=wait, daemon=True).start()


def run_screen(keys, exit_code=0, file_path=None, error=""):
    """Send `keys` to the screen, wait for the workers, return (state, Downloader mock)."""
    state = new_state(VdlConfig())
    with (
        create_pipe_input() as keyboard,
        create_app_session(input=keyboard, output=DummyOutput()),
        patch("vdl.interactive.Downloader") as downloader,
        patch("vdl.interactive.print_line") as printed,
    ):
        downloader.return_value.download.return_value = DownloadResult(exit_code, file_path, error=error)
        state.app = build_app(state)
        keyboard.send_text(keys)
        quit_when_idle(state, keyboard)
        state.app.run()
        state.pool.shutdown(wait=True)
    state.printed = printed  # type: ignore[attr-defined]
    return state, downloader


class TestClassify:
    @pytest.mark.parametrize(
        "raw, kind",
        [
            (URL, "url"),
            ("@QOVESStudio", "url"),
            ("youtu.be/abc", "url"),
            ("never gonna give you up", "search"),
            ("/history", "command"),
            ("/quit", "command"),
        ],
    )
    def test_kinds(self, raw, kind):
        assert classify(raw) == kind

    def test_existing_file(self, tmp_path):
        f = tmp_path / "clip.mov"
        f.write_bytes(b"x")
        assert classify(str(f)) == "file"


class TestSplitSection:
    def test_excerpt_after_link(self):
        assert split_section(f"{URL} 12:00-14:30") == (URL, "12:00-14:30")

    def test_plain_link(self):
        assert split_section(URL) == (URL, None)


class TestQueue:
    def test_paste_starts_download_with_remembered_mode(self, _neutral):
        state, downloader = run_screen(PASTE.format(URL))
        args = downloader.return_value.download.call_args[0]
        assert args[0] == URL
        assert args[1:3] == ("mp4", False)
        assert _neutral[0][0] == (False,)
        assert state.jobs == []

    def test_typed_link_and_enter(self):
        _, downloader = run_screen(URL + "\r")
        assert downloader.return_value.download.call_args[0][0] == URL

    def test_paste_several_links_queues_each(self):
        links = "https://youtu.be/a\nhttps://youtu.be/b\nhttps://youtu.be/c"
        _, downloader = run_screen(PASTE.format(links))
        urls = sorted(c[0][0] for c in downloader.return_value.download.call_args_list)
        assert urls == ["https://youtu.be/a", "https://youtu.be/b", "https://youtu.be/c"]

    def test_tab_and_arrows_change_settings_before_paste(self):
        # Tab -> audio (mp3, 320); down -> m4a; right -> 256
        _, downloader = run_screen(TAB + DOWN + RIGHT + PASTE.format(URL))
        args = downloader.return_value.download.call_args[0]
        assert args[1:5] == ("m4a", True, "bestaudio/best", "256")

    def test_arrows_edit_text_when_line_not_empty(self):
        state, _ = run_screen("abc" + UP + "\x1b")
        assert state.video["ext"] == "mp4"

    def test_excerpt_reaches_downloader(self):
        _, downloader = run_screen(f"{URL} 1:00-2:00\r")
        assert downloader.call_args.kwargs["sections"] == ["1:00-2:00"]

    def test_success_prints_path_and_keeps_last_file(self, tmp_path):
        out = tmp_path / "Video.mp4"
        out.write_bytes(b"x" * 10)
        state, _ = run_screen(PASTE.format(URL), file_path=out)
        assert state.last_file == out
        assert str(out) in str(state.printed.call_args[0][0])

    def test_failure_prints_error(self):
        state, _ = run_screen(PASTE.format(URL), exit_code=1, error="Private video")
        assert "Private video" in str(state.printed.call_args[0][0])

    def test_same_link_twice_from_clipboard_is_queued_once(self, monkeypatch):
        monkeypatch.setattr("vdl.interactive.clipboard_url", lambda: URL)
        _, downloader = run_screen("\r\r")
        assert downloader.return_value.download.call_count == 1


class TestSearch:
    def test_text_searches_then_digit_queues_result(self):
        results = [{"title": "Song", "url": "https://youtu.be/song", "duration": 200}]
        with patch("vdl.search.search_videos", return_value=results):
            state = new_state(VdlConfig())
            with (
                create_pipe_input() as keyboard,
                create_app_session(input=keyboard, output=DummyOutput()),
                patch("vdl.interactive.Downloader") as downloader,
                patch("vdl.interactive.print_line"),
            ):
                downloader.return_value.download.return_value = DownloadResult(0)
                state.app = build_app(state)
                keyboard.send_text("some song\r")

                def pick_then_quit():
                    while not state.results:
                        time.sleep(0.01)
                    keyboard.send_text("1")
                    quit_when_idle(state, keyboard)

                threading.Thread(target=pick_then_quit, daemon=True).start()
                state.app.run()
                state.pool.shutdown(wait=True)
        assert downloader.return_value.download.call_args[0][0] == "https://youtu.be/song"


class TestConvert:
    def test_dropped_file_is_converted_next_to_source(self, tmp_path):
        src = tmp_path / "clip.mov"
        src.write_bytes(b"x")
        state = new_state(VdlConfig())
        state.is_audio = True
        with patch("vdl.convert.convert_one") as convert:
            convert.side_effect = lambda s, d, e, q: Path(d).write_bytes(b"y")
            with patch("vdl.interactive.print_line"):
                enqueue(state, str(src))
                state.pool.shutdown(wait=True)
        dst = convert.call_args[0][1]
        assert dst == tmp_path / "clip.mp3"
        assert state.last_file == dst


class TestQuit:
    def test_quit_with_running_item_needs_confirmation(self):
        state = new_state(VdlConfig())
        with (
            create_pipe_input() as keyboard,
            create_app_session(input=keyboard, output=DummyOutput()),
            patch("vdl.interactive.run_job"),  # the job never finishes
        ):
            state.app = build_app(state)
            enqueue(state, URL)
            keyboard.send_text(CTRL_D)
            keyboard.send_text(CTRL_D)
            state.app.run()
        assert state.jobs[0].cancel.is_set()

    def test_folder_edit(self, tmp_path):
        state, _ = run_screen("\x0f" + "\x15" + str(tmp_path) + "\r")
        assert state.output_dir == str(tmp_path)
