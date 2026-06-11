"""Per-file scan progress: live bar on terminals, silent no-op on pipes."""
from __future__ import annotations

import os

from .console import _safe, console


class _NullScanProgress:
    """No-op progress for pipes/CI — keeps the call sites unconditional."""

    def __enter__(self) -> "_NullScanProgress":
        return self

    def __exit__(self, *exc) -> bool:
        return False

    def advance(self, current: str) -> None:
        pass


class _RichScanProgress:
    """Live per-file progress bar for the SCAN phase.

    transient=True: the bar vanishes when done, so the pipeline's SCAN
    stage line takes its place without leftover bar artifacts.
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
            transient=True,
        )
        self._total = total
        self._task: int | None = None

    def __enter__(self) -> "_RichScanProgress":
        self._progress.__enter__()
        self._task = self._progress.add_task(
            "scan", total=self._total, current="")
        return self

    def __exit__(self, *exc) -> bool:
        return bool(self._progress.__exit__(*exc))

    def advance(self, current: str) -> None:
        self._progress.update(self._task, advance=1,
                              current=_safe(console, current))


def scan_progress(n_files: int):
    """Per-file progress bar on real terminals; silent no-op otherwise."""
    if console.is_terminal and not os.environ.get("AGENTSWEEP_NO_ANIM"):
        return _RichScanProgress(n_files)
    return _NullScanProgress()
