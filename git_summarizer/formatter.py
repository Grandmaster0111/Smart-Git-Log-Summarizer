from datetime import date, datetime, timedelta
from typing import Optional
from collections import defaultdict

from .git_parser import Commit

TYPE_LABELS = {
    "feat":     "Features",
    "fix":      "Bug Fixes",
    "docs":     "Documentation",
    "style":    "Code Style",
    "refactor": "Refactoring",
    "perf":     "Performance",
    "test":     "Tests",
    "build":    "Build System",
    "ci":       "CI/CD",
    "chore":    "Chores",
    "revert":   "Reverts",
    "other":    "Other Changes",
}

TYPE_PRIORITY = list(TYPE_LABELS.keys())

# Only user-visible commit types surfaced in release notes
USER_FACING_TYPES = {"feat", "fix", "perf"}


def _sort_key(t: str) -> int:
    try:
        return TYPE_PRIORITY.index(t)
    except ValueError:
        return len(TYPE_PRIORITY)


def _repo_prefix(commit: Commit, multi_repo: bool) -> str:
    if multi_repo and commit.repo_name:
        return f"[{commit.repo_name}] "
    return ""


def _is_multi_repo(commits: list[Commit]) -> bool:
    names = {c.repo_name for c in commits if c.repo_name}
    return len(names) > 1


def format_changelog(commits: list[Commit], version: Optional[str] = None) -> str:
    if not commits:
        return "No commits found.\n"

    multi = _is_multi_repo(commits)
    header = f"## Changelog{f' — {version}' if version else ''}\n"
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [header, f"*Generated {date_str}*\n"]

    breaking = [c for c in commits if c.breaking]
    if breaking:
        lines.append("\n### ⚠ Breaking Changes\n")
        for c in breaking:
            lines.append(f"- {_repo_prefix(c, multi)}{c.display_subject} ({c.hash[:7]})")

    grouped: dict[str, list[Commit]] = defaultdict(list)
    for c in commits:
        grouped[c.commit_type].append(c)

    for ctype in sorted(grouped.keys(), key=_sort_key):
        label = TYPE_LABELS.get(ctype, ctype.title())
        lines.append(f"\n### {label}\n")
        for c in grouped[ctype]:
            scope_prefix = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {_repo_prefix(c, multi)}{scope_prefix}{c.display_subject} ({c.hash[:7]})")

    return "\n".join(lines) + "\n"


def format_standup(commits: list[Commit], days: int = 7) -> str:
    if not commits:
        return "No commits found in the specified period.\n"

    multi = _is_multi_repo(commits)
    lines = [f"## Standup Summary — Last {days} Day{'s' if days != 1 else ''}\n"]

    grouped: dict[date, list[Commit]] = defaultdict(list)
    for c in commits:
        grouped[c.date.date()].append(c)

    for day in sorted(grouped.keys(), reverse=True):
        day_commits = grouped[day]
        lines.append(f"\n### {day.strftime('%A, %b %d')}\n")
        for c in day_commits:
            scope_prefix = f"[{c.scope}] " if c.scope else ""
            lines.append(f"- {_repo_prefix(c, multi)}{scope_prefix}{c.display_subject}")

    return "\n".join(lines) + "\n"


def format_pr(commits: list[Commit], branch: str, base_branch: str) -> str:
    if not commits:
        return "No commits found between branches.\n"

    multi = _is_multi_repo(commits)
    grouped: dict[str, list[Commit]] = defaultdict(list)
    for c in commits:
        grouped[c.commit_type].append(c)

    breaking = [c for c in commits if c.breaking]
    feat_count = len(grouped.get("feat", []))
    fix_count = len(grouped.get("fix", []))

    summary_parts = []
    if feat_count:
        summary_parts.append(f"{feat_count} new feature{'s' if feat_count > 1 else ''}")
    if fix_count:
        summary_parts.append(f"{fix_count} bug fix{'es' if fix_count > 1 else ''}")
    if breaking:
        summary_parts.append(f"{len(breaking)} breaking change{'s' if len(breaking) > 1 else ''}")

    summary_line = ", ".join(summary_parts) if summary_parts else f"{len(commits)} commits"

    lines = [
        f"## PR: `{branch}` → `{base_branch}`\n",
        f"**Summary:** This PR includes {summary_line}.\n",
    ]

    if breaking:
        lines.append("\n### ⚠ Breaking Changes\n")
        for c in breaking:
            lines.append(f"- {_repo_prefix(c, multi)}{c.display_subject}")

    lines.append("\n### Changes\n")
    for ctype in sorted(grouped.keys(), key=_sort_key):
        label = TYPE_LABELS.get(ctype, ctype.title())
        lines.append(f"\n**{label}**")
        for c in grouped[ctype]:
            scope_prefix = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {_repo_prefix(c, multi)}{scope_prefix}{c.display_subject}")

    lines.append("\n### Test Plan\n")
    lines.append("- [ ] All existing tests pass")
    if feat_count:
        lines.append("- [ ] New features have test coverage")
    if fix_count:
        lines.append("- [ ] Bug fixes include regression tests")
    lines.append("- [ ] Manual testing completed on affected functionality")

    return "\n".join(lines) + "\n"


