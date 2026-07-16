# Raisume

CLI tool that tailors your master resume and cover letter to a job description using Claude Haiku 4.5.

It reads `config/profile.json` (your structured experience), parses a pasted job description, deterministically reorders your skills and bullets to match, and asks Haiku to rewrite the cover letter — without ever inventing experience.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env  # then add your ANTHROPIC_API_KEY
```

Edit `config/profile.json` with your data and (optionally) update the LaTeX templates in `templates/`.

## Usage

```bash
# Interactive — paste the JD, end with two blank lines (or Ctrl-D)
raisume tailor --company exampleCo

# From a file
raisume tailor --company exampleCo --jd path/to/jd.txt

# Resume only, skip cover letter
raisume tailor --company exampleCo --resume-only

# Batch — every .txt in a directory becomes a tailored set
raisume batch --jd-dir ./job_descriptions/
```

Output lands in `output/{company}/`:

- `resume.txt` — tailored EXPERIENCE + SKILLS LaTeX blocks (the meaty parts)
- `cover_letter.txt` — tailored cover letter body LaTeX

Paste those into your Overleaf project to render.

## How the tailoring works

**Skills are capped at 4 categories.** `Languages` is always kept. The other three slots go to the source categories most relevant to the JD (scored: required = 3pt, nice-to-have = 1pt per item). Categories that don't make the cut have their items folded into the nearest kept bucket via a fixed map (`databases → backend`, `testing → cloud_devops`, `ai_ml → backend`, etc.). Labels adapt to the new contents — e.g., `Backend` becomes `Backend & Data` if it absorbed `databases`, or `Cloud, DevOps & Testing` when `testing` folds in. Each bucket caps at 7 items, but JD-required matches are never cut.

**Bullets tighten when internships are kept.** When the matcher decides to include internships (because the JD's required years exceed your main-role tenure), main-role bullets get a single batched Haiku call to compress them ~20% while preserving every technology and outcome. This keeps the resume on one page. The trigger only fires if total main-role bullet text exceeds 1500 chars, so we don't pay the LLM cost when it isn't needed.
