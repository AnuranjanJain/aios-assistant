from career_agent.taxonomy import ACTION_VERBS, extract_technologies, normalize_terms


class ResumeOptimizer:
    def optimize(self, resume_text, job_description, profile, projects):
        if not resume_text.strip():
            raise ValueError("Resume text is required.")
        jd_terms = normalize_terms(job_description)
        resume_terms = normalize_terms(resume_text)
        project_names = [project["name"] for project in projects if project.get("portfolio_score", 0) >= 50]
        missing = sorted((jd_terms - resume_terms))[:12]
        technologies = extract_technologies(job_description)
        changes = []
        optimized = resume_text.strip()
        if technologies:
            optimized += "\n\nTargeted Skills: " + ", ".join(technologies)
            changes.append("Added a targeted skills line based on the job description.")
        if project_names:
            optimized += "\n\nRelevant Projects:\n" + "\n".join(
                f"- {ACTION_VERBS[index % len(ACTION_VERBS)]} {name}: connected project proof to the target role with measurable local-first engineering outcomes."
                for index, name in enumerate(project_names[:4])
            )
            changes.append("Reordered high-signal projects near the top of the resume draft.")
        if missing:
            optimized += "\n\nKeywords To Weave Naturally: " + ", ".join(missing[:8])
            changes.append("Flagged missing ATS keywords to add only where truthful.")
        ats_score = min(100, 45 + len(jd_terms & (resume_terms | set(term.lower() for term in technologies))) * 4 + len(project_names) * 5)
        return {
            "title": "Career Copilot Resume Draft",
            "original_text": resume_text,
            "job_description": job_description,
            "optimized_text": optimized,
            "ats_score": ats_score,
            "changes": changes or ["Resume already covers the strongest detected keywords."],
        }
