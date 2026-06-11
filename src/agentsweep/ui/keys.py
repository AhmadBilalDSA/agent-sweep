"""Cross-platform single-keypress reader for the interactive TUI.

No Rich imports — pure input. The caller's event loop calls read_key()
and dispatches on the returned constant.

RAW_INPUT_AVAILABLE is probed once at import; callers gate the TUI on it.
"""
from __future__ import annotations

import sys

# Key constants returned by read_key()
UP = "UP"
DOWN = "DOWN"
ENTER = "ENTER"
SPACE = "SPACE"
QUIT = "QUIT"
OTHER = "OTHER"


def _read_key_windows() -> str:
    import msvcrt
    ch = msvcrt.getwch()
    if ch in ("\x00", "\xe0"):
        # Arrow keys: second byte distinguishes
        ch2 = msvcrt.getwch()
        if ch2 == "H":
            return UP
        if ch2 == "P":
            return DOWN
        return OTHER
    if ch in ("\r", "\n"):
        return ENTER
    if ch == " ":
        return SPACE
    if ch in ("\x1b", "q", "Q"):
        return QUIT
    return OTHER


def _read_key_unix() -> str:
    import tty
    import termios
    import select

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Check for CSI sequence (arrow keys: ESC [ A/B)
            ready, _, _ = select.select([sys.stdin], [], [], 0.05)
            if ready:
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ready2, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if ready2:
                        ch3 = sys.stdin.read(1)
                        if ch3 == "A":
                            return UP
                        if ch3 == "B":
                            return DOWN
            return QUIT
        if ch in ("\r", "\n"):
            return ENTER
        if ch == " ":
            return SPACE
        if ch in ("q", "Q"):
            return QUIT
        return OTHER
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def read_key() -> str:
    """Block until a keypress and return a key constant."""
    if sys.platform == "win32":
        return _read_key_windows()
    return _read_key_unix()


def _probe() -> bool:
    """True when raw key input is available (real tty + libs present)."""
    if not sys.stdin.isatty():
        return False
    if sys.platform == "win32":
        try:
            import msvcrt  # noqa: F401
            return True
        except ImportError:
            return False
    try:
        import tty  # noqa: F401
        import termios  # noqa: F401
        import select  # noqa: F401
        return True
    except ImportError:
        return False


RAW_INPUT_AVAILABLE: bool = _probe()
