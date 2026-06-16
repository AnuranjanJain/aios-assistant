from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from automation_agent import AutomationEngine


class PlanRequest(BaseModel):
    request: str = Field(min_length=3, max_length=2000)
    parameters: dict = Field(default_factory=dict)


class ExecuteRequest(BaseModel):
    approval_token: str


def create_api(engine=None):
    app = FastAPI(title="AiOS Desktop Automation API", version="0.1.0")
    automation = engine or AutomationEngine()

    @app.get("/health")
    def health():
        return {"ok": True, "service": "aios-desktop-automation"}

    @app.get("/capabilities")
    def capabilities():
        return automation.capabilities()

    @app.get("/plans")
    def plans():
        return automation.store.list_plans()

    @app.get("/plans/{plan_id}")
    def plan(plan_id: str):
        item = automation.store.get_plan(plan_id)
        if item is None:
            raise HTTPException(404, "Plan not found")
        return item

    @app.post("/plans", status_code=201)
    def create_plan(payload: PlanRequest):
        try:
            return automation.create_plan(payload.request, payload.parameters)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/plans/{plan_id}/execute")
    def execute(plan_id: str, payload: ExecuteRequest):
        try:
            return automation.execute_plan(plan_id, payload.approval_token)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(403, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/actions/{action_id}/restore")
    def restore(action_id: str):
        try:
            return automation.restore_action(action_id)
        except KeyError as exc:
            raise HTTPException(404, str(exc)) from exc

    return app


app = create_api()
