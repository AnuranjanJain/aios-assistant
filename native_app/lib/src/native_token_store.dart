import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Persists the loopback API token without placing it in JSON preferences.
///
/// The plugin is the preferred store. The Windows runner provides a DPAPI
/// fallback because some installed shells cannot initialize the plugin store
/// early enough during startup. Both stores are bound to the current Windows
/// user account.
class NativeTokenStore {
  const NativeTokenStore({
    FlutterSecureStorage? secureStorage,
    MethodChannel? channel,
  }) : _secureStorage = secureStorage ?? const FlutterSecureStorage(),
       _channel = channel ?? const MethodChannel('aios/native_token_store');

  static const _key = 'aios.core.api_token';

  final FlutterSecureStorage _secureStorage;
  final MethodChannel _channel;

  Future<String?> read() async {
    try {
      final token = await _secureStorage.read(key: _key);
      if (token != null && token.isNotEmpty) return token;
    } catch (_) {
      // Try the runner-owned DPAPI store below.
    }
    if (!Platform.isWindows) return null;
    try {
      final token = await _channel.invokeMethod<String>('readApiToken');
      return token?.isNotEmpty == true ? token : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> write(String token) async {
    if (token.isEmpty) return;
    Object? secureStorageError;
    try {
      await _secureStorage.write(key: _key, value: token);
    } catch (error) {
      secureStorageError = error;
    }
    if (!Platform.isWindows) {
      if (secureStorageError != null) throw secureStorageError;
      return;
    }
    try {
      await _channel.invokeMethod<void>('writeApiToken', {'token': token});
    } catch (_) {
      if (secureStorageError != null) rethrow;
    }
  }
}
