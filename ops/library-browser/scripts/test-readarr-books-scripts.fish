#!/usr/bin/env fish

# Behavior: Given an unprovisioned Written catalogue, provisioning must create
# only the approved LXD resources; verification must reject an Audio mount.
# Oracle: docs/superpowers/plans/2026-08-01-complementary-format-readarr.md.
# Plausible wrong implementation: adding an Audio disk or a public proxy while
# creating the Books instance. Observable assertion: fake-LXD command log and
# verifier exit status. Layer: command-contract test because LXD is the public
# boundary these scripts control.

set -l script_dir (path dirname (status filename))
set -l sandbox (mktemp -d)
set -l fake_lxc "$sandbox/lxc"
set -l log "$sandbox/lxc.log"
set -l state "$sandbox/instance-created"
set -l bundle "$sandbox/readarr-bundle"
mkdir $bundle
touch "$bundle/Readarr"

function cleanup --on-event fish_exit
    command rm -rf "$sandbox"
end

printf '%s\n' '#!/usr/bin/env fish' >$fake_lxc
printf '%s\n' 'printf "%s\\n" (string join " " -- $argv) >>$READARR_BOOKS_TEST_LOG' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = info; test -e $READARR_BOOKS_TEST_STATE; and exit 0; or exit 1; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = launch; touch $READARR_BOOKS_TEST_STATE; exit 0; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = config; and test "$argv[2]" = device; and test "$argv[3]" = get; exit 1; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = config; and test "$argv[2]" = show' >>$fake_lxc
printf '%s\n' '  printf "%s\\n" "architecture: x86_64" "config:" "  security.privileged: false" "  limits.cpu: 2" "  limits.memory: 2GiB" "  boot.autostart: true" "devices:" "  root:" "    path: /" "    size: 20GiB" "  eth0:" "    parent: lxdbr1" "    ipv4.address: 10.114.28.186" "  books:" "    type: disk" "    source: /plex/Books" "    path: /plex/Books" "    shift: true"; if set -q READARR_BOOKS_TEST_BAD_AUDIO; printf "%s\\n" "  audio:" "    source: /plex/Audiobooks" "    path: /plex/Audiobooks"; end; exit 0' >>$fake_lxc
printf '%s\n' 'end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = exec; and test "$argv[4]" = ss; printf "%s\\n" "LISTEN 0 4096 10.114.28.186:8787 0.0.0.0:*"; exit 0; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = exec; and test "$argv[4]" = sqlite3; if string match -rq RootFolders -- "$argv[7]"; printf "%s\\n" /plex/Books; else; printf "%s\\n" 0; end; exit 0; end' >>$fake_lxc
printf '%s\n' 'exit 0' >>$fake_lxc
chmod +x $fake_lxc

env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_BUNDLE=$bundle fish --no-config "$script_dir/provision-readarr-books.fish"
or exit 1

string match -rq 'launch images:debian/12 readarr-books' < $log
or begin; printf '%s\n' 'missing launch command' >&2; exit 1; end
string match -rq 'device add readarr-books books disk source=/plex/Books path=/plex/Books shift=true' < $log
or begin; printf '%s\n' 'missing idmapped Books mount command' >&2; exit 1; end
if string match -rq '/plex/Audiobooks|proxy' < $log
    exit 1
end

env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state fish --no-config "$script_dir/verify-readarr-books.fish"
or begin; printf '%s\n' 'approved fake configuration did not verify' >&2; exit 1; end

if env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_TEST_BAD_AUDIO=1 fish --no-config "$script_dir/verify-readarr-books.fish" >/dev/null 2>&1
    printf '%s\n' 'verifier accepted an Audio mount' >&2
    exit 1
end

printf '%s\n' 'readarr-books script contracts pass'
