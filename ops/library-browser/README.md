# Rootless library-browser operations

The homeserver deployment runs as `sv` without sudo or systemd. The sole
active supervisor is `/home/sv/library-browser/run-library-browser.sh`, which
starts `server.py` with explicit `/plex/Books` and `/plex/Audiobooks` roots,
restarts the child after exit, and uses the atomic directory
`/home/sv/library-browser/watchdog.lock` to prevent duplicate supervisors.

Persistence is provided by these `sv` crontab entries:

```cron
@reboot /home/sv/library-browser/run-library-browser.sh >> /home/sv/library-browser/watchdog.log 2>&1
* * * * * /home/sv/library-browser/run-library-browser.sh >> /home/sv/library-browser/watchdog.log 2>&1
```

The minute-level entry is a recovery check. It exits immediately when the
watchdog lock is held, so it does not create a second listener. The user
systemd unit is intentionally not used because the user manager is unavailable;
when present, stale unit files and `default.target.wants` links are moved to a
timestamped backup under `/home/sv/.config/systemd/user/backups/` rather than
being left as misleading enabled state.

The old port-8090 command and deployment boundaries are recorded in
`/home/sv/library-browser/deployment-rollback.txt`. The watchdog must never
write under either media root, and Caddy, UFW, Fail2ban, and Readarr are
outside this deployment's scope.

## Readarr request desk configuration

The request desk is disabled safely unless
`/home/sv/library-browser/readarr-request.json` is present and valid. Keep
that file owned by `sv:sv`, mode `0600`, and untracked. It is the only place
for the Readarr API credential; never put a key in a command, environment
echo, process argument, README example, or shell history.

Create the file with the actual values returned by the authenticated Readarr
instance:

```json
{
  "url": "https://REPLACE_WITH_READARR_URL",
  "apiKey": "REPLACE_WITH_READARR_API_KEY",
  "rootFolderPath": "REPLACE_WITH_READARR_ROOT_FOLDER_PATH",
  "qualityProfileId": "REPLACE_WITH_READARR_QUALITY_PROFILE_ID",
  "metadataProfileId": "REPLACE_WITH_READARR_METADATA_PROFILE_ID",
  "monitor": "REPLACE_WITH_READARR_MONITOR_VALUE",
  "monitorNewItems": "REPLACE_WITH_READARR_MONITOR_NEW_ITEMS_VALUE"
}
```

Replace every placeholder before starting the watchdog. The template is valid
JSON, but the quoted profile placeholders must be replaced with the numeric IDs
returned by Readarr. After authenticated access to Readarr, use the instance's
root-folder, quality-profile, and metadata-profile listings to copy the actual
path and IDs; do not guess them. Set the file permissions after placing it:

```sh
chown sv:sv /home/sv/library-browser/readarr-request.json
chmod 0600 /home/sv/library-browser/readarr-request.json
```

On first deployment, install the complete runtime bundle together in
`/home/sv/library-browser`: `server.py`, `readarr.py`, `templates.py`,
`assets/reading-room.webp`, and `run-library-browser.sh`. Every runtime module
file must be updated together; keep the protected
`readarr-request.json` configuration separate and do not overwrite it during
bundle installation. Do not run a second watchdog while
`watchdog.lock` exists: it exits immediately. To reload safely, stop the one
active supervisor and let the minute cron entry restart it with a fresh lock:

```sh
supervisor_pid=$(pgrep -u sv -f '[r]un-library-browser\.sh' | awk 'NR == 1 { pid = $1 } NR == 2 { exit 1 } END { if (NR != 1) exit 1; print pid }') || exit 1
kill -TERM "$supervisor_pid"
```

Wait for cron to start the replacement supervisor, then confirm it leaves one
listener, inspect the watchdog log for only the sanitized configuration status,
and verify locally:

```sh
ps -eo pid,args | grep '[s]erver.py'
curl -i http://127.0.0.1:8090/library/request/
curl -I http://127.0.0.1:8090/library/Books/
```

The process listing must show the config-file path but no API key. A valid
configuration makes `/library/request/` available; absent or invalid
configuration returns the themed 503 page while catalogue routes remain
available. For rollback, restore the previous complete runtime bundle
(`server.py`, `readarr.py`, `templates.py`, `assets/reading-room.webp`, and
`run-library-browser.sh`) from the recorded deployment version, preserve the
protected configuration, stop the active supervisor with the same sequence,
and let cron restart it; do not alter either media root. Caddy, UFW, and
Fail2ban remain outside this deployment scope.

Search results deliberately separate books from authors. A book request adds
and searches that specific book. An author request is broader: it adds the
author and searches the books selected by the configured monitoring policy.
The confirmation page states which action will occur before its single-use
POST token is consumed. A success response confirms Readarr acceptance; it
does not promise that an indexer has a matching release.

## Responsive bookcase verification

The landing page and every request state share the same reading-room shell.
There is no outer cabinet surface: the identity sits directly over the room,
and Books, Audiobooks, and Request form one horizontal mobile-first shelf row.
The landing starts fully collapsed; tapping a shelf opens its full-width panel,
and pointer hover previews it on hover-capable devices. Routed request states
open Request automatically. Without JavaScript, all panels remain in document
flow so catalog links and request forms still work.
Books and Audiobooks previews use the same root-bound filtering as their
catalog routes.

Before deployment, test WebKit at 393 by 852 and 430 by 932 in portrait and
landscape. Confirm:

- shelf controls and actions have at least 44 by 44 CSS-pixel targets;
- request inputs compute to at least 16px and remain visible when focused;
- the page has no horizontal overflow at 100% and 200% zoom;
- safe-area padding protects content at the viewport edges;
- touch opens one shelf at a time, while keyboard focus and activation work;
- reduced-motion mode makes shelf changes immediate.

A late-model physical iPhone Safari pass remains the final hardware acceptance
check when a device is available. To roll back only the bookcase redesign,
restore the timestamped pre-deploy runtime bundle, preserve
`readarr-request.json`, stop exactly one verified watchdog process, and let the
existing cron supervisor restart it.
