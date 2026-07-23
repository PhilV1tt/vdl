from vdl.progress import ProgressPrinter, _bar


def test_bar_empty():
    result = _bar(0)
    assert result == "░" * 20


def test_bar_full():
    result = _bar(100)
    assert result == "█" * 20


def test_bar_half():
    result = _bar(50)
    assert result == "█" * 10 + "░" * 10


def test_bar_width():
    result = _bar(50, width=10)
    assert len(result) == 10


def test_bar_negative_clamped():
    result = _bar(-10)
    assert result == "░" * 20


def test_bar_over_100_clamped():
    result = _bar(110)
    assert result == "█" * 20


def test_progress_printer_initial_state():
    pp = ProgressPrinter()
    assert pp.title == ""
    assert pp._active is False


def test_progress_printer_done_no_active(capsys):
    pp = ProgressPrinter()
    pp.done("OK")
    captured = capsys.readouterr()
    assert "OK" in captured.out


def test_progress_printer_done_with_message(capsys):
    pp = ProgressPrinter()
    pp._active = True
    pp.done("Terminé")
    captured = capsys.readouterr()
    assert "Terminé" in captured.out


def test_update_live_marks_active(capsys):
    pp = ProgressPrinter()
    pp.update_live(1024 * 1024, 3, None, 500_000)
    assert pp._active is True
    assert "1.0 MiB" in capsys.readouterr().err


def test_update_live_shows_fragment_count(capsys):
    pp = ProgressPrinter()
    pp.update_live(0, 2, 5, 0)
    assert "fragment 2/5" in capsys.readouterr().err


def test_update_live_no_fragment_index(capsys):
    pp = ProgressPrinter()
    pp.update_live(0, None, None, 0)
    assert "fragment" not in capsys.readouterr().err
