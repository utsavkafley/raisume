# Raisume — CLI Resume & Cover Letter Tailoring Tool

> A CLI tool that takes a job description and dynamically reorders and tailors your resume and cover letter to match, using Claude Haiku 4.5 for intelligent matching at minimal cost. This tool only outputs the meaty part of the resume text for both resume and cover letter (user is expeced to manually update the resume.)

---

## Overview

Raisume reads your master resume and cover letter templates, analyzes a job description you paste in, and work experience and skills section with skills reordered, bullets reprioritized, and cover letter language adjusted — all while preserving your writing style and never fabricating experience.


```
resumeforge/
├── README.md
├── pyproject.toml
├── .env.example                  # ANTHROPIC_API_KEY=
├── templates/
│   ├── resume_master.tex         # Your master resume LaTeX
│   └── cover_letter_master.tex   # Your master cover letter LaTeX
├── config/
│   └── profile.json              # Your experience data (structured)
├── output/                       # Generated tailored files
│   └── {company_name}/
│       ├── resume.tex
│       └── cover_letter.tex
├── src/
│   ├── __init__.py
│   ├── cli.py                    # CLI entry point (click or argparse)
│   ├── parser.py                 # Job description parser
│   ├── matcher.py                # Skills/experience matching logic
│   ├── tailorer.py               # Resume + cover letter tailoring
│   └── llm.py                    # Anthropic API wrapper
└── tests/
    ├── test_parser.py
    ├── test_matcher.py
    └── test_tailorer.py
```

---

## Core Data Model

### `profile.json` — Your structured experience

This is the source of truth. The LLM never invents experience — it only selects and reorders from this data.

