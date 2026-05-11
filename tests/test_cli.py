"""Smoke tests for the `cce` CLI."""
from __future__ import annotations

import json
from pathlib import Path


from ccexplorer.cli import build_parser, main


class TestParser:
    def test_version_flag_set(self):
        # argparse exits when --version is parsed; that's fine in production
        # but `build_parser()` itself should construct successfully.
        parser = build_parser()
        assert parser.prog == "cce"

    def test_build_subcommand_exists(self):
        parser = build_parser()
        args = parser.parse_args(["build", "--no-open", "-q"])
        assert args.command == "build"
        assert args.open is False
        assert args.quiet is True

    def test_build_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["build"])
        assert args.command == "build"
        assert args.open is True
        assert args.quiet is False


class TestMain:
    def test_build_against_fixture_tree(self, tmp_path: Path):
        # Create a minimal projects tree with one tiny session
        root = tmp_path / "projects"
        proj = root / "-Users-admin-Code-github-com-mbailey-voicemode"
        proj.mkdir(parents=True)
        sess = proj / "12345678-1111-2222-3333-444444444444.jsonl"
        sess.write_text(json.dumps({
            "timestamp": "2026-05-10T12:00:00Z",
            "message": {
                "model": "claude-opus-4-7",
                "usage": {"output_tokens": 1_000_000},
                "content": [{"type": "tool_use", "name": "Bash"}],
            },
        }))

        out = tmp_path / "report.html"
        rc = main([
            "build", "--projects-root", str(root),
            "--output", str(out), "--no-open", "-q",
        ])
        assert rc == 0
        assert out.exists()
        text = out.read_text()
        # 1M opus output tokens = $75
        assert "$75.00" in text
        assert "Bash" in text

    def test_missing_projects_root_returns_nonzero(self, tmp_path: Path):
        out = tmp_path / "report.html"
        missing = tmp_path / "does-not-exist"
        rc = main([
            "build", "--projects-root", str(missing),
            "--output", str(out), "--no-open", "-q",
        ])
        assert rc == 2
        assert not out.exists()
