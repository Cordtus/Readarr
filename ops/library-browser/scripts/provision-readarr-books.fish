#!/usr/bin/env fish

# Provision the Written-only Readarr catalogue on the homeserver. This script
# deliberately does not read or copy another Readarr instance's database,
# configuration, credentials, API keys, or media mounts.

set -l instance readarr-books
set -l image images:debian/12
set -l address 10.114.28.186
set -l lxc /snap/bin/lxc

if set -q READARR_BOOKS_LXC
    set lxc $READARR_BOOKS_LXC
end

set -l bundle
if set -q READARR_BOOKS_BUNDLE
    set bundle $READARR_BOOKS_BUNDLE
else
    printf '%s\n' 'READARR_BOOKS_BUNDLE must name the separately built Readarr application bundle.' >&2
    exit 2
end


function lxc_run
    $READARR_BOOKS_LXC_COMMAND $argv
end

set -g READARR_BOOKS_LXC_COMMAND $lxc

function has_local_device
    set -l device_config (lxc_run config show $argv[1] --format json)
    or return 1
    printf '%s\n' $device_config | jq --exit-status --arg device "$argv[2]" '.devices | has($device)' >/dev/null
end

function ensure_device_override
    if not has_local_device $argv[1] $argv[2]
        lxc_run config device override $argv[1] $argv[2]
        or return 1
    end
end

if not lxc_run info $instance >/dev/null 2>&1
    lxc_run launch $image $instance
    or exit 1
end

# Apply these on every run so interrupted provisioning converges safely.
lxc_run config set $instance security.privileged false; or exit 1
lxc_run config set $instance limits.cpu 2; or exit 1
lxc_run config set $instance limits.memory 2GiB; or exit 1
lxc_run config set $instance boot.autostart true; or exit 1
ensure_device_override $instance root; or exit 1
lxc_run config device set $instance root size 20GiB; or exit 1
ensure_device_override $instance eth0; or exit 1
lxc_run config device set $instance eth0 parent lxdbr1; or exit 1
lxc_run config device set $instance eth0 ipv4.address $address; or exit 1

if not has_local_device $instance books
    lxc_run config device add $instance books disk source=/plex/Books path=/plex/Books shift=true
    or exit 1
end
lxc_run config device set $instance books source /plex/Books; or exit 1
lxc_run config device set $instance books path /plex/Books; or exit 1
lxc_run config device set $instance books shift true; or exit 1

if not test -d $bundle
    printf 'Readarr bundle does not exist: %s\n' $bundle >&2
    exit 2
end
set -l forbidden_bundle_file (find $bundle -type f \( -iname '*.db' -o -iname 'config.xml' \) -print -quit)
if test -n "$forbidden_bundle_file"
    printf '%s\n' 'READARR_BOOKS_BUNDLE must contain application files only, not databases or configuration.' >&2
    exit 2
end

# Do not add a proxy device. Port 8787 is intentionally reachable only on
# lxdbr1 at the fixed private address.
lxc_run exec $instance -- apt-get update; or exit 1
lxc_run exec $instance -- apt-get install --yes ca-certificates curl libicu72 sqlite3; or exit 1
lxc_run exec $instance -- id readarr
or lxc_run exec $instance -- useradd --system --home-dir /var/lib/readarr --create-home --shell /usr/sbin/nologin readarr
or exit 1
lxc_run exec $instance -- mkdir --parents /opt/Readarr /var/lib/readarr; or exit 1
lxc_run file push --recursive $bundle/ $instance/opt/Readarr/
or exit 1
lxc_run exec $instance -- chown --recursive readarr:readarr /opt/Readarr /var/lib/readarr
or exit 1

set -l unit (string join \n \
    '[Unit]' \
    'Description=Written Readarr catalogue' \
    'After=network-online.target' \
    'Wants=network-online.target' \
    '' \
    '[Service]' \
    'Type=simple' \
    'User=readarr' \
    'Group=readarr' \
    'ExecStart=/opt/Readarr/Readarr -nobrowser -data=/var/lib/readarr -bind=10.114.28.186 -port=8787' \
    'Restart=on-failure' \
    'RestartSec=5' \
    '' \
    '[Install]' \
    'WantedBy=multi-user.target')
printf '%s\n' $unit | lxc_run file push - $instance/etc/systemd/system/readarr-books.service
or exit 1
lxc_run exec $instance -- systemctl daemon-reload; or exit 1
lxc_run exec $instance -- systemctl enable --now readarr-books.service; or exit 1

printf '%s\n' 'Container service is installed, but catalogue credentials are intentionally absent.'
printf '%s\n' 'Use the private Readarr API inside readarr-books to add only /plex/Books, the Written quality profile, and the existing Deluge client with RemoveCompletedDownloads=false.'
printf '%s\n' 'Provide indexer and Deluge credentials separately inside the container; never copy them or host Readarr data into this instance.'
