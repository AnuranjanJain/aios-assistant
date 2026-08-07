# Gmail OAuth

AiOS uses Google's installed desktop OAuth flow with PKCE and a loopback callback.
It requests only `gmail.readonly`; it cannot send, edit, or delete email.

## Connect an account

1. Open **Accounts** in the native Windows app.
2. Select **Sign in with Google**.
3. AiOS shows a waiting screen while the system browser opens. Use **Continue
   in browser** to reopen it or **Cancel sign-in** to stop without storing access.
4. Choose a Gmail address in the system browser and approve read-only access.
5. Use **Add another Google account** to connect more mailboxes.

The sign-in state is checkpointed in the local AiOS database for its short
15-minute lifetime. If the desktop core restarts while the browser is open,
the waiting screen can recover the same job instead of losing the session.

The installed AiOS release reads its desktop OAuth client configuration from
the user app-data directory. The JSON is intentionally not embedded in the
executable or committed to the repository.

Each account can be renamed, paused, resumed, synchronized, or removed
independently. Removing an account asks Google to revoke its token and always
deletes the encrypted local token.

## Local privacy model

- Access and refresh tokens are encrypted with a device-local AiOS secret before
  they enter SQLite.
- Email content is stored in the local AiOS database and never sent to cloud AI.
- Ollama and rule-based analysis run locally.
- The Gmail API is used only for authorization, refresh, and mailbox sync.

Windows locations:

```text
Database:     %LOCALAPPDATA%\AiOS Assistant\aios_assistant.db
Secret key:   %LOCALAPPDATA%\AiOS Assistant\instance\secret_key
```

## Synchronization behavior

The first run downloads a bounded recent backfill for each account. Later runs
use Gmail History API cursors, including message additions and label changes. If
Google expires a history cursor, AiOS automatically performs a fresh bounded
sync. Duplicate messages are prevented by the account and Gmail message ID pair.

Application intelligence then combines every enabled account into one
timestamp-ordered scope of the latest 500 locally stored emails. Related updates
are grouped by company, so an application confirmation, assessment, interview,
and offer appear as one timeline rather than four separate opportunities. Older
mail remains local and can be synchronized incrementally; it is simply outside
the current fast dashboard scope.

Background synchronization is controlled by `EMAIL_SYNC_INTERVAL_MINUTES` in
Settings. A failure on one account does not stop other connected accounts.

## Troubleshooting

- `access_denied` or **Access blocked**: while the Google OAuth app is in Testing,
  add the Gmail address under **Google Auth Platform -> Audience -> Test users**.
- `redirect_uri_mismatch`: recreate the credential as a **Desktop app** client.
- Gmail API disabled: enable Gmail API in the same project as the OAuth client.
- Refresh token rejected: remove the account in AiOS and connect it again.
- Browser did not open: retry from the installed desktop app and allow the
  loopback callback on `127.0.0.1`.

## Universal account access

There is no client-side bypass for Google's OAuth audience policy.
`gmail.readonly` is a restricted Gmail scope. A Testing OAuth app only accepts
accounts explicitly added as test users. To allow arbitrary Google accounts,
the release OAuth project must be published for production and complete the
Google verification steps required for its brand, audience, and restricted
scope use. AiOS handles the same verified client without requiring any setup
from end users.

## Release maintainer setup

The release maintainer enables Gmail API, configures the Google OAuth consent
screen, and creates a **Desktop app** OAuth client. Keep the downloaded file
private and place it at
`%APPDATA%\AiOS Assistant\credentials\google_client_secret.json` on the
development/release machine before launching AiOS. The build does not copy or
embed it in `AiOS-Core.exe`. For source development only,
`GMAIL_CREDENTIALS_PATH` may point to an equivalent file.
