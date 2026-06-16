import re


TECHNOLOGIES = {
    "aws", "azure", "css", "django", "docker", "fastapi", "flask", "git",
    "graphql", "html", "java", "javascript", "kubernetes", "linux", "mongodb",
    "next.js", "node.js", "postgresql", "python", "react", "redis", "sql",
    "typescript",
}


def normalize_terms(values):
    return {
        str(value).strip().lower()
        for value in values or []
        if str(value).strip()
    }


def extract_skills(text):
    lowered = (text or "").lower()
    return sorted(skill for skill in TECHNOLOGIES if re.search(rf"\b{re.escape(skill)}\b", lowered))


def score_opportunity(job, profile):
    job_skills = normalize_terms(job.get("skills") or extract_skills(job.get("description", "")))
    user_skills = normalize_terms(profile.get("skills"))
    project_terms = normalize_terms(profile.get("projects"))
    resume_terms = normalize_terms(profile.get("resume_keywords"))
    experience_years = max(0.0, float(profile.get("experience_years") or 0))
    requested_years = max(0.0, float(job.get("experience_years") or 0))

    skill_overlap = job_skills & user_skills
    project_overlap = job_skills & project_terms
    resume_overlap = job_skills & resume_terms
    skill_score = (len(skill_overlap) / max(1, len(job_skills))) * 55
    project_score = min(20, len(project_overlap) * 7)
    resume_score = min(15, len(resume_overlap) * 5)
    experience_score = 10 if requested_years <= experience_years + 1 else max(0, 10 - (requested_years - experience_years) * 4)
    total = max(0, min(100, round(skill_score + project_score + resume_score + experience_score)))

    reasons = []
    if skill_overlap:
        reasons.append(f"skills: {', '.join(sorted(skill_overlap))}")
    if project_overlap:
        reasons.append(f"project evidence: {', '.join(sorted(project_overlap))}")
    if requested_years:
        reasons.append(f"experience target: {requested_years:g} years")
    if not reasons:
        reasons.append("limited overlap with the current local profile")
    return total, "; ".join(reasons)
