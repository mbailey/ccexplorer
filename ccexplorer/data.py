"""JSONL ingestion and aggregation.

Walks ``~/.claude/projects/<project-slug>/<session-uuid>.jsonl``,
apportions each assistant turn's token cost across its ``tool_use``
blocks (or to a synthetic ``(non-tool)`` bucket), and collapses the
stream to one row per ``(day, project, session, tool, model)`` tuple.

That dedupe takes a few million message-lines down to ~30-50K rows --
small enough to embed in a single HTML for client-side aggregation.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from ccexplorer.pricing import cost_for_usage

NON_TOOL = "(non-tool)"

DEFAULT_PROJECTS_ROOT = Path(os.path.expanduser("~/.claude/projects"))


@dataclass
class AggregatedRow:
    """One ``(day, project, session, tool, model)`` aggregate row."""

    day: str
    project: str
    session: str
    tool: str
    model: str
    cost_input: float
    cost_output: float
    cost_cw5: float
    cost_cw1: float
    cost_cr: float

    @property
    def cost(self) -> float:
        return (
            self.cost_input + self.cost_output + self.cost_cw5
            + self.cost_cw1 + self.cost_cr
        )

    @property
    def is_tool(self) -> bool:
        return self.tool != NON_TOOL

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "project": self.project,
            "session": self.session,
            "tool": self.tool,
            "isTool": self.is_tool,
            "model": self.model,
            "cost": round(self.cost, 4),
            "cost_input": round(self.cost_input, 4),
            "cost_output": round(self.cost_output, 4),
            "cost_cw5": round(self.cost_cw5, 4),
            "cost_cw1": round(self.cost_cw1, 4),
            "cost_cr": round(self.cost_cr, 4),
        }


def project_from_slug(slug: str) -> str:
    """Turn a Claude Code project-directory slug into a short project name.

    Claude Code stores transcripts under
    ``~/.claude/projects/<dash-escaped-path>/<session>.jsonl``. The
    directory name is the absolute working-directory path with slashes
    replaced by dashes -- e.g. ``-Users-admin-Code-github-com-mbailey-voicemode``.

    This heuristic picks the portion after a known organisation segment
    (``mbailey``) when present, falling back to the last segment.

    >>> project_from_slug("-Users-admin-Code-github-com-mbailey-voicemode")
    'voicemode'
    >>> project_from_slug("-tmp-foo-bar")
    'foo-bar'
    >>> project_from_slug("-single")
    'single'
    """
    parts = slug.lstrip("-").split("-")
    if "mbailey" in parts:
        i = parts.index("mbailey")
        tail = parts[i + 1:]
        if tail:
            return "-".join(tail)
        return parts[-1]
    if len(parts) >= 2:
        return "-".join(parts[-2:])
    return parts[0] if parts else slug


def _parse_day(ts: str) -> str | None:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None
    return dt.strftime("%Y-%m-%d")


def process_session(path: Path, agg: dict) -> None:
    """Fold one session JSONL into the running aggregate.

    Apportions each assistant turn's cost evenly across its ``tool_use``
    blocks. Turns with no tool calls accrue to a ``(non-tool)`` bucket.
    Cost-zero turns are skipped to keep the aggregate sparse.
    """
    sid_full = path.stem
    sid = sid_full[:8]
    project = project_from_slug(path.parent.name)
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = r.get("message") or {}
            usage = msg.get("usage") or {}
            model = msg.get("model") or ""
            ts = r.get("timestamp")
            if not usage or not model or model == "<synthetic>" or not ts:
                continue

            costs = cost_for_usage(model, usage)
            turn_cost = sum(costs.values())
            if turn_cost == 0:
                continue

            day = _parse_day(ts)
            if day is None:
                continue

            content = msg.get("content") if isinstance(msg.get("content"), list) else []
            tools = [
                b.get("name", "?") for b in content
                if isinstance(b, dict) and b.get("type") == "tool_use"
            ]
            if not tools:
                tools = [NON_TOOL]
            share = 1 / len(tools)

            for t in tools:
                key = (day, project, sid, t, model)
                a = agg.setdefault(key, {"input": 0, "output": 0, "cw5": 0, "cw1": 0, "cr": 0})
                a["input"]  += costs["input"]  * share
                a["output"] += costs["output"] * share
                a["cw5"]    += costs["cw5"]    * share
                a["cw1"]    += costs["cw1"]    * share
                a["cr"]     += costs["cr"]     * share


def iter_session_files(root: Path | None = None) -> Iterator[Path]:
    """Yield every ``<project>/<session>.jsonl`` under ``root``."""
    root = root or DEFAULT_PROJECTS_ROOT
    return iter(root.glob("*/*.jsonl"))


def aggregate(
    files: Iterable[Path],
    *,
    log_every: int = 500,
    verbose: bool = False,
) -> list[AggregatedRow]:
    """Walk JSONL files and return the dedupe'd aggregate as ``AggregatedRow``s.

    Errors on individual files (race conditions, corruption) are
    swallowed -- one bad file shouldn't fail the whole report.
    """
    files = list(files)
    if verbose:
        print(f"Walking {len(files)} session files...", file=sys.stderr)

    agg: dict = {}
    for i, f in enumerate(files):
        if verbose and log_every and i and i % log_every == 0:
            print(f"  {i}/{len(files)}...", file=sys.stderr)
        try:
            process_session(f, agg)
        except Exception:
            continue  # silently skip on race conditions / corruption

    rows: list[AggregatedRow] = []
    for (day, project, sid, tool, model), c in agg.items():
        row = AggregatedRow(
            day=day, project=project, session=sid, tool=tool, model=model,
            cost_input=c["input"], cost_output=c["output"],
            cost_cw5=c["cw5"], cost_cw1=c["cw1"], cost_cr=c["cr"],
        )
        if row.cost < 0.0001:
            continue
        rows.append(row)

    if verbose:
        total = sum(r.cost for r in rows)
        print(
            f"Aggregated to {len(rows)} rows, ${total:.2f} total",
            file=sys.stderr,
        )
    return rows
