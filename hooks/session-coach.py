#!/usr/bin/env python3
"""SessionEnd coaching hook.

Analyzes the finished session's JSONL transcript (token usage, tool calls,
message samples) with Haiku and writes a 5-dimension coaching digest to
~/.claude/session-coaching.md. Prints the report to the user's terminal
after Claude Code exits, and the companion SessionStart hook re-displays
it at the next session start.

Disable by creating ~/.claude/.coaching-off.
"""
import json, os, glob, sys, re, subprocess, traceback
from datetime import datetime

OFF_FLAG = os.path.expanduser("~/.claude/.coaching-off")
ERROR_LOG = os.path.expanduser("~/.claude/coach-errors.log")
DEBUG_LOG = os.path.expanduser("~/.claude/coach-debug.log")
COACHING_FILE = os.path.expanduser("~/.claude/session-coaching.md")

DIMENSIONS = ["model_fit", "prompt_quality", "underused_features", "context_management", "top_tip"]

def get_terminal():
    # The hook's parent (Claude Code) is attached to the user's terminal.
    # Capture its tty device BEFORE daemonizing so the survivor child can
    # print the report into the shell after Claude Code exits.
    try:
        tty = subprocess.run(
            ["ps", "-o", "tty=", "-p", str(os.getppid())],
            capture_output=True, text=True
        ).stdout.strip()
        if tty and tty != "??":
            return f"/dev/{tty}"
    except Exception:
        pass
    return None

def debug(msg):
    with open(DEBUG_LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} {msg}\n")

def get_session_jsonl(session_id):
    if session_id:
        matches = glob.glob(os.path.expanduser(f"~/.claude/projects/*/{session_id}.jsonl"))
        if matches:
            return matches[0]
    all_files = glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl"))
    return max(all_files, key=os.path.getmtime) if all_files else None

