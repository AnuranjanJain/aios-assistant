from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from career_agent import CareerCopilotEngine
from app.services.agent_auth import require_agent_token
from app.services.request_limits import install_request_size_limit


app = FastAPI(title="AiOS Career Copilot", version="0.1.0")
engine = CareerCopilotEngine()


class RepositoryRequest(BaseModel):
    source: str = Field(min_length=1, max_length=1000)
    project_name: str = Field(default="", max_length=200)


class ResumeRequest(BaseModel):
    resume_text: str = Field(min_length=1, max_length=50_000)
    job_description: str = Field(default="", max_length=50_000)


class JobRequest(BaseModel):
    job_description: str = Field(min_length=1, max_length=50_000)
    title: str = Field(default="", max_length=240)
    company: str = Field(default="", max_length=240)


class ApplicationRequest(BaseModel):
    company: str = Field(min_length=1, max_length=240)
    role: str = Field(min_length=1, max_length=240)
    status: str = Field(default="saved", max_length=40)
    source_url: str = Field(default="", max_length=2000)
    interview_date: str = Field(default="", max_length=80)
    offer_details: str = Field(default="", max_length=10_000)
    feedback: str = Field(default="", max_length=10_000)


install_request_size_limit(app)


@app.get("/health")
def health():
    return {"ok": True, "capabilities": engine.capabilities()}


@app.get("/dashboard", dependencies=[Depends(require_agent_token)])
def dashboard():
    return engine.dashboard()


@app.post("/github/analyze", dependencies=[Depends(require_agent_token)])
def analyze_repository(payload: RepositoryRequest):
    try:
        return engine.analyze_repository(payload.source, payload.project_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/resume/optimize", dependencies=[Depends(require_agent_token)])
def optimize_resume(payload: ResumeRequest):
    try:
        return engine.optimize_resume(payload.resume_text, payload.job_description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/jobs/match", dependencies=[Depends(require_agent_token)])
def match_job(payload: JobRequest):
    try:
        return engine.match_job(payload.job_description, payload.title, payload.company)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/applications", dependencies=[Depends(require_agent_token)])
def save_application(payload: ApplicationRequest):
    return {"id": engine.save_application(payload.model_dump())}


@app.get("/roadmap", dependencies=[Depends(require_agent_token)])
def roadmap(target_role: str = "AI Engineer"):
    return engine.roadmap_for(target_role)


@app.get("/search", dependencies=[Depends(require_agent_token)])
def search(q: str):
    return {"results": engine.search(q)}
