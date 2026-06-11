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


class Setting(db.Model):
    key = db.Column(db.String(120), primary_key=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
