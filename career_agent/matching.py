from career_agent.taxonomy import extract_technologies, normalize_terms


class JobMatchEngine:
    def match(self, job_description, profile, repositories, projects, title="", company=""):
        jd_terms = normalize_terms(job_description)
        profile_terms = normalize_terms(" ".join(profile.get("skills", []) + profile.get("target_roles", [])))
        repo_terms = normalize_terms(" ".join(
            tech for repo in repositories for tech in repo.get("technologies", []) + repo.get("frameworks", [])
        ))
        project_terms = normalize_terms(" ".join(
            " ".join(project.get("strengths", []) + project.get("missing_components", [])) + " " + project.get("name", "")
            for project in projects
        ))
        technologies = set(term.lower() for term in extract_technologies(job_description))
        matched = sorted((jd_terms & (profile_terms | repo_terms | project_terms)) | (technologies & repo_terms))
        missing = sorted(list(jd_terms - (profile_terms | repo_terms | project_terms)))[:12]
        skill_score = self._coverage(jd_terms, profile_terms | repo_terms)
        technology_score = self._coverage(technologies or jd_terms, repo_terms | profile_terms)
        project_score = self._coverage(jd_terms, project_terms | repo_terms)
        experience_score = 70 if any(project.get("portfolio_score", 0) >= 70 for project in projects) else 50
        overall = round(skill_score * 0.35 + technology_score * 0.25 + project_score * 0.25 + experience_score * 0.15)
        explanation = (
            f"Matched {len(matched)} important terms from profile, repositories, and projects. "
            f"Strongest area: {self._strongest(skill_score, technology_score, project_score, experience_score)}."
        )
        return {
            "title": title,
            "company": company,
            "job_description": job_description,
            "skill_score": skill_score,
            "technology_score": technology_score,
            "experience_score": experience_score,
            "project_score": project_score,
            "overall_score": overall,
            "explanation": explanation,
            "matched_skills": matched[:20],
            "missing_skills": missing,
        }

    def _coverage(self, required, available):
        if not required:
            return 50
        return min(100, round(100 * len(required & available) / max(1, len(required))))

    def _strongest(self, skill, technology, project, experience):
        scores = {"skills": skill, "technology": technology, "projects": project, "experience": experience}
        return max(scores, key=scores.get)
