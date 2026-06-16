from career_agent.config import CareerConfig
from career_agent.github_analyzer import GitHubAnalyzer
from career_agent.matching import JobMatchEngine
from career_agent.portfolio import PortfolioIntelligence
from career_agent.recommendations import CareerAdvisor
from career_agent.resume import ResumeOptimizer
from career_agent.roadmap import RoadmapGenerator
from career_agent.store import CareerStore
from career_agent.vectors import LocalVectorIndex


class CareerCopilotEngine:
    def __init__(self, config=None):
        self.config = (config or CareerConfig.from_environment()).ensure()
        self.store = CareerStore(self.config.data_dir / "career_copilot.db")
        self.github = GitHubAnalyzer(self.config)
        self.portfolio = PortfolioIntelligence(self.config.project_names)
        self.matcher = JobMatchEngine()
        self.resume = ResumeOptimizer()
        self.roadmap = RoadmapGenerator()
        self.advisor = CareerAdvisor()
        self.vectors = LocalVectorIndex(self.store)
        self._bootstrap()

    def _bootstrap(self):
        self.store.upsert_profile(self.store.get_profile())
        user_node = self.store.upsert_graph_node("User", self.store.get_profile()["name"])
        for skill in self.store.get_profile()["skills"]:
            skill_node = self.store.upsert_graph_node("Skill", skill)
            self.store.upsert_graph_edge(user_node, skill_node, "has_skill", 0.8)
        existing = {project["name"] for project in self.store.list_projects()}
        for project in self.portfolio.seed_missing_projects(existing):
            project_id = self.store.save_project(project)
            project_node = self.store.upsert_graph_node("Project", project["name"], {"status": project["status"]})
            self.store.upsert_graph_edge(user_node, project_node, "owns_project", 0.6)
            self.vectors.index("project", project_id, " ".join(project["strengths"] + project["missing_components"]))
        self.refresh_recommendations()

    def update_profile(self, profile):
        self.store.upsert_profile(profile)
        self._bootstrap()
        return self.store.get_profile()

    def analyze_repository(self, source, project_name=""):
        analysis = self.github.analyze(source)
        repo_id = self.store.save_repository(analysis)
        analysis["id"] = repo_id
        project = self.portfolio.from_repository(analysis)
        if project_name.strip():
            project["name"] = project_name.strip()
        project_id = self.store.save_project(project)
        self._index_repository_graph(analysis, project)
        self.vectors.index("repository", repo_id, self._repo_text(analysis))
        self.vectors.index("project", project_id, " ".join(project["strengths"] + project["weaknesses"] + project["missing_components"]))
        self.refresh_recommendations()
        return {"repository": analysis, "project": project}

    def portfolio_overview(self):
        repositories = self.store.list_repositories()
        projects = self.store.list_projects()
        aggregate = self.portfolio.aggregate(repositories, projects)
        return {"aggregate": aggregate, "repositories": repositories, "projects": projects}

    def optimize_resume(self, resume_text, job_description=""):
        result = self.resume.optimize(resume_text, job_description, self.store.get_profile(), self.store.list_projects())
        self.store.save_resume(result)
        self.vectors.index("resume", result["id"], result["optimized_text"])
        self.refresh_recommendations()
        return result

    def match_job(self, job_description, title="", company=""):
        if not job_description.strip():
            raise ValueError("Job description is required.")
        result = self.matcher.match(
            job_description,
            self.store.get_profile(),
            self.store.list_repositories(),
            self.store.list_projects(),
            title=title,
            company=company,
        )
        self.store.save_job_match(result)
        self.vectors.index("job_match", result["id"], job_description)
        self.refresh_recommendations()
        return result

    def save_application(self, application):
        application_id = self.store.save_application(application)
        self.refresh_recommendations()
        return application_id

    def roadmap_for(self, target_role="AI Engineer"):
        return self.roadmap.generate(self.store.get_profile(), self.portfolio_overview()["aggregate"], target_role)

    def refresh_recommendations(self):
        recommendations = self.advisor.recommend(
            self.portfolio_overview()["aggregate"],
            self.store.list_applications(),
            self.store.list_job_matches(),
        )
        self.store.replace_recommendations(recommendations)
        return recommendations

    def dashboard(self):
        portfolio = self.portfolio_overview()
        matches = self.store.list_job_matches()
        applications = self.store.list_applications()
        recommendations = self.store.list_recommendations()
        counts = {
            "repositories": len(portfolio["repositories"]),
            "projects": len(portfolio["projects"]),
            "applications": len(applications),
            "strong_matches": sum(match["overall_score"] >= 70 for match in matches),
        }
        return {
            "profile": self.store.get_profile(),
            "portfolio": portfolio,
            "matches": matches,
            "applications": applications,
            "recommendations": recommendations,
            "roadmap": self.roadmap_for(),
            "graph": self.store.graph(),
            "counts": counts,
            "capabilities": self.capabilities(),
        }

    def search(self, query):
        return self.vectors.search(query)

    def capabilities(self):
        return {
            "local_first": True,
            "database": str(self.store.database_path),
            "github_api": "available" if self.config.github_token else "optional",
            "credentials_stored": False,
            "vector_index": "sqlite_token_index",
        }

    def _index_repository_graph(self, repository, project):
        profile = self.store.get_profile()
        user_node = self.store.upsert_graph_node("User", profile["name"])
        project_node = self.store.upsert_graph_node("Project", project["name"], {"score": project["portfolio_score"]})
        self.store.upsert_graph_edge(user_node, project_node, "owns_project", 1.0)
        for technology in repository.get("technologies", []) + repository.get("frameworks", []):
            tech_node = self.store.upsert_graph_node("Technology", technology)
            self.store.upsert_graph_edge(project_node, tech_node, "uses", 0.9)
            self.store.upsert_graph_edge(user_node, tech_node, "has_evidence_for", 0.7)
        for role in project.get("relevance", {}).get("roles", []):
            role_node = self.store.upsert_graph_node("Goal", role)
            self.store.upsert_graph_edge(project_node, role_node, "supports", 0.7)

    def _repo_text(self, analysis):
        return " ".join(
            [
                analysis.get("name", ""),
                " ".join(analysis.get("technologies", [])),
                " ".join(analysis.get("frameworks", [])),
                " ".join(analysis.get("architecture", {}).get("signals", [])),
            ]
        )