```json
{
  "name": "Alex Morgan",
  "contact": {
    "phone": "(555) 123-4567",
    "email": "alex.morgan@example.com",
    "website": "alexmorgan.dev",
    "location": "Austin, TX"
  },
  "education": {
    "degree": "Computer Science, B.S.",
    "school": "State University",
    "dates": "May 2020 - May 2023"
  },
  "experience": [
    {
      "id": "acme",
      "title": "Software Engineer",
      "company": "Acme Analytics",
      "dates": "Apr 2025 - Apr 2026",
      "bullets": [
        {
          "id": "acme-ui",
          "text": "Built and shipped customer-facing UI features in JavaScript, collaborating with design and product to deliver responsive, accessible components used across the company's SaaS platform.",
          "tags": ["javascript", "vue.js", "frontend", "saas", "ui", "accessibility", "collaboration"]
        },
        {
          "id": "acme-agent",
          "text": "Designed and implemented a production AI agent in Python using LangGraph (StateGraph, ToolNode, ReAct pattern) with conditional branching and parallel tool execution to automate in-app guide creation for end users.",
          "tags": ["python", "langgraph", "ai", "agent", "llm", "tool-calling", "backend"]
        },
        {
          "id": "acme-mau",
          "text": "Shipped the agent to production, reaching 5,000 monthly active users within the first month of launch. Iterated on agent reliability and edge case handling based on real user behavior.",
          "tags": ["production", "metrics", "iteration", "reliability"]
        },
        {
          "id": "acme-streaming",
          "text": "Integrated the agent with the frontend via streaming APIs, giving users real-time visibility into agent progress and reducing perceived latency. Owned the full integration from backend endpoint to UI rendering.",
          "tags": ["streaming", "api", "frontend", "backend", "fullstack", "ownership", "real-time"]
        }
      ]
    },
    {
      "id": "vertex",
      "title": "Software Engineer",
      "company": "Vertex Systems",
      "dates": "Jun 2023 - Apr 2025",
      "bullets": [
        {
          "id": "vertex-frontend",
          "text": "Developed consumer-facing geospatial web applications in React, Redux, and TypeScript for enterprise customers, including interactive map interfaces and real-time data overlays.",
          "tags": ["react", "redux", "typescript", "frontend", "geospatial", "consumer-facing"]
        },
        {
          "id": "vertex-backend",
          "text": "Built RESTful APIs and backend services in Node.js, Java, and Python, containerized with Docker and deployed via Kubernetes on AWS. Designed schema and wrote migrations for PostgreSQL databases.",
          "tags": ["node.js", "java", "python", "rest", "api", "docker", "kubernetes", "aws", "postgresql", "database", "schema"]
        },
        {
          "id": "vertex-rabbitmq",
          "text": "Led adoption of RabbitMQ for live geospatial data streaming, using web workers and Protocol Buffers to reduce latency and improve throughput across real-time data pipelines powering operational dashboards.",
          "tags": ["rabbitmq", "streaming", "real-time", "data-pipeline", "protocol-buffers", "performance"]
        },
        {
          "id": "vertex-adrs",
          "text": "Authored architecture decision records to document system design choices, improving team alignment, onboarding velocity, and long-term maintainability of the codebase.",
          "tags": ["documentation", "architecture", "team", "onboarding", "maintainability"]
        }
      ]
    },
    {
      "id": "globex",
      "title": "Software Engineer Intern",
      "company": "Globex Logistics",
      "dates": "May 2022 - Aug 2022",
      "bullets": [
        {
          "id": "globex-main",
          "text": "Built user-facing features in JavaScript and Angular, integrated with .NET RESTful APIs, and wrote SQL scripts and stored procedures in MySQL for data retrieval and reporting.",
          "tags": ["javascript", "angular", ".net", "rest", "api", "sql", "mysql", "stored-procedures"]
        }
      ]
    },
    {
      "id": "healthco",
      "title": "Software Engineer Intern",
      "company": "HealthCo",
      "dates": "May 2021 - Aug 2021",
      "bullets": [
        {
          "id": "healthco-main",
          "text": "Shipped user-facing features in TypeScript and Vue.js with TDD (Jest, Cypress), and built endpoints in .NET backend services backed by MySQL.",
          "tags": ["typescript", "vue.js", "tdd", "jest", "cypress", "testing", ".net", "mysql"]
        }
      ]
    },
    {
      "id": "military",
      "title": "Supply and Logistics Management",
      "company": "U.S. Armed Forces",
      "dates": "Mar 2015 - Jun 2020",
      "bullets": [
        {
          "id": "military-main",
          "text": "Managed shift operations in an aircraft maintenance unit, coordinating logistics for 20+ aircraft, aircrew, and ground technicians in a high-tempo operational environment.",
          "tags": ["leadership", "operations", "logistics", "military"]
        }
      ]
    }
  ],
  "skills": {
    "languages": ["JavaScript", "TypeScript", "Python", "Java", "SQL"],
    "frontend": ["React", "Redux", "Vue.js", "Next.js", "Angular", "RxJS"],
    "backend": ["Node.js", "Python", "RESTful APIs", "RabbitMQ", "Protocol Buffers", ".NET"],
    "cloud_devops": ["AWS", "Azure", "Docker", "Kubernetes", "CI/CD", "GitHub Actions", "Jenkins", "GitLab CI", "Git"],
    "ai_ml": ["LangGraph", "LLM tool-calling", "Agent Design", "MCP"],
    "databases": ["PostgreSQL", "MySQL"],
    "testing": ["Jest", "Cypress", "Playwright", "TDD"]
  },
  "include_internships": true,
  "always_include": ["acme", "vertex", "military"]
}
```

---

## CLI Interface

### Basic usage

```bash
# Interactive mode — paste a job description
resumeforge tailor

# With company name
resumeforge tailor --company "IONNA"

# From a file
resumeforge tailor --company "IONNA" --jd path/to/job_description.txt

# Batch mode — multiple JDs in a directory
resumeforge batch --jd-dir ./job_descriptions/

# Skip cover letter
resumeforge tailor --company "IONNA" --resume-only
```

### Interactive flow

```
$ resumeforge tailor --company IONNA

📋 Paste the job description (press Enter twice when done):
> [user pastes JD]

🔍 Analyzing job description...

📊 Match analysis:
   Strong matches: React, TypeScript, Node.js, RESTful APIs, Docker, Kubernetes, AWS
   Partial matches: Next.js (in skills, not in bullets), PostgreSQL
   Nice-to-haves matched: Python, CI/CD, SQL, consumer-facing products
   Gaps: OCPP/ISO 15118 (industry-specific, skip), payment processing

📝 Tailoring resume...
   ✓ Skills reordered: TypeScript, JavaScript first; React before Vue.js
   ✓ Frontend line: React, Redux, Vue.js, Next.js
   ✓ Vertex bullets: frontend bullet first (React focus)
   ✓ Internships: excluded (3+ years covered by Acme + Vertex)

📝 Tailoring cover letter...
   ✓ Tech paragraph: leads with React, TypeScript, Node.js
   ✓ Company name: IONNA
   ✓ Role title: Full Stack Software Developer
   ✓ Mission paragraph: customized to EV charging / driver experience

✅ Output saved:
   → output/Alex_Morgan_Resume__IONNA.txt
   → output/IONNA/Alex_Morgan_Cover_Letter__IONNA.txt

```