def format_digest(commits: list[Commit], weeks: int = 1) -> str:
    if not commits:
        return f"No commits found in the last {weeks} week{'s' if weeks != 1 else ''}.\n"

    multi = _is_multi_repo(commits)
    total = len(commits)
    feat_count  = sum(1 for c in commits if c.commit_type == "feat")
    fix_count   = sum(1 for c in commits if c.commit_type == "fix")
    other_count = total - feat_count - fix_count

    lines = [
        f"## Progress Digest — Last {weeks} Week{'s' if weeks != 1 else ''}\n",
        f"**{total} commit{'s' if total != 1 else ''}** · "
        f"{feat_count} feature{'s' if feat_count != 1 else ''} · "
        f"{fix_count} fix{'es' if fix_count != 1 else ''} · "
        f"{other_count} other\n",
    ]

    weekly: dict[tuple[int, int], list[Commit]] = defaultdict(list)
    for c in commits:
        iso = c.date.isocalendar()
        weekly[(iso.year, iso.week)].append(c)

    for (year, week_num) in sorted(weekly.keys(), reverse=True):
        monday = date.fromisocalendar(year, week_num, 1)
        sunday = monday + timedelta(days=6)
        week_commits = weekly[(year, week_num)]

        lines.append(
            f"\n### Week of {monday.strftime('%b %d')} – {sunday.strftime('%b %d, %Y')}\n"
        )

        wf = sum(1 for c in week_commits if c.commit_type == "feat")
        wb = sum(1 for c in week_commits if c.commit_type == "fix")
        lines.append(
            f"*{len(week_commits)} commit{'s' if len(week_commits) != 1 else ''}"
            + (f" · {wf} feature{'s' if wf != 1 else ''}" if wf else "")
            + (f" · {wb} fix{'es' if wb != 1 else ''}" if wb else "")
            + "*\n"
        )

        grouped: dict[str, list[Commit]] = defaultdict(list)
        for c in week_commits:
            grouped[c.commit_type].append(c)

        for ctype in sorted(grouped.keys(), key=_sort_key):
            label = TYPE_LABELS.get(ctype, ctype.title())
            lines.append(f"**{label}**")
            for c in grouped[ctype]:
                scope_prefix = f"[{c.scope}] " if c.scope else ""
                lines.append(f"- {_repo_prefix(c, multi)}{scope_prefix}{c.display_subject}")
            lines.append("")

    return "\n".join(lines) + "\n"


def format_release_notes(commits: list[Commit], version: Optional[str] = None) -> str:
    """User-facing release notes: only feat/fix/perf and breaking changes."""
    visible = [c for c in commits if c.commit_type in USER_FACING_TYPES or c.breaking]
    if not visible:
        return "No user-facing changes found in this range.\n"

    multi = _is_multi_repo(visible)
    date_str = datetime.now().strftime("%Y-%m-%d")
    header = f"## Release Notes{f' — {version}' if version else ''}"
    lines = [header, f"*{date_str}*\n"]

    breaking = [c for c in visible if c.breaking]
    if breaking:
        lines.append("\n### ⚠ Breaking Changes\n")
        for c in breaking:
            lines.append(f"- {_repo_prefix(c, multi)}{c.display_subject}")

    RELEASE_LABELS = {
        "feat": "What's New",
        "fix":  "Bug Fixes",
        "perf": "Performance Improvements",
    }

    grouped: dict[str, list[Commit]] = defaultdict(list)
    for c in visible:
        grouped[c.commit_type].append(c)

    for ctype in ["feat", "fix", "perf"]:
        if ctype not in grouped:
            continue
        lines.append(f"\n### {RELEASE_LABELS[ctype]}\n")
        for c in grouped[ctype]:
            scope_prefix = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {_repo_prefix(c, multi)}{scope_prefix}{c.display_subject}")

    return "\n".join(lines) + "\n"


def format_stats(commits: list[Commit]) -> str:
    """Contributor table, commit-type breakdown, and weekly activity chart."""
    if not commits:
        return "No commits found.\n"

    multi = _is_multi_repo(commits)
    total = len(commits)
    dates = sorted(c.date.date() for c in commits)
    date_range = f"{dates[0]} – {dates[-1]}"

    lines = [f"## Repository Stats\n", f"*{total} commit{'s' if total != 1 else ''} · {date_range}*\n"]

    if multi:
        repo_counts: dict[str, int] = defaultdict(int)
        for c in commits:
            repo_counts[c.repo_name] += 1
        lines.append("\n### Repositories\n")
        for repo, count in sorted(repo_counts.items(), key=lambda x: x[1], reverse=True):
            bar = "█" * min(count, 40)
            lines.append(f"  {repo:<25} {bar} {count}")

    # Commit type breakdown
    type_counts: dict[str, int] = defaultdict(int)
    for c in commits:
        type_counts[c.commit_type] += 1

    lines.append("\n### Commit Types\n")
    for ctype in sorted(type_counts, key=lambda t: type_counts[t], reverse=True):
        label = TYPE_LABELS.get(ctype, ctype.title())
        count = type_counts[ctype]
        bar = "█" * min(count, 40)
        lines.append(f"  {label:<22} {bar} {count}")

    # Top contributors
    author_counts: dict[str, int] = defaultdict(int)
    for c in commits:
        author_counts[c.author_name] += 1

    lines.append("\n### Top Contributors\n")
    for author, count in sorted(author_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
        bar = "█" * min(count, 40)
        lines.append(f"  {author:<25} {bar} {count}")

    # Weekly activity (last 12 weeks)
    weekly: dict[tuple[int, int], int] = defaultdict(int)
    for c in commits:
        iso = c.date.isocalendar()
        weekly[(iso.year, iso.week)] += 1

    lines.append("\n### Weekly Activity\n")
    for (year, week_num) in sorted(weekly.keys())[-12:]:
        monday = date.fromisocalendar(year, week_num, 1)
        count = weekly[(year, week_num)]
        bar = "█" * min(count, 40)
        lines.append(f"  {monday.strftime('%b %d'):<10} {bar} {count}")

    return "\n".join(lines) + "\n"
