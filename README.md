# ccexplorer

**Local-first Cost Explorer for Claude Code sessions.** Walks
`~/.claude/projects/<project>/<session>.jsonl`, aggregates token usage,
and renders an AWS-Cost-Explorer-style interactive HTML report so you
can slice your spend by **tool, project, session, model, and time**.

> **Status: alpha** -- v0.0.1 ships the `cce build` static-HTML path.
> CLI query subcommands (`get-cost-and-usage`, `get-dimension-values`)
> and the Trusted-Advisor-style recommendations engine are next.

## Why

ccusage already does cost calculation well. ccexplorer adds two things
the existing tools don't:

1. **Tool/agent attribution.** Apportions each assistant turn's cost
   across its `tool_use` blocks so you can see *which tools* the money
   actually went to (and how much went to non-tool conversation).
2. **A slice-and-dice surface.** Same query model as AWS Cost
   Explorer -- time-period x granularity x metrics x group-by x filter
   -- so you can answer questions like "today's voicemode tool calls,
   grouped by session" without writing SQL.

A recommendations engine ("Trusted Advisor for Claude Code") is the
next layer on top -- top-N tool over-use, repeat-read detection,
cache-write premium, etc.

## Privacy

100% local. The tool never makes a network call. The report is a
single HTML file with your data embedded as JSON; it loads
[Chart.js](https://www.chartjs.org/) from a CDN but nothing else
leaves your machine.

## Install

```bash
# Zero-install run
uvx ccexplorer

# Or install persistently
pip install ccexplorer
```

## Usage

```bash
# Walk ~/.claude/projects, build /tmp/cce.html, open it in your browser
cce build

# Custom output path, no browser launch
cce build --output ~/cce-report.html --no-open

# Different projects root (rarely needed)
cce build --projects-root /path/to/.claude/projects
```

Run with no subcommand and you get `cce build` with default flags --
the "just show me the pretty thing" path.

## What the report shows

* Total spend, with breakdowns by tool, project, session, model, and day
* Tool vs non-tool token-cost split (often surprising -- ~50% of long
  sessions is non-tool conversation)
* Cache-write / cache-read / input / output split (cache writes are
  often the largest line item on Opus sessions)
* AWS-Cost-Explorer-style sidebar: time-range presets (1d / 7d / 30d /
  All), group-by dropdowns, filter chips, advanced toggles

## Roadmap

* [ ] `cce get-cost-and-usage` (CLI flagship, mirrors `aws ce`)
* [ ] `cce get-dimension-values` (enumerate tools / projects / models)
* [ ] AGENT dimension (extract sub-agent type from `Agent` tool calls)
* [ ] TAG support (sidecar `<session>.tags.json` or `cce tag` command)
* [ ] COST_CATEGORY rules engine
* [ ] `cce serve` (live local server, no rebuild on every change)
* [ ] `cce advise` -- recommendations engine

## Acknowledgements

Idea and voice-spec: [Mike Bailey](https://failmode.com)
([@mbailey](https://github.com/mbailey)) -- including the $46k of
his own session data we validated against. Research, prototype,
write-up: Cora 7. A "How this got built" page is forthcoming -- this
project is transparent about its AI-pair-programming origin.

## License

[MIT](LICENSE).
