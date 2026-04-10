#!/usr/bin/env python3
"""
Stealth PR Reviewer — looks like you wrote every word.

Usage:
    rpr 42                          # Review PR #42 in current repo
    rpr 42 --repo owner/repo        # Review PR #42 in specific repo
    rpr 42 --depth quick            # Fast scan: blockers & security only
    rpr 42 --depth thorough         # Deep review: architecture, style, edge cases
    rpr 42 --comment-only           # Post as a single PR comment (not inline review)
    rpr 42 --dry-run                # Print review to terminal, don't post
    rpr 42 --approve                # Post review + approve the PR
    rpr 42 --request-changes        # Post review + request changes
"""

# Postpones evaluation of annotations so PEP 604 syntax (e.g. `str | None`)
# works on Python 3.9 — required because pyproject.toml declares >= 3.9.
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import threading
import urllib.error
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "model": "claude-opus-4-6",
    "max_tokens": 16000,
    "max_diff_chars": 120000,
    "skip_patterns": [
        "*.lock",
        "*.g.dart",
        "*.freezed.dart",
        "*.gen.dart",
        "*.mocks.dart",
        "pubspec.lock",
        "package-lock.json",
        "yarn.lock",
        "Podfile.lock",
        "*.pbxproj",
    ],
}


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _config_search_paths() -> list[Path]:
    """Search order for the user's config file. First match wins."""
    return [
        Path.cwd() / "rpr.config.json",          # project-local override
        _xdg_config_home() / "rpr" / "config.json",  # user config
    ]


def _guidelines_search_paths() -> list[Path]:
    """Search order for the review-guidelines.md file. First match wins."""
    return [
        Path.cwd() / "review-guidelines.md",
        _xdg_config_home() / "rpr" / "review-guidelines.md",
    ]


def load_config() -> dict:
    config = DEFAULT_CONFIG.copy()
    for p in _config_search_paths():
        if p.exists():
            with open(p) as f:
                config.update(json.load(f))
            break
    return config


# ---------------------------------------------------------------------------
# Update check
# ---------------------------------------------------------------------------

UPDATE_CHECK_INTERVAL = 3600  # seconds between PyPI checks


def _update_cache_path() -> Path:
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return cache_dir / "rpr" / "update-check.json"


def _version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


def check_for_update() -> str | None:
    """Check PyPI for a newer version. Returns a notification string or None.

    Results are cached for UPDATE_CHECK_INTERVAL seconds so most runs
    hit a local file instead of the network.
    """
    from rpr import __version__

    cache_path = _update_cache_path()
    latest = None

    # Use cached result if fresh enough
    try:
        if cache_path.exists():
            cache = json.loads(cache_path.read_text())
            if time.time() - cache.get("checked_at", 0) < UPDATE_CHECK_INTERVAL:
                latest = cache.get("latest")
                if latest and _version_tuple(latest) > _version_tuple(__version__):
                    return _update_msg(__version__, latest)
                return None
    except (json.JSONDecodeError, OSError):
        pass

    # Fetch from PyPI
    try:
        req = urllib.request.Request(
            "https://pypi.org/pypi/rpr/json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latest = data["info"]["version"]
    except Exception:
        return None

    # Cache the result
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "checked_at": time.time(),
            "latest": latest,
        }))
    except OSError:
        pass

    if latest and _version_tuple(latest) > _version_tuple(__version__):
        return _update_msg(__version__, latest)
    return None


def _update_msg(current: str, latest: str) -> str:
    line1 = f" Update available: {current} → {latest} "
    line2 = " pip install -U rpr "
    width = max(len(line1), len(line2))
    return (
        f"\n╭{'─' * width}╮\n"
        f"│{line1:<{width}}│\n"
        f"│{line2:<{width}}│\n"
        f"╰{'─' * width}╯"
    )


# ---------------------------------------------------------------------------
# Review depth modes
# ---------------------------------------------------------------------------

