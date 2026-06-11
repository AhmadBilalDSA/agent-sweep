"""All terminal presentation for agentsweep.

cli.py owns logic and data; this module owns pixels. Nothing here mutates
state, reads files, or decides exit codes. --json mode never calls into
this module, so its output stays machine-clean.
"""
from __future__ import annotations

import contextlib
import os
import random
import time
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.live import Live
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


# 5-row block font for the interactive-mode banner. '#' is replaced with a
# full block when the stream can render it.
_FONT = {
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "G": [" ####", "#    ", "# ###", "#   #", " ### "],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #"],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "S": [" ####", "#    ", " ### ", "    #", "#### "],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "P": ["#### ", "#   #", "#### ", "#    ", "#    "],
}
_GRADIENT = ["red", "red", "dark_orange", "orange1", "yellow"]

# Glyph pools for the decode-noise phases of the banner animation. Picked
# per-console so the cp1252/legacy ASCII fallback still gets the full show.
_NOISE_UNICODE = "░▒▓█▌▐▀▄"
_NOISE_ASCII = "01<>#$%&*+=/\\?^~"
_NOISE_STYLES = ("grey35", "grey46", "grey58", "dark_red", "red3")
_DECODE_ZONE = 7  # columns behind the beam where glyphs are still resolving


def _noise_pool() -> str:
    return _NOISE_UNICODE if _encodes(console, _NOISE_UNICODE) else _NOISE_ASCII


def _grad_idx(row: int) -> int:
    """Map a banner row (AGENT=0-4, blank=5, SWEEP=6-10) to a gradient index."""
    return row if row < 5 else row - 6


def _banner_rows() -> tuple[list[str], list[str]]:
    """Render AGENT / SWEEP as (lines, per-line styles).

    Cells are doubled to 2 chars wide when the terminal allows — block
    glyphs are ~1:2, so doubling makes the letters read as solid squares.
    """
    fill = "█" if _encodes(console, "█") else "#"
    cell_w = 2 if console.width >= 70 else 1
    lines: list[str] = []
    styles: list[str] = []
    for word in ("AGENT", "SWEEP"):
        for r in range(5):
            row = " ".join(_FONT[ch][r] for ch in word)
            row = "".join(c * cell_w for c in row).replace("#", fill)
            lines.append(row)
            styles.append(f"bold {_GRADIENT[r]}")
        lines.append("")
        styles.append("")
    return lines[:-1], styles[:-1]  # drop the trailing blank


def _compose(rows: list[Text], footer: Text) -> Group:
    """Stack banner rows + footer line into one Live frame."""
    return Group(Text(), *rows, Text(), footer, Text())


def _status(label: str, tick: int) -> Text:
    """Dim hacker-console status line shown under the banner mid-animation."""
    lead = "▸" if _encodes(console, "▸") else ">"
    t = Text("   ")
    t.append(f"{lead} ", style="bold red")
    t.append(f"{label}{'.' * (1 + tick % 3)}", style="dim")
    return t


def _frame_noise(lines: list[str], width: int, density: float, pool: str,
                 rng: random.Random, footer: Text) -> Group:
    """Phase 1: the marque materializes out of churning glyph static."""
    rows: list[Text] = []
    for line in lines:
        t = Text("   ")
        for ch in line.ljust(width):
            if ch != " ":
                if rng.random() < density:
                    t.append(rng.choice(pool), style=rng.choice(_NOISE_STYLES))
                else:
                    t.append(" ")
            elif rng.random() < 0.03 * (1.0 - density):
                t.append(".", style="grey30")  # stray interference sparks
            else:
                t.append(" ")
        rows.append(t)
    return _compose(rows, footer)


