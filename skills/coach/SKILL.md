---
name: coach
description: Shows Claude usage coaching — model fit, prompting patterns, underused features — based on session history and past digests.
---

# Coach

Show the user coaching on how they're using Claude and AI engineering concepts.

## Steps

1. Read `~/.claude/session-coaching.md` for past session digests (last 3 entries).

2. Read the current session JSONL to understand what's happening now:
   - Find the most recent JSONL: `ls -t ~/.claude/projects/*/*.jsonl | head -1`
   - Count exchanges, tools used, recent user messages

3. Synthesize and show:
   - **Past patterns** — recurring themes from recent session digests
   - **Current session** — how this session looks so far
   - **Top 3 coaching tips** — specific, actionable, based on what you actually see

4. **Tooling suggestions** (only if a theme repeats in ≥2 session digests):
   - WebSearch for an existing Claude Code plugin, skill, or MCP server that addresses the recurring gap
   - Present at most 1–2 suggestions, each with a link and one sentence on why it fits the observed pattern
   - Skip this step entirely if no theme repeats — no padding

Keep it concise. No generic advice — everything must be specific to what you observe in the actual session data.
