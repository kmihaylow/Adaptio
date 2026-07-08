"""The AI coach — weekly plan review via Claude.

Token frugality (изискване т.9): the deterministic plan engine does all the
heavy lifting for free. Claude is consulted only for the weekly review, and it
receives a compact digest (profile one-liner + rating history + wellness
summary), not raw data dumps. Structured outputs guarantee parseable JSON.
"""

from __future__ import annotations

import json
import os

import anthropic

CLAUDE_MODEL = os.getenv("ADAPTIO_CLAUDE_MODEL", "claude-opus-4-8")

SYSTEM = (
    "You are Adaptio, an adaptive endurance coach (running + cycling) for busy "
    "amateurs. You review a week of training and decide small, safe adjustments. "
    "Principles: pyramidal intensity distribution, never intensity on poor "
    "recovery, consistency beats heroics. Reply in Bulgarian, warm but honest."
)

REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "assessment": {"type": "string", "description": "2-4 sentences, Bulgarian"},
        "intensity_factor": {
            "type": "number",
            "description": "Multiplier for upcoming quality sessions, 0.9-1.05. 1.0 = no change.",
        },
        "extra_rest_day": {"type": "boolean"},
        "advice": {"type": "string", "description": "One practical tip, Bulgarian"},
    },
    "required": ["assessment", "intensity_factor", "extra_rest_day", "advice"],
    "additionalProperties": False,
}


def weekly_review(profile_digest: dict, ratings: list[dict],
                  wellness: list[dict] | None, user_note: str = "") -> dict:
    """One compact Claude call. Raises RuntimeError if no API key configured."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set — AI review unavailable")

    client = anthropic.Anthropic()
    user = (
        f"Athlete: {json.dumps(profile_digest, ensure_ascii=False)}\n"
        f"This week's workout ratings (oldest first): {json.dumps(ratings, ensure_ascii=False)}\n"
    )
    if wellness:
        user += f"Wellness (last days): {json.dumps(wellness, ensure_ascii=False)}\n"
    if user_note:
        user += f'Athlete says: "{user_note}"\n'
    user += "Review the week and decide adjustments for the next one."

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        system=SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
        messages=[{"role": "user", "content": user}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("AI review declined the request")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)
