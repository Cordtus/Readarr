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
  "targets": {
    "audiobooks": {
      "rootFolderPath": "REPLACE_WITH_AUDIOBOOKS_ROOT_FOLDER_PATH",
      "qualityProfileId": "REPLACE_WITH_AUDIOBOOKS_QUALITY_PROFILE_ID",
      "metadataProfileId": "REPLACE_WITH_AUDIOBOOKS_METADATA_PROFILE_ID",
      "monitor": "REPLACE_WITH_AUDIOBOOKS_MONITOR_VALUE",
      "monitorNewItems": "REPLACE_WITH_AUDIOBOOKS_MONITOR_NEW_ITEMS_VALUE"
    },
    "books": {
      "rootFolderPath": "REPLACE_WITH_BOOKS_ROOT_FOLDER_PATH",
      "qualityProfileId": "REPLACE_WITH_BOOKS_QUALITY_PROFILE_ID",
      "metadataProfileId": "REPLACE_WITH_BOOKS_METADATA_PROFILE_ID",
      "monitor": "REPLACE_WITH_BOOKS_MONITOR_VALUE",
      "monitorNewItems": "REPLACE_WITH_BOOKS_MONITOR_NEW_ITEMS_VALUE"
    }
  }
}
```

Replace every placeholder before starting the watchdog. The template is valid
JSON, but the quoted profile placeholders must be replaced with the numeric IDs
returned by Readarr. The two target names are required. Audiobooks is selected
by default in the request desk; its root and quality profile must therefore be
the audiobook target. Written books remains an explicit alternate choice.
After authenticated access to Readarr, use the instance's root-folder,
quality-profile, and metadata-profile listings to copy the actual path and IDs;
do not guess them. Set the file permissions after placing it:

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

Search results deliberately separate books from authors. The desk defaults to
Audiobooks and carries the chosen target through confirmation. A book
confirmation adds and monitors that specific book without starting an automatic
search. Readarr then applies that target's quality profile when returning
eligible interactive releases, and the user must choose one exact release
before the server posts its `guid`, `indexerId`, and book ID to Readarr. No
release is grabbed merely because it was displayed. Author confirmation only
adds and monitors the author; it does not start a search. Every candidate and
release choice uses a short-lived, single-use server-side token. A success
response confirms the specific Readarr action; it does not promise that a file
has already imported into the library.

## MAM retention and release metadata

The MAM-capable Deluge download client is configured with
`RemoveCompletedDownloads: false`. Keep that setting in every Readarr
catalogue so imported MAM torrents stay in Deluge for their required sharing
period. The unrelated SABnzbd removal setting is not evidence about MAM
torrents and must not be used to decide Deluge retention.

`scripts/probe-mam-release-metadata.py` is a read-only, sanitized capability
probe for the homeserver. It reads only the protected local request-desk
configuration at `/home/sv/library-browser/readarr-request.json`, takes one
existing Readarr book ID on standard input, and reports the usable
`freeleech` field name and JSON type only. It never prints the configuration,
URLs, API key, cookies, GUIDs, download URLs, titles, or tracker passkeys. It
exits with status 3 if Readarr does not return an explicit boolean
`freeleech` field; that result means the request desk must not label the
release freeleech.

This is generic release metadata only. It does not prove that the account
currently has VIP status, which is time-bound and must be determined from
current account entitlement rather than inferred from a release field.

## Written Readarr catalogue

`scripts/provision-readarr-books.fish` provisions the independent Written
catalogue. It is intentionally an LXD-only operation: it creates one
unprivileged Debian 12 container named `readarr-books`, limited to 2 CPUs,
2GiB RAM, and a 20GiB root disk. It autostarts on the existing `lxdbr1`
bridge at `10.114.28.186`, and `readarr-books.service` binds Readarr only to
that private address on port 8787. It creates no LXD proxy device.

The only media device is an idmapped `books` disk from `/plex/Books` to
`/plex/Books`. `/plex/Audiobooks` is neither mounted nor configured as a root
folder. This boundary is what keeps Written imports independent from the
existing Audio Readarr instance.

Run this on the homeserver only after providing a separately built, already
trusted Readarr application bundle. The bundle is application files only; the
script never copies the host Readarr database, configuration, API key,
indexers, download-client passwords, Caddy configuration, or either media
root. Use Fish:

```fish
set -lx READARR_BOOKS_BUNDLE /srv/readarr-publish
fish /home/sv/library-browser/scripts/provision-readarr-books.fish
fish /home/sv/library-browser/scripts/verify-readarr-books.fish
```

Provisioning deliberately leaves all catalog credentials absent. Supply the
MAM and Deluge credentials separately through the new instance's private
local API, then configure exactly one root folder (`/plex/Books`), the Written
quality profile, and its Deluge client. That client must have
`RemoveCompletedDownloads: false`, so MAM torrents remain available to seed
after imports. Credentials must never be copied from the Audio instance or
placed in this repository, the command line, or the provisioning environment.

`scripts/verify-readarr-books.fish` is read-only. It rejects a missing or
privileged instance, the wrong bridge/address/resource limits, a missing
idmapped Books mount, any Audio mount or proxy device, an inactive service or
non-private listener, any root folder other than `/plex/Books`, and a Deluge
client that removes completed torrents. It reads LXD's expanded JSON and
checks the named `root` and `eth0` devices plus every disk/proxy device,
rather than accepting a matching value from unrelated YAML. Provisioning
overrides inherited `root` and `eth0` devices once, then reuses their local
overrides on later runs; rerunning it neither relaunches the container nor
adds a second Books mount. It prints only pass/fail facts, never database
values or credentials.

After the verifier passes, take an LXD snapshot. Rollback is limited to
stopping and deleting `readarr-books` (or restoring that snapshot); it must
never delete `/plex/Books`, the host Audio Readarr data, host Deluge data, or
the library-browser release.

Run it as `sv` on the homeserver, supplying a known local Readarr book ID:

```fish
printf '%s\n' BOOK_ID | python3 /home/sv/library-browser/scripts/probe-mam-release-metadata.py
```

## Responsive bookcase verification

The landing page and every request state share the same reading-room shell.
There is no outer cabinet surface: the identity sits directly over the room,
and Books, Audiobooks, and Request form one horizontal mobile-first shelf row.
The landing starts fully collapsed; tapping a shelf opens an overlay panel,
and pointer hover previews it on hover-capable devices. With JavaScript, the
overlay scrolls its own long content over the room while the page itself,
title, shelf controls, and archives notice stay fixed. Routed request states
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
- opening each shelf leaves the title, all three controls, and archives notice
  in place, without making the landing taller than the viewport;
- long shelf content scrolls within its overlay rather than scrolling or
  resizing the background page;
- reduced-motion mode makes shelf changes immediate.

A late-model physical iPhone Safari pass remains the final hardware acceptance
check when a device is available. To roll back only the bookcase redesign,
restore the timestamped pre-deploy runtime bundle, preserve
`readarr-request.json`, stop exactly one verified watchdog process, and let the
existing cron supervisor restart it.
