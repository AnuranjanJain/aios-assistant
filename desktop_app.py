import atexit
import json
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timezone

from werkzeug.serving import make_server

from runtime_paths import configure_desktop_environment


HOST = "127.0.0.1"
DEFAULT_PORT = 5050
INSTANCE_MUTEX_NAME = "Local\\AiOSAssistantDesktop"
_INSTANCE_MUTEX_HANDLE = None
ALLOWED_START_PATHS = {
    "/",
    "/automation",
    "/browser-agent",
    "/career",
    "/connectors",
    "/gmail",
    "/hackathons",
    "/jobs",
    "/memory",
    "/planner",
    "/planning-events",
    "/profile",
    "/projects",
    "/settings",
    "/sources",
    "/wellbeing",
    "/workers",
}


def request_existing_instance(paths, start_path="/"):
    runtime_path = paths.data_dir / "runtime.json"
    if not runtime_path.exists():
        return False
    try:
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    base_url = runtime.get("base_url")
    if not base_url:
        return False

    target = f"{base_url}/api/desktop/show"
    data = json.dumps({"path": start_path}).encode("utf-8")
    request = urllib.request.Request(
        target,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=1.5):
            return True
    except (OSError, urllib.error.URLError):
        try:
            webbrowser.open(f"{base_url}{start_path}")
            return True
        except Exception:
            return False


def acquire_single_instance(paths, start_path="/"):
    if os.name != "nt":
        return True

    import ctypes
    from ctypes import wintypes

    global _INSTANCE_MUTEX_HANDLE
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    mutex = kernel32.CreateMutexW(None, False, INSTANCE_MUTEX_NAME)
    if not mutex:
        return True
    if ctypes.get_last_error() == 183:
        request_existing_instance(paths, start_path)
        kernel32.CloseHandle(mutex)
        return False

    _INSTANCE_MUTEX_HANDLE = mutex

    def release_mutex():
        global _INSTANCE_MUTEX_HANDLE
        if _INSTANCE_MUTEX_HANDLE:
            kernel32.CloseHandle(_INSTANCE_MUTEX_HANDLE)
            _INSTANCE_MUTEX_HANDLE = None

    atexit.register(release_mutex)
    return True


