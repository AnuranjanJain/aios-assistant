import os
import ipaddress

from app import create_app


app = create_app()


if __name__ == "__main__":
    host = app.config["HOST"]
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host in {"localhost"}
    if not is_loopback and not os.getenv("AIOS_ALLOW_LAN", "").lower() in {"1", "true", "yes"}:
        raise RuntimeError("AiOS refuses non-loopback binding unless AIOS_ALLOW_LAN=1 is explicit.")
    if not is_loopback and not os.getenv("AIOS_AGENT_API_TOKEN", "").strip() and not app.config.get("LOCAL_API_TOKEN", "").strip():
        raise RuntimeError("A local API token is required before binding AiOS beyond loopback.")
    debug_enabled = os.getenv("FLASK_DEBUG", "").strip().lower() in {"1", "true", "yes"}
    app.run(
        host=app.config["HOST"],
        port=app.config["PORT"],
        debug=debug_enabled,
        use_reloader=debug_enabled,
    )
