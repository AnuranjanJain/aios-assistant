# AiOS Security Report

Audit date: 2026-08-08

## Threat model

The protected assets are Gmail metadata/bodies, OAuth tokens, reminders, activity snapshots, memory, job applications, resume content, local files, and automation outputs. The relevant threats are malicious local processes, hostile browser pages/extensions, prompt-injection emails, redirected browser pages, accidental destructive requests, and a user who enables LAN access.

## Controls now enforced

- Native pairing no longer returns the persistent bearer token to an arbitrary loopback caller. Browser approval uses a short-lived challenge; the native process uses a one-time launch secret.
- Ollama requests are loopback-only by default and are validated on every request. Unsafe settings fail before network I/O.
- Standalone automation, browser, and career APIs require `X-AiOS-Token` or Bearer auth. Health endpoints remain public for local liveness checks.
- Unsafe cross-origin mutations require a session form token or API token. CORS allows exact configured origins without credentialed wildcard behavior.
- Non-loopback binding requires explicit `AIOS_ALLOW_LAN=1` and a configured token.
- Email content is wrapped as untrusted data in AI prompts. Categories are allow-listed and confidence is finite and clamped.
- Browser final URLs and extension API destinations are revalidated. Automation rejects symlink/reparse-point paths.
- Profile images are decoded, resized, re-encoded as PNG, and stripped of source metadata. Request, upload, import, archive, analytics, and agent body limits are enforced.
- OAuth client JSON is external app data and is never bundled into PyInstaller output.
- Declared Python requirements pass `pip-audit` with no known vulnerabilities.

## Remaining risks

### High

**SEC-001: native token storage needs OS-level verification.** The Flutter client now stores its local API token through `flutter_secure_storage` on Windows, backed by Windows Credential Manager. JSON preferences retain only non-secret metadata, and legacy JSON tokens are migrated. A production sign-off still needs an OS-level inspection confirming the credential entry and ACL behavior on a clean Windows account.

**SEC-002: public artifact signing is not configured.** The build can sign with `signtool.exe` and `AIOS_SIGN_CERT_THUMBPRINT`, and `-RequireSigning` fails closed, but no certificate was available in this environment. Unsigned archives are developer previews only.

**SEC-003: live integration security is unverified.** Gmail OAuth expiry, multi-account isolation, GitHub token scope, browser extension permissions, and packaged installer behavior still need fixture or clean-machine verification.

**SEC-004: local data retention and purge are incomplete.** Raw email bodies and histories remain on disk until normal application cleanup. Add inventory, export, retention, and purge controls before public release.

## Security gates

1. Install Flutter and run native analyzer, widget, package, and high-DPI checks.
2. Verify Windows Credential Manager entry and ACL behavior on a clean Windows account.
3. Build with `scripts/build-windows-native.ps1 -RequireSigning` and verify Authenticode before publishing.
4. Run live connector fixtures with least-privilege OAuth scopes and expired-token cases.
5. Run the redacted AI corpus and adversarial prompt-injection suite on every model/prompt change.
