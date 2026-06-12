import os

from app import create_app


app = create_app()


if __name__ == "__main__":
    debug_enabled = os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=debug_enabled,
        use_reloader=debug_enabled,
    )
