from flask import Flask
from sqlalchemy import text

from config import Config
from app.models import db
from app.routes import bp


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        apply_lightweight_migrations()

    return app


def apply_lightweight_migrations():
    inspector = db.inspect(db.engine)
    if "reminder" not in inspector.get_table_names():
        return

    migrations = []
    reminder_columns = {column["name"] for column in inspector.get_columns("reminder")}

    if "is_read" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN is_read BOOLEAN NOT NULL DEFAULT 0")
    if "notified_at" not in reminder_columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN notified_at DATETIME")

    if "setting" in inspector.get_table_names():
        setting_columns = {column["name"] for column in inspector.get_columns("setting")}
        if "updated_at" not in setting_columns:
            migrations.append("ALTER TABLE setting ADD COLUMN updated_at DATETIME")

    for statement in migrations:
        db.session.execute(text(statement))

    if migrations:
        db.session.commit()
