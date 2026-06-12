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
    "gemini-cli":            GeminiCliSource,
    "continue-vscode":       ContinueSource,
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
    "GeminiCliSource",
    "ContinueSource",
    "GitHubCopilotSource",
    "OpenClawSource",
    "HermesSource",
    "GooseSource",
]
