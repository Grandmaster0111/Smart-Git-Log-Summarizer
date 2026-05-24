import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich import box

from . import __version__
from .git_parser import (
    parse_commits, get_current_branch, get_repo_name,
    get_diff_stat, git_fetch,
)
from .formatter import (
    format_changelog, format_standup, format_pr, format_digest,
    format_release_notes, format_stats,
)
from .ai_summarizer import summarize_with_ai
from .config import load_config, load_repo_config, merge_configs, build_default_map, set_key, unset_key, CONFIG_PATH, VALID_KEYS

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _render(text: str, raw: bool, fmt: str = "markdown") -> None:
    if fmt == "json":
        click.echo(text)
    elif raw:
        click.echo(text)
    else:
        console.print(Markdown(text))


def _write_output(text: str, output: str | None) -> None:
    if not output:
        return
    path = Path(output)
    path.write_text(text, encoding="utf-8")
    err_console.print(f"[green]✓ Written to[/green] [bold]{path}[/bold]")


def _copy_to_clipboard(text: str) -> None:
    try:
        import subprocess
        if sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        else:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
        err_console.print("[green]✓ Copied to clipboard.[/green]")
    except FileNotFoundError:
        err_console.print(
            "[yellow]Could not copy to clipboard.[/yellow] "
            "Install [bold]xclip[/bold] on Linux: [dim]sudo apt install xclip[/dim]"
        )
    except Exception:
        err_console.print("[yellow]Could not copy to clipboard.[/yellow]")


