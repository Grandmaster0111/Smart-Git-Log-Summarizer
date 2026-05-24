"""Tests for all formatter functions."""
from datetime import datetime

import pytest

from git_summarizer.formatter import (
    format_changelog, format_standup, format_pr, format_digest,
    format_release_notes, format_stats,
)
from git_summarizer.git_parser import Commit


# ---------------------------------------------------------------------------
# format_changelog
# ---------------------------------------------------------------------------

def test_changelog_empty():
    assert "No commits found" in format_changelog([])


def test_changelog_groups_by_type(sample_commits):
    out = format_changelog(sample_commits)
    assert "### Features" in out
    assert "### Bug Fixes" in out
    assert "### Documentation" in out


def test_changelog_includes_hashes(sample_commits):
    out = format_changelog(sample_commits)
    assert "aaa0001"[:7] in out


def test_changelog_breaking_first(breaking_commit, sample_commits):
    commits = [breaking_commit] + sample_commits
    out = format_changelog(commits)
    breaking_pos = out.index("Breaking Changes")
    feat_pos = out.index("Features")
    assert breaking_pos < feat_pos


def test_changelog_version_label(sample_commits):
    out = format_changelog(sample_commits, version="v1.2.0")
    assert "v1.2.0" in out


def test_changelog_scope_displayed(sample_commits):
    out = format_changelog(sample_commits)
    assert "auth" in out   # feat(auth) scope


def test_changelog_multi_repo_label():
    c1 = Commit("h1", "a@a.com", "Alice", datetime(2024, 5, 1), "feat: thing", "", repo_name="repo-a")
    c2 = Commit("h2", "b@b.com", "Bob",   datetime(2024, 5, 1), "fix: bug",   "", repo_name="repo-b")
    out = format_changelog([c1, c2])
    assert "[repo-a]" in out
    assert "[repo-b]" in out


# ---------------------------------------------------------------------------
# format_standup
# ---------------------------------------------------------------------------

def test_standup_empty():
    assert "No commits found" in format_standup([])


def test_standup_groups_by_day(sample_commits):
    out = format_standup(sample_commits, days=14)
    # Should have multiple day headers
    assert out.count("###") >= 2


def test_standup_strips_conventional_prefix(sample_commits):
    out = format_standup(sample_commits)
    # Conventional prefix stripped — raw "feat:" should not appear
    assert "feat:" not in out
    assert "add OAuth2 login" in out


def test_standup_newest_first(sample_commits):
    out = format_standup(sample_commits)
    # May 10 should appear before May 7
    pos_10 = out.find("May 10")
    pos_7  = out.find("May 07")
    assert pos_10 < pos_7


# ---------------------------------------------------------------------------
# format_pr
# ---------------------------------------------------------------------------

def test_pr_empty():
    assert "No commits found" in format_pr([], "feat", "main")


def test_pr_summary_line(sample_commits):
    out = format_pr(sample_commits, "feature/x", "main")
    assert "feature/x" in out
    assert "main" in out


def test_pr_test_plan_checklist(sample_commits):
    out = format_pr(sample_commits, "feat/x", "main")
    assert "- [ ]" in out
    assert "existing tests pass" in out


def test_pr_breaking_section(breaking_commit):
    out = format_pr([breaking_commit], "feat/x", "main")
    assert "Breaking Changes" in out


def test_pr_feat_fix_counts(sample_commits):
    out = format_pr(sample_commits, "feat/x", "main")
    assert "2 new features" in out
    assert "2 bug fixes" in out


# ---------------------------------------------------------------------------
# format_digest
# ---------------------------------------------------------------------------

def test_digest_empty():
    assert "No commits found" in format_digest([])


def test_digest_shows_totals(sample_commits):
    out = format_digest(sample_commits, weeks=2)
    assert "8 commits" in out


def test_digest_groups_by_week(sample_commits):
    out = format_digest(sample_commits, weeks=2)
    assert "Week of" in out


# ---------------------------------------------------------------------------
# format_release_notes
# ---------------------------------------------------------------------------

def test_release_notes_empty_list():
    assert "No user-facing changes" in format_release_notes([])


def test_release_notes_filters_internal(sample_commits):
    out = format_release_notes(sample_commits)
    # chore and refactor should NOT appear
    assert "Chores" not in out
    assert "bump dependencies" not in out
    assert "extract auth middleware" not in out


def test_release_notes_includes_feat_fix_perf(sample_commits):
    out = format_release_notes(sample_commits)
    assert "What's New" in out
    assert "Bug Fixes" in out
    assert "Performance" in out


def test_release_notes_version_label(sample_commits):
    out = format_release_notes(sample_commits, version="v2.0.0")
    assert "v2.0.0" in out


def test_release_notes_breaking_surfaced(breaking_commit, sample_commits):
    out = format_release_notes([breaking_commit] + sample_commits)
    assert "Breaking Changes" in out


def test_release_notes_no_hashes(sample_commits):
    out = format_release_notes(sample_commits)
    # Release notes intentionally omit commit hashes
    assert "aaa000" not in out


# ---------------------------------------------------------------------------
# format_stats
# ---------------------------------------------------------------------------

def test_stats_empty():
    assert "No commits found" in format_stats([])


def test_stats_shows_total(sample_commits):
    out = format_stats(sample_commits)
    assert "8 commits" in out


def test_stats_contributor_section(sample_commits):
    out = format_stats(sample_commits)
    assert "Top Contributors" in out
    assert "Alice" in out


def test_stats_type_breakdown(sample_commits):
    out = format_stats(sample_commits)
    assert "Commit Types" in out
    assert "Features" in out


def test_stats_weekly_activity(sample_commits):
    out = format_stats(sample_commits)
    assert "Weekly Activity" in out


def test_stats_multi_repo_section():
    c1 = Commit("h1", "a@a.com", "Alice", datetime(2024, 5, 1), "feat: x", "", repo_name="repo-a")
    c2 = Commit("h2", "b@b.com", "Bob",   datetime(2024, 5, 1), "fix: y",  "", repo_name="repo-b")
    out = format_stats([c1, c2])
    assert "Repositories" in out
    assert "repo-a" in out
