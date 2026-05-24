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


def _sort_key(t: str) -> int:
    try:
        return TYPE_PRIORITY.index(t)
    except ValueError:
        return len(TYPE_PRIORITY)


def format_changelog(commits: list[Commit], version: Optional[str] = None) -> str:
    if not commits:
        return "No commits found.\n"

    header = f"## Changelog{f' — {version}' if version else ''}\n"
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [header, f"*Generated {date_str}*\n"]

    breaking = [c for c in commits if c.breaking]
    if breaking:
        lines.append("\n### ⚠ Breaking Changes\n")
        for c in breaking:
            lines.append(f"- {c.display_subject} ({c.hash[:7]})")

    grouped: dict[str, list[Commit]] = defaultdict(list)
    for c in commits:
        grouped[c.commit_type].append(c)

    for ctype in sorted(grouped.keys(), key=_sort_key):
        label = TYPE_LABELS.get(ctype, ctype.title())
        lines.append(f"\n### {label}\n")
        for c in grouped[ctype]:
            scope_prefix = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {scope_prefix}{c.display_subject} ({c.hash[:7]})")

    return "\n".join(lines) + "\n"


def format_standup(commits: list[Commit], days: int = 7) -> str:
    if not commits:
        return "No commits found in the specified period.\n"

    lines = [f"## Standup Summary — Last {days} Day{'s' if days != 1 else ''}\n"]

    grouped: dict[date, list[Commit]] = defaultdict(list)
    for c in commits:
        grouped[c.date.date()].append(c)

    for day in sorted(grouped.keys(), reverse=True):
        day_commits = grouped[day]
        lines.append(f"\n### {day.strftime('%A, %b %d')}\n")
        for c in day_commits:
            scope_prefix = f"[{c.scope}] " if c.scope else ""
            lines.append(f"- {scope_prefix}{c.display_subject}")

    return "\n".join(lines) + "\n"


def format_pr(commits: list[Commit], branch: str, base_branch: str) -> str:
    if not commits:
        return "No commits found between branches.\n"

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
            lines.append(f"- {c.display_subject}")

    lines.append("\n### Changes\n")
    for ctype in sorted(grouped.keys(), key=_sort_key):
        label = TYPE_LABELS.get(ctype, ctype.title())
        lines.append(f"\n**{label}**")
        for c in grouped[ctype]:
            scope_prefix = f"**{c.scope}**: " if c.scope else ""
            lines.append(f"- {scope_prefix}{c.display_subject}")

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

    # Group by ISO (year, week_number)
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
                lines.append(f"- {scope_prefix}{c.display_subject}")
            lines.append("")

    return "\n".join(lines) + "\n"
