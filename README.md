# Smart Git Log Summarizer

Turn your git history into readable changelogs, standup notes, weekly digests, and PR descriptions — from the terminal, in seconds.

Works out of the box with plain Markdown. Optionally enhanced by Claude AI when you supply an API key.

---

## Features

- **Changelog** — grouped by commit type (feat, fix, docs…), breaking changes first
- **Standup** — day-by-day summary of what was done, ready to paste into Slack
- **Digest** — weekly progress report with commit/feature/fix counts per ISO week
- **PR description** — structured body with summary, grouped changes, and test-plan checklist
- **AI enhancement** — Claude polishes every output into natural, human-readable prose
- **Interactive TUI** — guided terminal UI for users who prefer prompts over flags
- **Config file** — save your defaults once, stop repeating them every time

---

## Installation

Requires Python 3.11+.

```bash
# Clone and install
git clone https://github.com/Grandmaster0111/Smart-Git-Log-Summarizer.git
cd Smart-Git-Log-Summarizer

# With a virtual environment (recommended)
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Or directly on the system Python
pip install -e . --break-system-packages
```

This installs the `git-summarizer` entry point.

---

## Quick Start

```bash
# Changelog for the current repo
git-summarizer changelog

# Last 3 days of commits as a standup
git-summarizer standup --days 3

# 2-week digest saved to a file
git-summarizer digest --weeks 2 --output weekly.md

# PR description vs develop, copied to clipboard
git-summarizer pr --base develop --copy

# Point at a different repo
git-summarizer changelog --repo ~/projects/myapp
```

---

## Commands

### `changelog`

Generates a changelog grouped by commit type. Breaking changes always appear first.

```bash
git-summarizer changelog [OPTIONS]

Options:
  --repo PATH       Local path to the git repository  [default: .]
  --since DATE      Include commits after this date (e.g. '2 weeks ago', '2024-01-01')
  --until DATE      Include commits before this date
  --author NAME     Filter by author name or email
  --version TAG     Version label in the changelog header (e.g. v1.2.0)
  --output FILE     Write output to FILE
  --no-ai           Skip Claude AI enhancement
  --raw             Print raw Markdown without Rich formatting
  --copy            Copy output to clipboard
```

### `standup`

Summarises commits by calendar day, newest first — stripped of conventional-commit prefixes so the text reads naturally.

```bash
git-summarizer standup [OPTIONS]

Options:
  --repo PATH       Local path to the git repository  [default: .]
  --days INT        How many days back to look  [default: 7]
  --author NAME     Filter by author name or email
  --output FILE     Write output to FILE
  --no-ai / --copy / --raw   (same as above)
```

### `digest`

Weekly progress report grouped by ISO week with per-week commit, feature, and fix counts.

```bash
git-summarizer digest [OPTIONS]

Options:
  --repo PATH       Local path to the git repository  [default: .]
  --weeks INT       How many weeks back to look  [default: 1]
  --author NAME     Filter by author name or email
  --output FILE / --no-ai / --raw / --copy   (same as above)
```

### `pr`

Generates a structured pull request description for the current branch compared to a base branch.

```bash
git-summarizer pr [OPTIONS]

Options:
  --repo PATH       Local path to the git repository  [default: .]
  --base BRANCH     Base branch to compare against  [default: main]
  --output FILE / --no-ai / --raw / --copy   (same as above)
```

### `config`

Save personal defaults so you don't have to repeat them every run. Config is stored at `~/.config/git-summarizer/config.toml`.

```bash
# Save defaults
git-summarizer config set author "Alice"
git-summarizer config set days 3
git-summarizer config set repo ~/projects/myapp
git-summarizer config set base develop

# View current config
git-summarizer config show

# Remove a key
git-summarizer config unset author
```

**Valid keys:** `author`, `days`, `weeks`, `repo`, `base`, `no_ai`, `model`

---

## Claude AI Enhancement

Set `ANTHROPIC_API_KEY` to enable AI-polished output on every command:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
git-summarizer standup --days 1
```

Without the key, all commands still work and produce clean plain Markdown. Use `--no-ai` to skip AI enhancement even when the key is set.

The default model is `claude-opus-4-7`. Override it with:

```bash
git-summarizer config set model claude-sonnet-4-6
```

---

## Interactive TUI

Prefer a guided experience? Run the interactive terminal UI:

```bash
python3 app.py
```

It walks you through mode selection, prompts for options (with config-file defaults pre-filled), renders the output, and offers to save, copy, or run again — no flags required.

---

## Conventional Commits

The tool understands [Conventional Commits](https://www.conventionalcommits.org/) prefixes automatically:

| Prefix | Section |
|--------|---------|
| `feat` | Features |
| `fix` | Bug Fixes |
| `docs` | Documentation |
| `refactor` | Refactoring |
| `perf` | Performance |
| `test` | Tests |
| `build` | Build System |
| `ci` | CI/CD |
| `chore` | Chores |

Non-conventional commits are grouped under **Other Changes**. Commits with `BREAKING CHANGE` in the body or a `!` after the type are always surfaced first.

---

## Project Structure

```
git_summarizer/
├── cli.py           Click entry point — all subcommands
├── git_parser.py    Runs git log, parses commits into dataclasses
├── formatter.py     Pure Markdown formatters (no I/O, no side effects)
├── ai_summarizer.py Anthropic SDK wrapper with plain-text fallback
└── config.py        TOML config read/write
app.py               Interactive guided TUI (no extra dependencies)
```

---

## Requirements

- Python 3.11+
- `click >= 8.1`
- `rich >= 13.0`
- `anthropic >= 0.40` *(only needed for AI enhancement)*
- `xclip` on Linux for `--copy` (`sudo apt install xclip`)

---

## License

MIT
