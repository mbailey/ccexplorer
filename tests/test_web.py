"""Tests for ccexplorer.web."""
from __future__ import annotations

from pathlib import Path

import pytest

from ccexplorer.data import AggregatedRow
from ccexplorer.web import TEMPLATE_PATH, render_html, write_html


@pytest.fixture
def sample_rows() -> list[AggregatedRow]:
    return [
        AggregatedRow(
            day="2026-05-10", project="voicemode", session="aaaaaaaa",
            tool="Bash", model="claude-opus-4-7",
            cost_input=10.0, cost_output=5.0, cost_cw5=2.0, cost_cw1=0.0, cost_cr=1.0,
        ),
        AggregatedRow(
            day="2026-05-11", project="taskmaster", session="bbbbbbbb",
            tool="Read", model="claude-sonnet-4-6",
            cost_input=1.0, cost_output=0.5, cost_cw5=0.1, cost_cw1=0.0, cost_cr=0.05,
        ),
    ]


class TestRenderHtml:
    def test_replaces_all_placeholders(self, sample_rows):
        html = render_html(sample_rows)
        # No raw placeholders should remain
        assert "__ROWS_JSON__" not in html
        assert "__PROJECTS__" not in html
        assert "__TOOLS__" not in html
        assert "__MODELS__" not in html
        assert "__DAY0__" not in html
        assert "__DAY1__" not in html
        assert "__GRAND_TOTAL__" not in html
        assert "__NROWS__" not in html
        assert "__NSESSIONS__" not in html
        assert "__NPROJECTS__" not in html

    def test_grand_total_in_header(self, sample_rows):
        html = render_html(sample_rows)
        # Total = 18.0 + 1.65 = 19.65
        assert "$19.65" in html

    def test_includes_row_data_as_embedded_json(self, sample_rows):
        html = render_html(sample_rows)
        # The template puts the JSON into a JS var; just confirm at least
        # one identifying value made it through.
        assert '"project": "voicemode"' in html or "voicemode" in html
        assert '"tool": "Bash"' in html or "Bash" in html

    def test_handles_empty_rows(self):
        html = render_html([])
        assert "__ROWS_JSON__" not in html
        assert "$0.00" in html

    def test_day_range_is_min_and_max(self, sample_rows):
        html = render_html(sample_rows)
        assert "2026-05-10" in html  # earliest
        assert "2026-05-11" in html  # latest


class TestWriteHtml:
    def test_writes_file(self, tmp_path: Path, sample_rows):
        out = tmp_path / "out" / "report.html"
        result = write_html(sample_rows, out)
        assert result == out
        assert out.exists()
        assert "$19.65" in out.read_text()


class TestTemplate:
    def test_template_file_exists(self):
        assert TEMPLATE_PATH.exists(), f"template missing at {TEMPLATE_PATH}"

    def test_template_has_expected_placeholders(self):
        content = TEMPLATE_PATH.read_text()
        for placeholder in (
            "__ROWS_JSON__", "__PROJECTS__", "__TOOLS__", "__MODELS__",
            "__DAY0__", "__DAY1__", "__GRAND_TOTAL__", "__NROWS__",
            "__NSESSIONS__", "__NPROJECTS__",
        ):
            assert placeholder in content, f"missing placeholder {placeholder}"
