"""Render the tailored resume text and call Haiku to rewrite the cover letter."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .llm import call_haiku
from .models import Bullet, Experience, ParsedJD, Profile
from .parser import _extract_json


# ---------- Resume rendering ----------

def render_skills_section(profile: Profile) -> str:
    """Render the SKILLS rSection block.

    The keys of ``profile.skills`` are already final display labels — no
    lookup needed (the matcher does the bucket selection + relabeling).
    """
    lines = ["\\begin{rSection}{SKILLS}", "\\begin{tabular}{ @{} l @{\\hspace{1ex}} l }"]
    for label, items in profile.skills.items():
        if not items:
            continue
        lines.append(f"\\textbf{{{label}}} & {', '.join(items)} \\\\")
    lines.append("\\end{tabular}")
    lines.append("\\end{rSection}")
    return "\n".join(lines)


def render_experience_section(profile: Profile) -> str:
    """Render the EXPERIENCE rSection block."""
    lines = ["\\begin{rSection}{EXPERIENCE}"]
    for exp in profile.experience:
        lines.append(f"\\textbf{{{exp.title}}} \\hfill {exp.dates}\\\\")
        lines.append(exp.company)
        lines.append(" \\begin{itemize}")
        lines.append("    \\itemsep 3pt {}")
        for bullet in exp.bullets:
            lines.append(f"    \\item {bullet.text}")
        lines.append(" \\end{itemize}")
    lines.append("\\end{rSection}")
    return "\n".join(lines)


def render_resume(profile: Profile) -> str:
    """Compose the meaty resume parts (EXPERIENCE + SKILLS) for paste-into-Overleaf."""
    return (
        "% --- EXPERIENCE ---\n"
        + render_experience_section(profile)
        + "\n\n% --- SKILLS ---\n"
        + render_skills_section(profile)
        + "\n"
    )


# ---------- Bullet tightening (LLM) ----------
#
# When internships are kept, the resume runs over a page. We compress
# main-role bullets ~20% via a single batched Haiku call, preserving every
# technology and outcome. Internship bullets are already short — we leave
# them alone.

# Trigger threshold: only call the LLM if main-role bullet text is long
# enough that the squeeze actually matters.
TIGHTEN_CHAR_THRESHOLD = 1500

# Skip individual bullets that are already concise.
TIGHTEN_PER_BULLET_MIN = 140


TIGHTEN_SYSTEM = """You are tightening resume bullets to fit on one page. Rules:

1. Reduce each bullet by roughly 15-25%, no more, no less.
2. Preserve EVERY technology, framework, language, and measurable outcome named in the original.
3. Keep the original meaning. Do NOT invent new facts.
4. Keep voice consistent: direct, action-led, past tense.
5. Output VALID JSON ONLY: a single object mapping bullet_id (string) -> tightened_text (string).
   No commentary, no markdown fences, no preamble.
"""


def _is_internship_title(title: str) -> bool:
    return "intern" in title.lower()


def _main_role_bullet_chars(profile: Profile) -> int:
    return sum(
        len(b.text)
        for exp in profile.experience
        if not _is_internship_title(exp.title)
        for b in exp.bullets
    )


def should_tighten(profile: Profile, internships_included: bool) -> bool:
    """Tighten only when interns are kept AND main-role bullets are long enough
    that the LLM call is worth its tokens."""
    if not internships_included:
        return False
    return _main_role_bullet_chars(profile) > TIGHTEN_CHAR_THRESHOLD


def tighten_bullets(profile: Profile) -> Profile:
    """Return a new Profile with main-role bullets compressed via a batched Haiku call."""
    targets = [
        {"id": b.id, "text": b.text}
        for exp in profile.experience
        if not _is_internship_title(exp.title)
        for b in exp.bullets
        if len(b.text) >= TIGHTEN_PER_BULLET_MIN
    ]
    if not targets:
        return profile

    user_prompt = (
        "Tighten the following resume bullets per the rules. "
        "Return JSON with the SAME ids:\n\n"
        + json.dumps(targets, indent=2)
    )
    raw = call_haiku(TIGHTEN_SYSTEM, user_prompt, max_tokens=1200)
    try:
        replacements = json.loads(_extract_json(raw))
    except (ValueError, json.JSONDecodeError):
        # If the LLM returned something unparseable, leave bullets untouched.
        return profile
    if not isinstance(replacements, dict):
        return profile

    new_experience = []
    for exp in profile.experience:
        new_bullets = []
        for b in exp.bullets:
            new_text = replacements.get(b.id, b.text)
            if not isinstance(new_text, str) or not new_text.strip():
                new_text = b.text
            new_bullets.append(Bullet(id=b.id, text=new_text, tags=list(b.tags)))
        new_experience.append(
            Experience(
                id=exp.id,
                title=exp.title,
                company=exp.company,
                dates=exp.dates,
                bullets=new_bullets,
            )
        )
    return Profile(
        name=profile.name,
        contact=profile.contact,
        education=profile.education,
        experience=new_experience,
        skills=profile.skills,
        include_internships=profile.include_internships,
        always_include=profile.always_include,
    )


# ---------- Cover letter tailoring ----------

COVER_LETTER_SYSTEM = """You are tailoring a cover letter for a job application. Follow these rules exactly:

