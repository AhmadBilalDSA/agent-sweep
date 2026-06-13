"""Public API for the sources package.

All external code imports from here:
    from .sources import SOURCES, Source
    from .sources import ClaudeCodeSource, ...
"""
from ._base import JsonlSource, KeyPath, Source
from ._community import GooseSource, HermesSource, OpenClawSource
from ._core import AiderSource, ClaudeCodeSource, CodexSource, OpenCodeSource
from ._extended import (
    ClineSource,
    ContinueSource,
    GeminiCliSource,
    GitHubCopilotSource,
    KiloCodeSource,
    OpenInterpreterSource,
    RooCodeSource,
)
from ._vscode import CursorSource, WindsurfSource

SOURCES: dict[str, type[Source]] = {
    "claude-code":           ClaudeCodeSource,
    "codex":                 CodexSource,
    "opencode":              OpenCodeSource,
    "cursor":                CursorSource,
    "windsurf":              WindsurfSource,
    "aider":                 AiderSource,
    "cline":                 ClineSource,
    "kilo-code":             KiloCodeSource,
    "roo-code":              RooCodeSource,
    "gemini-cli":            GeminiCliSource,
    "continue-vscode":       ContinueSource,
    "open-interpreter":      OpenInterpreterSource,
    "github-copilot-chat":   GitHubCopilotSource,
    "openclaw":              OpenClawSource,
    "hermes":                HermesSource,
    "goose":                 GooseSource,
}

__all__ = [
    "Source",
    "JsonlSource",
    "KeyPath",
    "SOURCES",
    "ClaudeCodeSource",
    "CodexSource",
    "OpenCodeSource",
    "CursorSource",
    "WindsurfSource",
    "AiderSource",
    "ClineSource",
    "KiloCodeSource",
    "RooCodeSource",
    "GeminiCliSource",
    "ContinueSource",
    "OpenInterpreterSource",
    "GitHubCopilotSource",
    "OpenClawSource",
    "HermesSource",
    "GooseSource",
]