REVIEW_DEPTHS = {
    "quick": {
        "label": "quick",
        "focus": (
            "REVIEW DEPTH: QUICK (blockers only)\n"
            "Only flag issues that would block a merge:\n"
            "- Bugs that WILL break production\n"
            "- Security vulnerabilities (injection, auth bypass, data exposure)\n"
            "- Data loss or corruption risks\n"
            "- Major architectural violations that are costly to fix later\n\n"
            "Skip everything else — no nits, no style, no suggestions, no minor edge cases.\n"
            "If nothing is blocking, approve with a short summary. Keep it fast."
        ),
    },
    "default": {
        "label": "default",
        "focus": "",  # uses the standard system prompt as-is
    },
    "thorough": {
        "label": "thorough",
        "focus": (
            "REVIEW DEPTH: THOROUGH\n"
            "Go deep on this one. In addition to the usual focus areas, also look at:\n"
            "- Architectural fit — does this change belong here? Is the abstraction right?\n"
            "- Edge cases and boundary conditions, even unlikely ones\n"
            "- Error messages — are they helpful for debugging?\n"
            "- Naming clarity — would a new team member understand this code?\n"
            "- API design — are the interfaces clean and hard to misuse?\n"
            "- Testability — is this code easy or hard to test?\n"
            "- Performance at scale — what happens with 10x/100x the data?\n\n"
            "Be thorough but still prioritize: lead with the important stuff."
        ),
    },
}

VALID_DEPTHS = list(REVIEW_DEPTHS.keys())


# ---------------------------------------------------------------------------
# GitHub helpers (uses `gh` CLI — no extra dependencies)
# ---------------------------------------------------------------------------


def run_gh(args: list, repo: str | None = None) -> str:
    cmd = ["gh"]
    if repo:
        cmd += ["--repo", repo]
    cmd += args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ gh error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def try_run_gh(args: list, repo: str | None = None) -> str | None:
    """Like run_gh but returns None on failure instead of exiting."""
    cmd = ["gh"]
    if repo:
        cmd += ["--repo", repo]
    cmd += args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout


def get_pr_info(pr_number: int, repo: str | None) -> dict:
    """Fetch PR metadata."""
    raw = run_gh(
        [
            "pr",
            "view",
            str(pr_number),
            "--json",
            "title,body,baseRefName,headRefName,files,url,additions,deletions",
        ],
        repo,
    )
    return json.loads(raw)


def get_pr_diff(pr_number: int, repo: str | None) -> str:
    """Fetch the unified diff."""
    return run_gh(["pr", "diff", str(pr_number)], repo)


