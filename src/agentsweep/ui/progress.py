"""Per-file scan progress: live bar on terminals, silent no-op on pipes."""
from __future__ import annotations

import os
from collections import deque

from .console import _encodes, _safe, console

# Maximum recent detections shown in the live feed.
_MAX_FEED = 6


class _NullScanProgress:
    """No-op progress for pipes/CI — keeps the call sites unconditional."""

    def __enter__(self) -> "_NullScanProgress":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def advance(self, current: str) -> None:
        pass

    def detection(self, rule_display: str, masked: str, location: str) -> None:
        pass


class _RichScanProgress:
    """Live per-file progress bar + detection feed for the SCAN phase.

    Renders a rich Live group:
      - header counter line  ("⚡ N secrets found")
      - rolling feed of the last _MAX_FEED detections
      - the SCAN progress bar with the current file

    transient=True (the Live is created with transient=True): the whole
    group vanishes when the context exits so the pipeline's SCAN stage line
    takes its place cleanly.
    """

    def __init__(self, total: int):
        from rich.progress import (
            BarColumn, MofNCompleteColumn, Progress, TaskProgressColumn,
            TextColumn, TimeElapsedColumn,
        )
        self._progress = Progress(
            TextColumn("        "),
            TextColumn("SCAN", style="bold cyan"),
            BarColumn(bar_width=28, complete_style="red",
                      finished_style="bold green"),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("{task.fields[current]}", style="dim"),
            console=console,
            # Progress is embedded inside a Live; don't auto-start/stop.
            auto_refresh=False,
        )
        self._total = total
        self._task: int | None = None
        self._hits: int = 0
        self._feed: deque[tuple[str, str, str]] = deque(maxlen=_MAX_FEED)
        self._live: object | None = None  # rich.live.Live

    # ------------------------------------------------------------------ render

    def _lightning(self) -> str:
        """⚡ if the stream can encode it, else '!'."""
        return "⚡" if _encodes(console, "⚡") else "!"

    def _bullet(self) -> str:
        return "▸" if _encodes(console, "▸") else ">"

    def _build_renderable(self):
        """Build the full Group for one Live frame."""
        from rich.console import Group
        from rich.text import Text

        parts: list[object] = []

        # ── header ──────────────────────────────────────────────────────────
        bolt = self._lightning()
        header = Text("        ")
        if self._hits == 0:
            header.append(f"{bolt} scanning…", style="dim")
        else:
            header.append(f"{bolt} ", style="bold red")
            header.append(str(self._hits), style="bold red")
            noun = "secret" if self._hits == 1 else "secrets"
            header.append(f" {noun} found", style="bold red")
        parts.append(header)

        # ── detection feed ───────────────────────────────────────────────────
        feed_list = list(self._feed)
        n = len(feed_list)
        bullet = self._bullet()
        for i, (rule, masked, loc) in enumerate(feed_list):
            age = n - 1 - i          # 0 = newest
            dim_factor = age / max(n, 1)

            line = Text("        ")
            # dim out older entries slightly
            if dim_factor > 0.6:
                line.append(f"  {bullet} ", style="dim")
                line.append(_safe(console, rule), style="dim")
                line.append("  ", style="dim")
                line.append(_safe(console, masked), style="dim red")
                line.append(f"  {_safe(console, loc)}", style="dim")
            elif dim_factor > 0.3:
                line.append(f"  {bullet} ", style="")
                line.append(_safe(console, rule), style="bold")
                line.append("  ", style="")
                line.append(_safe(console, masked), style="red")
                line.append(f"  {_safe(console, loc)}", style="dim")
            else:
                # newest: fully lit
                line.append(f"  {bullet} ", style="bold red")
                line.append(_safe(console, rule), style="bold")
                line.append("  ", style="")
                line.append(_safe(console, masked), style="bold red")
                line.append(f"  {_safe(console, loc)}", style="dim")
            parts.append(line)

        # Pad to keep the progress bar from jumping up and down.
        for _ in range(_MAX_FEED - n):
            parts.append(Text(""))

        # ── progress bar ─────────────────────────────────────────────────────
        parts.append(self._progress)

        return Group(*parts)

    # ------------------------------------------------------------------ ctx mgr

    def __enter__(self) -> "_RichScanProgress":
        from rich.live import Live
        self._task = self._progress.add_task(
            "scan", total=self._total, current="")
        self._live = Live(
            self._build_renderable(),
            console=console,
            transient=True,
            refresh_per_second=14,
            auto_refresh=True,
        )
        self._live.__enter__()
        return self

    def __exit__(self, *exc) -> bool:
        return bool(self._live.__exit__(*exc))

    # ------------------------------------------------------------------ API

    def advance(self, current: str) -> None:
        self._progress.update(
            self._task, advance=1, current=_safe(console, current))
        if self._live is not None:
            self._live.update(self._build_renderable())

    def detection(self, rule_display: str, masked: str, location: str) -> None:
        """Record a secret hit and refresh the live feed immediately."""
        self._hits += 1
        self._feed.append((rule_display, masked, location))
        if self._live is not None:
            self._live.update(self._build_renderable())


def scan_progress(n_files: int):
    """Per-file progress bar on real terminals; silent no-op otherwise."""
    if console.is_terminal and not os.environ.get("AGENTSWEEP_NO_ANIM"):
        return _RichScanProgress(n_files)
    return _NullScanProgress()
