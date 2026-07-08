import cordless._progress as progress
from cordless._progress import Spinner


class _FakeStdout:
    def __init__(self):
        self.writes = []

    def write(self, s):
        self.writes.append(s)

    def flush(self):
        pass


def _run_spinner(monkeypatch, raises=False):
    monkeypatch.setattr(progress, "_tty", True)
    fake = _FakeStdout()
    monkeypatch.setattr(progress.sys, "stdout", fake)

    if raises:
        try:
            with Spinner("IAM role"):
                raise ValueError("boom")
        except ValueError:
            pass
    else:
        with Spinner("IAM role"):
            pass

    return fake.writes


def test_spinner_success_erases_line_before_final_write(monkeypatch):
    writes = _run_spinner(monkeypatch)
    assert writes[-1] == f"\r{progress._ERASE_LINE}  {progress._GREEN}✓{progress._RESET} IAM role\n"


def test_spinner_failure_erases_line_before_final_write(monkeypatch):
    writes = _run_spinner(monkeypatch, raises=True)
    assert writes[-1] == f"\r{progress._ERASE_LINE}  {progress._RED}✗{progress._RESET} IAM role\n"
