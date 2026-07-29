#include <flutter/dart_project.h>
#include <flutter/flutter_view_controller.h>
#include <windows.h>

#include "flutter_window.h"
#include "utils.h"

namespace {

constexpr wchar_t kSingleInstanceMutex[] =
    L"Local\\AiOSAssistantNativeFlutter";

bool ActivateExistingWindow() {
  HWND existing = FindWindowW(nullptr, L"AiOS Assistant");
  if (existing == nullptr) {
    return false;
  }
  ShowWindow(existing, SW_RESTORE);
  SetForegroundWindow(existing);
  return true;
}

Win32Window::Point GetCenteredWindowOrigin(const Win32Window::Size& size) {
  HMONITOR monitor = MonitorFromPoint({0, 0}, MONITOR_DEFAULTTOPRIMARY);
  MONITORINFO monitor_info{};
  monitor_info.cbSize = sizeof(MONITORINFO);
  if (!GetMonitorInfo(monitor, &monitor_info)) {
    return Win32Window::Point(10, 10);
  }

  const UINT dpi = FlutterDesktopGetDpiForMonitor(monitor);
  const double scale_factor = dpi / 96.0;
  const int scaled_width = static_cast<int>(size.width * scale_factor);
  const int scaled_height = static_cast<int>(size.height * scale_factor);
  const RECT work_area = monitor_info.rcWork;
  const int physical_x =
      work_area.left + ((work_area.right - work_area.left) - scaled_width) / 2;
  const int physical_y =
      work_area.top + ((work_area.bottom - work_area.top) - scaled_height) / 2;
  return Win32Window::Point(
      static_cast<int>(physical_x / scale_factor),
      static_cast<int>(physical_y / scale_factor));
}

}  // namespace

int APIENTRY wWinMain(_In_ HINSTANCE instance, _In_opt_ HINSTANCE prev,
                      _In_ wchar_t *command_line, _In_ int show_command) {
  HANDLE instance_mutex = CreateMutexW(nullptr, TRUE, kSingleInstanceMutex);
  if (instance_mutex != nullptr && GetLastError() == ERROR_ALREADY_EXISTS) {
    ActivateExistingWindow();
    CloseHandle(instance_mutex);
    return EXIT_SUCCESS;
  }

  // Attach to console when present (e.g., 'flutter run') or create a
  // new console when running with a debugger.
  if (!::AttachConsole(ATTACH_PARENT_PROCESS) && ::IsDebuggerPresent()) {
    CreateAndAttachConsole();
  }

  // Initialize COM, so that it is available for use in the library and/or
  // plugins.
  ::CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);

  flutter::DartProject project(L"data");

  std::vector<std::string> command_line_arguments =
      GetCommandLineArguments();
  bool start_hidden = false;
  for (const auto& argument : command_line_arguments) {
    if (argument == "--hidden" || argument == "--tray") {
      start_hidden = true;
      break;
    }
  }

  project.set_dart_entrypoint_arguments(std::move(command_line_arguments));

  FlutterWindow window(project, start_hidden);
  Win32Window::Size size(1280, 760);
  Win32Window::Point origin = GetCenteredWindowOrigin(size);
  if (!window.Create(L"AiOS Assistant", origin, size)) {
    if (instance_mutex != nullptr) {
      ReleaseMutex(instance_mutex);
      CloseHandle(instance_mutex);
    }
    return EXIT_FAILURE;
  }
  window.SetQuitOnClose(true);

  ::MSG msg;
  while (::GetMessage(&msg, nullptr, 0, 0)) {
    ::TranslateMessage(&msg);
    ::DispatchMessage(&msg);
  }

  ::CoUninitialize();
  if (instance_mutex != nullptr) {
    ReleaseMutex(instance_mutex);
    CloseHandle(instance_mutex);
  }
  return EXIT_SUCCESS;
}