def get_pr_files(pr_number: int, repo: str | None) -> list:
    """Fetch changed files with patches via API."""
    raw = run_gh(
        ["api", f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/files", "--paginate"],
        repo,
    )
    return json.loads(raw)


def get_previous_reviews(pr_number: int, repo: str | None) -> tuple[list, list]:
    """Fetch previous reviews and inline comments on the PR."""
    reviews: list = []
    comments: list = []

    raw = try_run_gh(
        ["api", f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews", "--paginate"],
        repo,
    )
    if raw:
        try:
            reviews = json.loads(raw)
        except json.JSONDecodeError:
            pass

    raw = try_run_gh(
        ["api", f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments", "--paginate"],
        repo,
    )
    if raw:
        try:
            comments = json.loads(raw)
        except json.JSONDecodeError:
            pass

    return reviews, comments


def format_previous_reviews(reviews: list, comments: list) -> str:
    """Format previous reviews into a prompt section. Returns '' if none."""
    if not reviews and not comments:
        return ""

    parts: list[str] = []

    for r in reviews:
        body = (r.get("body") or "").strip()
        if not body:
            continue
        user = r.get("user", {}).get("login", "unknown")
        state = r.get("state", "COMMENTED")
        parts.append(f"[{user} — {state}]\n{body}")

    for c in comments:
        body = (c.get("body") or "").strip()
        if not body:
            continue
        user = c.get("user", {}).get("login", "unknown")
        path = c.get("path", "?")
        line = c.get("line") or c.get("original_line") or "?"
        parts.append(f"[{user} on {path}:{line}]\n{body}")

    if not parts:
        return ""

    section = "PREVIOUS REVIEWS AND COMMENTS ON THIS PR:\n"
    section += "---\n"
    section += "\n\n".join(parts)
    section += "\n---\n\n"
    section += (
        "IMPORTANT — when considering previous feedback:\n"
        "- Do NOT repeat comments that were already made\n"
        "- If a previous concern has been addressed in the current diff, do not raise it again\n"
        "- If all previous issues are resolved and no new issues found, use \"approve\"\n"
        "- Only raise NEW issues not already covered by previous reviews\n\n"
    )
    return section


def post_review_comment(pr_number: int, body: str, repo: str | None):
    """Post a simple comment on the PR (not an inline review)."""
    run_gh(["pr", "comment", str(pr_number), "--body", body], repo)


def post_review(
    pr_number: int,
    body: str,
    comments: list,
    event: str,
    repo: str | None,
):
    """
    Submit a pull request review with optional inline comments.
    event: COMMENT | APPROVE | REQUEST_CHANGES
    """
    # Build the review payload
    payload = {"event": event, "body": body}

    if comments:
        payload["comments"] = []
        for c in comments:
            entry = {
                "path": c["path"],
                "body": c["body"],
            }
            # Use line-based positioning
            if c.get("line"):
                entry["line"] = c["line"]
                entry["side"] = "RIGHT"
            elif c.get("position"):
                entry["position"] = c["position"]

            # Multi-line comment support
            if c.get("start_line") and c.get("line") and c["start_line"] != c["line"]:
                entry["start_line"] = c["start_line"]
                entry["start_side"] = "RIGHT"

            payload["comments"].append(entry)

    payload_json = json.dumps(payload)

    # Use gh api to submit the review
    result = subprocess.run(
        _gh_cmd(
            [
                "api",
                f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews",
                "--method",
                "POST",
                "--input",
                "-",
            ],
            repo,
        ),
        input=payload_json,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        err = result.stderr.strip()
        # If inline comments fail (common with line number mismatches),
        # fall back to posting as a single review body
        if "pull_request_review_thread" in err or "Validation" in err:
            print("⚠️  Inline comments failed, falling back to body-only review...", file=sys.stderr)
            fallback_body = body + "\n\n---\n\n"
            for c in comments:
                fallback_body += f"**`{c['path']}`**"
                if c.get("line"):
                    fallback_body += f" (line {c['line']})"
                fallback_body += f"\n{c['body']}\n\n"

            fallback_payload = json.dumps({"event": event, "body": fallback_body})
            subprocess.run(
                _gh_cmd(
                    [
                        "api",
                        f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews",
                        "--method",
                        "POST",
                        "--input",
                        "-",
                    ],
                    repo,
                ),
                input=fallback_payload,
                capture_output=True,
                text=True,
            )
        else:
            print(f"❌ Review submission error: {err}", file=sys.stderr)
            sys.exit(1)


def _gh_cmd(args: list, repo: str | None) -> list:
    cmd = ["gh"]
    if repo:
        cmd += ["--repo", repo]
    cmd += args
    return cmd


# ---------------------------------------------------------------------------
# Diff filtering
# ---------------------------------------------------------------------------


def should_skip_file(filename: str, skip_patterns: list) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(filename, pat) for pat in skip_patterns)


def filter_diff(diff: str, skip_patterns: list) -> str:
    """Remove diff hunks for files matching skip patterns."""
    lines = diff.split("\n")
    filtered = []
    skip_current = False
    current_file = None

    for line in lines:
        if line.startswith("diff --git"):
            # Extract filename: diff --git a/path b/path
            parts = line.split(" b/")
            current_file = parts[-1] if len(parts) > 1 else None
            skip_current = current_file and should_skip_file(current_file, skip_patterns)

        if not skip_current:
            filtered.append(line)

    return "\n".join(filtered)


def truncate_diff(diff: str, max_chars: int) -> tuple:
    """Truncate diff if too large, return (diff, was_truncated)."""
    if len(diff) <= max_chars:
        return diff, False
    return diff[:max_chars] + "\n\n... [diff truncated due to size]", True


def parse_diff_lines(diff: str) -> dict:
    """
    Parse a unified diff and extract the actual NEW-SIDE line numbers
    that were added or modified per file. This is the source of truth
    for which lines Claude is allowed to comment on.

    Returns: {"path/to/file.dart": [12, 13, 14, 55, 56], ...}
    """
    import re
    file_lines: dict = {}
    current_file = None
    current_line = 0

    for raw_line in diff.split("\n"):
        # New file in diff: diff --git a/path b/path
        if raw_line.startswith("diff --git"):
            parts = raw_line.split(" b/")
            current_file = parts[-1] if len(parts) > 1 else None
            if current_file and current_file not in file_lines:
                file_lines[current_file] = []
            continue

        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        hunk_match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', raw_line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue

        if current_file is None:
            continue

        # Added or modified line (starts with +, but not +++ header)
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            file_lines[current_file].append(current_line)
            current_line += 1
        # Removed line (starts with -, but not --- header) — doesn't advance new-side counter
        elif raw_line.startswith("-") and not raw_line.startswith("---"):
            pass
        # Context line (unchanged) — advances new-side counter
        elif not raw_line.startswith("\\"):
            current_line += 1

    # Remove files with no changed lines
    return {f: lines for f, lines in file_lines.items() if lines}


def build_valid_lines_summary(valid_lines: dict) -> str:
    """
    Build a compact summary of which files and line ranges were changed.
    e.g. "lib/auth.dart: 12-18, 45-50, 88"
    """
    parts = []
    for filepath, lines in sorted(valid_lines.items()):
        if not lines:
            continue
        # Compress consecutive lines into ranges
        ranges = []
        start = lines[0]
        end = lines[0]
        for ln in lines[1:]:
            if ln == end + 1:
                end = ln
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = end = ln
        ranges.append(f"{start}-{end}" if start != end else str(start))
        parts.append(f"  {filepath}: lines {', '.join(ranges)}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------


def call_claude(prompt: str, system: str, config: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Try loading from config
        api_key = config.get("anthropic_api_key")
    if not api_key:
        print(
            "❌ Set ANTHROPIC_API_KEY env var or add it to ~/.config/rpr/config.json",
            file=sys.stderr,
        )
        sys.exit(1)

    model = config["model"]
    payload = {
        "model": model,
        "max_tokens": config["max_tokens"],
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }

    # Enable adaptive thinking for 4.6 / opus models
    if "opus" in model or "4-6" in model or "4_6" in model:
        payload["temperature"] = 1  # required for thinking
        payload["thinking"] = {"type": "adaptive"}

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "accept": "text/event-stream",
        },
        method="POST",
    )

    try:
        resp = urllib.request.urlopen(req, timeout=300)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌ Claude API error ({e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ Network error contacting Claude API: {e.reason}", file=sys.stderr)
        sys.exit(1)

    text_content = ""
    start_time = time.time()

    try:
        while True:
            raw_line = resp.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8").strip()

            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                break

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = data.get("type")

            if event_type == "content_block_start":
                block_type = data.get("content_block", {}).get("type")
                elapsed = time.time() - start_time
                if block_type == "thinking":
                    print(
                        f"\r⏳ Thinking... ({elapsed:.0f}s)          ",
                        end="", file=sys.stderr, flush=True,
                    )
                elif block_type == "text":
                    print(
                        f"\r✍️  Writing review...                    ",
                        end="", file=sys.stderr, flush=True,
                    )

            elif event_type == "content_block_delta":
                delta = data.get("delta", {})
                elapsed = time.time() - start_time
                if delta.get("type") == "thinking_delta":
                    print(
                        f"\r⏳ Thinking... ({elapsed:.0f}s)          ",
                        end="", file=sys.stderr, flush=True,
                    )
                elif delta.get("type") == "text_delta":
                    text_content += delta.get("text", "")
                    print(
                        f"\r✍️  Writing review... ({len(text_content)} chars, {elapsed:.0f}s)     ",
                        end="", file=sys.stderr, flush=True,
                    )

            elif event_type == "error":
                error_msg = data.get("error", {}).get("message", "Unknown error")
                print(f"\n❌ Claude API stream error: {error_msg}", file=sys.stderr)
                sys.exit(1)

            elif event_type == "message_stop":
                break
    finally:
        resp.close()

    elapsed = time.time() - start_time
    print(
        f"\r✅ Review generated ({elapsed:.1f}s)                              ",
        file=sys.stderr,
    )

    if not text_content:
        print("❌ No text content in Claude's response", file=sys.stderr)
        sys.exit(1)

    return text_content


# ---------------------------------------------------------------------------
# Review prompt engineering
# ---------------------------------------------------------------------------


def get_review_guidelines() -> str:
    """Load custom review guidelines from cwd or XDG config dir."""
    for p in _guidelines_search_paths():
        if p.exists():
            return p.read_text()
    return ""


SYSTEM_PROMPT = """\
You are a senior software engineer doing a code review. You are NOT an AI — you are \
the developer reviewing this pull request. Write exactly how a sharp, experienced \
engineer writes PR reviews:

VOICE & TONE RULES:
- Be direct. No pleasantries, no "Great work overall!" fluff.
- Use first person naturally: "I think", "I'd suggest", "this concerns me"
- Be specific about what's wrong and why
- Occasionally use informal language — "this looks off", "hmm", "nit:", "not sure about this"
- Vary your sentence length. Mix short punchy observations with longer explanations.
- It's okay to say "looks good" for parts that are fine — but don't overdo it
- NEVER use phrases like "as an AI", "I notice", "I'd like to highlight"
- NEVER use bullet points with perfect parallel structure — real humans don't write that way
- Skip obvious stuff. Don't explain what the code does back to the author.

WHAT TO FOCUS ON:
- Bugs, logic errors, edge cases that will break
- Security issues (injection, auth gaps, data exposure)
- Performance problems that actually matter
- Missing error handling that will cause production issues
- Concurrency / race conditions
- Resource leaks

WHAT TO SKIP:
- Style preferences (formatting, naming conventions) unless truly confusing
- "Consider adding tests" — they know
- Obvious documentation suggestions
- Praise for basic competence

{custom_guidelines}

{depth_focus}"""

USER_PROMPT_TEMPLATE = """\
Review this pull request.

**{title}**
{description}

Base: `{base}` ← Head: `{head}`
{stats}

{previous_reviews_section}CHANGED FILES AND LINES (only these are reviewable):
{changed_lines_summary}

CRITICAL CONSTRAINT: You may ONLY comment on lines listed above. These are the \
lines that were actually added or modified in this PR. Do NOT comment on:
- Lines that appear in the diff as context (lines without + prefix)
- Lines from files not listed above
- Code that exists in the repo but was not changed in this PR
If an issue involves unchanged code, mention it in the summary instead.

Return your review as JSON with this exact structure — no markdown fences, no preamble:

{{
  "action": "approve" | "request_changes" | "comment",
  "summary": "Your overall assessment in 2-3 sentences. Be direct.",
  "comments": [
    {{
      "path": "relative/file/path.ext",
      "line": <line number from the CHANGED LINES list above>,
      "body": "Your comment about this specific line/section"
    }}
  ]
}}

Rules for "action":
- "approve" — the code is solid, no blocking issues. Minor nits are fine alongside an approval.
- "request_changes" — there are bugs, security holes, or logic errors that MUST be fixed before merge.
- "comment" — you have feedback but nothing blocking. Use this when you have suggestions but the code would work fine as-is.
- Default to "approve" if the changes look correct and there are no real issues.
- Only use "request_changes" for actual problems, not style preferences.

Rules for the JSON:
- "path" must be one of the files listed in CHANGED FILES above
- "line" must be a number from that file's changed lines listed above
- If you can't pinpoint an exact changed line, put it in the summary instead
- Keep comments concise — 1-3 sentences each
- If the PR looks solid, return an empty comments array and say so in the summary
- Do NOT invent issues just to have something to say

Here's the diff:

{diff}"""


def build_prompt(
    pr_info: dict,
    diff: str,
    valid_lines: dict,
    previous_reviews: str = "",
    depth: str = "default",
) -> tuple:
    """Build the system and user prompts."""
    custom_guidelines = get_review_guidelines()
    if custom_guidelines:
        custom_guidelines = f"\nADDITIONAL TEAM GUIDELINES:\n{custom_guidelines}"

    depth_focus = REVIEW_DEPTHS[depth]["focus"]

    system = SYSTEM_PROMPT.format(
        custom_guidelines=custom_guidelines,
        depth_focus=depth_focus,
    )

    description = pr_info.get("body") or "(no description)"
    # Truncate long descriptions
    if len(description) > 2000:
        description = description[:2000] + "..."

    stats = f"+{pr_info.get('additions', '?')} / -{pr_info.get('deletions', '?')}"
    changed_lines_summary = build_valid_lines_summary(valid_lines)

    user = USER_PROMPT_TEMPLATE.format(
        title=pr_info.get("title", "Untitled"),
        description=description,
        base=pr_info.get("baseRefName", "?"),
        head=pr_info.get("headRefName", "?"),
        stats=stats,
        changed_lines_summary=changed_lines_summary,
        previous_reviews_section=previous_reviews,
        diff=diff,
    )

    return system, user


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def parse_review(raw: str) -> dict:
    """Parse Claude's JSON response, handling common quirks."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        # Remove first line and last line
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # Last resort: return as plain comment
        return {"summary": raw, "comments": []}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        prog="rpr",
        description="Stealth PR Reviewer — looks like you wrote every word.",
    )
    parser.add_argument("pr_number", type=int, help="PR number to review")
    parser.add_argument("--repo", "-r", help="owner/repo (default: current repo)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Print review, don't post")
    parser.add_argument("--comment-only", action="store_true", help="Post as simple comment, not inline review")
    parser.add_argument("--approve", action="store_true", help="Approve the PR with review")
    parser.add_argument("--request-changes", action="store_true", help="Request changes")
    parser.add_argument(
        "--depth", "-d",
        choices=VALID_DEPTHS,
        default="default",
        help="Review depth: quick (blockers only), default, thorough (deep analysis)",
    )
    parser.add_argument("--model", help="Override Claude model")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show debug info")

    args = parser.parse_args()
    config = load_config()

    # Start update check in background (non-blocking)
    update_result: list[str | None] = [None]

    def _bg_update_check():
        update_result[0] = check_for_update()

    update_thread = threading.Thread(target=_bg_update_check, daemon=True)
    update_thread.start()

    if args.model:
        config["model"] = args.model

    # 1. Fetch PR info
    print(f"📋 Fetching PR #{args.pr_number}...", file=sys.stderr)
    pr_info = get_pr_info(args.pr_number, args.repo)

    if args.verbose:
        print(f"   Title: {pr_info.get('title')}", file=sys.stderr)
        files = pr_info.get("files", [])
        print(f"   Files: {len(files)} changed", file=sys.stderr)

    # 2. Get diff
    print("📝 Fetching diff...", file=sys.stderr)
    diff = get_pr_diff(args.pr_number, args.repo)

    # 3. Filter out noise
    diff = filter_diff(diff, config["skip_patterns"])
    diff, was_truncated = truncate_diff(diff, config["max_diff_chars"])

    if was_truncated:
        print("⚠️  Diff was truncated (too large). Review may miss some files.", file=sys.stderr)

    if not diff.strip():
        print("⚠️  No reviewable changes found (all files matched skip patterns).", file=sys.stderr)
        sys.exit(0)

    # 3b. Parse diff to get exact changed lines per file
    valid_lines = parse_diff_lines(diff)
    valid_files = set(valid_lines.keys())

    if args.verbose:
        total_changed = sum(len(v) for v in valid_lines.values())
        print(f"   Changed lines: {total_changed} across {len(valid_files)} files", file=sys.stderr)

    # 4. Fetch previous reviews for context
    print("🔍 Checking previous reviews...", file=sys.stderr)
    prev_reviews, prev_comments = get_previous_reviews(args.pr_number, args.repo)
    previous_section = format_previous_reviews(prev_reviews, prev_comments)

    if previous_section and args.verbose:
        nr = len([r for r in prev_reviews if (r.get("body") or "").strip()])
        nc = len([c for c in prev_comments if (c.get("body") or "").strip()])
        print(f"   Found {nr} prior reviews, {nc} inline comments", file=sys.stderr)

    # 5. Build prompt and call Claude
    depth_label = REVIEW_DEPTHS[args.depth]["label"]
    system, user = build_prompt(pr_info, diff, valid_lines, previous_section, args.depth)

    depth_tag = f" [{depth_label}]" if args.depth != "default" else ""
    print(f"🤖 Reviewing with {config['model']}{depth_tag}...", file=sys.stderr)
    raw_response = call_claude(user, system, config)

    if args.verbose:
        print(f"\n--- Raw response ---\n{raw_response}\n---\n", file=sys.stderr)

    # 5. Parse response
    review = parse_review(raw_response)
    summary = review.get("summary", "Looks good.")
    comments = review.get("comments", [])

    # Filter out comments that target files/lines NOT in the diff
    valid_comments = []
    dropped = 0
    for c in comments:
        path = c.get("path")
        line = c.get("line")
        if not path or not line:
            dropped += 1
            continue
        if path not in valid_files:
            dropped += 1
            if args.verbose:
                print(f"   ⛔ Dropped comment on {path}:{line} — file not in diff", file=sys.stderr)
            # Append to summary instead
            summary += f"\n\n**Note on `{path}`** (line {line}): {c.get('body', '')}"
            continue
        if line not in valid_lines.get(path, []):
            # Try to snap to the nearest valid line in that file
            file_valid = valid_lines.get(path, [])
            if file_valid:
                nearest = min(file_valid, key=lambda x: abs(x - line))
                # Only snap if within 5 lines (likely referring to same block)
                if abs(nearest - line) <= 5:
                    if args.verbose:
                        print(f"   📌 Snapped {path}:{line} → {path}:{nearest}", file=sys.stderr)
                    c["line"] = nearest
                    valid_comments.append(c)
                else:
                    dropped += 1
                    if args.verbose:
                        print(f"   ⛔ Dropped comment on {path}:{line} — not a changed line", file=sys.stderr)
                    summary += f"\n\n**Note on `{path}`** (line {line}): {c.get('body', '')}"
            else:
                dropped += 1
            continue
        valid_comments.append(c)

    if dropped and args.verbose:
        print(f"   ⚠️  {dropped} comments dropped (not on changed lines)", file=sys.stderr)

    print(f"✅ Review ready: {len(valid_comments)} inline comments", file=sys.stderr)

    # 6. Determine review action
    # CLI flags override, otherwise use Claude's decision
    if args.approve:
        event = "APPROVE"
    elif args.request_changes:
        event = "REQUEST_CHANGES"
    else:
        # Use Claude's recommendation
        ai_action = review.get("action", "comment").lower().strip()
        action_map = {
            "approve": "APPROVE",
            "request_changes": "REQUEST_CHANGES",
            "comment": "COMMENT",
        }
        event = action_map.get(ai_action, "COMMENT")

    action_label = {
        "COMMENT": "💬 commented on",
        "APPROVE": "✅ approved",
        "REQUEST_CHANGES": "🔄 requested changes on",
    }

    # 7. Output or post
    if args.dry_run:
        print("\n" + "=" * 60)
        print(f"ACTION: {action_label.get(event, event)}")
        print("=" * 60)
        print("REVIEW SUMMARY:")
        print(summary)
        if valid_comments:
            print("\n" + "-" * 60)
            print("INLINE COMMENTS:")
            print("-" * 60)
            for c in valid_comments:
                print(f"\n📄 {c['path']}:{c['line']}")
                print(f"   {c['body']}")
        print()
        update_thread.join(timeout=2)
        if update_result[0]:
            print(update_result[0], file=sys.stderr)
        return

    if args.comment_only:
        # Post as a single PR comment
        body = summary
        if valid_comments:
            body += "\n\n---\n"
            for c in valid_comments:
                body += f"\n**`{c['path']}`** (L{c['line']})\n{c['body']}\n"
        post_review_comment(args.pr_number, body, args.repo)
        print(f"✅ Posted as comment on PR #{args.pr_number}", file=sys.stderr)
    else:
        post_review(args.pr_number, summary, valid_comments, event, args.repo)
        print(f"{action_label[event]} PR #{args.pr_number}", file=sys.stderr)

    print(f"🔗 {pr_info.get('url', '')}", file=sys.stderr)

    # Show update notification (if check finished in time)
    update_thread.join(timeout=2)
    if update_result[0]:
        print(update_result[0], file=sys.stderr)


if __name__ == "__main__":
    main()