def _post_webhook(text: str, url: str, mode: str, repo_name: str) -> None:
    import urllib.request
    payload = json.dumps({"text": text, "mode": mode, "repo": repo_name}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        err_console.print("[green]✓ Posted to webhook.[/green]")
    except Exception as e:
        err_console.print(f"[yellow]Webhook post failed: {e}[/yellow]")


def _to_json(result: str, mode: str, repos: tuple, commits: list) -> str:
    repo_names = [get_repo_name(r) for r in repos]
    return json.dumps({
        "mode": mode,
        "repos": repo_names,
        "generated_at": datetime.now().isoformat(),
        "commit_count": len(commits),
        "output": result,
    }, indent=2)


def _load_commits_one(repo: str, empty_hint: str = "", **kwargs) -> list | None:
    """Load commits from a single repo. Returns None on fatal error (exits)."""
    repo_cfg = load_repo_config(repo)
    try:
        commits = parse_commits(repo_path=repo, **kwargs)
        return commits
    except RuntimeError as e:
        msg = str(e)
        err_console.print(f"[red]Error ({repo}):[/red] {msg}")
        if "Not a directory" in msg:
            err_console.print("[dim]  Use --repo to point to your project, e.g. --repo ~/projects/myapp[/dim]")
        elif "Not a git repository" in msg:
            err_console.print("[dim]  Make sure the path contains a .git folder.[/dim]")
        sys.exit(1)


def _load_commits(repos: tuple[str, ...], empty_hint: str = "", **kwargs) -> list:
    """Load and merge commits from one or more repos, sorted newest-first."""
    all_commits = []
    for repo in repos:
        commits = _load_commits_one(repo, empty_hint=empty_hint, **kwargs)
        if commits:
            all_commits.extend(commits)
    all_commits.sort(key=lambda c: c.date, reverse=True)
    if not all_commits and empty_hint:
        err_console.print("[yellow]No commits found for the given filters.[/yellow]")
        err_console.print(f"[dim]  {empty_hint}[/dim]")
    return all_commits


def _print_context(repos: tuple[str, ...], commits: list, period: str) -> None:
    if len(repos) == 1:
        label = get_repo_name(repos[0])
    else:
        label = ", ".join(get_repo_name(r) for r in repos)
    count = len(commits)
    commit_label = f"{count} commit{'s' if count != 1 else ''}"
    err_console.print(
        f"[dim]Scanning [bold]{label}[/bold] · {commit_label} · {period}[/dim]"
    )


def _hint_ai(no_ai: bool) -> None:
    if not no_ai and not os.environ.get("ANTHROPIC_API_KEY"):
        err_console.print(
            "[dim]  Tip: set [bold]ANTHROPIC_API_KEY[/bold] to enhance this output with Claude AI[/dim]"
        )


def _maybe_enhance(plain: str, mode: str, repos: tuple, no_ai: bool, extra_context: str = "") -> str:
    if no_ai or not os.environ.get("ANTHROPIC_API_KEY"):
        return plain
    repo_name = get_repo_name(repos[0]) if repos else ""
    with console.status(f"[bold cyan]Enhancing with Claude ({repo_name})…[/bold cyan]"):
        try:
            return summarize_with_ai(plain, mode=mode, repo_name=repo_name, extra_context=extra_context)
        except Exception as e:
            err_console.print(f"[yellow]AI enhancement failed ({e}) — showing plain output.[/yellow]")
            return plain


# Shared option decorators
_REPO_OPTION  = click.option("--repo", default=(".",), multiple=True, show_default=False,
                              metavar="PATH", help="Local path to the git repo (repeat for multiple repos). [default: .]")
_OUTPUT_OPTION = click.option("--output",  default=None, metavar="FILE", help="Write output to FILE.")
_NO_AI_OPTION  = click.option("--no-ai",   is_flag=True, default=False, help="Skip Claude AI enhancement.")
_RAW_OPTION    = click.option("--raw",     is_flag=True, default=False, help="Print raw Markdown without Rich formatting.")
_COPY_OPTION   = click.option("--copy",    is_flag=True, default=False, help="Copy output to clipboard.")
_FORMAT_OPTION = click.option("--format",  "fmt", default="markdown",
                               type=click.Choice(["markdown", "json"], case_sensitive=False),
                               help="Output format.")
_WEBHOOK_OPTION = click.option("--webhook", default=None, metavar="URL",
                                help="POST output as JSON to this URL (e.g. Slack webhook).")
_AUTHOR_OPTION  = click.option("--author", default=None, metavar="NAME",
                                help="Filter by author name or email.")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group(
    epilog=(
        "\b\n"
        "Quick start:\n"
        "  git-summarizer changelog                                   # this repo, all history\n"
        "  git-summarizer standup --days 3                            # last 3 days\n"
        "  git-summarizer digest --weeks 2 --output out.md            # 2-week digest → file\n"
        "  git-summarizer pr --base develop                           # PR vs develop\n"
        "  git-summarizer release-notes --since '2 weeks ago'         # user-facing notes\n"
        "  git-summarizer stats --repo ~/a --repo ~/b                 # multi-repo stats\n"
        "  git-summarizer config set author \"Your Name\"              # save a default\n"
        "\n"
        "Set ANTHROPIC_API_KEY to enhance any output with Claude AI."
    )
)
@click.version_option(__version__, "--version", "-V", message="git-summarizer %(version)s")
@click.pass_context
def cli(ctx, **_):
    """Smart Git Log Summarizer — turn git history into readable summaries.

    Supports six output modes: changelog, standup, digest, pr, release-notes, stats.
    All commands work without an API key and produce plain Markdown.
    """
    ctx.ensure_object(dict)
    cfg = load_config()
    ctx.default_map = build_default_map(cfg)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer changelog\n"
        "  git-summarizer changelog --since '2 weeks ago' --version v1.2.0\n"
        "  git-summarizer changelog --author alice --output CHANGELOG.md\n"
        "  git-summarizer changelog --format json | jq .output\n"
        "  git-summarizer changelog --repo ~/a --repo ~/b"
    )
)
@_REPO_OPTION
@click.option("--since",   default=None, metavar="DATE", help="Include commits after this date (e.g. '2 weeks ago', '2024-01-01').")
@click.option("--until",   default=None, metavar="DATE", help="Include commits before this date.")
@_AUTHOR_OPTION
@click.option("--version", default=None, metavar="TAG",  help="Version label in the changelog header (e.g. v1.2.0).")
@_OUTPUT_OPTION
@_NO_AI_OPTION
@_RAW_OPTION
@_COPY_OPTION
@_FORMAT_OPTION
@_WEBHOOK_OPTION
def changelog(repo, since, until, author, version, output, no_ai, raw, copy, fmt, webhook):
    """Generate a changelog grouped by commit type (feat, fix, docs…).

    Groups all commits by type and sorts them — breaking changes first,
    then features, bug fixes, and so on. Commit hashes are preserved.
    """
    period = f"since {since}" if since else "all history"
    commits = _load_commits(
        repo, since=since, until=until, author=author,
        empty_hint="Try widening the date range with --since '30 days ago'.",
    )
    if not commits:
        return
    _print_context(repo, commits, period)
    plain = format_changelog(commits, version=version)
    result = _maybe_enhance(plain, "changelog", repo, no_ai)
    _hint_ai(no_ai)
    out = _to_json(result, "changelog", repo, commits) if fmt == "json" else result
    _render(out, raw, fmt)
    _write_output(out, output)
    if copy:
        _copy_to_clipboard(out)
    if webhook:
        _post_webhook(out, webhook, "changelog", get_repo_name(repo[0]))


