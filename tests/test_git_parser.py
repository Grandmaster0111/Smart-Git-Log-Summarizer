"""Tests for git_parser — Commit dataclass and parse logic."""
import subprocess
from datetime import datetime

import pytest

from git_summarizer.git_parser import (
    Commit, _parse_output, parse_commits, get_repo_name, get_current_branch,
)


# ---------------------------------------------------------------------------
# Commit dataclass — type inference
# ---------------------------------------------------------------------------

def _c(subject: str, body: str = "") -> Commit:
    return Commit("abc", "e@e.com", "Dev", datetime(2024, 1, 1), subject, body)


class TestConventionalCommits:
    def test_feat(self):
        assert _c("feat: add login").commit_type == "feat"

    def test_fix(self):
        assert _c("fix: crash on startup").commit_type == "fix"

    def test_docs(self):
        assert _c("docs: update README").commit_type == "docs"

    def test_refactor(self):
        assert _c("refactor: extract service").commit_type == "refactor"

    def test_chore(self):
        assert _c("chore: bump deps").commit_type == "chore"

    def test_ci(self):
        assert _c("ci: add GitHub Actions").commit_type == "ci"

    def test_test(self):
        assert _c("test: add auth tests").commit_type == "test"

    def test_perf(self):
        assert _c("perf: cache queries").commit_type == "perf"

    def test_style(self):
        assert _c("style: fix indentation").commit_type == "style"

    def test_build(self):
        assert _c("build: update webpack").commit_type == "build"

    def test_revert(self):
        assert _c("revert: undo last change").commit_type == "revert"

    def test_scope_extracted(self):
        c = _c("feat(auth): add OAuth")
        assert c.scope == "auth"

    def test_breaking_bang(self):
        assert _c("feat!: redesign API").breaking is True

    def test_breaking_body(self):
        assert _c("feat: change", body="BREAKING CHANGE: removes X").breaking is True

    def test_display_subject_strips_prefix(self):
        assert _c("feat: add thing").display_subject == "add thing"

    def test_display_subject_no_prefix(self):
        assert _c("just a plain message").display_subject == "just a plain message"


class TestHeuristicFallback:
    def test_fix_heuristic(self):
        assert _c("fix crash on login").commit_type == "fix"

    def test_feat_heuristic(self):
        assert _c("add new dashboard").commit_type == "feat"

    def test_docs_heuristic(self):
        assert _c("readme updates").commit_type == "docs"

    def test_other_fallback(self):
        assert _c("something random").commit_type == "other"


# ---------------------------------------------------------------------------
# _parse_output
# ---------------------------------------------------------------------------

def test_parse_output_basic():
    raw = (
        "---COMMIT---\n"
        "abc1234\n"
        "dev@example.com\n"
        "Dev\n"
        "2024-05-01 10:00:00 +0000\n"
        "feat: add thing\n"
        "Some body text\n"
    )
    commits = _parse_output(raw)
    assert len(commits) == 1
    assert commits[0].hash == "abc1234"
    assert commits[0].subject == "feat: add thing"
    assert commits[0].body == "Some body text"


def test_parse_output_multiple():
    block = "---COMMIT---\n{}\ne@e.com\nDev\n2024-05-01 10:00:00 +0000\nfeat: {}\n\n"
    raw = block.format("aaa", "first") + block.format("bbb", "second")
    commits = _parse_output(raw)
    assert len(commits) == 2


def test_parse_output_skips_malformed():
    raw = "---COMMIT---\ntooshort\n"
    commits = _parse_output(raw)
    assert commits == []


def test_parse_output_empty():
    assert _parse_output("") == []


# ---------------------------------------------------------------------------
# parse_commits (integration — uses real git repo fixture)
# ---------------------------------------------------------------------------

def test_parse_commits_real_repo(git_repo):
    commits = parse_commits(str(git_repo))
    assert len(commits) == 2
    assert commits[0].subject == "fix: add main module"   # newest first
    assert commits[1].subject == "feat: initial commit"


def test_parse_commits_sets_repo_name(git_repo):
    commits = parse_commits(str(git_repo))
    assert all(c.repo_name for c in commits)


def test_parse_commits_not_a_dir():
    with pytest.raises(RuntimeError, match="Not a directory"):
        parse_commits("/nonexistent/path/xyz")


def test_parse_commits_not_a_git_repo(tmp_path):
    with pytest.raises(RuntimeError, match="Not a git repository"):
        parse_commits(str(tmp_path))


def test_parse_commits_author_filter(git_repo):
    commits = parse_commits(str(git_repo), author="nobody@nowhere.com")
    assert commits == []


def test_parse_commits_since_filter(git_repo):
    # Future date → no commits
    commits = parse_commits(str(git_repo), since="2099-01-01")
    assert commits == []


def test_get_repo_name(git_repo):
    name = get_repo_name(str(git_repo))
    assert name == git_repo.name


def test_get_current_branch(git_repo):
    branch = get_current_branch(str(git_repo))
    assert branch == "main"