def _frame_sweep(lines: list[str], styles: list[str], width: int, beam: int,
                 bar: str, pool: str, rng: random.Random,
                 footer: Text) -> Group:
    """Phase 2: a white scanline wipes across; glyphs behind it flicker
    through a hot decode zone before locking into the gradient letters;
    ahead of it the phase-1 static keeps churning."""
    rows: list[Text] = []
    for r, (line, style) in enumerate(zip(lines, styles)):
        color = _GRADIENT[_grad_idx(r)]
        t = Text("   ")
        for c, ch in enumerate(line.ljust(width)):
            if beam <= c < beam + 2:
                t.append(bar, style="bold white")  # the scanline itself
            elif c < beam:
                if ch == " ":
                    t.append(" ")
                elif beam - c <= 1:
                    t.append(rng.choice(pool), style="bold yellow")  # hot edge
                elif beam - c < _DECODE_ZONE and \
                        rng.random() > (beam - c) / _DECODE_ZONE:
                    t.append(rng.choice(pool), style=f"bold {color}")
                else:
                    t.append(ch, style=style)
            elif ch != " " and rng.random() < 0.55:
                t.append(rng.choice(pool), style=rng.choice(_NOISE_STYLES))
            else:
                t.append(" ")
        rows.append(t)
    return _compose(rows, footer)


def _frame_glint(lines: list[str], styles: list[str], g: int,
                 footer: Text) -> Group:
    """Phase 3: a slanted white-hot glint with yellow bloom races over the
    finished letters, one row of lag per line for a diagonal streak."""
    rows: list[Text] = []
    for r, (line, style) in enumerate(zip(lines, styles)):
        lo = g - r
        t = Text("   ")
        for c, ch in enumerate(line):
            if ch == " ":
                t.append(" ")
            elif lo <= c < lo + 2:
                t.append(ch, style="bold white")
            elif lo - 2 <= c < lo or lo + 2 <= c < lo + 4:
                t.append(ch, style="bold yellow")
            else:
                t.append(ch, style=style)
        rows.append(t)
    return _compose(rows, footer)


def _frame_shimmer(lines: list[str], shift: int, sparkle: bool,
                   rng: random.Random, footer: Text) -> Group:
    """Phase 4: the fire gradient rolls through the letters, with white
    sparkle pops on the final pass, then settles into place."""
    rows: list[Text] = []
    for r, line in enumerate(lines):
        color = _GRADIENT[(_grad_idx(r) + shift) % len(_GRADIENT)]
        t = Text("   ")
        for ch in line:
            if ch == " ":
                t.append(" ")
            elif sparkle and rng.random() < 0.04:
                t.append(ch, style="bold white")
            else:
                t.append(ch, style=f"bold {color}")
        rows.append(t)
    return _compose(rows, footer)


def _banner_frame(
    lines: list[str],
    styles: list[str],
    width: int,
    tagline: str,
    tag_chars: int | None = None,
    tag_noise: str = "",
    cursor: bool = False,
) -> Group:
    """A settled frame: full gradient letters, tagline typed to `tag_chars`
    with an optional decoding head of noise glyphs and a block cursor."""
    bar = "█" if _encodes(console, "█") else "#"
    rows: list[Text] = []
    for line, style in zip(lines, styles):
        rows.append(Text("   ") + Text(line, style=style))
    shown = tagline if tag_chars is None else tagline[:tag_chars]
    tag = Text("   ")
    tag.append(shown, style="dim")
    if tag_noise:
        tag.append(tag_noise, style="dim red")
    if cursor:
        tag.append(bar, style="bold red")
    return _compose(rows, tag)