@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer standup\n"
        "  git-summarizer standup --days 3\n"
        "  git-summarizer standup --author alice@example.com\n"
        "  git-summarizer standup --watch --interval 60"
    )
)
@_REPO_OPTION
@click.option("--days",     default=7,    show_default=True, help="How many days back to look.")
@_AUTHOR_OPTION
@_OUTPUT_OPTION
@_NO_AI_OPTION
@_RAW_OPTION
@_COPY_OPTION
@_FORMAT_OPTION
@_WEBHOOK_OPTION
@click.option("--watch",    is_flag=True, default=False, help="Watch for new commits and refresh output.")
@click.option("--interval", default=30,   show_default=True, metavar="SECS", help="Watch poll interval in seconds.")
def standup(repo, days, author, output, no_ai, raw, copy, fmt, webhook, watch, interval):
    """Generate a standup summary grouped by day.

    Shows what was committed each day, oldest-to-newest, with conventional
    commit prefixes stripped so the text reads naturally.
    """
    def _run():
        commits = _load_commits(
            repo, since=f"{days} days ago", author=author,
            empty_hint=f"No commits in the last {days} days. Try --days {days * 2} to look further back.",
        )
        if not commits:
            return None, []
        _print_context(repo, commits, f"last {days} day{'s' if days != 1 else ''}")
        plain = format_standup(commits, days=days)
        result = _maybe_enhance(plain, "standup", repo, no_ai)
        _hint_ai(no_ai)
        return result, commits

    result, commits = _run()
    if not result:
        return

    out = _to_json(result, "standup", repo, commits) if fmt == "json" else result
    _render(out, raw, fmt)
    _write_output(out, output)
    if copy:
        _copy_to_clipboard(out)
    if webhook:
        _post_webhook(out, webhook, "standup", get_repo_name(repo[0]))

    if watch:
        prev_hashes = {c.hash for c in commits}
        err_console.print(f"\n[dim]Watching every {interval}s… Ctrl+C to stop.[/dim]")
        try:
            while True:
                time.sleep(interval)
                for r in repo:
                    git_fetch(r)
                new_result, new_commits = _run()
                if new_commits:
                    new_hashes = {c.hash for c in new_commits}
                    added = new_hashes - prev_hashes
                    if added:
                        err_console.print(f"[green]↑ {len(added)} new commit(s) — refreshing…[/green]")
                        out = _to_json(new_result, "standup", repo, new_commits) if fmt == "json" else new_result
                        _render(out, raw, fmt)
                        if webhook:
                            _post_webhook(out, webhook, "standup", get_repo_name(repo[0]))
                        prev_hashes = new_hashes
        except KeyboardInterrupt:
            err_console.print("\n[dim]Watch stopped.[/dim]")


@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer digest\n"
        "  git-summarizer digest --weeks 4\n"
        "  git-summarizer digest --weeks 2 --output weekly.md\n"
        "  git-summarizer digest --watch --interval 120"
    )
)
@_REPO_OPTION
@click.option("--weeks",  default=1,   show_default=True, help="How many weeks back to look.")
@_AUTHOR_OPTION
@_OUTPUT_OPTION
@_NO_AI_OPTION
@_RAW_OPTION
@_COPY_OPTION
@_FORMAT_OPTION
@_WEBHOOK_OPTION
@click.option("--watch",    is_flag=True, default=False, help="Watch for new commits and refresh output.")
@click.option("--interval", default=120,  show_default=True, metavar="SECS", help="Watch poll interval in seconds.")
def digest(repo, weeks, author, output, no_ai, raw, copy, fmt, webhook, watch, interval):
    """Generate a weekly progress digest grouped by ISO week.

    Shows total commit / feature / fix counts, then a per-week breakdown.
    Good for team newsletters or performance reviews.
    """
    def _run():
        commits = _load_commits(
            repo, since=f"{weeks * 7} days ago", author=author,
            empty_hint=f"No commits in the last {weeks} week(s). Try --weeks {weeks * 2}.",
        )
        if not commits:
            return None, []
        _print_context(repo, commits, f"last {weeks} week{'s' if weeks != 1 else ''}")
        plain = format_digest(commits, weeks=weeks)
        result = _maybe_enhance(plain, "digest", repo, no_ai)
        _hint_ai(no_ai)
        return result, commits

    result, commits = _run()
    if not result:
        return

    out = _to_json(result, "digest", repo, commits) if fmt == "json" else result
    _render(out, raw, fmt)
    _write_output(out, output)
    if copy:
        _copy_to_clipboard(out)
    if webhook:
        _post_webhook(out, webhook, "digest", get_repo_name(repo[0]))

    if watch:
        prev_hashes = {c.hash for c in commits}
        err_console.print(f"\n[dim]Watching every {interval}s… Ctrl+C to stop.[/dim]")
        try:
            while True:
                time.sleep(interval)
                for r in repo:
                    git_fetch(r)
                new_result, new_commits = _run()
                if new_commits:
                    new_hashes = {c.hash for c in new_commits}
                    if new_hashes != prev_hashes:
                        err_console.print("[green]↑ New commits detected — refreshing…[/green]")
                        out = _to_json(new_result, "digest", repo, new_commits) if fmt == "json" else new_result
                        _render(out, raw, fmt)
                        if webhook:
                            _post_webhook(out, webhook, "digest", get_repo_name(repo[0]))
                        prev_hashes = new_hashes
        except KeyboardInterrupt:
            err_console.print("\n[dim]Watch stopped.[/dim]")


