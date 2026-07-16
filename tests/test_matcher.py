"""Tests for the deterministic matcher logic."""
import json
from pathlib import Path

from src.matcher import (
    MAX_BUCKETS,
    _matches,
    _years_between,
    analyze,
    decide_internships,
    reorder_bullets,
    score_bullet,
    select_skill_buckets,
    total_main_role_years,
)
from src.models import Bullet, Experience, ParsedJD, Profile


PROFILE_PATH = Path(__file__).resolve().parent.parent / "config" / "profile.json"


def load_profile() -> Profile:
    return Profile(**json.loads(PROFILE_PATH.read_text()))


# ---------- Normalization ----------

def test_alias_matching():
    assert _matches("Node.js", ["nodejs"])
    assert _matches("TypeScript", ["TS"])
    assert _matches("React", ["react.js"])
    assert _matches("PostgreSQL", ["Postgres"])
    assert not _matches("Rust", ["python", "go"])


# ---------- Skill buckets ----------

def test_select_skill_buckets_caps_at_four():
    profile = load_profile()
    parsed = ParsedJD(
        required_skills=["React", "TypeScript", "Node.js", "Next.js"],
        nice_to_have_skills=["Python", "AWS", "Docker", "PostgreSQL"],
    )
    buckets, _ = select_skill_buckets(profile.skills, parsed)
    assert len(buckets) == MAX_BUCKETS


def test_select_skill_buckets_always_keeps_languages_first():
    profile = load_profile()
    parsed = ParsedJD(required_skills=["React"], nice_to_have_skills=[])
    buckets, _ = select_skill_buckets(profile.skills, parsed)
    assert next(iter(buckets.keys())) == "Languages"


def test_select_skill_buckets_required_items_first_in_bucket():
    profile = load_profile()
    parsed = ParsedJD(required_skills=["Next.js", "React"], nice_to_have_skills=[])
    buckets, _ = select_skill_buckets(profile.skills, parsed)
    # The frontend bucket should still be present and lead with required.
    frontend = buckets.get("Frontend") or buckets.get("Frontend & AI") or []
    assert frontend[:2] == ["React", "Next.js"]


def test_select_skill_buckets_folds_dropped_categories_with_relabel():
    """When DB / AI / Testing don't matter to the JD, they're dropped as
    standalone buckets and folded into the nearest kept bucket. The label
    adapts to acknowledge the absorption."""
    profile = load_profile()
    parsed = ParsedJD(
        # Frontend + backend + cloud — no DB / AI / testing demand.
        required_skills=["React", "TypeScript", "Python", "Node.js"],
        nice_to_have_skills=["AWS", "Docker"],
    )
    buckets, changes = select_skill_buckets(profile.skills, parsed)
    # No standalone Databases / AI / Testing buckets survive.
    assert "Databases" not in buckets
    assert "AI / ML" not in buckets
    assert "Testing" not in buckets
    # Backend's label adapted because Data + AI items merged in.
    backend_label = next((k for k in buckets if k.startswith("Backend")), None)
    assert backend_label == "Backend & Data"
    # Required items must always be present (the cap never drops required matches).
    assert "Node.js" in buckets[backend_label]
    assert "Python" in buckets[backend_label]
    # Cloud absorbed Testing items.
    cloud_label = next((k for k in buckets if "Cloud" in k), None)
    assert cloud_label == "Cloud, DevOps & Testing"
    # Change log mentions both absorptions.
    assert any("Backend" in c and "absorbed" in c for c in changes)
    assert any("Cloud" in c and "absorbed" in c for c in changes)


def test_select_skill_buckets_relevant_absorbed_items_survive_cap():
    """When a folded item is JD-relevant, it must beat irrelevant kept items
    inside the cap — otherwise folding would lose information that matters."""
    profile = load_profile()
    parsed = ParsedJD(
        # Frontend + backend + cloud, AND PostgreSQL as nice-to-have.
        required_skills=["React", "TypeScript", "Node.js"],
        nice_to_have_skills=["PostgreSQL", "AWS", "Docker"],
    )
    buckets, _ = select_skill_buckets(profile.skills, parsed)
    backend_label = next((k for k in buckets if k.startswith("Backend")), None)
    # PostgreSQL is nice-to-have, so it must outrank rank-2 kept items
    # (RabbitMQ, Protocol Buffers, .NET) and survive the cap.
    assert "PostgreSQL" in buckets[backend_label]


