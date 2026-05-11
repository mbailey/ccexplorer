"""Tests for ccexplorer.data."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ccexplorer.data import (
    AggregatedRow,
    NON_TOOL,
    aggregate,
    process_session,
    project_from_slug,
)


class TestProjectFromSlug:
    def test_mbailey_path_returns_project_name(self):
        assert project_from_slug("-Users-admin-Code-github-com-mbailey-voicemode") == "voicemode"

    def test_mbailey_path_with_nested_segments(self):
        # Anything after 'mbailey' joined with dashes
        assert (
            project_from_slug("-Users-admin-Code-github-com-mbailey-foo-bar")
            == "foo-bar"
        )

    def test_no_mbailey_falls_back_to_last_two(self):
        assert project_from_slug("-tmp-foo-bar") == "foo-bar"

    def test_single_segment(self):
        # Single segment after stripping leading dash falls through to last-2
        # path which collapses to the one segment
        assert project_from_slug("-onlyone") == "onlyone"

    def test_empty_slug_does_not_crash(self):
        # Defensive: edge inputs shouldn't blow up
        result = project_from_slug("")
        assert isinstance(result, str)

    def test_mbailey_at_end_falls_back_to_last_part(self):
        # Pathological: "mbailey" is the last segment, nothing after
        assert project_from_slug("-Users-admin-mbailey") == "mbailey"


class TestAggregatedRow:
    def test_cost_sums_components(self):
        row = AggregatedRow(
            day="2026-05-10", project="voicemode", session="abc12345",
            tool="Bash", model="claude-opus-4-7",
            cost_input=1.0, cost_output=2.0, cost_cw5=3.0, cost_cw1=4.0, cost_cr=5.0,
        )
        assert row.cost == 15.0

    def test_is_tool_true_for_real_tool(self):
        row = AggregatedRow(
            day="d", project="p", session="s", tool="Bash", model="m",
            cost_input=0, cost_output=0, cost_cw5=0, cost_cw1=0, cost_cr=0,
        )
        assert row.is_tool is True

    def test_is_tool_false_for_non_tool_bucket(self):
        row = AggregatedRow(
            day="d", project="p", session="s", tool=NON_TOOL, model="m",
            cost_input=0, cost_output=0, cost_cw5=0, cost_cw1=0, cost_cr=0,
        )
        assert row.is_tool is False

    def test_to_dict_rounds_to_4_places(self):
        row = AggregatedRow(
            day="d", project="p", session="s", tool="Bash", model="m",
            cost_input=0.12345678, cost_output=0, cost_cw5=0, cost_cw1=0, cost_cr=0,
        )
        d = row.to_dict()
        assert d["cost_input"] == 0.1235
        assert d["cost"] == 0.1235
        assert d["isTool"] is True


@pytest.fixture
def fixture_session(tmp_path: Path) -> Path:
    """Write a tiny synthetic JSONL session and return its path."""
    project_dir = tmp_path / "-Users-admin-Code-github-com-mbailey-voicemode"
    project_dir.mkdir()
    session_file = project_dir / "12345678-1111-2222-3333-444444444444.jsonl"

    lines = [
        # Assistant turn with one tool call -- attributed to Bash
        {
            "timestamp": "2026-05-10T12:00:00.000Z",
            "message": {
                "model": "claude-opus-4-7",
                "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
                "content": [{"type": "tool_use", "name": "Bash"}],
            },
        },
        # Assistant turn with no tool -- goes to (non-tool)
        {
            "timestamp": "2026-05-10T13:00:00.000Z",
            "message": {
                "model": "claude-opus-4-7",
                "usage": {"output_tokens": 1_000_000},
                "content": [{"type": "text", "text": "hello"}],
            },
        },
        # Assistant turn with two tool calls -- output_tokens split 50/50
        {
            "timestamp": "2026-05-10T14:00:00.000Z",
            "message": {
                "model": "claude-opus-4-7",
                "usage": {"output_tokens": 2_000_000},
                "content": [
                    {"type": "tool_use", "name": "Read"},
                    {"type": "tool_use", "name": "Edit"},
                ],
            },
        },
        # Synthetic / cost-zero entries that should be skipped
        {
            "timestamp": "2026-05-10T15:00:00.000Z",
            "message": {"model": "<synthetic>", "usage": {"input_tokens": 1000}},
        },
        {
            "timestamp": "2026-05-10T16:00:00.000Z",
            "message": {"model": "claude-opus-4-7", "usage": {}},
        },
    ]
    session_file.write_text("\n".join(json.dumps(line) for line in lines))
    return session_file


class TestProcessSession:
    def test_apportionment_by_tool(self, fixture_session: Path):
        agg: dict = {}
        process_session(fixture_session, agg)

        # Keys are (day, project, session, tool, model)
        day = "2026-05-10"
        project = "voicemode"
        sid = "12345678"  # first 8 chars of the uuid
        model = "claude-opus-4-7"

        bash_key = (day, project, sid, "Bash", model)
        non_tool_key = (day, project, sid, NON_TOOL, model)
        read_key = (day, project, sid, "Read", model)
        edit_key = (day, project, sid, "Edit", model)

        assert bash_key in agg
        assert non_tool_key in agg
        assert read_key in agg
        assert edit_key in agg

        # Bash got the full input cost: 1M tokens * $15/M = $15
        assert agg[bash_key]["input"] == pytest.approx(15.0)

        # (non-tool) got the full $75 output
        assert agg[non_tool_key]["output"] == pytest.approx(75.0)

        # Read + Edit split 2M tokens evenly -- 1M output each = $75 each
        assert agg[read_key]["output"] == pytest.approx(75.0)
        assert agg[edit_key]["output"] == pytest.approx(75.0)

    def test_synthetic_and_zero_cost_rows_skipped(self, fixture_session: Path):
        agg: dict = {}
        process_session(fixture_session, agg)
        # We wrote 5 rows but two are skipped (synthetic, empty usage)
        # leaving Bash (1) + non-tool (1) + Read (1) + Edit (1) = 4 keys
        assert len(agg) == 4


class TestAggregate:
    def test_returns_aggregated_rows(self, fixture_session: Path):
        rows = aggregate([fixture_session])
        assert all(isinstance(r, AggregatedRow) for r in rows)
        assert len(rows) == 4

    def test_total_cost_matches_decomposition(self, fixture_session: Path):
        rows = aggregate([fixture_session])
        total = sum(r.cost for r in rows)
        # $15 (bash input) + $75 (non-tool output) + $75 + $75 (Read/Edit split)
        assert total == pytest.approx(240.0)

    def test_swallows_unreadable_file(self, tmp_path: Path, fixture_session: Path):
        # If one file is unreadable, aggregate() should keep going on the rest.
        bad = tmp_path / "-bad-project" / "doesnotexist.jsonl"
        # bad parent doesn't exist -- open() will raise -- aggregate must skip
        rows = aggregate([bad, fixture_session])
        assert len(rows) == 4  # only the good file's rows

    def test_empty_input_returns_empty_list(self):
        assert aggregate([]) == []