1. Replace the company name and the role-specific phrasing with values from the job description.
2. Rewrite the FIRST paragraph to lead with the skills most relevant to THIS role, drawn from the candidate's profile.
3. Rewrite the mission/interest paragraph to reference THIS company's specific mission and product, using details from the job description.
4. Keep the same overall structure: greeting -> intro -> experience paragraph -> mission paragraph -> AI tools paragraph -> close.
5. Keep the candidate's voice: direct, confident, not flowery. No buzzwords.
6. NEVER invent experience. Only reference items present in the candidate profile.
7. Keep the body under 350 words.
8. Output VALID LaTeX only — no markdown, no commentary, no code fences. Begin with \\noindent and end with \\vskip 2.0cm.
"""


def _profile_for_prompt(profile: Profile) -> str:
    """Compact, LLM-friendly view of the profile."""
    parts = [f"Name: {profile.name}"]
    parts.append("Experience:")
    for exp in profile.experience:
        parts.append(f"- {exp.title} @ {exp.company} ({exp.dates})")
        for b in exp.bullets:
            parts.append(f"  * {b.text}")
    parts.append("Skills:")
    for cat, items in profile.skills.items():
        parts.append(f"- {cat}: {', '.join(items)}")
    return "\n".join(parts)


def tailor_cover_letter(
    profile: Profile,
    parsed: ParsedJD,
    template: str,
    raw_jd: Optional[str] = None,
) -> str:
    """Call Haiku to produce a tailored cover letter body in LaTeX."""
    user_prompt_parts = [
        "Parsed job description (JSON):",
        parsed.model_dump_json(indent=2),
    ]
    if raw_jd:
        user_prompt_parts += [
            "",
            "Raw job description (for additional context — do NOT invent skills):",
            raw_jd.strip(),
        ]
    user_prompt_parts += [
        "",
        "Candidate profile:",
        _profile_for_prompt(profile),
        "",
        "Cover letter template (preserve structure and voice; replace placeholders and update the leading skills + mission paragraph):",
        template.strip(),
        "",
        "Now produce the final tailored cover letter as valid LaTeX.",
    ]
    user_prompt = "\n".join(user_prompt_parts)
    return call_haiku(COVER_LETTER_SYSTEM, user_prompt, max_tokens=1500).strip()


# ---------- File output ----------

def write_outputs(
    output_dir: Path,
    company: str,
    resume_text: str,
    cover_letter_text: Optional[str],
) -> dict:
    """Write tailored files to output/{company}/ and return their paths."""
    safe_company = company.replace("/", "_").replace("\\", "_").strip() or "Company"
    company_dir = output_dir / safe_company
    company_dir.mkdir(parents=True, exist_ok=True)

    resume_path = company_dir / "resume.txt"
    resume_path.write_text(resume_text, encoding="utf-8")

    written = {"resume": resume_path}
    if cover_letter_text is not None:
        cover_path = company_dir / "cover_letter.txt"
        cover_path.write_text(cover_letter_text + "\n", encoding="utf-8")
        written["cover_letter"] = cover_path
    return written
