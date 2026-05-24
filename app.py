#!/usr/bin/env python3
"""Interactive terminal UI for Smart Git Log Summarizer.

Run with:  python app.py
"""

import os
import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.rule import Rule
from rich.text import Text
from rich.table import Table
from rich import box

from git_summarizer import __version__
from git_summarizer.git_parser import parse_commits, get_current_branch, get_repo_name
from git_summarizer.formatter import format_changelog, format_standup, format_pr, format_digest
from git_summarizer.ai_summarizer import summarize_with_ai
from git_summarizer.config import load_config

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def clear() -> None:
    console.clear()


def banner() -> None:
    ai_status = (
        "[green]Claude AI active[/green]"
        if os.environ.get("ANTHROPIC_API_KEY")
        else "[dim]No API key — plain output[/dim]"
    )
    console.print(Panel(
        f"[bold cyan]Smart Git Log Summarizer[/bold cyan]  [dim]v{__version__}[/dim]\n"
        f"{ai_status}",
        box=box.ROUNDED,
        expand=False,
        padding=(0, 2),
    ))
    console.print()


def section(title: str) -> None:
    console.print(Rule(f"[bold]{title}[/bold]", style="cyan"))
    console.print()


def success(msg: str) -> None:
    console.print(f"[green]✓[/green] {msg}")


def warn(msg: str) -> None:
    console.print(f"[yellow]⚠[/yellow]  {msg}")


