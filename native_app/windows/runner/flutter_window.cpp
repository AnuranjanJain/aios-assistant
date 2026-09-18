#include "flutter_window.h"

#include <optional>
#include <shellapi.h>
#include <shlobj_core.h>
#include <vector>
#include <wincrypt.h>

#include "flutter/generated_plugin_registrant.h"
#include "resource.h"

namespace {
constexpr UINT kTrayIconId = 1;
constexpr UINT kTrayMessage = WM_APP + 1;
constexpr UINT kTrayOpenCommand = 1001;
constexpr UINT kTrayExitCommand = 1002;
constexpr wchar_t kTokenFileName[] = L"native-api-token.dat";

std::wstring NativeTokenPath() {
  PWSTR local_app_data = nullptr;
  if (FAILED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr,
                                  &local_app_data))) {
    return L"";
  }
  std::wstring directory(local_app_data);
  CoTaskMemFree(local_app_data);
  directory += L"\\AiOS Assistant";
  if (!CreateDirectoryW(directory.c_str(), nullptr) &&
      GetLastError() != ERROR_ALREADY_EXISTS) {
    return L"";
  }
  return directory + L"\\" + kTokenFileName;
}

bool WriteProtectedToken(const std::string& token) {
  const std::wstring path = NativeTokenPath();
  if (path.empty() || token.empty()) return false;
  DATA_BLOB input{static_cast<DWORD>(token.size()),
                  reinterpret_cast<BYTE*>(const_cast<char*>(token.data()))};
  DATA_BLOB encrypted{};
  if (!CryptProtectData(&input, L"AiOS native API token", nullptr, nullptr,
                        nullptr, CRYPTPROTECT_UI_FORBIDDEN, &encrypted)) {
    return false;
  }
  HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr,
                            CREATE_ALWAYS, FILE_ATTRIBUTE_HIDDEN, nullptr);
  if (file == INVALID_HANDLE_VALUE) {
    LocalFree(encrypted.pbData);
    return false;
  }
  DWORD written = 0;
  const bool ok = WriteFile(file, encrypted.pbData, encrypted.cbData, &written,
                            nullptr) && written == encrypted.cbData;
  CloseHandle(file);
  LocalFree(encrypted.pbData);
  return ok;
}

std::optional<std::string> ReadProtectedToken() {
  const std::wstring path = NativeTokenPath();
  if (path.empty()) return std::nullopt;
  HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ,
                            nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_HIDDEN,
                            nullptr);
  if (file == INVALID_HANDLE_VALUE) return std::nullopt;
  const DWORD size = GetFileSize(file, nullptr);
  if (size == INVALID_FILE_SIZE || size == 0 || size > 4096) {
    CloseHandle(file);
    return std::nullopt;
  }
  std::vector<BYTE> encrypted_bytes(size);
  DWORD read = 0;
  const bool read_ok = ReadFile(file, encrypted_bytes.data(), size, &read,
                                nullptr) && read == size;
  CloseHandle(file);
  if (!read_ok) return std::nullopt;
  DATA_BLOB encrypted{size, encrypted_bytes.data()};
  DATA_BLOB plain{};
  if (!CryptUnprotectData(&encrypted, nullptr, nullptr, nullptr, nullptr,
                          CRYPTPROTECT_UI_FORBIDDEN, &plain)) {
    return std::nullopt;
  }
  std::string token(reinterpret_cast<char*>(plain.pbData), plain.cbData);
  LocalFree(plain.pbData);
  return token.empty() ? std::nullopt : std::optional<std::string>(token);
}
}  // namespace

FlutterWindow::FlutterWindow(const flutter::DartProject& project,
                             bool start_hidden)
    : project_(project), start_hidden_(start_hidden) {}

FlutterWindow::~FlutterWindow() {}

bool FlutterWindow::OnCreate() {
  if (!Win32Window::OnCreate()) {
    return false;
  }

  RECT frame = GetClientArea();

  // The size here must match the window dimensions to avoid unnecessary surface
  // creation / destruction in the startup path.
  flutter_controller_ = std::make_unique<flutter::FlutterViewController>(
      frame.right - frame.left, frame.bottom - frame.top, project_);
  // Ensure that basic setup of the controller was successful.
  if (!flutter_controller_->engine() || !flutter_controller_->view()) {
    return false;
  }
  RegisterPlugins(flutter_controller_->engine());
  RegisterLifecycleChannel();
  RegisterNativeTokenStoreChannel();
  SetChildContent(flutter_controller_->view()->GetNativeWindow());
  AddTrayIcon();

  flutter_controller_->engine()->SetNextFrameCallback([&]() {
    if (!start_hidden_) {
      this->Show();
    }
  });

  // Flutter can complete the first frame before the "show window" callback is
  // registered. The following call ensures a frame is pending to ensure the
  // window is shown. It is a no-op if the first frame hasn't completed yet.
  flutter_controller_->ForceRedraw();

  return true;
}

void FlutterWindow::OnDestroy() {
  RemoveTrayIcon();
  if (flutter_controller_) {
    flutter_controller_ = nullptr;
  }

  Win32Window::OnDestroy();
}