@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer pr\n"
        "  git-summarizer pr --base develop\n"
        "  git-summarizer pr --diff\n"
        "  git-summarizer pr --copy\n"
        "  git-summarizer pr --output PR_DESCRIPTION.md"
    )
)
@_REPO_OPTION
@click.option("--base",  default="main", show_default=True, help="Base branch to compare against.")
@_OUTPUT_OPTION
@_NO_AI_OPTION
@_RAW_OPTION
@_COPY_OPTION
@_FORMAT_OPTION
@_WEBHOOK_OPTION
@click.option("--diff", "include_diff", is_flag=True, default=False,
              help="Include diff --stat in AI context for richer summaries.")
def pr(repo, base, output, no_ai, raw, copy, fmt, webhook, include_diff):
    """Generate a PR description for the current branch vs a base branch.

    Compares HEAD against BASE and produces a structured PR body with a
    summary, grouped changes, and a test-plan checklist.
    """
    primary_repo = repo[0]
    try:
        branch = get_current_branch(primary_repo)
    except RuntimeError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    if branch == base:
        err_console.print(
            f"[yellow]You are already on [bold]{base}[/bold].[/yellow] "
            f"Check out a feature branch first, or use [bold]--base[/bold] to change the comparison target."
        )
        sys.exit(1)

    commits = _load_commits(
        repo, base_branch=base,
        empty_hint=f"No commits between '{branch}' and '{base}'. Have you pushed your commits?",
    )
    if not commits:
        return
    _print_context(repo, commits, f"{branch} → {base}")

    extra_context = ""
    if include_diff:
        extra_context = get_diff_stat(primary_repo, base_branch=base)

    plain = format_pr(commits, branch=branch, base_branch=base)
    result = _maybe_enhance(plain, "pr", repo, no_ai, extra_context=extra_context)
    _hint_ai(no_ai)
    out = _to_json(result, "pr", repo, commits) if fmt == "json" else result
    _render(out, raw, fmt)
    _write_output(out, output)
    if copy:
        _copy_to_clipboard(out)
    if webhook:
        _post_webhook(out, webhook, "pr", get_repo_name(primary_repo))


@cli.command(
    "release-notes",
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer release-notes\n"
        "  git-summarizer release-notes --version v2.0.0 --since '1 month ago'\n"
        "  git-summarizer release-notes --output RELEASE.md"
    )
)
@_REPO_OPTION
@click.option("--since",   default=None, metavar="DATE", help="Include commits after this date.")
@click.option("--until",   default=None, metavar="DATE", help="Include commits before this date.")
@_AUTHOR_OPTION
@click.option("--version", default=None, metavar="TAG",  help="Version label (e.g. v2.0.0).")
@_OUTPUT_OPTION
@_NO_AI_OPTION
@_RAW_OPTION
@_COPY_OPTION
@_FORMAT_OPTION
@_WEBHOOK_OPTION
def release_notes(repo, since, until, author, version, output, no_ai, raw, copy, fmt, webhook):
    """Generate user-facing release notes (feat, fix, perf only).

    Strips internal commits (chore, ci, refactor, style, test, build) and
    produces a clean announcement suitable for GitHub Releases or a blog post.
    """
    period = f"since {since}" if since else "all history"
    commits = _load_commits(
        repo, since=since, until=until, author=author,
        empty_hint="Try widening the date range with --since '1 month ago'.",
    )
    if not commits:
        return
    _print_context(repo, commits, period)
    plain = format_release_notes(commits, version=version)
    result = _maybe_enhance(plain, "release-notes", repo, no_ai)
    _hint_ai(no_ai)
    out = _to_json(result, "release-notes", repo, commits) if fmt == "json" else result
    _render(out, raw, fmt)
    _write_output(out, output)
    if copy:
        _copy_to_clipboard(out)
    if webhook:
        _post_webhook(out, webhook, "release-notes", get_repo_name(repo[0]))