---

## How Tailoring Works

### Step 1: Parse the job description

Extract structured data from the raw JD text using Haiku:

```json
{
  "company": "IONNA",
  "role_title": "Full Stack Software Developer",
  "required_skills": ["React", "TypeScript", "Node.js", "Next.js", "RESTful APIs", "Git"],
  "nice_to_have_skills": ["Python", "AWS", "Docker", "Kubernetes", "SQL", "CI/CD"],
  "key_themes": ["consumer-facing", "small team", "ownership", "data pipelines", "real-time"],
  "industry": "EV charging / clean energy",
  "experience_years": "3+",
  "mission_keywords": ["driver experience", "EV charging", "physical world impact"]
}
```

### Step 2: Match against profile

Deterministic matching (no LLM needed for this step):

1. **Skills reorder**: For each skill category, sort items by whether they appear in required_skills (first), nice_to_have_skills (second), then remaining.

2. **Bullet reorder**: For each job, score bullets by tag overlap with required + nice-to-have skills. Higher-scoring bullets go first.

3. **Internship decision**: If required experience years ≤ total years from main roles, exclude internships to save space. Otherwise include them.

4. **Skill category filtering**: If a skill category has items not relevant to the JD and space is tight, trim the least relevant items.

### Step 3: Tailor cover letter

This is the one step that uses the LLM substantively. Send Haiku:
- The parsed JD structure
- The cover letter template
- Your profile data
- Instructions:

```
You are tailoring a cover letter for a job application. You must:

1. Replace the company name, role title, and "Dear Hiring Manager" line
2. Rewrite the first paragraph to lead with the skills most relevant to THIS role
3. Rewrite the mission/interest paragraph to reference THIS company's specific
   mission and product, using details from the job description
4. Keep the same overall structure: intro → experience → mission → AI tools → close
5. Keep the same voice and tone — direct, confident, not flowery
6. NEVER invent experience. Only reference things from the profile data.
7. Keep it under 350 words.
8. Output valid LaTeX.
```

### Step 4: Render to LaTeX

Take the reordered data and write it into the `.txt` files following latex templates:
- Replace skill lines with reordered versions
- Replace bullet items with reordered versions
- Write cover letter with LLM-generated content
- Save both files to `output/{company_name}/`

---

### API setup

```python
# src/llm.py
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

def call_haiku(system: str, prompt: str) -> str:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
```

---

## Dependencies

```toml
[project]
name = "resumeforge"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "click>=8.1.0",
    "pydantic>=2.0.0",
    "rich>=13.0.0",
]

[project.scripts]
resumeforge = "src.cli:main"
```

- **anthropic**: API client for Haiku calls
- **click**: CLI framework
- **pydantic**: Profile and JD schema validation
- **rich**: Pretty terminal output (match analysis, progress)

No LaTeX compilation dependency — the tool outputs `.tex` files that you compile in Overleaf as you already do.

---

## Development sequence

```
Step 1:  Project scaffolding (pyproject.toml, src structure, .env handling)
Step 2:  Define Pydantic models for profile.json and parsed JD
Step 3:  Build profile.json with your complete experience data
Step 4:  JD parser — LLM call to extract structured data from raw text
Step 5:  Matcher — deterministic skill/bullet scoring and reordering
Step 6:  Resume renderer — write reordered data into resume .tex template
Step 7:  Cover letter tailorer — LLM call to customize cover letter
Step 8:  Cover letter renderer — write into cover letter .tex template
Step 9:  CLI wiring — click commands, interactive paste mode, file input
Step 10: Batch mode — process multiple JDs from a directory
Step 11: Cost tracking — log token usage and cumulative spend
Step 12: Tests — parser, matcher, renderer unit tests
```

---

## Example: What changes per application

Given the same master resume, here's what ResumeForge would change for two different jobs:

### IONNA (React + Node.js + data pipelines)
- **Skills**: TypeScript before JavaScript; React before Vue.js; Node.js first in backend; add Next.js to frontend
- **Vertex bullets**: Frontend bullet first, backend bullet second
- **Internships**: Excluded (3+ years covered)
- **Cover letter**: Leads with React/TypeScript/Node.js, mentions data pipelines and real-time systems

