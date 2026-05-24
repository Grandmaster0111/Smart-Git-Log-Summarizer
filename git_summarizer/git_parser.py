import subprocess
import re
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

CONVENTIONAL_PATTERN = re.compile(
    r'^(?P<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)'
    r'(?:\((?P<scope>[^)]+)\))?'
    r'(?P<breaking>!)?'
    r':\s+(?P<description>.+)'
)

SEPARATOR = "---COMMIT---"


@dataclass
class Commit:
    hash: str
    author_email: str
    author_name: str
    date: datetime
    subject: str
    body: str
    commit_type: str = field(default="", init=False)
    scope: str = field(default="", init=False)
    breaking: bool = field(default=False, init=False)

    def __post_init__(self):
        match = CONVENTIONAL_PATTERN.match(self.subject)
        if match:
            self.commit_type = match.group("type")
            self.scope = match.group("scope") or ""
            self.breaking = bool(match.group("breaking"))
        else:
            subject_lower = self.subject.lower()
            if re.match(r'(fix|bug|patch|resolve|revert)', subject_lower):
                self.commit_type = "fix"
            elif re.match(r'(add|feat|new|implement|create|introduce)', subject_lower):
                self.commit_type = "feat"
            elif re.match(r'(doc|readme|comment|changelog)', subject_lower):
                self.commit_type = "docs"
            elif re.match(r'(test|spec|coverage)', subject_lower):
                self.commit_type = "test"
            elif re.match(r'(refactor|clean|rename|move|restructure)', subject_lower):
                self.commit_type = "refactor"
            elif re.match(r'(perf|optim|speed|faster)', subject_lower):
                self.commit_type = "perf"
            elif re.match(r'(chore|bump|update|upgrade|ci|build|release)', subject_lower):
                self.commit_type = "chore"
            else:
                self.commit_type = "other"

    @property
    def display_subject(self) -> str:
        """Subject with conventional commit prefix stripped."""
        match = CONVENTIONAL_PATTERN.match(self.subject)
        if match:
            return match.group("description")
        return self.subject


def parse_commits(
    repo_path: str = ".",
    since: Optional[str] = None,
    until: Optional[str] = None,
    author: Optional[str] = None,
    base_branch: Optional[str] = None,
    max_count: Optional[int] = None,
) -> list[Commit]:
    format_str = f"{SEPARATOR}\n%H\n%ae\n%an\n%ai\n%s\n%b\n"
    cmd = ["git", "log", f"--format={format_str}", "--no-merges"]

    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")
    if author:
        cmd.append(f"--author={author}")
    if max_count:
        cmd.append(f"-n{max_count}")
    if base_branch:
        cmd.append(f"{base_branch}..HEAD")

    abs_path = os.path.abspath(repo_path)
    if not os.path.isdir(abs_path):
        raise RuntimeError(f"Not a directory: {abs_path!r}")
    if not os.path.isdir(os.path.join(abs_path, ".git")):
        raise RuntimeError(f"Not a git repository: {abs_path!r}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=abs_path,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip()
        if "does not have any commits yet" in stderr:
            return []
        raise RuntimeError(f"git log failed: {stderr}") from e

    return _parse_output(result.stdout)


def _parse_output(raw: str) -> list[Commit]:
    commits = []
    blocks = raw.split(SEPARATOR)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        if len(lines) < 5:
            continue
        hash_ = lines[0].strip()
        email = lines[1].strip()
        name = lines[2].strip()
        date_str = lines[3].strip()
        subject = lines[4].strip()
        body = "\n".join(lines[5:]).strip()

        if not hash_ or not subject:
            continue

        try:
            # git's %ai format: 2024-01-15 10:30:00 +0530
            date = datetime.fromisoformat(date_str)
        except ValueError:
            date = datetime.now()

        commits.append(Commit(
            hash=hash_,
            author_email=email,
            author_name=name,
            date=date,
            subject=subject,
            body=body,
        ))

    return commits


def get_current_branch(repo_path: str = ".") -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=os.path.abspath(repo_path),
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "HEAD"


def get_repo_name(repo_path: str = ".") -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=os.path.abspath(repo_path),
            check=True,
        )
        return os.path.basename(result.stdout.strip())
    except subprocess.CalledProcessError:
        return os.path.basename(os.path.abspath(repo_path))
