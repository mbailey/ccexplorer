"""Render aggregated session data as an interactive HTML report.

The template at ``ccexplorer/templates/all.html`` uses ``__SLUG__``-style
placeholders. We embed the data as JSON and let the browser do
slice-and-dice client-side -- no server, no upload, no account.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ccexplorer.data import AggregatedRow

TEMPLATE_PATH = Path(__file__).parent / "templates" / "all.html"


def render_html(rows: Iterable[AggregatedRow]) -> str:
    """Return a fully-self-contained HTML report for ``rows``."""
    rows = list(rows)
    row_dicts = [r.to_dict() for r in rows]

    days = sorted({r.day for r in rows})
    projects = sorted({r.project for r in rows})
    tools = sorted({r.tool for r in rows})
    models = sorted({r.model for r in rows})
    sessions = {r.session for r in rows}

    grand_total = sum(r.cost for r in rows)

    template = TEMPLATE_PATH.read_text()
    substitutions = {
        "__ROWS_JSON__": json.dumps(row_dicts),
        "__PROJECTS__": json.dumps(projects),
        "__TOOLS__": json.dumps(tools),
        "__MODELS__": json.dumps(models),
        "__DAY0__": days[0] if days else "",
        "__DAY1__": days[-1] if days else "",
        "__GRAND_TOTAL__": f"{grand_total:.2f}",
        "__NROWS__": str(len(row_dicts)),
        "__NSESSIONS__": str(len(sessions)),
        "__NPROJECTS__": str(len(projects)),
    }
    for placeholder, value in substitutions.items():
        template = template.replace(placeholder, value)
    return template


def write_html(rows: Iterable[AggregatedRow], output: Path) -> Path:
    """Render and write the report to ``output``, returning the path."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(rows))
    return output
