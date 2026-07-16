"""Click CLI entry point for raisume."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from . import llm
from .matcher import analyze
from .models import Profile
from .parser import parse_jd
from .tailorer import (
    render_resume,
    should_tighten,
    tailor_cover_letter,
    tighten_bullets,
    write_outputs,
)


console = Console()

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "config" / "profile.json"
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output"


# ---------- Helpers ----------

def _load_profile(path: Path) -> Profile:
    if not path.exists():
        raise click.ClickException(f"Profile not found at {path}")
    return Profile(**json.loads(path.read_text(encoding="utf-8")))


def _load_template(name: str) -> str:
    p = TEMPLATES_DIR / name
    if not p.exists():
        raise click.ClickException(f"Template not found: {p}")
    return p.read_text(encoding="utf-8")


def _read_jd_interactive() -> str:
    console.print(
        "[bold]Paste the job description.[/bold] "
        "End with [cyan]two blank lines[/cyan] or [cyan]Ctrl-D[/cyan]:\n"
    )
    lines: list[str] = []
    blank_streak = 0
    try:
        while True:
            line = input()
            if line == "":
                blank_streak += 1
                if blank_streak >= 2:
                    break
            else:
                blank_streak = 0
            lines.append(line)
    except EOFError:
        pass
    return "\n".join(lines).strip()


def _print_match_analysis(analysis, parsed) -> None:
    body_lines = [
        f"[bold]Company:[/bold] {parsed.company or '(unknown)'}",
        f"[bold]Role:[/bold] {parsed.role_title or '(unknown)'}",
        "",
        f"[green]Strong matches:[/green] {', '.join(analysis.strong_matches) or '—'}",
        f"[yellow]Partial matches:[/yellow] {', '.join(analysis.partial_matches) or '—'}",
        f"[cyan]Nice-to-haves matched:[/cyan] {', '.join(analysis.nice_to_have_matched) or '—'}",
        f"[red]Gaps:[/red] {', '.join(analysis.gaps) or '—'}",
        "",
        f"[bold]Internships included:[/bold] {analysis.include_internships}",
    ]
    if analysis.skill_changes:
        body_lines.append("[bold]Skill changes:[/bold]")
        body_lines.extend(f"  • {c}" for c in analysis.skill_changes)
    if analysis.bullet_changes:
        body_lines.append("[bold]Bullet changes:[/bold]")
        body_lines.extend(f"  • {c}" for c in analysis.bullet_changes)
    console.print(Panel("\n".join(body_lines), title="📊 Match analysis", expand=False))


def _process_one(
    raw_jd: str,
    company: Optional[str],
    profile: Profile,
    cover_template: str,
    resume_only: bool,
) -> None:
    if not raw_jd:
        raise click.ClickException("Job description is empty.")

    console.print("\n🔍 Analyzing job description…")
    parsed = parse_jd(raw_jd, company_hint=company)
    final_company = parsed.company or company or "Company"

    tailored, analysis = analyze(profile, parsed)
    _print_match_analysis(analysis, parsed)

    if should_tighten(tailored, analysis.include_internships):
        console.print(
            "\n✂️  Internships kept — tightening main-role bullets to fit one page…"
        )
        tailored = tighten_bullets(tailored)

    console.print("\n📝 Rendering resume…")
    resume_text = render_resume(tailored)

    cover_text: Optional[str] = None
    if not resume_only:
        console.print("📝 Tailoring cover letter via Haiku…")
        cover_text = tailor_cover_letter(
            tailored, parsed, cover_template, raw_jd=raw_jd
        )

    written = write_outputs(OUTPUT_DIR, final_company, resume_text, cover_text)
    console.print("\n[bold green]✅ Output saved:[/bold green]")
    for kind, path in written.items():
        console.print(f"  → {path.relative_to(ROOT)}")


# ---------- Commands ----------

@click.group()
@click.version_option()
def main() -> None:
    """Raisume — tailor your resume and cover letter to a job description."""


@main.command()
@click.option("--company", default=None, help="Company name (used for output folder).")
@click.option(
    "--jd",
    "jd_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to a job description file. If omitted, paste interactively.",
)
@click.option("--resume-only", is_flag=True, help="Skip cover letter generation.")
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to profile.json (defaults to ./config/profile.json).",
)
def tailor(
    company: Optional[str],
    jd_path: Optional[Path],
    resume_only: bool,
    profile_path: Optional[Path],
) -> None:
    """Tailor a single resume + cover letter."""
    profile = _load_profile(profile_path or PROFILE_PATH)
    cover_template = _load_template("cover_letter_master.tex")

    if jd_path:
        raw_jd = jd_path.read_text(encoding="utf-8")
    else:
        raw_jd = _read_jd_interactive()

    _process_one(raw_jd, company, profile, cover_template, resume_only)
    console.print(f"\n[dim]Token usage: {llm.usage.summary()}[/dim]")


@main.command()
@click.option(
    "--jd-dir",
    "jd_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory containing one .txt file per job description.",
)
@click.option("--resume-only", is_flag=True, help="Skip cover letter generation.")
@click.option(
    "--profile",
    "profile_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
)
def batch(jd_dir: Path, resume_only: bool, profile_path: Optional[Path]) -> None:
    """Tailor every JD in a directory. Filename (sans extension) becomes the company."""
    profile = _load_profile(profile_path or PROFILE_PATH)
    cover_template = _load_template("cover_letter_master.tex")

    files = sorted(p for p in jd_dir.iterdir() if p.suffix.lower() == ".txt")
    if not files:
        raise click.ClickException(f"No .txt files found in {jd_dir}")

    for jd_file in files:
        company = jd_file.stem.replace("_", " ")
        console.rule(f"[bold]{company}[/bold] — {jd_file.name}")
        try:
            raw_jd = jd_file.read_text(encoding="utf-8")
            _process_one(raw_jd, company, profile, cover_template, resume_only)
        except Exception as e:  # noqa: BLE001 — keep batch going on individual failures
            console.print(f"[red]Failed for {jd_file.name}:[/red] {e}")

    console.rule("[bold]Batch complete[/bold]")
    console.print(f"[dim]Total token usage: {llm.usage.summary()}[/dim]")


if __name__ == "__main__":
    main()