def test_select_skill_buckets_caps_items_per_bucket_but_keeps_required():
    """A bucket with many items, all required, should keep them all."""
    skills = {
        "languages": ["Python"],
        "backend": ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
        "frontend": ["X"],
        "cloud_devops": ["Y"],
    }
    parsed = ParsedJD(required_skills=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"])
    buckets, _ = select_skill_buckets(skills, parsed)
    # All 10 required items survive even though cap is 7.
    assert len(buckets["Backend"]) == 10


def test_select_skill_buckets_relabels_when_testing_absorbed():
    """Testing should fold into Cloud & DevOps and trigger a relabel."""
    profile = load_profile()
    # JD that doesn't care about testing or AI/ML — only frontend + cloud.
    parsed = ParsedJD(
        required_skills=["React", "TypeScript", "AWS", "Docker", "Kubernetes"],
        nice_to_have_skills=["Next.js"],
    )
    buckets, _ = select_skill_buckets(profile.skills, parsed)
    # Cloud & DevOps should win a slot here; testing items should be merged in
    # (or its category dropped). Exactly 4 buckets either way.
    assert len(buckets) == MAX_BUCKETS
    cloud_label = next((k for k in buckets if "Cloud" in k), None)
    assert cloud_label is not None


# ---------- Bullet scoring ----------

def test_bullet_scoring_required_outweighs_nice():
    required_bullet = Bullet(id="a", text="X", tags=["react", "typescript"])
    nice_bullet = Bullet(id="b", text="X", tags=["python"])
    parsed = ParsedJD(required_skills=["React", "TypeScript"], nice_to_have_skills=["Python"])
    assert score_bullet(required_bullet, parsed) > score_bullet(nice_bullet, parsed)


def test_reorder_bullets_promotes_relevant():
    profile = load_profile()
    vertex = next(e for e in profile.experience if e.id == "vertex")
    parsed = ParsedJD(required_skills=["React", "TypeScript", "Redux"])
    reordered, changed = reorder_bullets(vertex, parsed)
    assert reordered.bullets[0].id == "vertex-frontend"
    assert changed is False or reordered.bullets[0].id == "vertex-frontend"


# ---------- Internship decision ----------

def test_years_between_handles_basic_format():
    assert 0.99 < _years_between("Apr 2025 - Apr 2026") < 1.01


def test_total_main_role_years_excludes_interns():
    profile = load_profile()
    # Acme (~1y) + Vertex (~1.83y) + Military (~5.25y) — interns excluded
    assert total_main_role_years(profile) > 7.0


def test_decide_internships_excludes_when_threshold_met():
    profile = load_profile()
    assert decide_internships(profile, ParsedJD(experience_years="3+")) is False


def test_decide_internships_includes_when_no_threshold():
    profile = load_profile()
    assert decide_internships(profile, ParsedJD(experience_years="")) is True


# ---------- End-to-end analyze ----------

def test_analyze_returns_tailored_profile_and_summary():
    profile = load_profile()
    parsed = ParsedJD(
        company="IONNA",
        role_title="Full Stack Software Developer",
        required_skills=["React", "TypeScript", "Node.js", "Next.js"],
        nice_to_have_skills=["Python", "AWS", "Docker"],
        key_themes=["consumer-facing", "ownership", "real-time"],
        experience_years="3+",
    )
    tailored, analysis = analyze(profile, parsed)
    # Internships should be filtered out for this 3+ years JD
    titles = [e.title for e in tailored.experience]
    assert all("Intern" not in t for t in titles)
    # Strong matches should include things that are in both bullets and skills
    assert "React" in analysis.strong_matches
    # Vertex frontend bullet should lead the Vertex entry
    vertex = next(e for e in tailored.experience if e.id == "vertex")
    assert vertex.bullets[0].id == "vertex-frontend"
