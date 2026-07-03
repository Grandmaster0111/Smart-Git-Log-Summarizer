"""Reports Claude call/token usage to the api_tracker dashboard.

See that project's integrations/README.md (on this machine, under
projects/api_tracker) for the full write-up of this pattern — this is a
Python port of the same wrapper used there.
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import anthropic

TRACKER_URL = os.environ.get("API_TRACKER_URL", "http://localhost:4000")
FALLBACK_FILE = Path(
    os.environ.get("API_TRACKER_FALLBACK_FILE")
    or (Path(__file__).parent / "failed-calls.jsonl")
)

RETRY_DELAYS = [0.3, 1.0, 3.0]

_warned_unreachable = False


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


def _append_fallback(entry: dict) -> None:
    try:
        with open(FALLBACK_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError as err:
        print(f"api-tracker: could not write fallback log — {err}")


def _log_call(source, usage) -> None:
    global _warned_unreachable
    entry = {
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source or "unlabeled",
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }

    delays = [*RETRY_DELAYS, None]
    for delay in delays:
        try:
            _post_call(entry)
            return
        except (urllib.error.URLError, RuntimeError, OSError):
            if delay is None:
                if not _warned_unreachable:
                    _warned_unreachable = True
                    print(
                        f"api-tracker: tracker at {TRACKER_URL} unreachable — "
                        f"queuing calls to {FALLBACK_FILE} "
                        "(run flush_fallback.py once it's back up)"
                    )
                _append_fallback(entry)
                return
            time.sleep(delay)


def create_tracked_client(source: str | None = None, **anthropic_kwargs) -> anthropic.Anthropic:
    """Wraps an Anthropic client so every messages.create() call is logged
    to the API Usage Tracker with its token usage.

    `source` labels *where* these calls come from (e.g. "smart-git-log-summarizer")
    so the dashboard's "where it's used" breakdown is meaningful.
    """
    client = anthropic.Anthropic(**anthropic_kwargs)
    original_create = client.messages.create

    def tracked_create(*args, **kwargs):
        try:
            response = original_create(*args, **kwargs)
            _log_call(source, response.usage)
            return response
        except Exception:
            _log_call(source, None)
            raise

    client.messages.create = tracked_create
    return client
