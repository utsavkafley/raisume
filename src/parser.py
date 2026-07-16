"""Parse a raw job description into structured ParsedJD via Haiku."""
from __future__ import annotations

import json
import re
from typing import Optional

from .llm import call_haiku
from .models import ParsedJD


SYSTEM_PROMPT = """You are a job description parser. Given a raw job description, you extract structured data and return ONLY a single JSON object — no preamble, no markdown fences, no commentary.

The JSON must have exactly these keys:
- company (string)
- role_title (string)
- required_skills (array of strings — concrete technologies, frameworks, languages explicitly required)
- nice_to_have_skills (array of strings — same, but nice-to-have or preferred)
- key_themes (array of strings — short descriptors like "consumer-facing", "small team", "ownership")
- industry (string — e.g. "EV charging / clean energy")
- experience_years (string — e.g. "3+", "5-7", or "" if not stated)
- mission_keywords (array of strings — phrases describing the company mission or product)

Rules:
- Use the casing the JD uses for skill names ("React", "Node.js", "TypeScript").
- Do not invent skills or themes not present in the JD.
- If a field is genuinely absent, use an empty string or empty array.
- Return strictly valid JSON.
"""


def _extract_json(text: str) -> str:
    """Strip code fences and find the first {...} JSON object."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object found in LLM output: {text!r}")
    return text[start : end + 1]


def parse_jd(raw_jd: str, company_hint: Optional[str] = None) -> ParsedJD:
    """Send the JD to Haiku and parse the structured response."""
    user_prompt = f"Job description:\n\n{raw_jd.strip()}"
    if company_hint:
        user_prompt += (
            f"\n\nNote: the user told us the company is '{company_hint}'. "
            "Prefer that value for the 'company' field."
        )

    raw = call_haiku(SYSTEM_PROMPT, user_prompt, max_tokens=1024)
    payload = json.loads(_extract_json(raw))
    parsed = ParsedJD(**payload)
    if company_hint and not parsed.company:
        parsed.company = company_hint
    return parsed