def error(msg: str) -> None:
    console.print(f"[red]✗[/red]  {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Main menu
# ─────────────────────────────────────────────────────────────────────────────

MODES = {
    "1": ("Changelog",       "commits grouped by type  (feat, fix, docs…)"),
    "2": ("Standup",         "daily summary of what you shipped"),
    "3": ("Digest",          "week-by-week progress report"),
    "4": ("PR Description",  "current branch vs a base branch"),
}


def main_menu() -> str:
    """Show the mode menu and return the user's choice ('1'–'4' or 'q')."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(style="white")
    table.add_column(style="dim")

    for key, (name, desc) in MODES.items():
        table.add_row(f"[{key}]", name, f"— {desc}")
    table.add_row("[q]", "Quit", "")

    console.print(table)
    console.print()

    choice = Prompt.ask(
        "[bold]Choose a mode[/bold]",
        choices=["1", "2", "3", "4", "q"],
        show_choices=False,
    )
    return choice


# ─────────────────────────────────────────────────────────────────────────────
# Shared option prompts
# ─────────────────────────────────────────────────────────────────────────────

def ask_repo(cfg: dict) -> str:
    default = cfg.get("repo", ".")
    repo = Prompt.ask("  Repo path", default=default)
    path = Path(repo).expanduser()
    if not path.is_dir():
        error(f"Directory not found: {path}")
        error("Enter a valid local path (not a URL).")
        return ask_repo({**cfg, "repo": "."})
    if not (path / ".git").is_dir():
        error(f"No .git folder found in {path}")
        return ask_repo({**cfg, "repo": "."})
    return str(path)


def ask_author(cfg: dict) -> str | None:
    default = cfg.get("author", "")
    val = Prompt.ask("  Author filter [dim](name or email, blank = all)[/dim]", default=default)
    return val.strip() or None


def ask_no_ai(cfg: dict) -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return True
    default_no_ai = cfg.get("no_ai", False)
    return not Confirm.ask(
        "  Enhance with Claude AI?",
        default=not default_no_ai,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mode flows
# ─────────────────────────────────────────────────────────────────────────────

def run_changelog(cfg: dict) -> str | None:
    section("Changelog")
    repo   = ask_repo(cfg)
    author = ask_author(cfg)
    since  = Prompt.ask("  Since [dim](e.g. '2 weeks ago', '2024-01-01', blank = all)[/dim]", default="")
    until  = Prompt.ask("  Until [dim](blank = now)[/dim]", default="")
    ver    = Prompt.ask("  Version tag [dim](e.g. v1.2.0, blank to skip)[/dim]", default="")
    no_ai  = ask_no_ai(cfg)
    console.print()

    try:
        commits = parse_commits(
            repo_path=repo,
            since=since or None,
            until=until or None,
            author=author,
        )
    except RuntimeError as e:
        error(str(e))
        return None

    if not commits:
        warn("No commits found. Try a wider date range.")
        return None

    repo_name = get_repo_name(repo)
    period    = f"since {since}" if since else "all history"
    console.print(f"[dim]Scanning [bold]{repo_name}[/bold] · {len(commits)} commits · {period}[/dim]\n")

    plain = format_changelog(commits, version=ver or None)
    return _enhance(plain, "changelog", repo, repo_name, no_ai)


def run_standup(cfg: dict) -> str | None:
    section("Standup Summary")
    repo   = ask_repo(cfg)
    author = ask_author(cfg)
    days   = IntPrompt.ask("  Look back how many days?", default=cfg.get("days", 7))
    no_ai  = ask_no_ai(cfg)
    console.print()

    try:
        commits = parse_commits(repo_path=repo, since=f"{days} days ago", author=author)
    except RuntimeError as e:
        error(str(e))
        return None

    if not commits:
        warn(f"No commits in the last {days} days. Try a larger number.")
        return None

    repo_name = get_repo_name(repo)
    console.print(f"[dim]Scanning [bold]{repo_name}[/bold] · {len(commits)} commits · last {days} days[/dim]\n")

    plain = format_standup(commits, days=days)
    return _enhance(plain, "standup", repo, repo_name, no_ai)


def run_digest(cfg: dict) -> str | None:
    section("Weekly Digest")
    repo   = ask_repo(cfg)
    author = ask_author(cfg)
    weeks  = IntPrompt.ask("  Look back how many weeks?", default=cfg.get("weeks", 1))
    no_ai  = ask_no_ai(cfg)
    console.print()

    try:
        commits = parse_commits(repo_path=repo, since=f"{weeks * 7} days ago", author=author)
    except RuntimeError as e:
        error(str(e))
        return None

    if not commits:
        warn(f"No commits in the last {weeks} week(s). Try a larger number.")
        return None

    repo_name = get_repo_name(repo)
    label = f"last {weeks} week{'s' if weeks != 1 else ''}"
    console.print(f"[dim]Scanning [bold]{repo_name}[/bold] · {len(commits)} commits · {label}[/dim]\n")

    plain = format_digest(commits, weeks=weeks)
    return _enhance(plain, "digest", repo, repo_name, no_ai)


def run_pr(cfg: dict) -> str | None:
    section("PR Description")
    repo  = ask_repo(cfg)
    base  = Prompt.ask("  Base branch", default=cfg.get("base", "main"))
    no_ai = ask_no_ai(cfg)
    console.print()

    try:
        branch  = get_current_branch(repo)
        commits = parse_commits(repo_path=repo, base_branch=base)
    except RuntimeError as e:
        error(str(e))
        return None

    if branch == base:
        warn(f"You are already on '{base}'. Check out a feature branch first.")
        return None

    if not commits:
        warn(f"No commits between '{branch}' and '{base}'.")
        return None

    repo_name = get_repo_name(repo)
    console.print(f"[dim]Scanning [bold]{repo_name}[/bold] · {len(commits)} commits · {branch} → {base}[/dim]\n")

    plain = format_pr(commits, branch=branch, base_branch=base)
    return _enhance(plain, "pr", repo, repo_name, no_ai)


def _enhance(plain: str, mode: str, repo: str, repo_name: str, no_ai: bool) -> str:
    if no_ai or not os.environ.get("ANTHROPIC_API_KEY"):
        return plain
    with console.status(f"[bold cyan]Enhancing with Claude ({repo_name})…[/bold cyan]"):
        try:
            return summarize_with_ai(plain, mode=mode, repo_name=repo_name)
        except Exception as e:
            warn(f"AI enhancement failed ({e}) — showing plain output.")
            return plain


# ─────────────────────────────────────────────────────────────────────────────
# Output display & post-output actions
# ─────────────────────────────────────────────────────────────────────────────

def show_output(result: str) -> None:
    console.print(Rule("[dim]Output[/dim]", style="dim"))
    console.print(Markdown(result))
    console.print(Rule(style="dim"))
    console.print()


def post_output_actions(result: str) -> str:
    """Show action menu after output. Returns 'again', 'menu', or 'quit'."""
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()
    table.add_row("[s]", "Save to file")
    table.add_row("[c]", "Copy to clipboard")
    table.add_row("[v]", "View raw Markdown")
    table.add_row("[r]", "Run again")
    table.add_row("[m]", "Back to menu")
    table.add_row("[q]", "Quit")
    console.print(table)
    console.print()

    action = Prompt.ask(
        "[bold]What next?[/bold]",
        choices=["s", "c", "v", "r", "m", "q"],
        show_choices=False,
    )

    if action == "s":
        filename = Prompt.ask("  Save to file", default="output.md")
        Path(filename).write_text(result, encoding="utf-8")
        success(f"Saved to [bold]{filename}[/bold]")
        console.print()
        return post_output_actions(result)

    elif action == "c":
        try:
            import subprocess, sys as _sys
            if _sys.platform == "darwin":
                subprocess.run(["pbcopy"], input=result.encode(), check=True)
            else:
                subprocess.run(["xclip", "-selection", "clipboard"], input=result.encode(), check=True)
            success("Copied to clipboard.")
        except FileNotFoundError:
            warn("xclip not found. Install it: [dim]sudo apt install xclip[/dim]")
        console.print()
        return post_output_actions(result)

    elif action == "v":
        console.print(Rule("[dim]Raw Markdown[/dim]", style="dim"))
        console.print(result)
        console.print(Rule(style="dim"))
        console.print()
        return post_output_actions(result)

    elif action == "r":
        return "again"
    elif action == "m":
        return "menu"
    else:
        return "quit"


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

MODE_RUNNERS = {
    "1": run_changelog,
    "2": run_standup,
    "3": run_digest,
    "4": run_pr,
}


def main() -> None:
    cfg = load_config()
    current_mode: str | None = None

    try:
        while True:
            clear()
            banner()

            if current_mode is None:
                choice = main_menu()
                if choice == "q":
                    console.print("\n[dim]Bye![/dim]\n")
                    break
                current_mode = choice

            runner = MODE_RUNNERS[current_mode]
            result = runner(cfg)

            if result:
                console.print()
                show_output(result)
                action = post_output_actions(result)
                if action == "again":
                    pass  # current_mode stays set → re-run same mode
                elif action == "menu":
                    current_mode = None
                else:
                    console.print("\n[dim]Bye![/dim]\n")
                    break
            else:
                # Error or empty — go back to menu after pause
                console.print()
                Prompt.ask("[dim]Press Enter to return to the menu[/dim]", default="")
                current_mode = None

    except KeyboardInterrupt:
        console.print("\n\n[dim]Interrupted. Bye![/dim]\n")


if __name__ == "__main__":
    main()
