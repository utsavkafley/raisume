"""Tests for the rendering side of the tailorer (LLM call is not exercised)."""
import json
from pathlib import Path

from src.matcher import analyze
from src.models import Bullet, Experience, ParsedJD, Profile
from src.tailorer import (
    _main_role_bullet_chars,
    render_experience_section,
    render_resume,
    render_skills_section,
    should_tighten,
    write_outputs,
)


PROFILE_PATH = Path(__file__).resolve().parent.parent / "config" / "profile.json"


def load_profile() -> Profile:
    return Profile(**json.loads(PROFILE_PATH.read_text()))


def _tailored_profile() -> Profile:
    profile = load_profile()
    parsed = ParsedJD(
        company="IONNA",
        required_skills=["React", "TypeScript", "Node.js"],
        nice_to_have_skills=["Python", "AWS", "Docker"],
        experience_years="3+",
    )
    tailored, _ = analyze(profile, parsed)
    return tailored


def test_render_experience_section_uses_bullets_in_order():
    profile = load_profile()
    out = render_experience_section(profile)
    assert "\\begin{rSection}{EXPERIENCE}" in out
    assert "\\end{rSection}" in out
    # First bullet of the first role should appear before the second company
    first_role_first_bullet = profile.experience[0].bullets[0].text
    second_company = "Vertex Systems"
    assert out.find(first_role_first_bullet) < out.find(second_company)


def test_render_skills_section_uses_display_labels():
    """Render takes the dict keys as display labels (post-bucket-selection)."""
    profile = _tailored_profile()
    out = render_skills_section(profile)
    assert "\\begin{rSection}{SKILLS}" in out
    assert "\\textbf{Languages}" in out
    # Exactly four \textbf{...} skill-row entries.
    assert out.count("\\textbf{") == 4


def test_render_resume_combines_both_sections():
    profile = _tailored_profile()
    out = render_resume(profile)
    assert "EXPERIENCE" in out
    assert "SKILLS" in out
    assert out.index("EXPERIENCE") < out.index("SKILLS")


# ---------- Tightening triggers ----------

def test_should_tighten_skips_when_no_internships():
    profile = load_profile()
    assert should_tighten(profile, internships_included=False) is False


def test_should_tighten_triggers_when_internships_and_long_bullets():
    profile = load_profile()
    # Sanity: the master profile is comfortably over the threshold.
    assert _main_role_bullet_chars(profile) > 1500
    assert should_tighten(profile, internships_included=True) is True


def test_should_tighten_skips_when_short_main_role():
    short = Profile(
        name="X",
        experience=[
            Experience(
                id="x",
                title="Software Engineer",
                company="Acme",
                dates="Jan 2024 - Jan 2025",
                bullets=[Bullet(id="x-1", text="Did a thing.", tags=[])],
            ),
        ],
        skills={"languages": ["Python"]},
    )
    assert should_tighten(short, internships_included=True) is False


def test_write_outputs_creates_files(tmp_path: Path):
    written = write_outputs(
        tmp_path,
        company="IONNA",
        resume_text="resume body",
        cover_letter_text="cover body",
    )
    assert written["resume"].read_text() == "resume body"
    assert written["cover_letter"].read_text().startswith("cover body")
    assert written["resume"].parent.name == "IONNA"


def test_write_outputs_skips_cover_when_none(tmp_path: Path):
    written = write_outputs(tmp_path, "Acme", "r", None)
    assert "cover_letter" not in written
    assert written["resume"].exists()
