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


def _require_key() -> None:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "Липсва ANTHROPIC_API_KEY — добави го в backend/.env и РЕСТАРТИРАЙ "
            "сървъра (.env се чете само при стартиране)."
        )


def _call(schema: dict, user_text: str) -> dict:
    """One structured Claude call with API errors translated for the athlete."""
    client = anthropic.Anthropic()
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": user_text}],
        )
    except anthropic.AuthenticationError:
        raise RuntimeError("API ключът е невалиден — провери го в console.anthropic.com → API keys.")
    except anthropic.BadRequestError as e:
        if "credit" in str(e).lower() or "billing" in str(e).lower():
            raise RuntimeError(
                "Ключът е валиден, но акаунтът няма кредит. API-то се плаща отделно от "
                "claude.ai: console.anthropic.com → Billing → добави кредит (мин. $5; "
                "един преглед струва центове)."
            )
        raise RuntimeError(f"Заявката към AI беше отказана: {e}")
    except anthropic.RateLimitError:
        raise RuntimeError("Твърде много заявки за кратко време — изчакай минута и опитай пак.")
    except anthropic.APIError:
        raise RuntimeError("AI услугата не отговори — опитай пак след малко.")
    if response.stop_reason == "refusal":
        raise RuntimeError("AI прегледът отказа заявката.")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "description": "One-line overall verdict, Bulgarian"},
        "execution_score": {"type": "integer", "minimum": 1, "maximum": 10,
                            "description": "How well the session matched its purpose"},
        "strengths": {"type": "array", "items": {"type": "string"},
                      "description": "2-3 things done well, Bulgarian"},
        "improvements": {"type": "array", "items": {"type": "string"},
                         "description": "1-3 concrete things to improve, Bulgarian"},
        "next_advice": {"type": "string", "description": "What this means for the next sessions, Bulgarian"},
    },
    "required": ["verdict", "execution_score", "strengths", "improvements", "next_advice"],
    "additionalProperties": False,
}


def analyze_activity(digest: dict) -> dict:
    """Deep single-activity review — one compact Claude call, button-triggered.

    `digest` carries the planned workout summary, the actual numbers and the
    athlete's zones — a dozen numbers, no raw streams (token frugality)."""
    _require_key()
    user = (
        "Analyze this single completed session like a coach reviewing an athlete's day. "
        "Judge execution against the session's PURPOSE (an easy run done too fast is a "
        "miss, not a win). Be specific with the numbers you are given.\n"
        f"{json.dumps(digest, ensure_ascii=False)}"
    )
    return _call(ANALYSIS_SCHEMA, user)


def weekly_review(profile_digest: dict, ratings: list[dict],
                  wellness: list[dict] | None, user_note: str = "") -> dict:
    """One compact Claude call. Raises RuntimeError if no API key configured."""
    _require_key()
    user = (
        f"Athlete: {json.dumps(profile_digest, ensure_ascii=False)}\n"
        f"This week's workout ratings (oldest first): {json.dumps(ratings, ensure_ascii=False)}\n"
    )
    if wellness:
        user += f"Wellness (last days): {json.dumps(wellness, ensure_ascii=False)}\n"
    if user_note:
        user += f'Athlete says: "{user_note}"\n'
    user += "Review the week and decide adjustments for the next one."
    return _call(REVIEW_SCHEMA, user)
