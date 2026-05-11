"""ccexplorer -- local-first Cost Explorer for Claude Code sessions.

Reads ``~/.claude/projects/*/*.jsonl``, aggregates token usage by
(day, project, session, tool, model), and renders an AWS-Cost-Explorer-style
interactive HTML report. No data leaves your machine.

Entry point: ``cce`` (see :mod:`ccexplorer.cli`).
"""

__version__ = "0.0.1"

__all__ = ["__version__"]
