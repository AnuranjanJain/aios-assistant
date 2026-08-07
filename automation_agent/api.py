from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from automation_agent import AutomationEngine
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
    approval_token: str = Field(min_length=1, max_length=256)


def create_api(engine=None):
    app = FastAPI(title="AiOS Desktop Automation API", version="0.1.0")
    install_request_size_limit(app)
    automation = engine or AutomationEngine()

    @app.get("/health")
    def health():
        return {"ok": True, "service": "aios-desktop-automation"}

    @app.get("/capabilities", dependencies=[Depends(require_agent_token)])
    def capabilities():
        return automation.capabilities()

    @app.get("/plans", dependencies=[Depends(require_agent_token)])
    def plans():
        return automation.store.list_plans()

    @app.get("/plans/{plan_id}", dependencies=[Depends(require_agent_token)])
    def plan(plan_id: str):
        item = automation.store.get_plan(plan_id)
        if item is None:
            raise HTTPException(404, "Plan not found")
        return item

    @app.post("/plans", status_code=201, dependencies=[Depends(require_agent_token)])
    def create_plan(payload: PlanRequest):
        try:
            return automation.create_plan(payload.request, payload.parameters)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/plans/{plan_id}/execute", dependencies=[Depends(require_agent_token)])
    def execute(plan_id: str, payload: ExecuteRequest):
        try:
            return automation.execute_plan(plan_id, payload.approval_token)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/actions/{action_id}/restore", dependencies=[Depends(require_agent_token)])
    def restore(action_id: str):
        try:
            return automation.restore_action(action_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    return app


app = create_api()
