class RoadmapGenerator:
    def generate(self, profile, portfolio, target_role="AI Engineer"):
        gaps = portfolio.get("gaps", [])
        technologies = portfolio.get("technologies", [])
        missing_core = ["Docker", "CI/CD", "PostgreSQL", "system design"]
        if "Ollama" not in technologies:
            missing_core.append("local LLM integration")
        return {
            "target_role": target_role or "AI Engineer",
            "qualified_for": self._qualified_roles(portfolio),
            "next_skills": missing_core[:5],
            "projects_to_build": [
                "Ship AiOS Career Copilot with GitHub, resume, and job scoring evidence.",
                "Publish one full-stack case study with architecture, screenshots, tests, and release notes.",
                "Build one data-backed project using SQLite plus vector search.",
            ],
            "certifications": ["GitHub Foundations", "AWS Cloud Practitioner or Azure AI Fundamentals"],
            "plans": {
                "30_days": [
                    "Analyze all portfolio repositories and fix README gaps.",
                    "Create one ATS resume variant for AI/backend roles.",
                    "Track every application with status and feedback.",
                ],
                "90_days": [
                    "Add CI, tests, screenshots, and releases to two flagship projects.",
                    "Apply to targeted internships and score each JD before applying.",
                    "Write two project case studies with measurable outcomes.",
                ],
                "6_months": [
                    "Complete one production-grade AI automation module.",
                    "Add cloud or deployment proof without exposing private user data.",
                    "Collect interview feedback and update skill roadmap monthly.",
                ],
                "1_year": [
                    "Build a portfolio narrative around local-first AI systems.",
                    "Maintain consistent GitHub activity and release cadence.",
                    "Convert strongest projects into internship/job interview stories.",
                ],
            },
            "portfolio_gaps": gaps,
        }

    def _qualified_roles(self, portfolio):
        groups = set(portfolio.get("skill_groups", []))
        roles = ["Software Engineer Intern"]
        if {"ai", "python"} & groups:
            roles.append("AI Engineer Intern")
        if "python" in groups:
            roles.append("Backend Developer Intern")
        if "javascript" in groups:
            roles.append("Full Stack Developer Intern")
        if "devops" in groups:
            roles.append("Automation Engineer Intern")
        return roles
