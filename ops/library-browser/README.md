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
  "qualityProfileId": 0,
  "metadataProfileId": 0,
  "monitor": "REPLACE_WITH_READARR_MONITOR_VALUE",
  "monitorNewItems": "REPLACE_WITH_READARR_MONITOR_NEW_ITEMS_VALUE"
}
```

Replace every placeholder, including both `0` IDs, before starting the
watchdog. After authenticated access to Readarr, use the instance's root-folder,
quality-profile, and metadata-profile listings to copy the actual path and IDs;
do not guess them. Set the file permissions after placing it:

```sh
chown sv:sv /home/sv/library-browser/readarr-request.json
chmod 0600 /home/sv/library-browser/readarr-request.json
```

Deploy the updated `server.py` and `run-library-browser.sh` through the normal
rootless release process, then restart the watchdog by stopping its current
child and running `/home/sv/library-browser/run-library-browser.sh`. Confirm
the minute cron check leaves one listener, inspect the watchdog log for only
the sanitized configuration status, and verify locally:

```sh
ps -eo pid,args | grep '[s]erver.py'
curl -i http://127.0.0.1:8090/library/request/
curl -I http://127.0.0.1:8090/library/Books/
```

The process listing must show the config-file path but no API key. A valid
configuration makes `/library/request/` available; absent or invalid
configuration returns the themed 503 page while catalogue routes remain
available. For rollback, restore the previous `server.py` and
`run-library-browser.sh` from the recorded deployment version, then restart
the watchdog; do not alter either media root. Caddy, UFW, and Fail2ban remain
outside this deployment scope.
