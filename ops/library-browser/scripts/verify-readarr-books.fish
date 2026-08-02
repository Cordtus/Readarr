#!/usr/bin/env fish

# Read-only boundary verification. It prints no database fields or credentials.

set -l instance readarr-books
set -l address 10.114.28.186
set -l lxc /snap/bin/lxc
if set -q READARR_BOOKS_LXC
    set lxc $READARR_BOOKS_LXC
end

function fail --argument-names message
    printf 'readarr-books verification failed: %s\n' $message >&2
    exit 1
end

function lxc_output
    $READARR_BOOKS_LXC_COMMAND $argv
end

set -g READARR_BOOKS_LXC_COMMAND $lxc

lxc_output info $instance >/dev/null 2>&1
or fail 'instance does not exist'

set -l config (lxc_output config show $instance --expanded)
or fail 'cannot read expanded LXD configuration'
string match -rq 'security\.privileged: false' -- $config
or fail 'instance must be unprivileged'
string match -rq 'parent: lxdbr1' -- $config
or fail 'instance must use lxdbr1'
string match -rq "ipv4.address: $address" -- $config
or fail 'instance must use the approved private address'
string match -rq 'size: 20GiB' -- $config
or fail 'root disk must be limited to 20GiB'
string match -rq 'limits.cpu: 2' -- $config
or fail 'CPU limit must be 2'
string match -rq 'limits.memory: 2GiB' -- $config
or fail 'memory limit must be 2GiB'
string match -rq 'boot.autostart: true' -- $config
or fail 'boot autostart must be enabled'
string match -rq 'source: /plex/Books' -- $config
and string match -rq 'path: /plex/Books' -- $config
and string match -rq 'shift: true' -- $config
or fail 'Books must be the idmapped media mount'
if string match -rq '/plex/Audiobooks|proxy:' -- $config
    fail 'Audio mount or public proxy device is forbidden'
end

lxc_output exec $instance -- systemctl is-active --quiet readarr-books.service
or fail 'Readarr service is not active'
set -l listening (lxc_output exec $instance -- ss -ltnH 'sport = :8787')
or fail 'cannot inspect the private listener'
test (count $listening) -eq 1; and string match -rq "^LISTEN.*$address:8787" -- $listening
or fail 'Readarr is not bound only to the approved private endpoint'

set -l roots (lxc_output exec $instance -- sqlite3 -readonly /var/lib/readarr/readarr.db 'SELECT "Path" FROM "RootFolders" ORDER BY "Path";')
or fail 'cannot inspect configured root folders'
test (count $roots) -eq 1; and test "$roots[1]" = /plex/Books
or fail 'configured root must be exactly /plex/Books'
set -l deluge_rows (lxc_output exec $instance -- sqlite3 -readonly /var/lib/readarr/readarr.db 'SELECT "RemoveCompletedDownloads" FROM "DownloadClients" WHERE "Implementation" = "Deluge";')
or fail 'cannot inspect Deluge retention'
test (count $deluge_rows) -eq 1; and contains -- $deluge_rows[1] 0 false False FALSE
or fail 'exactly one Deluge client must retain completed torrents'

printf '%s\n' 'readarr-books boundary verification passed'
