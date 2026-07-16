"""Deterministic skills/experience matching and reordering.

This module never calls the LLM — it works purely from the parsed JD and
the structured profile, so it's cheap, fast, and easy to reason about.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Set, Tuple

from .models import Bullet, Experience, MatchAnalysis, ParsedJD, Profile


# ----- Normalization -----

_NORMALIZE_RE = re.compile(r"[^a-z0-9+]+")
_ALIASES: Dict[str, Set[str]] = {
    "javascript": {"javascript", "js", "ecmascript"},
    "typescript": {"typescript", "ts"},
    "node.js": {"node.js", "nodejs", "node"},
    "vue.js": {"vue.js", "vuejs", "vue"},
    "next.js": {"next.js", "nextjs", "next"},
    "react": {"react", "reactjs", "react.js"},
    "rest": {"rest", "restful", "restful apis", "rest api", "rest apis"},
    "ai": {"ai", "artificial intelligence", "genai"},
    "ml": {"ml", "machine learning"},
    "ci/cd": {"ci/cd", "cicd", "ci-cd", "continuous integration"},
    ".net": {".net", "dotnet", "dot net"},
    "postgresql": {"postgresql", "postgres"},
}


def _norm(s: str) -> str:
    return _NORMALIZE_RE.sub("", s.lower())


def _expand(token: str) -> Set[str]:
    """Return the set of normalized aliases for `token`."""
    n = _norm(token)
    for canonical, aliases in _ALIASES.items():
        if n in {_norm(a) for a in aliases} or n == _norm(canonical):
            return {_norm(a) for a in aliases} | {_norm(canonical)}
    return {n}


def _matches(skill: str, pool: Iterable[str]) -> bool:
    target = _expand(skill)
    pool_norm: Set[str] = set()
    for p in pool:
        pool_norm |= _expand(p)
    return bool(target & pool_norm)


# ----- Skill bucket selection -----
#
# We always render exactly `MAX_BUCKETS` skill categories. `Languages` is
# always kept (it's universal); the other slots are picked by JD relevance.
# Categories that don't make the cut have their items folded into a kept
# bucket per `_FOLD_TARGETS` so we don't lose information that matters.

MAX_BUCKETS = 4
ITEMS_PER_BUCKET = 7

# When category X is dropped, fold its items into the first kept entry from
# this list. Empty list = drop the items entirely.
_FOLD_TARGETS: Dict[str, List[str]] = {
    "languages": [],
    "frontend": ["languages"],
    "backend": ["cloud_devops", "languages"],
    "cloud_devops": ["backend"],
    "ai_ml": ["backend", "languages"],
    "databases": ["backend", "cloud_devops"],
    "testing": ["cloud_devops", "backend"],
}

_BASE_LABELS = {
    "languages": "Languages",
    "frontend": "Frontend",
    "backend": "Backend",
    "cloud_devops": "Cloud & DevOps",
    "ai_ml": "AI / ML",
    "databases": "Databases",
    "testing": "Testing",
}


def _rank_item(item: str, parsed: ParsedJD) -> int:
    if _matches(item, parsed.required_skills):
        return 0
    if _matches(item, parsed.nice_to_have_skills):
        return 1
    return 2


def _category_score(items: List[str], parsed: ParsedJD) -> int:
    """Sum-of-relevance score: required = 3pt, nice-to-have = 1pt per item."""
    score = 0
    for item in items:
        r = _rank_item(item, parsed)
        if r == 0:
            score += 3
        elif r == 1:
            score += 1
    return score


def _label_for(kept_cat: str, absorbed: Set[str]) -> str:
    """Adapt the bucket label when other source categories were folded in."""
    base = _BASE_LABELS.get(kept_cat, kept_cat.replace("_", " ").title())
    if kept_cat == "backend":
        if "ai_ml" in absorbed and "databases" in absorbed:
            return "Backend & Data"
        if "ai_ml" in absorbed:
            return "Backend & AI"
        if "databases" in absorbed:
            return "Backend & Data"
    if kept_cat == "cloud_devops":
        if "testing" in absorbed:
            return "Cloud, DevOps & Testing"
    if kept_cat == "languages" and ("frontend" in absorbed or "ai_ml" in absorbed):
        return "Languages"  # frontend/AI items folded in are usually framework names
    return base


def select_skill_buckets(
    skills: Dict[str, List[str]],
    parsed: ParsedJD,
    max_categories: int = MAX_BUCKETS,
    items_per_bucket: int = ITEMS_PER_BUCKET,
) -> Tuple[Dict[str, List[str]], List[str]]:
    """Collapse the source skill dict to at most `max_categories` JD-relevant buckets.

    Returns ``(buckets, change_descriptions)``. The buckets dict uses the
    final display label as its key, in render order.
    """
    if not skills:
        return {}, []

    # 1. Always keep Languages first (if present).
    kept_order: List[str] = []
    if "languages" in skills:
        kept_order.append("languages")

    # 2. Score the others; pick by score desc, ties broken by original order.
    others = [c for c in skills if c not in kept_order]
    original_order = list(skills.keys())
    others_sorted = sorted(
        others,
        key=lambda c: (-_category_score(skills[c], parsed), original_order.index(c)),
    )
    for cat in others_sorted:
        if len(kept_order) >= max_categories:
            break
        kept_order.append(cat)

    dropped = [c for c in original_order if c not in kept_order]

    # 3. Start each kept bucket with its own items.
    bucket_items: Dict[str, List[str]] = {c: list(skills[c]) for c in kept_order}
    absorbed: Dict[str, Set[str]] = {c: set() for c in kept_order}

    # 4. Fold dropped categories into the first kept fallback.
    for cat in dropped:
        for fallback in _FOLD_TARGETS.get(cat, []):
            if fallback in bucket_items:
                existing_norm = {_norm(x) for x in bucket_items[fallback]}
                for item in skills[cat]:
                    if _norm(item) not in existing_norm:
                        bucket_items[fallback].append(item)
                        existing_norm.add(_norm(item))
                absorbed[fallback].add(cat)
                break

    # 5. Within each kept bucket, sort by relevance (stable on rank), then trim.
    final: Dict[str, List[str]] = {}
    changes: List[str] = []
    for cat in kept_order:
        items = bucket_items[cat]
        ranked = sorted(items, key=lambda i: _rank_item(i, parsed))
        # Trim, but never drop a required-skill match.
        required = [i for i in ranked if _rank_item(i, parsed) == 0]
        rest = [i for i in ranked if _rank_item(i, parsed) != 0]
        cap_for_rest = max(0, items_per_bucket - len(required))
        trimmed = required + rest[:cap_for_rest]

        label = _label_for(cat, absorbed[cat])
        final[label] = trimmed

        if absorbed[cat]:
            absorbed_labels = ", ".join(_BASE_LABELS.get(a, a) for a in absorbed[cat])
            changes.append(f"{label}: absorbed {absorbed_labels}")
        if len(trimmed) < len(items):
            changes.append(
                f"{label}: trimmed to {len(trimmed)} items "
                f"(dropped {len(items) - len(trimmed)} less-relevant)"
            )

    if dropped and not any(_FOLD_TARGETS.get(c) for c in dropped):
        # Some categories had no fold target and were dropped outright.
        truly_dropped = [
            _BASE_LABELS.get(c, c) for c in dropped
            if not any(t in kept_order for t in _FOLD_TARGETS.get(c, []))
        ]
        if truly_dropped:
            changes.append(f"dropped categories: {', '.join(truly_dropped)}")

    return final, changes


# ----- Bullet scoring -----

def score_bullet(bullet: Bullet, parsed: ParsedJD) -> int:
    """Higher = more relevant. Required skills weight 3, nice-to-have 1, themes 1."""
    score = 0
    target_required = set()
    for s in parsed.required_skills:
        target_required |= _expand(s)
    target_nice = set()
    for s in parsed.nice_to_have_skills:
        target_nice |= _expand(s)
    target_themes = set()
    for t in parsed.key_themes:
        target_themes |= _expand(t)

    tag_norm: Set[str] = set()
    for tag in bullet.tags:
        tag_norm |= _expand(tag)

    score += 3 * len(tag_norm & target_required)
    score += 1 * len(tag_norm & target_nice)
    score += 1 * len(tag_norm & target_themes)

    # Light boost for keywords appearing in the bullet text itself
    text_lower = bullet.text.lower()
    for s in parsed.required_skills:
        if s.lower() in text_lower:
            score += 1
    return score


def reorder_bullets(
    experience: Experience, parsed: ParsedJD
) -> Tuple[Experience, bool]:
    """Return a copy of `experience` with bullets reordered by score (desc, stable)."""
    scored = [(score_bullet(b, parsed), i, b) for i, b in enumerate(experience.bullets)]
    # sort by -score, then original index for a stable order on ties
    scored.sort(key=lambda x: (-x[0], x[1]))
    new_bullets = [b for _, _, b in scored]
    changed = [b.id for b in new_bullets] != [b.id for b in experience.bullets]
    return (
        Experience(
            id=experience.id,
            title=experience.title,
            company=experience.company,
            dates=experience.dates,
            bullets=new_bullets,
        ),
        changed,
    )


# ----- Internship inclusion -----

_MAIN_ROLE_KEYWORDS = ("intern",)


def _is_internship(exp: Experience) -> bool:
    return any(k in exp.title.lower() for k in _MAIN_ROLE_KEYWORDS)


_DATE_RE = re.compile(
    r"(?P<sm>\w{3,9})\s+(?P<sy>\d{4})\s*[-–]\s*(?P<em>\w{3,9})\s+(?P<ey>\d{4})"
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}


def _years_between(dates: str) -> float:
    m = _DATE_RE.search(dates or "")
    if not m:
        return 0.0
    sm = _MONTHS.get(m.group("sm").lower()[:3], 1)
    em = _MONTHS.get(m.group("em").lower()[:3], 1)
    sy = int(m.group("sy"))
    ey = int(m.group("ey"))
    months = (ey - sy) * 12 + (em - sm)
    return max(0.0, months / 12.0)


def total_main_role_years(profile: Profile) -> float:
    return sum(
        _years_between(e.dates)
        for e in profile.experience
        if not _is_internship(e)
    )


def _required_years(parsed: ParsedJD) -> float:
    """Best-effort numeric extraction from strings like '3+', '5-7'."""
    if not parsed.experience_years:
        return 0.0
    m = re.search(r"\d+", parsed.experience_years)
    return float(m.group(0)) if m else 0.0


def decide_internships(profile: Profile, parsed: ParsedJD) -> bool:
    """Include internships if main-role years are below the requirement,
    or if the profile-level toggle says so."""
    if not profile.include_internships:
        return False
    required = _required_years(parsed)
    if required == 0.0:
        return True  # No bar set — keep them.
    return total_main_role_years(profile) < required


# ----- Top-level analysis -----

def analyze(profile: Profile, parsed: ParsedJD) -> Tuple[Profile, MatchAnalysis]:
    """Build a tailored Profile (skills + experience reordered, internships filtered)
    along with a MatchAnalysis summary.
    """
    new_skills, skill_changes = select_skill_buckets(profile.skills, parsed)

    include_interns = decide_internships(profile, parsed)
    new_experience: List[Experience] = []
    bullet_changes: List[str] = []

    for exp in profile.experience:
        keep = True
        if _is_internship(exp) and not include_interns:
            keep = exp.id in profile.always_include
        if not keep:
            continue
        reordered, changed = reorder_bullets(exp, parsed)
        if changed:
            bullet_changes.append(
                f"{exp.company}: bullet '{reordered.bullets[0].id}' moved to first"
            )
        new_experience.append(reordered)

    # ----- Match analysis surface -----
    profile_skill_pool = [s for items in profile.skills.values() for s in items]
    bullet_text_pool = " ".join(
        b.text for e in profile.experience for b in e.bullets
    ).lower()

    strong, partial = [], []
    for skill in parsed.required_skills:
        in_skills = _matches(skill, profile_skill_pool)
        in_bullets = skill.lower() in bullet_text_pool
        if in_skills and in_bullets:
            strong.append(skill)
        elif in_skills:
            partial.append(f"{skill} (in skills, not in bullets)")
        elif in_bullets:
            partial.append(f"{skill} (in bullets, not in skills)")

    nice_matched = [
        s for s in parsed.nice_to_have_skills
        if _matches(s, profile_skill_pool) or s.lower() in bullet_text_pool
    ]
    gaps = [
        s for s in parsed.required_skills
        if not _matches(s, profile_skill_pool)
        and s.lower() not in bullet_text_pool
    ]

    analysis = MatchAnalysis(
        strong_matches=strong,
        partial_matches=partial,
        nice_to_have_matched=nice_matched,
        gaps=gaps,
        include_internships=include_interns,
        skill_changes=skill_changes,
        bullet_changes=bullet_changes,
    )

    tailored_profile = Profile(
        name=profile.name,
        contact=profile.contact,
        education=profile.education,
        experience=new_experience,
        skills=new_skills,
        include_internships=include_interns,
        always_include=profile.always_include,
    )
    return tailored_profile, analysis
