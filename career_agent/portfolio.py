from career_agent.taxonomy import group_skills


class PortfolioIntelligence:
    def __init__(self, project_names):
        self.project_names = project_names

    def from_repository(self, repository):
        technologies = repository.get("technologies", [])
        frameworks = repository.get("frameworks", [])
        documentation = repository.get("documentation", {})
        architecture = repository.get("architecture", {})
        score = repository.get("score", 0)
        strengths = []
        if frameworks:
            strengths.append(f"Uses practical technologies: {', '.join(frameworks[:5])}.")
        if "test suite" in architecture.get("signals", []):
            strengths.append("Includes tests, which improves hiring confidence.")
        if documentation.get("score", 0) >= 60:
            strengths.append("Documentation is visible enough for portfolio review.")
        if repository.get("commit_activity", {}).get("recent_commits", 0):
            strengths.append("Shows recent commit activity.")
        weaknesses = []
        if documentation.get("score", 0) < 60:
            weaknesses.append("README, setup guide, screenshots, or license can be improved.")
        if "CI pipeline" not in architecture.get("signals", []):
            weaknesses.append("No CI signal detected.")
        if "test suite" not in architecture.get("signals", []):
            weaknesses.append("Testing signal is weak or missing.")
        missing = []
        if "API layer" not in architecture.get("signals", []):
            missing.append("Public API or service boundary is not obvious.")
        if "containerization" not in architecture.get("signals", []):
            missing.append("Deployment/container instructions are missing.")
        if not frameworks:
            missing.append("Technology stack is not clearly declared.")
        relevance = self._relevance(technologies, repository.get("name", ""))
        return {
            "name": repository.get("name", "Project"),
            "repository_id": repository.get("id", ""),
            "status": "Active",
            "strengths": strengths or ["Project is present and analyzable."],
            "weaknesses": weaknesses or ["Needs deeper live usage metrics for stronger proof."],
            "missing_components": missing or ["Add a concise case study with problem, architecture, and result."],
            "relevance": relevance,
            "portfolio_score": min(100, max(0, score + relevance["industry_score"] // 10)),
        }

    def seed_missing_projects(self, existing_names):
        existing = {name.lower() for name in existing_names}
        projects = []
        for name in self.project_names:
            if name.lower() in existing:
                continue
            projects.append(
                {
                    "name": name,
                    "repository_id": "",
                    "status": "Needs source",
                    "strengths": ["Known portfolio target for AiOS career tracking."],
                    "weaknesses": ["Repository or project evidence has not been analyzed yet."],
                    "missing_components": ["Connect a GitHub URL or local repository path."],
                    "relevance": {"roles": ["AI Engineer", "Backend Engineer"], "industry_score": 45, "skill_groups": []},
                    "portfolio_score": 45,
                }
            )
        return projects

    def aggregate(self, repositories, projects):
        techs = sorted({tech for repo in repositories for tech in repo.get("technologies", [])})
        skill_groups = group_skills(techs, " ".join(techs))
        average_score = round(sum(project.get("portfolio_score", 0) for project in projects) / max(1, len(projects)))
        strengths = []
        if "ai" in skill_groups:
            strengths.append("AI automation and local-agent systems are emerging as a clear portfolio theme.")
        if "python" in skill_groups:
            strengths.append("Python backend capability is supported by repository evidence.")
        if len(repositories) >= 3:
            strengths.append("Multiple projects can be positioned for different hiring narratives.")
        gaps = []
        if average_score < 70:
            gaps.append("Bring two flagship projects above 80 with docs, tests, screenshots, and deployment notes.")
        if "devops" not in skill_groups:
            gaps.append("Add CI/CD, containerization, and release automation proof.")
        if "data" not in skill_groups:
            gaps.append("Add stronger database, analytics, or vector-search evidence.")
        return {
            "portfolio_score": average_score,
            "technologies": techs,
            "skill_groups": skill_groups,
            "strengths": strengths or ["Portfolio has analyzable project evidence."],
            "gaps": gaps or ["Next improvement is clearer outcome metrics in project case studies."],
        }

    def _relevance(self, technologies, name):
        text = " ".join(technologies + [name]).lower()
        roles = []
        if any(term in text for term in ("ai", "llm", "ollama", "agent", "automation")):
            roles.append("AI Engineer")
        if any(term in text for term in ("fastapi", "flask", "sqlite", "python")):
            roles.append("Backend Engineer")
        if any(term in text for term in ("react", "vite", "dashboard")):
            roles.append("Full Stack Developer")
        score = 35 + min(45, len(roles) * 15) + min(20, len(technologies) * 3)
        return {"roles": roles or ["Software Engineer"], "industry_score": min(100, score), "skill_groups": group_skills(technologies)}
