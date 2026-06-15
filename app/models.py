from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Opportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    organization = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(60), nullable=False, default="Tracked")
    source = db.Column(db.String(80), nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(180), nullable=False)
    due_at = db.Column(db.DateTime, nullable=False)
    channel = db.Column(db.String(40), nullable=False, default="dashboard")
    is_done = db.Column(db.Boolean, default=False, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    notified_at = db.Column(db.DateTime, nullable=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id"), nullable=True)
    opportunity = db.relationship("Opportunity", backref="reminders")


class InboxItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender = db.Column(db.String(180), nullable=True)
    subject = db.Column(db.String(240), nullable=False)
    body = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=False, default="general")
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ActivityEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(80), nullable=False, default="manual")
    app_name = db.Column(db.String(120), nullable=True)
    category = db.Column(db.String(80), nullable=False, default="unknown")
    planned_task = db.Column(db.String(180), nullable=True)
    actual_task = db.Column(db.String(180), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)
    agent_summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AgentDecision(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    input_type = db.Column(db.String(80), nullable=False)
    provider = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(120), nullable=True)
    decision_json = db.Column(db.Text, nullable=False)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class ConnectorRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    connector_id = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(40), nullable=False)
    message = db.Column(db.Text, nullable=True)
    records_seen = db.Column(db.Integer, nullable=False, default=0)
    records_imported = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class HackathonUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id"), nullable=False)
    opportunity = db.relationship("Opportunity", backref="hackathon_updates")
    platform = db.Column(db.String(80), nullable=False, default="other")
    source = db.Column(db.String(180), nullable=False)
    external_id = db.Column(db.String(240), nullable=True, unique=True)
    event_type = db.Column(db.String(60), nullable=False, default="update")
    title = db.Column(db.String(240), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    action_needed = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class PlacementUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id"), nullable=False)
    opportunity = db.relationship("Opportunity", backref="placement_updates")
    source = db.Column(db.String(180), nullable=False)
    external_id = db.Column(db.String(240), nullable=True, unique=True)
    event_type = db.Column(db.String(60), nullable=False, default="update")
    title = db.Column(db.String(240), nullable=False)
    summary = db.Column(db.Text, nullable=True)
    action_needed = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    occurred_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Setting(db.Model):
    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class MemoryEntity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(40), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    slug = db.Column(db.String(200), nullable=False, unique=True, index=True)
    status = db.Column(db.String(60), nullable=False, default="active", index=True)
    summary = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    last_worked_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class MemoryFact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entity_id = db.Column(db.Integer, db.ForeignKey("memory_entity.id"), nullable=True, index=True)
    entity = db.relationship("MemoryEntity", backref=db.backref("facts", cascade="all, delete-orphan"))
    fact_type = db.Column(db.String(50), nullable=False, default="note", index=True)
    content = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(120), nullable=False, default="manual")
    importance = db.Column(db.Float, nullable=False, default=0.5)
    embedding_json = db.Column(db.Text, nullable=True)
    occurred_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class MemoryRelation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("memory_entity.id"), nullable=False, index=True)
    target_id = db.Column(db.Integer, db.ForeignKey("memory_entity.id"), nullable=False, index=True)
    relation_type = db.Column(db.String(60), nullable=False, default="related_to")
    source = db.relationship("MemoryEntity", foreign_keys=[source_id])
    target = db.relationship("MemoryEntity", foreign_keys=[target_id])
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("source_id", "target_id", "relation_type", name="uq_memory_relation"),
    )


class WorkCheckpoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("memory_entity.id"), nullable=False, index=True)
    project = db.relationship("MemoryEntity", backref=db.backref("checkpoints", cascade="all, delete-orphan"))
    summary = db.Column(db.Text, nullable=True)
    open_files_json = db.Column(db.Text, nullable=True)
    active_tasks_json = db.Column(db.Text, nullable=True)
    next_actions_json = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    source = db.Column(db.String(120), nullable=False, default="manual")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class GoalPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("memory_entity.id"), nullable=False, index=True)
    goal = db.relationship("MemoryEntity", backref=db.backref("plans", cascade="all, delete-orphan"))
    title = db.Column(db.String(180), nullable=False)
    cadence = db.Column(db.String(20), nullable=False, default="weekly")
    status = db.Column(db.String(30), nullable=False, default="active", index=True)
    duration_units = db.Column(db.Integer, nullable=False, default=4)
    strategy = db.Column(db.Text, nullable=True)
    generated_by = db.Column(db.String(80), nullable=False, default="rule_based")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlanTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("goal_plan.id"), nullable=False, index=True)
    plan = db.relationship("GoalPlan", backref=db.backref("tasks", cascade="all, delete-orphan"))
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    period_number = db.Column(db.Integer, nullable=False, default=1)
    position = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(30), nullable=False, default="not_started", index=True)
    estimated_minutes = db.Column(db.Integer, nullable=False, default=60)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    resources_json = db.Column(db.Text, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    suggested_next = db.Column(db.String(180), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlanTaskSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("plan_task.id"), nullable=False, index=True)
    task = db.relationship("PlanTask", backref=db.backref("sessions", cascade="all, delete-orphan"))
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    resources_json = db.Column(db.Text, nullable=True)
    summary = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
