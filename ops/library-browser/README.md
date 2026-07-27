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
