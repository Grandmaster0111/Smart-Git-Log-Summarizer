"""Shared fixtures for the test suite."""
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from git_summarizer.git_parser import Commit


def _make_commit(
    subject: str = "feat: add thing",
    body: str = "",
    author_name: str = "Alice",
    author_email: str = "alice@example.com",
    hash_: str = "abc1234",
    date: datetime | None = None,
    repo_name: str = "",
) -> Commit:
    return Commit(
        hash=hash_,
        author_email=author_email,
        author_name=author_name,
        date=date or datetime(2024, 5, 1, 10, 0, 0),
        subject=subject,
        body=body,
        repo_name=repo_name,
    )


@pytest.fixture
def sample_commits():
    """A realistic list of commits covering multiple types."""
    return [
        _make_commit("feat(auth): add OAuth2 login", hash_="aaa0001",
                     date=datetime(2024, 5, 10, 9, 0)),
        _make_commit("feat: add dark mode", hash_="aaa0002",
                     date=datetime(2024, 5, 9, 14, 0)),
        _make_commit("fix(api): handle 429 rate limit", hash_="aaa0003",
                     date=datetime(2024, 5, 8, 11, 0)),
        _make_commit("fix: correct typo in error message", hash_="aaa0004",
                     date=datetime(2024, 5, 7, 16, 0)),
        _make_commit("docs: update README", hash_="aaa0005",
                     date=datetime(2024, 5, 6, 10, 0)),
        _make_commit("chore: bump dependencies", hash_="aaa0006",
                     date=datetime(2024, 5, 5, 9, 0)),
        _make_commit("perf: cache database queries", hash_="aaa0007",
                     date=datetime(2024, 5, 4, 13, 0)),
        _make_commit("refactor: extract auth middleware", hash_="aaa0008",
                     date=datetime(2024, 5, 3, 15, 0)),
    ]


@pytest.fixture
def breaking_commit():
    return _make_commit(
        "feat!: redesign config API",
        body="BREAKING CHANGE: config format changed",
        hash_="bbb0001",
    )


@pytest.fixture
def git_repo(tmp_path):
    """A minimal real git repository for integration tests."""
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"],
                   cwd=tmp_path, check=True, capture_output=True)

    # First commit
    (tmp_path / "README.md").write_text("# Test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feat: initial commit"],
                   cwd=tmp_path, check=True, capture_output=True)

    # Second commit
    (tmp_path / "main.py").write_text("print('hello')\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "fix: add main module"],
                   cwd=tmp_path, check=True, capture_output=True)

    return tmp_path
