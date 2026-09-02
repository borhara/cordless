"""Minimal terminal spinner, no external dependencies."""

import sys
import threading
import time
from collections.abc import Callable, Iterable
from typing import TypeVar

_T = TypeVar("_T")

_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
ERASE_LINE = "\033[K"

tty = sys.stdout.isatty()

# Set by callers (e.g. --verbose) to suppress the animated thread, since it
# stomps on any print() the deploy code (or a caller) does mid-spin.
verbose = False


class Spinner:
    """Context manager that shows an animated spinner, then ✓ or ✗ on exit."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "Spinner":
        if tty and not verbose:
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            print(f"  {self.label}...", flush=True)
        return self

    def __exit__(self, exc_type: type[BaseException] | None, *_: object) -> bool:
        if tty and not verbose:
            self._stop.set()
            if self._thread:
                self._thread.join()
            if exc_type:
                sys.stdout.write(f"\r{ERASE_LINE}  {RED}✗{RESET} {self.label}\n")
            else:
                sys.stdout.write(f"\r{ERASE_LINE}  {GREEN}✓{RESET} {self.label}\n")
            sys.stdout.flush()
        elif exc_type is None:
            print(f"  ✓ {self.label}", flush=True)
        return False  # don't suppress exceptions

    def _spin(self) -> None:
        i = 0
        while not self._stop.is_set():
            frame = _FRAMES[i % len(_FRAMES)]
            sys.stdout.write(f"\r  {DIM}{frame}{RESET} {self.label}...")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)


def wait(label: str, fn: Callable[[], _T]) -> _T:
    """Show an animated 'label...' spinner while fn() runs, then erase it -
    no checkmark, since the outcome here isn't exception-shaped (a doctor
    section can come back with failing checks without fn() itself raising),
    so the caller prints its own per-check result lines right after."""
    if not tty or verbose:
        print(f"  {label}...", flush=True)
        return fn()

    stop = threading.Event()

    def _spin() -> None:
        i = 0
        while not stop.is_set():
            frame = _FRAMES[i % len(_FRAMES)]
            sys.stdout.write(f"\r  {DIM}{frame}{RESET} {label}...")
            sys.stdout.flush()
            i += 1
            time.sleep(0.08)

    thread = threading.Thread(target=_spin, daemon=True)
    thread.start()
    try:
        return fn()
    finally:
        stop.set()
        thread.join()
        sys.stdout.write(f"\r{ERASE_LINE}")
        sys.stdout.flush()


def success(message: str) -> None:
    if tty:
        print(f"\n  {BOLD}{GREEN}✓{RESET}  {message}\n")
    else:
        print(f"\n✓  {message}\n")


def summary(lines: Iterable[tuple[bool, str, str]]) -> None:
    """Print a short list of (ok, label, detail) status lines, e.g. what
    runtime and signature verification method a deploy actually ended up
    with - printed once, at the end, in its own clearly marked block, so it
    can't get missed or stomped by an earlier spinner."""
    print()
    print(f"  {DIM}── summary ──{RESET}")
    for ok, label, detail in lines:
        mark = f"{GREEN}✓{RESET}" if ok else f"{YELLOW}⚠{RESET}"
        print(f"  {mark} {label}: {detail}")
