import os
import anthropic

SYSTEM_PROMPT = """\
You are an expert technical writer who creates clear, concise, and human-readable git summaries \
for developers. Your summaries are professional, accurate, and highlight what matters most.

Guidelines:
- Use plain Markdown that renders well in terminals and GitHub
- Be concise but complete — omit nothing important, but don't pad
- Group related changes when it aids readability
- Use active voice and present tense ("Add feature" not "Added feature")
- For changelogs: emphasize user-facing impact, not implementation details
- For standups: focus on what was accomplished each day, keep it conversational
- For PRs: lead with a clear one-line summary, then structured details
- Preserve commit hashes (short form) as references where helpful
- Flag breaking changes prominently with ⚠
"""

MODE_INSTRUCTIONS = {
    "changelog": (
        "Rewrite the following raw changelog into a polished, human-readable CHANGELOG entry. "
        "Keep all commit hashes. Group logically. Make breaking changes impossible to miss."
    ),
    "standup": (
        "Rewrite the following raw standup notes into a natural, conversational standup summary. "
        "Group by day. Use past tense. Sound like a developer giving a real standup update."
    ),
    "pr": (
        "Rewrite the following raw PR description into a polished GitHub pull request description. "
        "Start with a crisp one-sentence summary. Include a structured changes section and a test plan checklist."
    ),
    "digest": (
        "Rewrite the following raw weekly progress digest into a polished summary suitable for a "
        "weekly engineering update or team newsletter. Lead with a one-sentence highlight of the week. "
        "Group by week, emphasise shipped features and fixed bugs, and keep the tone concise and professional."
    ),
}


def summarize_with_ai(
    plain_text: str,
    mode: str,
    repo_name: str = "",
    model: str = "claude-opus-4-7",
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return plain_text

    instruction = MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["changelog"])
    repo_context = f" for the `{repo_name}` repository" if repo_name else ""
    user_message = (
        f"{instruction}\n\nRepo{repo_context}:\n\n```\n{plain_text}\n```\n\n"
        "Respond with only the formatted Markdown — no preamble, no explanation."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except anthropic.AuthenticationError:
        raise
    except Exception:
        return plain_text
