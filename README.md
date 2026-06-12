# session-coach

Learn something about your AI usage every session. When you quit Claude Code, this plugin analyzes the session you just finished — real token usage, cache hit rate, tool calls, your actual prompts — and prints a 5-dimension coaching report:

```
📋 Session coaching:
  Model fit: Fable-5 was appropriate for this skill-building session, though ...
  Prompt quality: Prompts were fragmented initially; stating the goal upfront ...
  Underused features: Plan mode would have structured the workflow before coding ...
  Context mgmt: 94% cache hit is excellent; consider /clear between phases ...
  Top tip: Start with a one-sentence goal and request a plan before coding.
```

The report appears in your terminal ~5 seconds after quitting, again at the next session start, and `/coach` shows cross-session patterns on demand.

## How it works

| Piece | Mechanism |
|---|---|
| **SessionEnd hook** | On quit, reads the session transcript (JSONL), daemonizes (Claude Code kills hooks during teardown, so the analysis runs in a detached child), sends usage stats to `claude-haiku-4-5`, appends a digest to `~/.claude/session-coaching.md`, prints the report to your terminal. |
| **SessionStart hook** | Displays the last digest at the start of your next session — also loads it into Claude's context, so Claude sees its own coaching. |
| **`/coach` skill** | On-demand: recurring themes across sessions + suggestions for plugins/skills that address repeated gaps. |

One digest per session — re-quitting a resumed session replaces its entry instead of duplicating.

## Requirements

- macOS or Linux (uses `fork`, `ps`, tty devices — no Windows)
- Python 3 with the `anthropic` package: `pip3 install anthropic`
- `ANTHROPIC_API_KEY` environment variable with API billing — a Claude Pro/Max subscription alone is **not** enough; the hook calls the API directly. Cost: one Haiku call per session, well under $0.01.

If the key or package is missing, the hook silently skips (see `~/.claude/coach-debug.log`).

## Install

```
/plugin marketplace add Shahana-Hamza-Mamutty/session-coach
/plugin install session-coach
```

Or clone and add as a local marketplace:

```
git clone https://github.com/Shahana-Hamza-Mamutty/session-coach.git
/plugin marketplace add /path/to/session-coach
```

## Privacy note

The hook sends short samples of your session messages (up to 8 messages, 200 chars each) plus token/tool statistics to the Anthropic API. This is the same data Claude Code already sends during normal use, but via your API key instead of your subscription. If your organization treats those channels differently, check policy before enabling.

## Disable / debug

- Disable without uninstalling: `touch ~/.claude/.coaching-off`
- Invocation trace: `~/.claude/coach-debug.log`
- Failures: `~/.claude/coach-errors.log`
- Digest history: `~/.claude/session-coaching.md`

## Known limitations

- The report prints over your shell prompt a few seconds after quit — press Enter for a clean prompt.
- Haiku judges from samples and statistics; treat tips as prompts for reflection, not verdicts.
- Sessions under 3 exchanges are skipped.
