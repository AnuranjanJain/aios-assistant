import 'dart:convert';

import 'package:aios_assistant/src/api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('accepts the current native core contract', () async {
    final api =
        AiosApi(
            client: MockClient(
              (_) async => http.Response(
                jsonEncode({
                  'native_contract_version': AiosApi.nativeContractVersion,
                }),
                200,
              ),
            ),
          )
          ..baseUrl = 'http://127.0.0.1:5050'
          ..token = 'local-token';

    expect(await api.discover(), isTrue);
    expect(api.connected, isTrue);
  });

  test('rejects a stale local core instead of treating it as ready', () async {
    final api =
        AiosApi(
            client: MockClient(
              (_) async => http.Response(
                jsonEncode({'native_contract_version': 1}),
                200,
              ),
            ),
          )
          ..baseUrl = 'http://127.0.0.1:5050'
          ..token = 'stale-token';

    expect(await api.discover(), isFalse);
    expect(api.connected, isFalse);
  });
}
