import unittest
from unittest.mock import patch

from desktop_app import TrayController


class FakeWindow:
    def __init__(self):
        self.hidden = False
        self.destroyed = False
        self.loaded_url = None

    def show(self):
        self.hidden = False

    def restore(self):
        pass

    def load_url(self, url):
        self.loaded_url = url

    def hide(self):
        self.hidden = True

    def destroy(self):
        self.destroyed = True


class ImmediateTimer:
    def __init__(self, _delay, callback):
        self.callback = callback

    def start(self):
        self.callback()


class FakeIcon:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class DesktopTrayTestCase(unittest.TestCase):
    def test_window_close_hides_to_tray_and_cancels_close(self):
        controller = TrayController("AiOS Assistant")
        window = FakeWindow()
        controller.window = window
        controller.ready = True

        with patch("desktop_app.threading.Timer", ImmediateTimer):
            should_close = controller.on_window_closing()

        self.assertFalse(should_close)
        self.assertTrue(window.hidden)
        self.assertFalse(window.destroyed)

    def test_explicit_exit_allows_close(self):
        controller = TrayController("AiOS Assistant")
        controller.exiting = True

        self.assertTrue(controller.on_window_closing())

    def test_explicit_exit_stops_tray_and_destroys_window(self):
        controller = TrayController("AiOS Assistant")
        controller.window = FakeWindow()
        controller.icon = FakeIcon()
        controller.ready = True

        controller.exit()

        self.assertTrue(controller.exiting)
        self.assertFalse(controller.ready)
        self.assertTrue(controller.icon.stopped)
        self.assertTrue(controller.window.destroyed)

    def test_tray_settings_action_opens_settings_page(self):
        controller = TrayController("AiOS Assistant")
        window = FakeWindow()
        controller.window = window

        controller.show("/settings")

        self.assertEqual(window.loaded_url, "http://127.0.0.1:5050/settings")
        self.assertFalse(window.hidden)

    def test_close_exits_when_tray_could_not_start(self):
        controller = TrayController("AiOS Assistant")
        controller.window = FakeWindow()

        self.assertTrue(controller.on_window_closing())


if __name__ == "__main__":
    unittest.main()
