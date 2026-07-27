#!/bin/sh
set -u

umask 022
lock_dir=/home/sv/library-browser/watchdog.lock
if ! mkdir "$lock_dir" 2>/dev/null; then
    printf 'library browser watchdog already running\n' >&2
    exit 0
fi

remove_lock() {
    rmdir "$lock_dir" 2>/dev/null || true
}

child_pid=
stop_children() {
    if [ -n "${child_pid:-}" ] && kill -0 "$child_pid" 2>/dev/null; then
        kill "$child_pid" 2>/dev/null || true
        wait "$child_pid" 2>/dev/null || true
    fi
    exit 143
}

trap remove_lock EXIT
trap stop_children HUP INT TERM

cd /home/sv/library-browser || exit 1

while :; do
    /usr/bin/python3 /home/sv/library-browser/server.py \
        --host 0.0.0.0 \
        --port 8090 \
        --books-root /plex/Books \
        --audiobooks-root /plex/Audiobooks \
        --readarr-config /home/sv/library-browser/readarr-request.json &
    child_pid=$!
    wait "$child_pid"
    status=$?
    child_pid=
    printf 'library browser exited with status %s; restarting in 2 seconds\n' "$status" >&2
    /usr/bin/sleep 2
done