@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer stats\n"
        "  git-summarizer stats --since '3 months ago'\n"
        "  git-summarizer stats --repo ~/a --repo ~/b\n"
        "  git-summarizer stats --format json"
    )
)
@_REPO_OPTION
@click.option("--since",  default=None, metavar="DATE", help="Include commits after this date.")
@click.option("--until",  default=None, metavar="DATE", help="Include commits before this date.")
@_AUTHOR_OPTION
@_OUTPUT_OPTION
@_RAW_OPTION
@_COPY_OPTION
@_FORMAT_OPTION
@_WEBHOOK_OPTION
def stats(repo, since, until, author, output, raw, copy, fmt, webhook):
    """Show contributor stats, commit-type breakdown, and weekly activity.

    Pure data — no AI enhancement needed. Works great across multiple repos
    with --repo <path1> --repo <path2>.
    """
    period = f"since {since}" if since else "all history"
    commits = _load_commits(
        repo, since=since, until=until, author=author,
        empty_hint="Try widening the date range with --since '3 months ago'.",
    )
    if not commits:
        return
    _print_context(repo, commits, period)
    result = format_stats(commits)
    out = _to_json(result, "stats", repo, commits) if fmt == "json" else result
    _render(out, raw, fmt)
    _write_output(out, output)
    if copy:
        _copy_to_clipboard(out)
    if webhook:
        _post_webhook(out, webhook, "stats", get_repo_name(repo[0]))


# ---------------------------------------------------------------------------
# Config subcommand
# ---------------------------------------------------------------------------

@cli.group(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer config set author \"Alice\"\n"
        "  git-summarizer config set days 14\n"
        "  git-summarizer config set repo ~/projects/myapp\n"
        "  git-summarizer config show\n"
        "  git-summarizer config unset author"
    )
)
def config():
    """Manage personal defaults saved in ~/.config/git-summarizer/config.toml.

    Set any option once so you don't have to repeat it every time.
    Per-repo overrides are supported via .git-summarizer.toml in the repo root.
    """


@config.command("show")
def config_show():
    """Show all saved defaults."""
    cfg = load_config()
    if not cfg:
        err_console.print(f"[yellow]No config found.[/yellow] File would be at: [dim]{CONFIG_PATH}[/dim]")
        err_console.print(
            "Run [bold]git-summarizer config set <key> <value>[/bold] to create one.\n"
            f"[dim]Valid keys: {', '.join(VALID_KEYS)}[/dim]"
        )
        return

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    table.add_column("Key",   style="cyan",  no_wrap=True)
    table.add_column("Value", style="white")
    table.add_column("Applies to", style="dim")

    APPLIES_TO = {
        "author": "all commands",
        "repo":   "all commands",
        "no_ai":  "all commands",
        "model":  "all commands",
        "days":   "standup",
        "weeks":  "digest",
        "base":   "pr",
    }

    for key in sorted(cfg.keys()):
        table.add_row(key, str(cfg[key]), APPLIES_TO.get(key, ""))

    console.print(f"\n[dim]{CONFIG_PATH}[/dim]")
    console.print(table)


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set KEY to VALUE.

    \b
    Available keys:
      author   default author filter (name or email)
      days     default --days for standup
      weeks    default --weeks for digest
      repo     default --repo path
      base     default --base branch for pr
      no_ai    skip AI by default (true/false)
      model    Claude model to use
    """
    try:
        set_key(key, value)
        console.print(f"[green]✓[/green] [cyan]{key}[/cyan] = [bold]{value}[/bold]")
        console.print(f"[dim]  Saved to {CONFIG_PATH}[/dim]")
    except ValueError as e:
        err_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@config.command("unset")
@click.argument("key")
def config_unset(key):
    """Remove KEY from saved defaults."""
    unset_key(key)
    console.print(f"[yellow]Removed[/yellow] [cyan]{key}[/cyan] from config.")
