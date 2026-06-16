# AiOS Career Copilot

AiOS Career Copilot is the local-first career brain for AiOS. It converts project evidence, GitHub activity, resumes, job descriptions, and application outcomes into a career knowledge graph and practical recommendations.

## Mission

Help Anuranjan understand what his current portfolio proves, what roles he is closest to, what gaps are blocking stronger applications, and what to do next.

The module is designed to become the bridge between:

- Memory Agent: long-term profile, goals, projects, skills, and learning history
- Planner Agent: daily and weekly execution plans
- Browser Agent: job discovery and opportunity intake
- What Do You Do: activity and focus evidence from real computer usage

## Architecture

```text
GitHub / local repos
Resume text
Job descriptions
Application notes
        |
CareerCopilotEngine
        |
GitHub Analyzer      Resume Optimizer
Portfolio Engine     Job Match Engine
Roadmap Generator    Career Advisor
        |
SQLite + local token vector index
        |
Flask dashboard + FastAPI service
```

## Folder Structure

```text
career_agent/
  api.py                 FastAPI API
  config.py              local config and optional GitHub token
  engine.py              orchestration layer
  github_analyzer.py     local repo and GitHub API analyzer
  matching.py            job description scoring
  portfolio.py           project intelligence
  recommendations.py     career advisor
  resume.py              resume optimizer
  roadmap.py             30/90/6-month/1-year plans
  store.py               SQLite schema and persistence
  vectors.py             local search index
```

## Database Design

SQLite tables:

- `career_profile`: name, headline, target roles, skills, goals
- `github_repository`: languages, frameworks, architecture, complexity, docs, commit activity
- `project_profile`: strengths, weaknesses, missing components, industry relevance
- `graph_node`: User, Project, Skill, Technology, Goal, Job Application, Learning Path
- `graph_edge`: relationships such as `owns_project`, `uses`, `supports`, `has_evidence_for`
- `resume_version`: original resume, optimized draft, ATS score, changes
- `job_match`: score breakdown and missing skills
- `career_application`: company, role, status, interview date, offer details, feedback
- `career_recommendation`: prioritized advisor output
- `vector_document`: local search terms for semantic-style retrieval

## Knowledge Graph Design

```text
User
  owns_project -> Project
  has_skill -> Skill
  has_evidence_for -> Technology

Project
  uses -> Technology
  supports -> Goal

Job Description
  requires -> Skill
  matches -> Project

Application
  targets -> Company
  targets -> Role
```

The current MVP stores nodes and edges locally in SQLite. Later, the Memory Agent can absorb the same graph into the larger AiOS memory graph.

## GitHub Analysis Engine

The analyzer supports:

- local repository paths without internet
- GitHub repository URLs through the GitHub API
- optional `GITHUB_TOKEN` from environment only

It extracts:

- language percentages
- frameworks and technologies
- architecture signals
- entrypoints
- file count and line count
- README/license/test quality
- recent git commit activity for local repos

Sensitive paths are skipped during local scanning, including `.env`, credential-like names, `.git`, virtual environments, build outputs, and `node_modules`.

## Portfolio Intelligence

The portfolio engine evaluates:

- AiOS
- What Do You Do
- Healthcare App
- Video Enhancer
- Hackathon Projects

For each project it produces strengths, weaknesses, missing components, role relevance, and a portfolio score. Missing projects are seeded as placeholders so the dashboard clearly shows what still needs evidence.

## Resume Optimization Pipeline

Input:

- resume text
- target job description
- profile skills
- project evidence

Output:

- optimized resume draft
- ATS-style score
- suggested truthful keywords
- reordered high-signal projects
- change list

The MVP is deterministic and local. It does not send resume content to OpenAI, Google, or any cloud model.

## Job Matching Algorithm

Scores:

- Skill Match: profile and repo terms against JD terms
- Technology Match: detected technologies against repository evidence
- Experience Match: portfolio strength proxy
- Project Match: project descriptions and proof against JD terms

Overall score:

```text
skill * 0.35 + technology * 0.25 + project * 0.25 + experience * 0.15
```

The result includes matched terms, missing terms, and a short explanation.

## Career Recommendation Engine

The advisor watches portfolio score, application statuses, recent job match scores, and repeated skill gaps. It recommends concrete actions like improving flagship proof, prioritizing high-score roles, closing repeated JD gaps, and keeping release cadence visible.

## Dashboard Design

The `/career` dashboard includes portfolio readiness cards, repository analysis, resume optimization, job scoring, application tracking, project evidence, recommendations, roadmap, and the local database boundary.

## Security Model

- Local-first by default.
- SQLite database is stored under the AiOS local data directory.
- GitHub token is optional and read only from environment.
- GitHub token is never stored in SQLite.
- Resume and job descriptions stay local.
- Browser/API access continues to use the existing AiOS local auth and trusted-origin rules.
- No automatic job submission is performed by this module.

## MVP Roadmap

Completed in this phase:

- local Career Copilot engine
- SQLite database schema
- local repository analyzer
- optional GitHub API analyzer
- project intelligence
- resume optimizer
- job match algorithm
- application database
- roadmap generator
- recommendation engine
- Flask dashboard
- FastAPI service module

Next:

- import application data from Browser Agent opportunities
- sync projects and goals into Memory Agent
- turn roadmap actions into Planner Agent tasks
- add PDF/DOCX resume import and export
- add richer vector embeddings through Ollama or ChromaDB
- add trend ingestion from curated local snapshots or user-approved web research