def extract_data(path):
    lines = [l.strip() for l in open(path) if l.strip()]
    user_msgs, tools, tokens = [], {}, {}
    exchanges = 0

    for line in lines:
        try:
            obj = json.loads(line)
            msg = obj.get("message", {})
            if msg.get("role") == "assistant" and "usage" in msg:
                exchanges += 1
                model = msg.get("model", "").replace("claude-", "")
                usage = msg.get("usage", {})
                t = tokens.setdefault(model, {"in": 0, "out": 0, "cache_read": 0, "cache_write": 0})
                t["in"] += usage.get("input_tokens", 0)
                t["out"] += usage.get("output_tokens", 0)
                t["cache_read"] += usage.get("cache_read_input_tokens", 0)
                t["cache_write"] += usage.get("cache_creation_input_tokens", 0)
                for b in msg.get("content", []):
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        name = b.get("name", "")
                        tools[name] = tools.get(name, 0) + 1
            if obj.get("type") == "user":
                content = msg.get("content", "")
                text = content if isinstance(content, str) else next(
                    (b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"), ""
                )
                clean = re.sub(r"<[^>]+>.*?</[^>]+>", "", text, flags=re.DOTALL).strip()
                if clean and len(clean) > 8 and not clean.startswith("<"):
                    user_msgs.append(clean[:200])
        except Exception:
            continue

    tokens = {m: t for m, t in tokens.items() if t["in"] + t["out"] + t["cache_read"] + t["cache_write"] > 0}
    sample = (user_msgs[:4] + ["..."] + user_msgs[-4:]) if len(user_msgs) > 8 else user_msgs
    latest = user_msgs[-1] if user_msgs else ""
    tool_summary = ", ".join(f"{k}×{v}" for k, v in sorted(tools.items(), key=lambda x: -x[1]))
    return {
        "exchanges": exchanges,
        "tokens": tokens,
        "tools": tool_summary,
        "sample": sample,
        "latest": latest,
    }

def format_tokens(tokens):
    lines = []
    for model, t in tokens.items():
        total_in = t["in"] + t["cache_read"] + t["cache_write"]
        hit = (t["cache_read"] / total_in * 100) if total_in else 0
        lines.append(f"  {model}: in={t['in']:,} out={t['out']:,} cache_read={t['cache_read']:,} cache_write={t['cache_write']:,} (cache hit {hit:.0f}%)")
    return "\n".join(lines)

def get_digest(data):
    from anthropic import Anthropic
    client = Anthropic()

    prompt = f"""You are a Claude Code coaching advisor. Analyze this session.

Session pattern:
- Exchanges: {data['exchanges']}
- Token usage per model:
{format_tokens(data['tokens'])}
- Tool calls: {data['tools']}
- Message sample: {data['sample']}

Latest user message: {data['latest']}

The model(s) actually used: {', '.join(data['tokens'].keys())} — refer to them by these exact names, do not guess other model names.

Note: this report is itself produced by an existing SessionEnd coaching hook. Never recommend building a session-summary hook, session-end report, or coaching system — it already exists and is what generated this analysis.

Judge across these dimensions, each grounded in the actual numbers/messages above (no generic advice):
- model_fit: was the model(s) right for the work? Could a cheaper model (Haiku/Sonnet) have handled it? Use token volumes and task types as evidence.
- prompt_quality: were prompts clear? Signs of repeated clarification or rework?
- underused_features: Claude Code features that would have helped (plan mode, subagents, hooks, skills, /clear, loops, MCP, structured outputs).
- context_management: judge from cache hit rate and input token volume — was context bloated, should the session have been split?
- top_tip: the single most valuable change for next session.

Keep each value to one short sentence. If the session is only conversational/social (thanks, ok, hi) return null for every key.

Return only JSON:
{{
  "model_fit": "...",
  "prompt_quality": "...",
  "underused_features": "...",
  "context_management": "...",
  "top_tip": "..."
}}"""

    resp = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = re.sub(r"^```(?:json)?\s*", "", resp.content[0].text.strip())
    raw = re.sub(r"\s*```$", "", raw).strip()
    return json.loads(raw)

def main():
    stdin_data = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            stdin_data = json.loads(raw)
    except Exception:
        pass

    debug(f"invoked session={stdin_data.get('session_id', '?')} reason={stdin_data.get('reason', '?')}")

    if os.path.exists(OFF_FLAG):
        debug("skip: coaching disabled (~/.claude/.coaching-off)")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        debug("skip: ANTHROPIC_API_KEY not set")
        return

    path = get_session_jsonl(stdin_data.get("session_id", ""))
    if not path:
        debug("skip: no jsonl found")
        return

    data = extract_data(path)
    if data["exchanges"] < 3:
        debug(f"skip: only {data['exchanges']} exchanges")
        return

    tty_path = get_terminal()

    # Detach from Claude Code before the API call — teardown kills the hook
    # process, so the slow part must run in a survivor child.
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)

    debug(f"calling haiku: {data['exchanges']} exchanges")
    digest = get_digest(data)
    debug("haiku returned")
    if not digest or not digest.get("top_tip"):
        return

    sid = (stdin_data.get("session_id") or "unknown")[:8]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    models = ", ".join(data["tokens"].keys())

    labels = {
        "model_fit": "Model fit",
        "prompt_quality": "Prompt quality",
        "underused_features": "Underused features",
        "context_management": "Context mgmt",
        "top_tip": "Top tip",
    }

    report_lines = []
    entry_lines = [f"## {timestamp} · {data['exchanges']} exchanges · {models} · sid:{sid}"]
    for key in DIMENSIONS:
        val = digest.get(key)
        if val:
            report_lines.append(f"  {labels[key]}: {val}")
            entry_lines.append(f"- **{labels[key]}:** {val}")
    entry_lines.append(f"- Tokens: {format_tokens(data['tokens']).strip()}")
    entry_lines.append(f"- Tools: {data['tools']}")

    # One digest per session: re-quitting the same session replaces its entry.
    blocks = []
    if os.path.exists(COACHING_FILE):
        content = open(COACHING_FILE).read()
        blocks = [b.strip() for b in content.split("\n---\n") if b.strip() and f"sid:{sid}" not in b]
    blocks.append("\n".join(entry_lines))
    with open(COACHING_FILE, "w") as f:
        f.write("\n---\n".join([""] + blocks) + "\n")

    if tty_path:
        try:
            with open(tty_path, "w") as t:
                t.write("\n📋 Session coaching:\n" + "\n".join(report_lines) + "\n")
            debug(f"report written to {tty_path}")
        except Exception:
            debug(f"tty write failed: {tty_path}")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        with open(ERROR_LOG, "a") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n{traceback.format_exc()}")
