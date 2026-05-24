import os
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich import box

from . import __version__
from .git_parser import parse_commits, get_current_branch, get_repo_name
from .formatter import format_changelog, format_standup, format_pr, format_digest
from .ai_summarizer import summarize_with_ai
from .config import load_config, build_default_map, set_key, unset_key, CONFIG_PATH, VALID_KEYS

console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _render(text: str, raw: bool) -> None:
    if raw:
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


def _load_commits(repo, empty_hint: str = "", **kwargs):
    try:
        commits = parse_commits(repo_path=repo, **kwargs)
        if not commits:
            err_console.print("[yellow]No commits found for the given filters.[/yellow]")
            if empty_hint:
                err_console.print(f"[dim]  {empty_hint}[/dim]")
        return commits
    except RuntimeError as e:
        msg = str(e)
        err_console.print(f"[red]Error:[/red] {msg}")
        # Contextual suggestions
        if "Not a directory" in msg:
            err_console.print("[dim]  Use --repo to point to your project, e.g. --repo ~/projects/myapp[/dim]")
        elif "Not a git repository" in msg:
            err_console.print("[dim]  Make sure the path contains a .git folder.[/dim]")
        sys.exit(1)


def _print_context(repo: str, commits: list, period: str) -> None:
    repo_name = get_repo_name(repo)
    count = len(commits)
    commit_label = f"{count} commit{'s' if count != 1 else ''}"
    err_console.print(
        f"[dim]Scanning [bold]{repo_name}[/bold] · {commit_label} · {period}[/dim]"
    )


def _hint_ai(no_ai: bool) -> None:
    if not no_ai and not os.environ.get("ANTHROPIC_API_KEY"):
        err_console.print(
            "[dim]  Tip: set [bold]ANTHROPIC_API_KEY[/bold] to enhance this output with Claude AI[/dim]"
        )