### LangChain (Python + LangGraph + agents)
- **Skills**: Python before JavaScript; LangGraph/AI line moved up
- **Acme bullets**: Agent bullet first, MAU bullet second
- **Internships**: Excluded
- **Cover letter**: Leads with LangGraph/agentic systems, mentions production agent with 5K MAU

### Known (Python + FastAPI + Vue.js + agents)
- **Skills**: Python first; Vue.js before React; add FastAPI if comfortable claiming it
- **Acme bullets**: Agent bullet first, Vue.js bullet second
- **Internships**: Excluded
- **Cover letter**: Leads with Python + Vue.js full-stack, mentions agent + streaming integration


Example Resume Latex text:
```
\begin{document}
%----------------------------------------------------------------------------------------
%	WORK EXPERIENCE SECTION
%----------------------------------------------------------------------------------------
\begin{rSection}{EXPERIENCE}
\textbf{Software Engineer} \hfill Apr 2025 - Apr 2026\\
Acme Analytics
 \begin{itemize}
    \itemsep 3pt {}
    \item Built and shipped customer-facing UI features in JavaScript, collaborating with design and product to deliver responsive, accessible components used across the company's SaaS platform.
    \item Designed and implemented a production AI agent in Python using LangGraph (StateGraph, ToolNode, ReAct pattern) with conditional branching and parallel tool execution to automate in-app guide creation for end users.
    \item Shipped the agent to production, reaching 5,000 monthly active users within the first month of launch. Iterated on agent reliability and edge case handling based on real user behavior.
    \item Integrated the agent with the frontend via streaming APIs, giving users real-time visibility into agent progress and reducing perceived latency. Owned the full integration from backend endpoint to UI rendering.
 \end{itemize}
\textbf{Software Engineer} \hfill Jun 2023 - Apr 2025\\
Vertex Systems
 \begin{itemize}
    \itemsep 3pt {}
    \item Developed consumer-facing geospatial web applications in React, Redux, and TypeScript for enterprise customers, including interactive map interfaces and real-time data overlays.
    \item Built RESTful APIs and backend services in Node.js, Java, and Python, containerized with Docker and deployed via Kubernetes. Designed schemas and wrote migrations for PostgreSQL databases.
    \item Led adoption of RabbitMQ for live geospatial data streaming, using web workers and Protocol Buffers to reduce latency and improve throughput across real-time data pipelines powering operational dashboards.
    \item Authored architecture decision records to document system design choices, improving team alignment, onboarding velocity, and long-term maintainability of the codebase.
 \end{itemize}
\textbf{Supply and Logistics Management} \hfill Mar 2015 - Jun 2020\\
U.S. Armed Forces
 \begin{itemize}
    \itemsep 3pt {}
    \item Managed shift operations in an aircraft maintenance unit, coordinating logistics for 20+ aircraft, aircrew, and ground technicians in a high-tempo operational environment.
 \end{itemize}
\end{rSection}
```

Example Cover Letter Latext text
```

\noindent
Dear Hiring Manager,
\\

I am a full-stack engineer with production experience creating customer-facing applications using React, TypeScript, building RESTful APIs with  Python and Java, and shipping agentic features using frameworks like LangGraph with MCP services and tool-calling workflows.

In my previous role at Vertex Systems, I built UI/UX features for a geospatial analysis platform using React and TypeScript with a small group of engineers. There I also led the adoption of RabbitMQ for managing live data streams using Protocol Buffers. At Acme Analytics, I shipped customer-facing features in JavaScript and built an AI agent in Python using LangGraph that reached 5,000 monthly active users within a month of launch. I was closely involved in these two efforts taking ownership of design, architecture, requirements collection, testing strategy, and deployment.

What draws me to IONNA is the combination of mission and team structure. EV charging infrastructure is something that will soon affect millions as the transportation industry shifts and I would love to be part of a solution in that space. I'm interested in being part of a team that builds products in a high-ownership environment and based on the job description IONNA offers the kind of small team, extreme ownership culture that I do my best work in.

I also want to highlight my interest in using AI development tools as a part of my daily engineering workflow. At Acme Analytics I was encouraged to use these powerful tools, primarily Claude, and I have integrated that habit even into my personal projects. I'd love to work with a team that does the same.

I hope you will give me a chance to discuss how my experience could contribute to IONNA's platform.

\vskip 2.0cm
```
