from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from browser_agent import BrowserAgentEngine


class PlanRequest(BaseModel):
    request: str = Field(min_length=3, max_length=2000)
    parameters: dict = Field(default_factory=dict)


class ExecuteRequest(BaseModel):
    approval_token: str = ""
    profile: dict = Field(default_factory=dict)


def create_api(engine=None):
    app = FastAPI(title="AiOS Browser Automation API", version="0.1.0")
    browser_agent = engine or BrowserAgentEngine()

    @app.get("/health")
    def health():
        return {"ok": True, "service": "aios-browser-agent"}

    @app.get("/capabilities")
    def capabilities():
        return browser_agent.capabilities()

    @app.get("/plans")
    def plans():
        return browser_agent.store.list_plans()

    @app.post("/plans", status_code=201)
    def create_plan(payload: PlanRequest):
        try:
            return browser_agent.create_plan(payload.request, payload.parameters)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/plans/{plan_id}/execute")
    def execute(plan_id: str, payload: ExecuteRequest):
        try:
            return browser_agent.execute_plan(plan_id, payload.approval_token, payload.profile)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/opportunities")
    def opportunities():
        return browser_agent.store.list_opportunities()

    return app


app = create_api()
