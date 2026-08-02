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

set -l config (lxc_output config show $instance --expanded --format json)
or fail 'cannot read expanded LXD configuration'
printf '%s\n' $config | jq --exit-status --arg address "$address" '
    .config["security.privileged"] == "false" and
    .config["limits.cpu"] == "2" and
    .config["limits.memory"] == "2GiB" and
    .config["boot.autostart"] == "true" and
    (.devices.root | .type == "disk" and .path == "/" and .size == "20GiB") and
    (.devices.eth0 | .type == "nic" and .parent == "lxdbr1" and .["ipv4.address"] == $address) and
    (.devices.books | .type == "disk" and .source == "/plex/Books" and .path == "/plex/Books" and .shift == "true") and
    ([.devices | to_entries[] | select(.value.type == "proxy")] | length == 0) and
    ([.devices | to_entries[] | select(.value.type == "disk" and .key != "root" and (.key != "books" or .value.source != "/plex/Books" or .value.path != "/plex/Books" or .value.shift != "true"))] | length == 0)
' >/dev/null
or fail 'LXD device or resource boundary is not exact'

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
