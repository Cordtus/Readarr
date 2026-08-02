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
    set -l device_config (lxc_run query "/1.0/instances/$argv[1]")
    or return 1
    printf '%s\n' $device_config | jq --exit-status --arg device "$argv[2]" '.devices | has($device)' >/dev/null
end

function ensure_device_override
    if not has_local_device $argv[1] $argv[2]
        lxc_run config device override $argv[1] $argv[2]
        or return 1
    end
end

function lxd_boundary_is_safe
    set -l config (lxc_run query "/1.0/instances/$argv[1]?recursion=1")
    or return 1
    printf '%s\n' $config | jq --exit-status --arg address "$argv[2]" '
        .expanded_config["security.privileged"] == "false" and
        (.expanded_config | has("raw.idmap") | not) and
        (.expanded_devices.root | .type == "disk" and .path == "/" and .size == "20GiB") and
        (.expanded_devices.eth0 | .type == "nic" and .network == "lxdbr1" and .["ipv4.address"] == $address) and
        (.expanded_devices.books | .type == "disk" and .source == "/plex/Books" and .path == "/plex/Books" and .shift == "true") and
        ([.expanded_devices | to_entries[] | select(.value.type == "proxy")] | length == 0) and
        ([.expanded_devices | to_entries[] | select(.value.type == "disk" and .key != "root" and (.key != "books" or .value.source != "/plex/Books" or .value.path != "/plex/Books" or .value.shift != "true"))] | length == 0)
    ' >/dev/null
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
lxc_run config device set $instance eth0 network lxdbr1; or exit 1
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
set -l readarr_uid (lxc_run exec $instance -- id -u readarr)
if test $status -eq 0
    if test "$readarr_uid" != 1000
        if lxc_run exec $instance -- getent passwd 1000 >/dev/null
            printf '%s\n' 'Cannot align the Readarr user with the Books mount: container UID 1000 is already assigned.' >&2
            exit 1
        end
        lxc_run exec $instance -- usermod --uid 1000 readarr
        or exit 1
    end
else
    if lxc_run exec $instance -- getent passwd 1000 >/dev/null
        printf '%s\n' 'Cannot create the Readarr user: container UID 1000 is already assigned.' >&2
        exit 1
    end
    lxc_run exec $instance -- useradd --system --uid 1000 --home-dir /var/lib/readarr --create-home --shell /usr/sbin/nologin readarr
    or exit 1
end
lxc_run exec $instance -- mkdir --parents /opt/Readarr /var/lib/readarr; or exit 1
set -l bundle_entries $bundle/*
if test (count $bundle_entries) -eq 0
    printf '%s\n' 'READARR_BOOKS_BUNDLE has no application files to install.' >&2
    exit 2
end
for bundle_entry in $bundle_entries
    lxc_run file push --recursive $bundle_entry $instance/opt/Readarr/
    or exit 1
end
lxc_run exec $instance -- test -x /opt/Readarr/Readarr
or begin
    printf '%s\n' 'Readarr executable was not installed at /opt/Readarr/Readarr.' >&2
    exit 1
end
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
    'Environment=Readarr__Server__BindAddress=10.114.28.186' \
    'Environment=Readarr__Server__Port=8787' \
    'ExecStart=/opt/Readarr/Readarr -nobrowser -data=/var/lib/readarr' \
    'Restart=on-failure' \
    'RestartSec=5' \
    '' \
    '[Install]' \
    'WantedBy=multi-user.target')
printf '%s\n' $unit | lxc_run file push - $instance/etc/systemd/system/readarr-books.service
or exit 1
lxd_boundary_is_safe $instance $address
or begin
    printf '%s\n' 'Refusing to enable Readarr: expanded LXD topology exceeds the Written catalogue boundary.' >&2
    exit 1
end
lxc_run exec $instance -- systemctl daemon-reload; or exit 1
lxc_run exec $instance -- systemctl enable --now readarr-books.service; or exit 1

printf '%s\n' 'Container service is installed, but catalogue credentials are intentionally absent.'
printf '%s\n' 'Use the private Readarr API inside readarr-books to add only /plex/Books, the Written quality profile, and the existing Deluge client with RemoveCompletedDownloads=false.'
printf '%s\n' 'An operator may configure the approved shared MAM and Deluge credentials through the private API; never copy host Readarr data into this instance.'
