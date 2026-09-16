import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'api.dart';

class CoreManager {
  CoreManager({AiosApi? api}) : api = api ?? AiosApi();

  final AiosApi api;
  Process? _startedCore;

  Future<void> ensureRunning() async {
    if (await api.discover()) return;
    if (_startedCore != null) {
      return _waitForPairing();
    }
    final executable = _coreExecutable();
    if (!await executable.exists()) {
      throw StateError(
        'AiOS-Core.exe is missing. Reinstall the Windows-native build.',
      );
    }
    api.pairingSecret = _newPairingSecret();
    await _writePairingSecret(api.pairingSecret);
    final dataDirectory = _dataDirectory();
    final environment = Map<String, String>.from(Platform.environment)
      ..['AIOS_NATIVE_PAIRING_SECRET'] = api.pairingSecret
      // The packaged core can run through a virtualized Python host on
      // Windows. Pin its data root to the same real profile directory used
      // by the Flutter shell so pairing, OAuth, and SQLite stay together.
      ..['AIOS_DATA_DIR'] = dataDirectory.path;
    _startedCore = await Process.start(
      executable.path,
      const ['--core-only'],
      workingDirectory: executable.parent.path,
      environment: environment,
      mode: ProcessStartMode.detached,
    );
    await _waitForPairing();
  }

  Future<void> _waitForPairing() async {
    for (var attempt = 0; attempt < 40; attempt += 1) {
      await Future<void>.delayed(const Duration(milliseconds: 350));
      if (await api.discover()) return;
    }
    throw StateError('AiOS Core did not become ready.');
  }

  Future<void> stop() async {
    if (api.connected) {
      try {
        await api.post('/api/desktop/exit');
      } catch (_) {
        _startedCore?.kill();
      }
    } else {
      _startedCore?.kill();
    }
  }

  File _coreExecutable() {
    final installed = File(
      '${File(Platform.resolvedExecutable).parent.path}\\AiOS-Core.exe',
    );
    if (installed.existsSync()) return installed;
    return File('${Directory.current.parent.path}\\dist\\AiOS-Core.exe');
  }

  String _newPairingSecret() {
    final bytes = List<int>.generate(32, (_) => Random.secure().nextInt(256));
    return base64UrlEncode(bytes);
  }

  Future<void> _writePairingSecret(String secret) async {
    final file = File('${_dataDirectory().path}\\native-pairing.secret');
    await file.parent.create(recursive: true);
    await file.writeAsString(secret, flush: true);
  }

  Directory _dataDirectory() {
    final root = Platform.environment['LOCALAPPDATA'] ?? Directory.current.path;
    return Directory('$root\\AiOS Assistant');
  }
}
