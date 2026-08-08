from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from browser_agent import BrowserAgentEngine
from app.services.agent_auth import require_agent_token
from app.services.request_limits import install_request_size_limit


class PlanRequest(BaseModel):
    request: str = Field(min_length=3, max_length=2000)
    parameters: dict = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def parameters_are_bounded(cls, value):
        if len(repr(value)) > 20_000:
            raise ValueError("Plan parameters exceed the local agent limit.")
        return value


class ExecuteRequest(BaseModel):
    approval_token: str = Field(default="", max_length=256)
    profile: dict = Field(default_factory=dict)

    @field_validator("profile")
    @classmethod
    def profile_is_bounded(cls, value):
        if len(repr(value)) > 20_000:
            raise ValueError("Browser profile exceeds the local agent limit.")
        return value


def create_api(engine=None):
    app = FastAPI(title="AiOS Browser Automation API", version="0.1.0")
    install_request_size_limit(app)
    browser_agent = engine or BrowserAgentEngine()

    @app.get("/health")
    def health():
        return {"ok": True, "service": "aios-browser-agent"}

    @app.get("/capabilities", dependencies=[Depends(require_agent_token)])
    def capabilities():
        return browser_agent.capabilities()

    @app.get("/plans", dependencies=[Depends(require_agent_token)])
    def plans():
        return browser_agent.store.list_plans()

    @app.post("/plans", status_code=201, dependencies=[Depends(require_agent_token)])
    def create_plan(payload: PlanRequest):
        try:
            return browser_agent.create_plan(payload.request, payload.parameters)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/plans/{plan_id}/execute", dependencies=[Depends(require_agent_token)])
    def execute(plan_id: str, payload: ExecuteRequest):
        try:
            return browser_agent.execute_plan(plan_id, payload.approval_token, payload.profile)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/opportunities", dependencies=[Depends(require_agent_token)])
    def opportunities():
        return browser_agent.store.list_opportunities()

    return app


app = create_api()