def _animate_banner(lines: list[str], styles: list[str], tagline: str) -> None:
    """~2.8s cinematic reveal. Live runs with auto_refresh OFF and every
    frame is painted explicitly (update(refresh=True)): with the default
    refresh thread, update() never paints — a 60Hz daemon samples whatever
    frame is current, dropping frames queued faster than 16.7ms and making
    a short animation look like a static print."""
    width = max(len(line) for line in lines)
    bar = "█" if _encodes(console, "█") else "#"
    pool = _noise_pool()
    rng = random.Random()
    with Live(console=console, auto_refresh=False, transient=False) as live:
        def frame(renderable: Group, hold: float) -> None:
            live.update(renderable, refresh=True)
            time.sleep(hold)

        try:
            # Phase 1 — signal acquisition: static materializes (~0.4s).
            for i in range(12):
                f = _status("intercepting agent history stream", i // 4)
                frame(_frame_noise(lines, width, (i + 1) / 12, pool, rng, f),
                      0.028)
            # Phase 2 — decode sweep, 1 column per frame (~1.1s).
            for beam in range(0, width + _DECODE_ZONE + 2):
                f = _status("sweeping for exposed secrets", beam // 8)
                frame(_frame_sweep(lines, styles, width, beam, bar, pool,
                                   rng, f), 0.013)
            # Phase 3 — diagonal glint streak (~0.3s).
            f = _status("signal locked", 0)
            for g in range(0, width + len(lines) + 6, 3):
                frame(_frame_glint(lines, styles, g, f), 0.012)
            # Phase 4 — gradient fire rolls through, then settles (~0.3s).
            for k, shift in enumerate((4, 3, 2, 1, 0, 4, 3, 2, 1, 0)):
                frame(_frame_shimmer(lines, shift, k >= 5, rng, f), 0.028)
            # Phase 5 — tagline decodes itself under a block cursor (~0.6s).
            for i in range(0, len(tagline) + 2, 2):
                shown = min(i, len(tagline))
                head = "".join(rng.choice(pool)
                               for _ in range(min(2, len(tagline) - shown)))
                frame(_banner_frame(lines, styles, width, tagline,
                                    tag_chars=shown, tag_noise=head,
                                    cursor=True), 0.015)
            for blink in (False, True, False):
                frame(_banner_frame(lines, styles, width, tagline,
                                    cursor=blink), 0.07)
        finally:
            # Always settle on the finished banner — including on Ctrl-C.
            live.update(_banner_frame(lines, styles, width, tagline),
                        refresh=True)


def big_banner(version: str) -> None:
    """Full-size AGENT / SWEEP banner; animated scanner-sweep on real
    terminals, static art on pipes/CI or with AGENTSWEEP_NO_ANIM set."""
    lines, styles = _banner_rows()
    tagline = f"secret scanner for AI agent histories — v{version}"
    if console.is_terminal and not os.environ.get("AGENTSWEEP_NO_ANIM"):
        # Ctrl-C lands here mid-animation: the finally above has already
        # painted the settled banner, so just skip ahead — never fall
        # through to the static print (that would draw it twice).
        with contextlib.suppress(KeyboardInterrupt):
            _animate_banner(lines, styles, tagline)
        return
    console.print()
    for line, style in zip(lines, styles):
        console.print(Text("   " + line, style=style))
    console.print()
    console.print(Text(f"   {tagline}", style="dim"))
    console.print()


def menu_options() -> None:
    """Numbered action menu for interactive mode."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold red", justify="right")
    grid.add_column()
    grid.add_column(style="dim")
    grid.add_row("[1]", "Scan Claude Code history", "read-only")
    grid.add_row("[2]", "Scan a custom folder", "read-only")
    grid.add_row("[3]", "Redact Claude Code history", "asks to confirm · .bak backups")
    grid.add_row("[4]", "Undo last redaction", "restores .bak backups")
    grid.add_row("[5]", "Findings as JSON", "read-only")
    grid.add_row("[6]", "Quit", "")
    console.print(Padding(Panel(
        grid,
        title="MENU",
        title_align="left",
        border_style="red",
        box=_box(console, box.HEAVY),
        padding=(1, 2),
        expand=False,
    ), (0, 0, 0, 2)))


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


def stage(n: int, status: str, name: str, *parts: object, err: bool = False) -> None:
    """One pipeline line: `  [n/5] ✔ NAME      detail · detail`.

    soft_wrap: long details (paths) must overflow like plain print() rather
    than hard-wrap or crop at rich's assumed 80-col width on pipes.
    """
    target = err_console if err else console
    ic = _icons(target)
    sep = " · " if _encodes(target, "·") else " | "
    style = _STAGE_STYLE[status]
    t = Text("  ")
    t.append(f"[{n}/{TOTAL_STAGES}] ", style="dim")
    t.append(f"{ic[status]} ", style=style)
    t.append(f"{name:<9}", style=style)
    detail = sep.join(_safe(target, p) for p in parts if str(p))
    if detail:
        t.append(" ")
        t.append(detail)
    target.print(t, soft_wrap=True)


def scanning(n_files: int):
    """Spinner context manager for the scan phase.

    Only animate on a real terminal that can encode braille frames:
    FORCE_COLOR on a cp1252 pipe would otherwise crash rich mid-spin.
    """
    if console.is_terminal and _encodes(console, "⠋"):
        return console.status(
            Text(f"scanning {n_files} file(s)...", style="bold cyan"),
            spinner="dots",
        )
    return contextlib.nullcontext()


def findings_table(rows: list[tuple[str, str, Path, int]], root: Path) -> None:
    """Red table of (rule display, masked secret, file, line).

    Cells are wrapped in Text so bracketed path segments (e.g. a Next.js
    `[id]` directory) are never parsed as rich markup — raw strings would
    silently vanish or raise MarkupError.
    """
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
        table.add_row(
            Text(_safe(console, display)),
            Text(_safe(console, masked)),
            Text(_safe(console, rel(path, root))),
            str(line),
        )
    console.print(Padding(table, (0, 0, 0, 8)))


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def redact_row(status: str, path_display: str, note: str = "") -> None:
    """Per-file result under the REDACT stage. ok→stdout, skip/fail→stderr."""
    target = console if status == "ok" else err_console
    ic = _icons(target)
    label = {"ok": "OK", "skip": "SKIP", "fail": "FAIL"}[status]
    t = Text("        ")
    t.append(f"{ic[status]} {label:<5}", style=_STAGE_STYLE[status])
    t.append(_safe(target, path_display))
    if note:
        t.append(f"  {_safe(target, note)}", style="dim")
    target.print(t, soft_wrap=True)


def rotation_panel(items: list[tuple[str, str]]) -> None:
    """Red double-border ACTION REQUIRED panel: (rule, rotation guidance).

    Body is a two-column grid so guidance that wraps keeps a hanging
    indent instead of snapping back to the panel edge.
    """
    ic = _icons(console)
    grid = Table.grid(padding=0)
    grid.add_column(width=2)
    grid.add_column()
    for rule, guidance in items:
        grid.add_row("", Text(_safe(console, rule), style="bold red"))
        grid.add_row("  ", Text(_safe(console, guidance)))
    grid.add_row("", "")
    grid.add_row("", Text(
        "Redaction removes the secret from local history,\n"
        "but the key still works until you rotate it.",
        style="dim",
    ))
    console.print(Padding(Panel(
        grid,
        title=f"{ic['warn']} ACTION REQUIRED — rotate these secrets now",
        title_align="left",
        border_style="bold red",
        box=_box(console, box.DOUBLE),
        padding=(0, 1),
        expand=False,
    ), (0, 0, 0, 8)))


def gate_panel(title: str, lines: list[str]) -> None:
    """Yellow safety-gate refusal panel on stderr.

    On a non-terminal stream (tests, CI greps) emit plain unwrapped lines:
    a Panel honors COLUMNS even when piped, and wrapping could split the
    exact phrases callers grep for.
    """
    ic = _icons(err_console)
    if not err_console.is_terminal:
        for line in [f"{ic['warn']} {title}"] + lines:
            err_console.print(Text(_safe(err_console, line)), soft_wrap=True)
        return
    body = Text("\n".join(_safe(err_console, line) for line in lines))
    err_console.print(Padding(Panel(
        body,
        title=f"{ic['warn']} {title}",
        title_align="left",
        border_style="bold yellow",
        box=_box(err_console, box.DOUBLE),
        padding=(0, 1),
        expand=False,
    ), (0, 0, 0, 2)))


def warn_line(message: str) -> None:
    ic = _icons(err_console)
    err_console.print(Text(f"  {ic['warn']} {_safe(err_console, message)}",
                           style="yellow"), soft_wrap=True)
