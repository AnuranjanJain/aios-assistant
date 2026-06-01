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

    columns = {column["name"] for column in inspector.get_columns("reminder")}
    migrations = []

    if "is_read" not in columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN is_read BOOLEAN NOT NULL DEFAULT 0")
    if "notified_at" not in columns:
        migrations.append("ALTER TABLE reminder ADD COLUMN notified_at DATETIME")

    for statement in migrations:
        db.session.execute(text(statement))

    if migrations:
        db.session.commit()
