"""Tests for ai_summarizer — fallback and prompt construction."""
import os
import pytest

from git_summarizer.ai_summarizer import summarize_with_ai, MODE_INSTRUCTIONS


# ---------------------------------------------------------------------------
# Fallback when no API key
# ---------------------------------------------------------------------------

def test_returns_plain_text_when_no_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    plain = "## Changelog\n- feat: add thing"
    assert summarize_with_ai(plain, mode="changelog") == plain


def test_returns_plain_text_for_all_modes(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    for mode in MODE_INSTRUCTIONS:
        result = summarize_with_ai("some text", mode=mode)
        assert result == "some text"


# ---------------------------------------------------------------------------
# MODE_INSTRUCTIONS coverage
# ---------------------------------------------------------------------------

def test_all_expected_modes_present():
    for mode in ("changelog", "standup", "pr", "digest", "release-notes"):
        assert mode in MODE_INSTRUCTIONS, f"Missing mode: {mode}"


def test_mode_instructions_are_non_empty():
    for mode, instruction in MODE_INSTRUCTIONS.items():
        assert len(instruction) > 10, f"Instruction for {mode!r} is too short"


# ---------------------------------------------------------------------------
# Unknown mode falls back to changelog instruction
# ---------------------------------------------------------------------------

def test_unknown_mode_uses_changelog_instruction(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Without an API key, always returns plain text — just confirm no crash
    result = summarize_with_ai("text", mode="nonexistent-mode")
    assert result == "text"
