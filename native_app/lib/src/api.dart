import 'dart:convert';

import 'package:http/http.dart' as http;

class AiosApi {
  AiosApi({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;
  String baseUrl = '';
  String token = '';

  bool get connected => baseUrl.isNotEmpty && token.isNotEmpty;

  Future<bool> discover() async {
    for (var port = 5050; port <= 5069; port += 1) {
      final candidate = 'http://127.0.0.1:$port';
      try {
        final response = await _client
            .get(Uri.parse('$candidate/api/local/pairing'))
            .timeout(const Duration(milliseconds: 650));
        if (response.statusCode != 200) continue;
        final body = jsonDecode(response.body) as Map<String, dynamic>;
        if (body['ok'] != true || body['service'] != 'aios-assistant') continue;
        final nextToken = body['api_token']?.toString() ?? '';
        if (nextToken.isEmpty) continue;
        baseUrl = _normalizeLoopback(body['base_url']?.toString() ?? candidate);
        token = nextToken;
        return true;
      } catch (_) {
        // The native core may still be starting. Try the next port.
      }
    }
    return false;
  }

  Future<Map<String, dynamic>> get(String path) => _request('GET', path);

  Future<Map<String, dynamic>> post(
    String path, [
    Map<String, dynamic> body = const {},
  ]) => _request('POST', path, body);

  Future<Map<String, dynamic>> patch(String path, Map<String, dynamic> body) =>
      _request('PATCH', path, body);

  Future<Map<String, dynamic>> delete(String path) => _request('DELETE', path);

  Future<Map<String, dynamic>> _request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    if (!connected && !await discover()) {
      throw StateError('AiOS Core is not running.');
    }
    final uri = Uri.parse('$baseUrl$path');
    final headers = {
      'X-AiOS-Token': token,
      if (body != null) 'Content-Type': 'application/json',
    };
    final encodedBody = body == null ? null : jsonEncode(body);
    final response = await switch (method) {
      'POST' => _client.post(uri, headers: headers, body: encodedBody),
      'PATCH' => _client.patch(uri, headers: headers, body: encodedBody),
      'DELETE' => _client.delete(uri, headers: headers),
      _ => _client.get(uri, headers: headers),
    }.timeout(const Duration(seconds: 45));

    final text = response.body.trimLeft();
    if (response.statusCode == 401) {
      throw StateError('AiOS Core is locked.');
    }
    if (text.startsWith('<')) {
      throw FormatException('$path returned a web page instead of API data.');
    }
    final decoded = response.body.isEmpty
        ? <String, dynamic>{}
        : jsonDecode(response.body);
    final data = decoded is Map<String, dynamic>
        ? decoded
        : <String, dynamic>{'items': decoded};
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError(
        data['message']?.toString() ??
            data['error']?.toString() ??
            '$path failed with ${response.statusCode}.',
      );
    }
    return data;
  }

  String _normalizeLoopback(String value) {
    final uri = Uri.parse(value);
    if (uri.scheme != 'http' ||
        !{'127.0.0.1', 'localhost', '::1'}.contains(uri.host)) {
      throw StateError('AiOS Core must stay on this device.');
    }
    return Uri(
      scheme: 'http',
      host: uri.host,
      port: uri.hasPort ? uri.port : null,
    ).toString().replaceAll(RegExp(r'/+$'), '');
  }
}
