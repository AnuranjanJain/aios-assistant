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
    final executable = _coreExecutable();
    if (!await executable.exists()) {
      throw StateError(
        'AiOS-Core.exe is missing. Reinstall the Windows-native build.',
      );
    }
    api.pairingSecret = _newPairingSecret();
    final environment = Map<String, String>.from(Platform.environment)
      ..['AIOS_NATIVE_PAIRING_SECRET'] = api.pairingSecret;
    _startedCore = await Process.start(
      executable.path,
      const ['--core-only'],
      workingDirectory: executable.parent.path,
      environment: environment,
      mode: ProcessStartMode.detached,
    );
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
}
