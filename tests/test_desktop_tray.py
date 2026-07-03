import unittest
from unittest.mock import patch

from desktop_app import TrayController


class FakeWindow:
    def __init__(self):
        self.hidden = False
        self.destroyed = False

    def hide(self):
        self.hidden = True

    def destroy(self):
        self.destroyed = True


class ImmediateTimer:
    def __init__(self, _delay, callback):
        self.callback = callback

    def start(self):
        self.callback()


class DesktopTrayTestCase(unittest.TestCase):
    def test_window_close_hides_to_tray_and_cancels_close(self):
        controller = TrayController("AiOS Assistant")
        window = FakeWindow()
        controller.window = window

        with patch("desktop_app.threading.Timer", ImmediateTimer):
            should_close = controller.on_window_closing()

        self.assertFalse(should_close)
        self.assertTrue(window.hidden)
        self.assertFalse(window.destroyed)

    def test_explicit_exit_allows_close(self):
        controller = TrayController("AiOS Assistant")
        controller.exiting = True

        self.assertTrue(controller.on_window_closing())


if __name__ == "__main__":
    unittest.main()