LRESULT
FlutterWindow::MessageHandler(HWND hwnd, UINT const message,
                              WPARAM const wparam,
                              LPARAM const lparam) noexcept {
  switch (message) {
    case WM_CLOSE:
      if (!exiting_) {
        HideToTray();
        return 0;
      }
      break;
    case WM_SYSCOMMAND:
      if ((wparam & 0xFFF0) == SC_MINIMIZE) {
        HideToTray();
        return 0;
      }
      break;
    case kTrayMessage:
      if (lparam == WM_LBUTTONUP || lparam == WM_LBUTTONDBLCLK) {
        ShowFromTray();
        return 0;
      }
      if (lparam == WM_RBUTTONUP || lparam == WM_CONTEXTMENU) {
        ShowTrayMenu();
        return 0;
      }
      break;
    case WM_COMMAND:
      if (LOWORD(wparam) == kTrayOpenCommand) {
        ShowFromTray();
        return 0;
      }
      if (LOWORD(wparam) == kTrayExitCommand) {
        if (lifecycle_channel_) {
          lifecycle_channel_->InvokeMethod("exitRequested", nullptr);
        }
        return 0;
      }
      break;
  }

  // Give Flutter, including plugins, an opportunity to handle window messages.
  if (flutter_controller_) {
    std::optional<LRESULT> result =
        flutter_controller_->HandleTopLevelWindowProc(hwnd, message, wparam,
                                                      lparam);
    if (result) {
      return *result;
    }
  }

  switch (message) {
    case WM_FONTCHANGE:
      flutter_controller_->engine()->ReloadSystemFonts();
      break;
  }

  return Win32Window::MessageHandler(hwnd, message, wparam, lparam);
}

void FlutterWindow::AddTrayIcon() {
  if (tray_icon_added_) {
    return;
  }

  notify_icon_data_ = {};
  notify_icon_data_.cbSize = sizeof(NOTIFYICONDATA);
  notify_icon_data_.hWnd = GetHandle();
  notify_icon_data_.uID = kTrayIconId;
  notify_icon_data_.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP;
  notify_icon_data_.uCallbackMessage = kTrayMessage;
  notify_icon_data_.hIcon =
      LoadIcon(GetModuleHandle(nullptr), MAKEINTRESOURCE(IDI_APP_ICON));
  wcscpy_s(notify_icon_data_.szTip, L"AiOS Assistant");

  tray_icon_added_ = Shell_NotifyIcon(NIM_ADD, &notify_icon_data_) == TRUE;
}

void FlutterWindow::RemoveTrayIcon() {
  if (!tray_icon_added_) {
    return;
  }
  Shell_NotifyIcon(NIM_DELETE, &notify_icon_data_);
  tray_icon_added_ = false;
}

void FlutterWindow::HideToTray() {
  ::ShowWindow(GetHandle(), SW_HIDE);
}

void FlutterWindow::ShowFromTray() {
  ::ShowWindow(GetHandle(), SW_RESTORE);
  SetForegroundWindow(GetHandle());
}

void FlutterWindow::ShowTrayMenu() {
  POINT cursor{};
  GetCursorPos(&cursor);
  HMENU menu = CreatePopupMenu();
  if (menu == nullptr) {
    return;
  }
  AppendMenuW(menu, MF_STRING, kTrayOpenCommand, L"Open AiOS");
  AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
  AppendMenuW(menu, MF_STRING, kTrayExitCommand, L"Exit AiOS completely");
  SetForegroundWindow(GetHandle());
  TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_BOTTOMALIGN | TPM_LEFTALIGN,
                 cursor.x, cursor.y, 0, GetHandle(), nullptr);
  DestroyMenu(menu);
}

void FlutterWindow::ExitApplication() {
  exiting_ = true;
  Destroy();
}

void FlutterWindow::RegisterLifecycleChannel() {
  lifecycle_channel_ =
      std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
          flutter_controller_->engine()->messenger(), "aios/window_lifecycle",
          &flutter::StandardMethodCodec::GetInstance());

  lifecycle_channel_->SetMethodCallHandler(
      [this](const flutter::MethodCall<flutter::EncodableValue>& call,
             std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>>
                 result) {
        const std::string& method = call.method_name();
        if (method == "show") {
          ShowFromTray();
          result->Success();
          return;
        }
        if (method == "hideToTray") {
          HideToTray();
          result->Success();
          return;
        }
        if (method == "exit") {
          result->Success();
          ExitApplication();
          return;
        }
        result->NotImplemented();
      });
}

void FlutterWindow::RegisterNativeTokenStoreChannel() {
  auto channel = std::make_unique<flutter::MethodChannel<flutter::EncodableValue>>(
      flutter_controller_->engine()->messenger(), "aios/native_token_store",
      &flutter::StandardMethodCodec::GetInstance());
  channel->SetMethodCallHandler(
      [](const flutter::MethodCall<flutter::EncodableValue>& call,
         std::unique_ptr<flutter::MethodResult<flutter::EncodableValue>> result) {
        if (call.method_name() == "readApiToken") {
          const auto token = ReadProtectedToken();
          if (token) {
            result->Success(flutter::EncodableValue(*token));
          } else {
            result->Success();
          }
          return;
        }
        if (call.method_name() == "writeApiToken") {
          const auto* arguments = std::get_if<flutter::EncodableMap>(call.arguments());
          if (arguments == nullptr) {
            result->Error("invalid_arguments", "Missing local API token.");
            return;
          }
          const auto token = arguments->find(flutter::EncodableValue("token"));
          if (token == arguments->end() || !std::holds_alternative<std::string>(token->second) ||
              !WriteProtectedToken(std::get<std::string>(token->second))) {
            result->Error("token_store_failed", "Could not protect the local API token.");
            return;
          }
          result->Success();
          return;
        }
        result->NotImplemented();
      });
  // The engine owns the binary messenger for its lifetime. Keep this channel
  // alive with the window so Dart can use it after startup.
  native_token_store_channel_ = std::move(channel);
}
