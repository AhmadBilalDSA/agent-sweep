"""Shared console singletons and stream-capability probes.

Everything that needs to answer "can this stream show that?" lives here:
encoding probes, icon sets, box fallbacks, and the _safe() escape hatch.
"""
from __future__ import annotations

from rich import box
from rich.console import Console

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

TOTAL_STAGES = 5

STAGE_STYLE = {
    "ok": "bold green",
    "fail": "bold red",
    "skip": "dim",
    "warn": "bold yellow",
}

_ICONS_UNICODE = {"ok": "✔", "fail": "✘", "skip": "⊘", "warn": "⚠"}
_ICONS_ASCII = {"ok": "+", "fail": "x", "skip": "-", "warn": "!"}


def _encodes(c: Console, chars: str) -> bool:
    """True if the console's underlying stream can encode `chars`.

    Guards against UnicodeEncodeError on cp1252 pipes (Windows redirects).
    Interactive consoles on py3.6+ are UTF-8 via PEP 528, but a legacy
    cmd.exe raster font can't *render* these glyphs even though the stream
    encodes them — so legacy_windows also forces the ASCII fallback.
    """
    if c.legacy_windows:
        return False
    enc = getattr(c.file, "encoding", None)
    if not enc:
        return True
    try:
        chars.encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _safe(c: Console, s: object) -> str:
    """Make an arbitrary string printable on the console's stream.

    Paths can contain characters outside a cp1252 pipe's charset; printing
    them raw would raise UnicodeEncodeError mid-report and abort with the
    wrong exit code. Backslash-escape anything the stream can't encode.
    """
    text = str(s)
    enc = getattr(c.file, "encoding", None)
    if not enc:
        return text
    try:
        text.encode(enc)
        return text
    except (UnicodeEncodeError, LookupError):
        return text.encode(enc, "backslashreplace").decode(enc, "replace")
    except Exception:
        return text


def _icons(c: Console) -> dict[str, str]:
    uni = _encodes(c, "".join(_ICONS_UNICODE.values()))
    return _ICONS_UNICODE if uni else _ICONS_ASCII


def _box(c: Console, fancy: box.Box) -> box.Box:
    return fancy if _encodes(c, "═━│┃") else box.ASCII
