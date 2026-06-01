import socket
import threading
import time
import webbrowser

from werkzeug.serving import make_server

from app import create_app
from local_worker import CHECK_INTERVAL_SECONDS, check_reminders, load_state, save_state


HOST = "127.0.0.1"
PORT = 5050
URL = f"http://{HOST}:{PORT}"


class ServerThread(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.app = create_app()
        self.server = make_server(HOST, PORT, self.app)
        self.app.app_context().push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()


class ReminderWorkerThread(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.state = load_state()
        self.is_running = True

    def run(self):
        while self.is_running:
            check_reminders(self.app, self.state)
            save_state(self.state)
            time.sleep(CHECK_INTERVAL_SECONDS)

    def shutdown(self):
        self.is_running = False


def wait_for_server(timeout=8):
    started = time.time()
    while time.time() - started < timeout:
        try:
            with socket.create_connection((HOST, PORT), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def main():
    server = ServerThread()
    server.start()
    worker = ReminderWorkerThread(server.app)
    worker.start()

    if not wait_for_server():
        raise RuntimeError("AiOS Assistant server did not start.")

    try:
        import webview

        window = webview.create_window(
            "AiOS Assistant",
            URL,
            width=1240,
            height=840,
            min_size=(980, 680),
            text_select=True,
        )
        webview.start()
        worker.shutdown()
        server.shutdown()
        return window
    except Exception:
        webbrowser.open(URL)
        print(f"AiOS Assistant is running at {URL}")
        print("Install pywebview for the native desktop window.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            worker.shutdown()
            server.shutdown()


if __name__ == "__main__":
    main()
