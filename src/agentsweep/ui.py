"""All terminal presentation for agentsweep.

cli.py owns logic and data; this module owns pixels. Nothing here mutates
state, reads files, or decides exit codes. --json mode never calls into
this module, so its output stays machine-clean.
"""
from __future__ import annotations

from pathlib import Path

from rich import box
from rich.console import Console
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

TOTAL_STAGES = 5

_STAGE_STYLE = {
    "ok": "bold green",
    "fail": "bold red",
    "skip": "dim",
    "warn": "bold yellow",
}

_ICONS_UNICODE = {"ok": "✔", "fail": "✘", "skip": "⊘", "warn": "⚠"}
_ICONS_ASCII = {"ok": "+", "fail": "x", "skip": "-", "warn": "!"}


def _encodes(c: Console, chars: str) -> bool:
    """True if the console's underlying stream can encode `chars`.

    Guards against UnicodeEncodeError on cp1252 pipes (Windows redirects);
    interactive consoles on py3.6+ are UTF-8 via PEP 528.
    """
    enc = getattr(c.file, "encoding", None)
    if not enc:
        return True
    try:
        chars.encode(enc)
        return True
    except (UnicodeEncodeError, LookupError):
        return False


def _icons(c: Console) -> dict[str, str]:
    uni = _encodes(c, "".join(_ICONS_UNICODE.values()))
    return _ICONS_UNICODE if uni else _ICONS_ASCII


def _box(c: Console, fancy: box.Box) -> box.Box:
    return fancy if _encodes(c, "═━│┃") else box.ASCII


def banner(version: str) -> None:
    wing = "▄▄▄" if _encodes(console, "▄") else "==="
    t = Text("  ")
    t.append(f"{wing} ", style="bold red")
    t.append(f"AGENTSWEEP v{version}", style="bold")
    t.append(f" {wing}", style="bold red")
    t.append("  secret scanner for AI agent histories", style="dim")
    console.print()
    console.print(t)
    console.print()


def stage(n: int, status: str, name: str, *parts: object) -> None:
    """One pipeline line: `  [n/5] ✔ NAME      detail · detail`."""
    ic = _icons(console)
    sep = " · " if _encodes(console, "·") else " | "
    style = _STAGE_STYLE[status]
    t = Text("  ")
    t.append(f"[{n}/{TOTAL_STAGES}] ", style="dim")
    t.append(f"{ic[status]} ", style=style)
    t.append(f"{name:<9}", style=style)
    detail = sep.join(str(p) for p in parts if str(p))
    if detail:
        t.append(" ")
        t.append(detail)
    console.print(t)


def scanning(n_files: int):
    """Spinner context manager for the scan phase. Silent when piped."""
    return console.status(
        Text(f"scanning {n_files} file(s)...", style="bold cyan"),
        spinner="dots",
    )


def findings_table(rows: list[tuple[str, str, Path, int]], root: Path) -> None:
    """Red table of (rule display, masked secret, file, line)."""
    table = Table(
        box=_box(console, box.HEAVY_HEAD),
        border_style="red",
        header_style="bold red",
    )
    table.add_column("RULE", style="bold")
    table.add_column("SECRET (masked)", style="red")
    table.add_column("FILE")
    table.add_column("LINE", justify="right", style="dim")
    for display, masked, path, line in rows:
        table.add_row(display, masked, _rel(path, root), str(line))
    console.print(Padding(table, (0, 0, 0, 8)))


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def redact_row(status: str, path: Path, note: str = "") -> None:
    """Per-file result under the REDACT stage. ok→stdout, skip/fail→stderr."""
    target = console if status == "ok" else err_console
    ic = _icons(target)
    label = {"ok": "OK", "skip": "SKIP", "fail": "FAIL"}[status]
    t = Text("        ")
    t.append(f"{ic[status]} {label:<5}", style=_STAGE_STYLE[status])
    t.append(str(path))
    if note:
        t.append(f"  {note}", style="dim")
    target.print(t)


def rotation_panel(items: list[tuple[str, str]]) -> None:
    """Red double-border ACTION REQUIRED panel: (rule, rotation guidance)."""
    ic = _icons(console)
    body = Text()
    for rule, guidance in items:
        body.append(f"{rule}\n", style="bold red")
        body.append(f"  {guidance}\n")
    body.append(
        "\nRedaction removes the secret from local history,"
        "\nbut the key still works until you rotate it.",
        style="dim",
    )
    console.print(Padding(Panel(
        body,
        title=f"{ic['warn']} ACTION REQUIRED — rotate these secrets now",
        title_align="left",
        border_style="bold red",
        box=_box(console, box.DOUBLE),
        padding=(0, 1),
        expand=False,
    ), (0, 0, 0, 8)))


def gate_panel(title: str, lines: list[str]) -> None:
    """Yellow safety-gate refusal panel on stderr.

    Keep each line under ~70 chars: the panel sizes to content, and lines
    longer than the terminal wrap — splitting phrases tests grep for.
    """
    ic = _icons(err_console)
    err_console.print(Padding(Panel(
        Text("\n".join(lines)),
        title=f"{ic['warn']} {title}",
        title_align="left",
        border_style="bold yellow",
        box=_box(err_console, box.DOUBLE),
        padding=(0, 1),
        expand=False,
    ), (0, 0, 0, 2)))


def warn_line(message: str) -> None:
    ic = _icons(err_console)
    err_console.print(Text(f"  {ic['warn']} {message}", style="yellow"))
