from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class Opportunity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(240), nullable=True, unique=True, index=True)
    email_message_id = db.Column(db.Integer, db.ForeignKey("email_message.id"), nullable=True, index=True)
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
    notification_type = db.Column(db.String(60), nullable=False, default="reminder", index=True)
    priority = db.Column(db.String(40), nullable=False, default="normal", index=True)
    source_key = db.Column(db.String(240), nullable=True, unique=True, index=True)
    is_done = db.Column(db.Boolean, default=False, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    notified_at = db.Column(db.DateTime, nullable=True)
    snoozed_until = db.Column(db.DateTime, nullable=True, index=True)
    metadata_json = db.Column(db.Text, nullable=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunity.id"), nullable=True)
    opportunity = db.relationship("Opportunity", backref="reminders")


class InboxItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(240), nullable=True, unique=True, index=True)
    email_message_id = db.Column(db.Integer, db.ForeignKey("email_message.id"), nullable=True, index=True)
    sender = db.Column(db.String(180), nullable=True)
    subject = db.Column(db.String(240), nullable=False)
    body = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=False, default="general")
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    summary = db.Column(db.Text, nullable=True)
    next_action = db.Column(db.Text, nullable=True)
    occurred_at = db.Column(db.DateTime, nullable=True, index=True)
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


class ConnectedAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(40), nullable=False, default="google", index=True)
    email = db.Column(db.String(240), nullable=False, index=True)
    display_name = db.Column(db.String(160), nullable=True)
    label = db.Column(db.String(120), nullable=True)
    sync_enabled = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_sync_at = db.Column(db.DateTime, nullable=True)
    sync_cursor = db.Column(db.String(240), nullable=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    __table_args__ = (
        db.UniqueConstraint("provider", "email", name="uq_connected_account_provider_email"),
    )


class OAuthToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("connected_account.id"), nullable=False, unique=True)
    account = db.relationship("ConnectedAccount", backref=db.backref("oauth_token", uselist=False, cascade="all, delete-orphan"))
    token_json_encrypted = db.Column(db.Text, nullable=False)
    scopes_json = db.Column(db.Text, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class EmailThread(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("connected_account.id"), nullable=False, index=True)
    account = db.relationship("ConnectedAccount", backref=db.backref("email_threads", cascade="all, delete-orphan"))
    provider_thread_id = db.Column(db.String(240), nullable=False)
    subject = db.Column(db.String(300), nullable=True)
    last_message_at = db.Column(db.DateTime, nullable=True, index=True)
    labels_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    __table_args__ = (
        db.UniqueConstraint("account_id", "provider_thread_id", name="uq_email_thread_account_provider"),
    )


class EmailMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey("connected_account.id"), nullable=False, index=True)
    account = db.relationship("ConnectedAccount", backref=db.backref("emails", cascade="all, delete-orphan"))
    thread_id = db.Column(db.Integer, db.ForeignKey("email_thread.id"), nullable=True, index=True)
    thread = db.relationship("EmailThread", backref=db.backref("messages", cascade="all, delete-orphan"))
    provider_message_id = db.Column(db.String(240), nullable=False)
    provider_thread_id = db.Column(db.String(240), nullable=True, index=True)
    history_id = db.Column(db.String(120), nullable=True)
    sender = db.Column(db.String(240), nullable=True)
    recipients_json = db.Column(db.Text, nullable=True)
    subject = db.Column(db.String(300), nullable=False, default="")
    snippet = db.Column(db.Text, nullable=True)
    body_text = db.Column(db.Text, nullable=True)
    labels_json = db.Column(db.Text, nullable=True)
    is_unread = db.Column(db.Boolean, default=False, nullable=False, index=True)
    sent_at = db.Column(db.DateTime, nullable=True, index=True)
    analyzed_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    __table_args__ = (
        db.UniqueConstraint("account_id", "provider_message_id", name="uq_email_account_provider_message"),
    )


class EmailAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey("email_message.id"), nullable=False, index=True)
    email = db.relationship("EmailMessage", backref=db.backref("attachments", cascade="all, delete-orphan"))
    filename = db.Column(db.String(260), nullable=True)
    mime_type = db.Column(db.String(160), nullable=True)
    size_bytes = db.Column(db.Integer, nullable=False, default=0)
    provider_attachment_id = db.Column(db.String(240), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class EmailInsight(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey("email_message.id"), nullable=False, unique=True)
    email = db.relationship("EmailMessage", backref=db.backref("insight", uselist=False, cascade="all, delete-orphan"))
    life_item_id = db.Column(db.Integer, db.ForeignKey("life_item.id"), nullable=True, index=True)
    life_item = db.relationship("LifeItem", backref=db.backref("email_insights", cascade="all, delete-orphan"))
    priority = db.Column(db.String(40), nullable=False, default="normal", index=True)
    urgency = db.Column(db.String(40), nullable=False, default="normal", index=True)
    category = db.Column(db.String(80), nullable=False, default="general", index=True)
    summary = db.Column(db.Text, nullable=True)
    action_items_json = db.Column(db.Text, nullable=True)
    deadlines_json = db.Column(db.Text, nullable=True)
    meetings_json = db.Column(db.Text, nullable=True)
    follow_ups_json = db.Column(db.Text, nullable=True)
    waiting_on_json = db.Column(db.Text, nullable=True)
    projects_json = db.Column(db.Text, nullable=True)
    people_json = db.Column(db.Text, nullable=True)
    companies_json = db.Column(db.Text, nullable=True)
    required_documents_json = db.Column(db.Text, nullable=True)
    repositories_json = db.Column(db.Text, nullable=True)
    suggested_actions_json = db.Column(db.Text, nullable=True)
    embedding_json = db.Column(db.Text, nullable=True)
    model = db.Column(db.String(120), nullable=True)
    confidence = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class LifeItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(240), nullable=False, unique=True, index=True)
    title = db.Column(db.String(240), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=False, default="personal", index=True)
    priority = db.Column(db.String(40), nullable=False, default="normal", index=True)
    status = db.Column(db.String(40), nullable=False, default="open", index=True)
    deadline = db.Column(db.DateTime, nullable=True, index=True)
    estimated_hours = db.Column(db.Float, nullable=True)
    progress = db.Column(db.Float, nullable=False, default=0.0)
    energy_level = db.Column(db.String(40), nullable=True)
    difficulty = db.Column(db.String(40), nullable=True)
    repository = db.Column(db.String(500), nullable=True)
    working_directory = db.Column(db.String(1000), nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    next_action = db.Column(db.Text, nullable=True)
    tags_json = db.Column(db.Text, nullable=True)
    analytics_json = db.Column(db.Text, nullable=True)
    history_json = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class LifeItemRelation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    source_item_id = db.Column(db.Integer, db.ForeignKey("life_item.id"), nullable=False, index=True)
    target_item_id = db.Column(db.Integer, db.ForeignKey("life_item.id"), nullable=False, index=True)
    source_item = db.relationship("LifeItem", foreign_keys=[source_item_id], backref=db.backref("outgoing_relations", cascade="all, delete-orphan"))
    target_item = db.relationship("LifeItem", foreign_keys=[target_item_id], backref=db.backref("incoming_relations", cascade="all, delete-orphan"))
    relation_type = db.Column(db.String(80), nullable=False, default="related", index=True)
    strength = db.Column(db.Float, nullable=False, default=0.5)
    reason = db.Column(db.Text, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        db.UniqueConstraint("source_item_id", "target_item_id", "relation_type", name="uq_life_item_relation_pair_type"),
    )


class GitHubRepository(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repo_full_name = db.Column(db.String(240), nullable=False, unique=True, index=True)
    html_url = db.Column(db.String(500), nullable=False)
    life_item_id = db.Column(db.Integer, db.ForeignKey("life_item.id"), nullable=True, index=True)
    life_item = db.relationship("LifeItem", backref=db.backref("github_repositories", cascade="all, delete-orphan"))
    description = db.Column(db.Text, nullable=True)
    default_branch = db.Column(db.String(120), nullable=True)
    primary_language = db.Column(db.String(120), nullable=True)
    is_private = db.Column(db.Boolean, nullable=False, default=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    pushed_at = db.Column(db.DateTime, nullable=True, index=True)
    last_synced_at = db.Column(db.DateTime, nullable=True, index=True)
    inactive = db.Column(db.Boolean, nullable=False, default=False, index=True)
    completion_percentage = db.Column(db.Integer, nullable=False, default=0)
    current_sprint = db.Column(db.Text, nullable=True)
    remaining_work = db.Column(db.Text, nullable=True)
    recent_progress = db.Column(db.Text, nullable=True)
    suggested_next_task = db.Column(db.Text, nullable=True)
    commits_json = db.Column(db.Text, nullable=True)
    pull_requests_json = db.Column(db.Text, nullable=True)
    issues_json = db.Column(db.Text, nullable=True)
    branches_json = db.Column(db.Text, nullable=True)
    releases_json = db.Column(db.Text, nullable=True)
    discussions_json = db.Column(db.Text, nullable=True)
    workflows_json = db.Column(db.Text, nullable=True)
    contributors_json = db.Column(db.Text, nullable=True)
    raw_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class GitHubDailySummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summary_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    summary = db.Column(db.Text, nullable=False)
    repo_count = db.Column(db.Integer, nullable=False, default=0)
    inactive_count = db.Column(db.Integer, nullable=False, default=0)
    suggested_tasks_json = db.Column(db.Text, nullable=True)
    repositories_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class LearningItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    life_item_id = db.Column(db.Integer, db.ForeignKey("life_item.id"), nullable=True, index=True)
    life_item = db.relationship("LifeItem", backref=db.backref("learning_items", cascade="all, delete-orphan"))
    item_type = db.Column(db.String(40), nullable=False, default="course", index=True)
    title = db.Column(db.String(240), nullable=False)
    source_url = db.Column(db.String(500), nullable=True)
    project = db.Column(db.String(180), nullable=True, index=True)
    status = db.Column(db.String(40), nullable=False, default="not_started", index=True)
    completion = db.Column(db.Float, nullable=False, default=0.0)
    notes = db.Column(db.Text, nullable=True)
    revision_json = db.Column(db.Text, nullable=True)
    quiz_json = db.Column(db.Text, nullable=True)
    weak_topics_json = db.Column(db.Text, nullable=True)
    projects_json = db.Column(db.Text, nullable=True)
    scheduled_at = db.Column(db.DateTime, nullable=True, index=True)
    deadline = db.Column(db.DateTime, nullable=True, index=True)
    estimated_minutes = db.Column(db.Integer, nullable=False, default=45)
    last_reviewed_at = db.Column(db.DateTime, nullable=True)
    next_revision_at = db.Column(db.DateTime, nullable=True, index=True)
    evening_prompt_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class EmailTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_id = db.Column(db.Integer, db.ForeignKey("email_message.id"), nullable=True, index=True)
    email = db.relationship("EmailMessage", backref=db.backref("tasks", cascade="all, delete-orphan"))
    title = db.Column(db.String(220), nullable=False)
    owner = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(40), nullable=False, default="open", index=True)
    priority = db.Column(db.String(40), nullable=False, default="normal")
    due_at = db.Column(db.DateTime, nullable=True, index=True)
    source = db.Column(db.String(80), nullable=False, default="email")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False, unique=True, index=True)
    status = db.Column(db.String(60), nullable=False, default="active", index=True)
    risk_level = db.Column(db.String(40), nullable=False, default="normal")
    summary = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class DailyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    summary = db.Column(db.Text, nullable=True)
    items_json = db.Column(db.Text, nullable=False)
    generated_by = db.Column(db.String(80), nullable=False, default="email_intelligence")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class DailyAssistantEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_date = db.Column(db.Date, nullable=False, index=True)
    kind = db.Column(db.String(40), nullable=False, index=True)
    summary = db.Column(db.Text, nullable=True)
    schedule_json = db.Column(db.Text, nullable=True)
    explanations_json = db.Column(db.Text, nullable=True)
    risks_json = db.Column(db.Text, nullable=True)
    questions_json = db.Column(db.Text, nullable=True)
    responses_json = db.Column(db.Text, nullable=True)
    replans_json = db.Column(db.Text, nullable=True)
    estimated_hours = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)


class WeeklyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, nullable=False, unique=True, index=True)
    summary = db.Column(db.Text, nullable=True)
    items_json = db.Column(db.Text, nullable=False)
    generated_by = db.Column(db.String(80), nullable=False, default="email_intelligence")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class AISuggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(220), nullable=False)
    details = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(40), nullable=False, default="open", index=True)
    source = db.Column(db.String(80), nullable=False, default="email_intelligence")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class PlanningEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(60), nullable=False, default="task", index=True)
    source = db.Column(db.String(80), nullable=False, default="manual", index=True)
    source_key = db.Column(db.String(240), nullable=False, unique=True, index=True)
    title = db.Column(db.String(240), nullable=False)
    project = db.Column(db.String(180), nullable=True, index=True)
    idea = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True, index=True)
    planned_start = db.Column(db.DateTime, nullable=True, index=True)
    planned_minutes = db.Column(db.Integer, nullable=False, default=45)
    priority = db.Column(db.String(40), nullable=False, default="normal", index=True)
    status = db.Column(db.String(40), nullable=False, default="planned", index=True)
    work_done = db.Column(db.Text, nullable=True)
    work_left = db.Column(db.Text, nullable=True)
    repo_url = db.Column(db.String(500), nullable=True)
    repo_latest_activity = db.Column(db.Text, nullable=True)
    next_question = db.Column(db.String(260), nullable=True)
    last_prompted_at = db.Column(db.DateTime, nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


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