class TrayController:
    def __init__(self, title):
        self.title = title
        self.window = None
        self.icon = None
        self.exiting = False
        self.ready = False
        self.close_notice_sent = False

    def attach_window(self, window):
        self.window = window
        try:
            window.events.closing += self.on_window_closing
        except Exception:
            pass

    def start(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception:
            return False

        image = Image.new("RGBA", (64, 64), (76, 29, 149, 255))
        draw = ImageDraw.Draw(image)
        draw.ellipse((10, 10, 54, 54), fill=(255, 216, 77, 255))
        draw.ellipse((22, 22, 42, 42), fill=(76, 29, 149, 255))
        menu = pystray.Menu(
            pystray.MenuItem("Open AiOS", lambda _icon, _item: self.show(), default=True),
            pystray.MenuItem("Settings", lambda _icon, _item: self.show("/settings")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit AiOS completely", lambda _icon, _item: self.exit()),
        )
        self.icon = pystray.Icon("aios-assistant", image, self.title, menu)
        self.ready = True

        def run_icon():
            try:
                self.icon.run()
            finally:
                self.ready = False

        threading.Thread(target=run_icon, name="aios-tray", daemon=True).start()
        return True

    def show(self, path=None):
        if not self.window:
            return
        try:
            if path:
                self.window.load_url(f"http://{HOST}:{DEFAULT_PORT}{path}")
            self.window.show()
            self.window.restore()
        except Exception:
            pass

    def hide(self):
        if not self.window:
            return
        try:
            self.window.hide()
        except Exception:
            pass

    def exit(self):
        self.exiting = True
        self.ready = False
        try:
            if self.icon:
                self.icon.stop()
        except Exception:
            pass
        try:
            if self.window:
                self.window.destroy()
        except Exception:
            os._exit(0)

    def on_window_closing(self, *args, **kwargs):
        if self.exiting:
            return True
        if not self.ready:
            return True
        threading.Timer(0.05, self.hide).start()
        if self.icon and not self.close_notice_sent:
            self.close_notice_sent = True
            try:
                self.icon.notify(
                    "AiOS is still running. Right-click its tray icon to open Settings or exit completely.",
                    "AiOS minimized to tray",
                )
            except Exception:
                pass
        return False


def run_worker_mode(worker_id):
    configure_desktop_environment()
    worker_entrypoints = {
        "reminders": ("local_worker", "main"),
        "activity": ("desktop_activity_worker", "main"),
        "watch_imports": ("watch_import_worker", "main"),
        "hackathons": ("hackathon_monitor_worker", "main"),
        "email_intelligence": ("email_intelligence_worker", "main"),
    }
    target = worker_entrypoints.get(worker_id)
    if target is None:
        raise ValueError(f"Unknown desktop worker: {worker_id}")

    module = __import__(target[0])
    getattr(module, target[1])()


def run_migration_mode(source_root):
    from desktop_migration import migrate_legacy_data

    result = migrate_legacy_data(source_root)
    report_path = configure_desktop_environment().logs_dir / "migration-report.txt"
    report_path.write_text(
        "\n".join(f"{key}={value}" for key, value in result.items()),
        encoding="utf-8",
    )


def reserve_desktop_port(port=DEFAULT_PORT):
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((HOST, port))
    except OSError:
        probe.close()
        return None
    return probe


class ServerThread(threading.Thread):
    def __init__(self, app, port):
        super().__init__(daemon=True)
        self.server = make_server(HOST, port, app, threaded=True)

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


class PollingWorker(threading.Thread):
    def __init__(self, service_id, callback, state, save_callback, interval):
        super().__init__(daemon=True)
        self.service_id = service_id
        self.callback = callback
        self.state = state
        self.save_callback = save_callback
        self.interval = interval
        self.stop_event = threading.Event()

    def run(self):
        while not self.stop_event.is_set():
            try:
                self.callback(self.state)
                self.save_callback(self.state)
                from app.services.background_services import record_service_run

                record_service_run(self.service_id)
            except Exception as exc:
                from app.services.background_services import record_service_run

                record_service_run(self.service_id, exc)
            self.stop_event.wait(self.interval)

    def shutdown(self):
        self.stop_event.set()


class RuntimeDescriptor(threading.Thread):
    def __init__(self, path, payload):
        super().__init__(daemon=True)
        self.path = path
        self.payload = payload
        self.stop_event = threading.Event()

    def write(self):
        self.path.write_text(json.dumps(self.payload, indent=2), encoding="utf-8")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def run(self):
        while not self.stop_event.is_set():
            self.write()
            self.stop_event.wait(5)

    def shutdown(self):
        self.stop_event.set()


def wait_for_server(port, timeout=10):
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            with socket.create_connection((HOST, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    paths = configure_desktop_environment()
    start_path = os.getenv("AIOS_START_PATH", "/").strip()
    if start_path not in ALLOWED_START_PATHS:
        start_path = "/"
    if not acquire_single_instance(paths, start_path):
        return
    reserved_port = reserve_desktop_port()
    if reserved_port is None:
        request_existing_instance(paths, start_path)
        return

    from app import create_app
    from app.models import db
    from app.services.background_services import register_service, unregister_service
    from app.services.settings import get_setting, set_setting
    from desktop_activity_worker import CHECK_SECONDS as ACTIVITY_INTERVAL_SECONDS, scan_once as scan_activity_once
    from email_intelligence_worker import sync_interval_seconds, scan_once as scan_email_once
    from hackathon_monitor_worker import scan_once as scan_opportunities
    from local_worker import CHECK_INTERVAL_SECONDS, check_reminders, load_state, save_state
    from watch_import_worker import (
        CHECK_INTERVAL_SECONDS as WATCH_INTERVAL_SECONDS,
        load_state as load_watch_state,
        save_state as save_watch_state,
        scan_once as scan_watch_once,
    )

    app = create_app()
    with app.app_context():
        api_token = get_setting("LOCAL_API_TOKEN", app.config.get("LOCAL_API_TOKEN", "")).strip()
        scan_interval_minutes = max(
            5,
            int(get_setting("HACKATHON_SCAN_INTERVAL_MINUTES", app.config.get("HACKATHON_SCAN_INTERVAL_MINUTES", 15))),
        )
        if not api_token:
            api_token = secrets.token_urlsafe(32)
            set_setting("LOCAL_API_TOKEN", api_token)
            db.session.commit()
    port = DEFAULT_PORT
    start_hidden = os.getenv("AIOS_START_HIDDEN", "") == "1" or "--hidden" in sys.argv or "--tray" in sys.argv
    base_url = f"http://{HOST}:{port}"
    url = f"{base_url}{start_path}"
    reserved_port.close()
    server = ServerThread(app, port)
    reminder_worker = PollingWorker(
        service_id="reminders",
        callback=lambda state: check_reminders(app, state),
        state=load_state(),
        save_callback=save_state,
        interval=CHECK_INTERVAL_SECONDS,
    )
    watch_worker = PollingWorker(
        service_id="watch_imports",
        callback=lambda state: scan_watch_once(app, state),
        state=load_watch_state(),
        save_callback=save_watch_state,
        interval=WATCH_INTERVAL_SECONDS,
    )
    opportunity_worker = PollingWorker(
        service_id="opportunities",
        callback=lambda _state: scan_opportunities(app, interactive=False),
        state={},
        save_callback=lambda _state: None,
        interval=scan_interval_minutes * 60,
    )
    activity_worker = PollingWorker(
        service_id="activity",
        callback=lambda state: scan_activity_once(app, state),
        state={},
        save_callback=lambda _state: None,
        interval=ACTIVITY_INTERVAL_SECONDS,
    )
    email_worker = PollingWorker(
        service_id="email_intelligence",
        callback=lambda state: scan_email_once(app, state),
        state={},
        save_callback=lambda _state: None,
        interval=sync_interval_seconds(app),
    )

    components = (email_worker, activity_worker, opportunity_worker, watch_worker, reminder_worker, server)
    runtime_path = paths.data_dir / "runtime.json"
    runtime_descriptor = RuntimeDescriptor(
        runtime_path,
        {
            "service": "aios-assistant",
            "base_url": base_url,
            "api_token": api_token,
            "pid": os.getpid(),
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    runtime_descriptor.write()
    components = (runtime_descriptor,) + components

    register_service("reminders", "Reminder service", "Checks due reminders in the background.", reminder_worker)
    register_service("watch_imports", "Import watcher", "Imports files added to watch folders.", watch_worker)
    register_service(
        "opportunities",
        "Opportunity monitor",
        "Refreshes Gmail, hackathon, NeoPat, and placement updates.",
        opportunity_worker,
    )
    register_service(
        "activity",
        "Desktop activity tracker",
        "Logs active desktop windows into wellbeing signals.",
        activity_worker,
    )
    register_service(
        "email_intelligence",
        "Email intelligence planner",
        "Syncs connected Gmail accounts and generates local AI plans.",
        email_worker,
    )

    def shutdown():
        for component in components:
            try:
                component.shutdown()
            except Exception:
                pass
        for service_id in ("reminders", "watch_imports", "opportunities", "activity", "email_intelligence"):
            unregister_service(service_id)

    atexit.register(shutdown)
    server.start()
    runtime_descriptor.start()
    reminder_worker.start()
    watch_worker.start()
    opportunity_worker.start()
    activity_worker.start()
    email_worker.start()

    if not wait_for_server(port):
        shutdown()
        raise RuntimeError("AiOS Assistant server did not start.")

    print(f"AiOS data: {paths.data_dir}")
    print(f"AiOS local URL: {url}")

    if os.getenv("AIOS_HEADLESS", "") == "1":
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            shutdown()
        return

    try:
        import webview

        tray = TrayController("AiOS Assistant")
        window = webview.create_window(
            "AiOS Assistant",
            url,
            width=1320,
            height=860,
            min_size=(1024, 700),
            text_select=True,
            confirm_close=False,
        )
        tray.attach_window(window)

        def request_exit():
            threading.Timer(0.1, tray.exit).start()

        def request_show(path="/"):
            if path not in ALLOWED_START_PATHS:
                path = "/"

            def show_window():
                try:
                    window.load_url(f"{base_url}{path}")
                except Exception:
                    pass
                tray.show()

            threading.Timer(0.1, show_window).start()

        app.config["AIOS_EXIT_CALLBACK"] = request_exit
        app.config["AIOS_SHOW_CALLBACK"] = request_show

        def on_started():
            tray.start()
            if start_hidden:
                tray.hide()

        webview.start(on_started, debug=False, private_mode=False)
        shutdown()
        return window
    except ImportError:
        webbrowser.open(url)
        print("pywebview is unavailable. AiOS opened in the system browser.")
    except Exception as exc:
        webbrowser.open(url)
        print(f"Native window unavailable ({exc}). AiOS opened in the system browser.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--worker":
            run_worker_mode(sys.argv[2])
        elif len(sys.argv) == 3 and sys.argv[1] == "--migrate":
            run_migration_mode(sys.argv[2])
        else:
            main()
    except Exception as exc:
        print(f"AiOS desktop failed to start: {exc}", file=sys.stderr)
        raise