def _maybe_enhance(plain: str, mode: str, repo: str, no_ai: bool) -> str:
    if no_ai or not os.environ.get("ANTHROPIC_API_KEY"):
        return plain
    repo_name = get_repo_name(repo)
    with console.status(f"[bold cyan]Enhancing with Claude ({repo_name})…[/bold cyan]"):
        try:
            return summarize_with_ai(plain, mode=mode, repo_name=repo_name)
        except Exception as e:
            err_console.print(f"[yellow]AI enhancement failed ({e}) — showing plain output.[/yellow]")
            return plain


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group(
    epilog=(
        "\b\n"
        "Quick start:\n"
        "  git-summarizer changelog                         # this repo, all history\n"
        "  git-summarizer standup --days 3                  # last 3 days\n"
        "  git-summarizer digest --weeks 2 --output out.md  # 2-week digest → file\n"
        "  git-summarizer pr --base develop                  # PR vs develop\n"
        "  git-summarizer config set author \"Your Name\"     # save a default\n"
        "\n"
        "Set ANTHROPIC_API_KEY to enhance any output with Claude AI."
    )
)
@click.version_option(__version__, "--version", "-V", message="git-summarizer %(version)s")
@click.pass_context
def cli(ctx, **_):
    """Smart Git Log Summarizer — turn git history into readable summaries.

    Supports four output modes: changelog, standup, digest, and pr.
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
        "  git-summarizer changelog --no-ai --raw | grep Features"
    )
)
@click.option("--repo",    default=".", show_default=True, help="Local path to the git repository.")
@click.option("--since",   default=None, metavar="DATE", help="Include commits after this date (e.g. '2 weeks ago', '2024-01-01').")
@click.option("--until",   default=None, metavar="DATE", help="Include commits before this date.")
@click.option("--author",  default=None, metavar="NAME", help="Filter by author name or email.")
@click.option("--version", default=None, metavar="TAG",  help="Version label in the changelog header (e.g. v1.2.0).")
@click.option("--output",  default=None, metavar="FILE", help="Write output to FILE instead of (or in addition to) stdout.")
@click.option("--no-ai",   is_flag=True, default=False, help="Skip Claude AI enhancement and output plain Markdown.")
@click.option("--raw",     is_flag=True, default=False, help="Print raw Markdown without Rich formatting (good for piping).")
@click.option("--copy",    is_flag=True, default=False, help="Copy output to clipboard.")
def changelog(repo, since, until, author, version, output, no_ai, raw, copy):
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
    _render(result, raw)
    _write_output(result, output)
    if copy:
        _copy_to_clipboard(result)


@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer standup\n"
        "  git-summarizer standup --days 3\n"
        "  git-summarizer standup --author alice@example.com\n"
        "  git-summarizer standup --copy"
    )
)
@click.option("--repo",   default=".", show_default=True, help="Local path to the git repository.")
@click.option("--days",   default=7,   show_default=True, help="How many days back to look.")
@click.option("--author", default=None, metavar="NAME",  help="Filter by author name or email.")
@click.option("--output", default=None, metavar="FILE",  help="Write output to FILE.")
@click.option("--no-ai",  is_flag=True, default=False,   help="Skip Claude AI enhancement.")
@click.option("--raw",    is_flag=True, default=False,   help="Print raw Markdown without Rich formatting.")
@click.option("--copy",   is_flag=True, default=False,   help="Copy output to clipboard.")
def standup(repo, days, author, output, no_ai, raw, copy):
    """Generate a standup summary grouped by day.

    Shows what was committed each day, oldest-to-newest, with conventional
    commit prefixes stripped so the text reads naturally.
    """
    commits = _load_commits(
        repo, since=f"{days} days ago", author=author,
        empty_hint=f"No commits in the last {days} days. Try --days {days * 2} to look further back.",
    )
    if not commits:
        return
    _print_context(repo, commits, f"last {days} day{'s' if days != 1 else ''}")
    plain = format_standup(commits, days=days)
    result = _maybe_enhance(plain, "standup", repo, no_ai)
    _hint_ai(no_ai)
    _render(result, raw)
    _write_output(result, output)
    if copy:
        _copy_to_clipboard(result)


@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer digest\n"
        "  git-summarizer digest --weeks 4\n"
        "  git-summarizer digest --weeks 2 --output weekly.md"
    )
)
@click.option("--repo",   default=".", show_default=True, help="Local path to the git repository.")
@click.option("--weeks",  default=1,   show_default=True, help="How many weeks back to look.")
@click.option("--author", default=None, metavar="NAME",  help="Filter by author name or email.")
@click.option("--output", default=None, metavar="FILE",  help="Write output to FILE.")
@click.option("--no-ai",  is_flag=True, default=False,   help="Skip Claude AI enhancement.")
@click.option("--raw",    is_flag=True, default=False,   help="Print raw Markdown without Rich formatting.")
@click.option("--copy",   is_flag=True, default=False,   help="Copy output to clipboard.")
def digest(repo, weeks, author, output, no_ai, raw, copy):
    """Generate a weekly progress digest grouped by ISO week.

    Shows total commit / feature / fix counts, then a per-week breakdown.
    Good for team newsletters or performance reviews.
    """
    commits = _load_commits(
        repo, since=f"{weeks * 7} days ago", author=author,
        empty_hint=f"No commits in the last {weeks} week(s). Try --weeks {weeks * 2}.",
    )
    if not commits:
        return
    _print_context(repo, commits, f"last {weeks} week{'s' if weeks != 1 else ''}")
    plain = format_digest(commits, weeks=weeks)
    result = _maybe_enhance(plain, "digest", repo, no_ai)
    _hint_ai(no_ai)
    _render(result, raw)
    _write_output(result, output)
    if copy:
        _copy_to_clipboard(result)


@cli.command(
    epilog=(
        "\b\n"
        "Examples:\n"
        "  git-summarizer pr\n"
        "  git-summarizer pr --base develop\n"
        "  git-summarizer pr --copy\n"
        "  git-summarizer pr --output PR_DESCRIPTION.md"
    )
)
@click.option("--repo",   default=".", show_default=True, help="Local path to the git repository.")
@click.option("--base",   default="main", show_default=True, help="Base branch to compare against.")
@click.option("--output", default=None, metavar="FILE", help="Write output to FILE.")
@click.option("--no-ai",  is_flag=True, default=False,  help="Skip Claude AI enhancement.")
@click.option("--raw",    is_flag=True, default=False,  help="Print raw Markdown without Rich formatting.")
@click.option("--copy",   is_flag=True, default=False,  help="Copy output to clipboard.")
def pr(repo, base, output, no_ai, raw, copy):
    """Generate a PR description for the current branch vs a base branch.

    Compares HEAD against BASE and produces a structured PR body with a
    summary, grouped changes, and a test-plan checklist.
    """
    try:
        branch = get_current_branch(repo)
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
    plain = format_pr(commits, branch=branch, base_branch=base)
    result = _maybe_enhance(plain, "pr", repo, no_ai)
    _hint_ai(no_ai)
    _render(result, raw)
    _write_output(result, output)
    if copy:
        _copy_to_clipboard(result)


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
