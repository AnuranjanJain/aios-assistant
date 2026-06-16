from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from career_agent import CareerCopilotEngine


app = FastAPI(title="AiOS Career Copilot", version="0.1.0")
engine = CareerCopilotEngine()


class RepositoryRequest(BaseModel):
    source: str
    project_name: str = ""


class ResumeRequest(BaseModel):
    resume_text: str
    job_description: str = ""


class JobRequest(BaseModel):
    job_description: str
    title: str = ""
    company: str = ""


class ApplicationRequest(BaseModel):
    company: str
    role: str
    status: str = Field(default="saved")
    source_url: str = ""
    interview_date: str = ""
    offer_details: str = ""
    feedback: str = ""


@app.get("/health")
def health():
    return {"ok": True, "capabilities": engine.capabilities()}


@app.get("/dashboard")
def dashboard():
    return engine.dashboard()


@app.post("/github/analyze")
def analyze_repository(payload: RepositoryRequest):
    try:
        return engine.analyze_repository(payload.source, payload.project_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/resume/optimize")
def optimize_resume(payload: ResumeRequest):
    try:
        return engine.optimize_resume(payload.resume_text, payload.job_description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/jobs/match")
def match_job(payload: JobRequest):
    try:
        return engine.match_job(payload.job_description, payload.title, payload.company)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/applications")
def save_application(payload: ApplicationRequest):
    return {"id": engine.save_application(payload.model_dump())}


@app.get("/roadmap")
def roadmap(target_role: str = "AI Engineer"):
    return engine.roadmap_for(target_role)


@app.get("/search")
def search(q: str):
    return {"results": engine.search(q)}
