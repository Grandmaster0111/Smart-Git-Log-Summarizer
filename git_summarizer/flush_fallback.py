"""Replays queued Claude calls (from claude_tracked.py's fallback file) into
the api_tracker dashboard once it's back up.

Usage: python -m git_summarizer.flush_fallback
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

TRACKER_URL = os.environ.get("API_TRACKER_URL", "http://localhost:4000")
FALLBACK_FILE = Path(
    os.environ.get("API_TRACKER_FALLBACK_FILE")
    or (Path(__file__).parent / "failed-calls.jsonl")
)


def _post_call(entry: dict) -> None:
    data = json.dumps(entry).encode("utf-8")
    req = urllib.request.Request(
        f"{TRACKER_URL}/api/claude-calls",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"tracker responded {resp.status}")


def main() -> None:
    if not FALLBACK_FILE.exists():
        print("No fallback file found — nothing to flush.")
        return

    lines = [line for line in FALLBACK_FILE.read_text().splitlines() if line.strip()]
    if not lines:
        print("Fallback file is empty — nothing to flush.")
        return

    print(f"Flushing {len(lines)} queued call(s) to {TRACKER_URL}...")

    failed_lines = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            _post_call(entry)
        except (urllib.error.URLError, RuntimeError, OSError) as err:
            print(f"Still failing, keeping in queue: {err}")
            failed_lines.append(line)

    if failed_lines:
        FALLBACK_FILE.write_text("\n".join(failed_lines) + "\n")
        print(f"Flushed {len(lines) - len(failed_lines)}; {len(failed_lines)} still queued.")
    else:
        FALLBACK_FILE.unlink(missing_ok=True)
        print(f"Flushed all {len(lines)} call(s). Fallback file cleared.")


if __name__ == "__main__":
    main()
