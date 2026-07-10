"""Minimal terminal spinner, no external dependencies."""

import sys
import threading
import time

_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_GREEN = "\033[32m"
_RED = "\033[31m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"
_ERASE_LINE = "\033[K"

_tty = sys.stdout.isatty()

# Set by callers (e.g. --verbose) to suppress the animated thread, since it
# stomps on any print() the deploy code (or a caller) does mid-spin.
verbose = False


class Spinner:
    """Context manager that shows an animated spinner, then ✓ or ✗ on exit."""

    def __init__(self, label):
        self.label = label
        self._stop = threading.Event()
        self._thread = None

    def __enter__(self):
        if _tty and not verbose:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            print(f"  {self.label}...", flush=True)
        return self

    def __exit__(self, exc_type, *_):
        if _tty and not verbose:
            self._stop.set()
            if self._thread:
                self._thread.join()
            if exc_type:
                sys.stdout.write(f"\r{_ERASE_LINE}  {_RED}✗{_RESET} {self.label}\n")
            else:
                sys.stdout.write(f"\r{_ERASE_LINE}  {_GREEN}✓{_RESET} {self.label}\n")
            sys.stdout.flush()
        elif exc_type is None:
            print(f"  ✓ {self.label}", flush=True)
        return False  # don't suppress exceptions

    def _spin(self):
        i = 0
        while not self._stop.is_set():
            frame = _FRAMES[i % len(_FRAMES)]
            sys.stdout.write(f"\r  {_DIM}{frame}{_RESET} {self.label}...")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)


def success(message):
    if _tty:
        print(f"\n  {_BOLD}{_GREEN}✓{_RESET}  {message}\n")
    else:
        print(f"\n✓  {message}\n")
