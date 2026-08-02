#!/usr/bin/env fish

# Behavior: Given an unprovisioned Written catalogue, provisioning must create
# only the approved LXD resources; verification must reject every unsafe
# device and preserve the same topology on a second run.
# Oracle: docs/superpowers/plans/2026-08-01-complementary-format-readarr.md.
# Plausible wrong implementation: re-adding an inherited device, retaining an
# inherited default NIC, or accepting an arbitrary host bind. Observable
# assertion: fake-LXD command log and verifier exit status. Layer:
# command-contract test because LXD is the public boundary these scripts
# control.

set -l script_dir (path dirname (status filename))
set -l sandbox (mktemp -d)
set -l fake_lxc "$sandbox/lxc"
set -l log "$sandbox/lxc.log"
set -l state "$sandbox/instance-created"
set -l devices "$sandbox/local-devices"
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
printf '%s\n' 'if test "$argv[1]" = config; and test "$argv[2]" = device; and test "$argv[3]" = override; if contains -- "$argv[5]" (cat $READARR_BOOKS_TEST_DEVICES 2>/dev/null); exit 1; end; printf "%s\\n" "$argv[5]" >>$READARR_BOOKS_TEST_DEVICES; exit 0; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = config; and test "$argv[2]" = device; and test "$argv[3]" = add; if contains -- "$argv[5]" (cat $READARR_BOOKS_TEST_DEVICES 2>/dev/null); exit 1; end; printf "%s\\n" "$argv[5]" >>$READARR_BOOKS_TEST_DEVICES; exit 0; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = config; and test "$argv[2]" = device; and test "$argv[3]" = get; contains -- "$argv[5]" (cat $READARR_BOOKS_TEST_DEVICES 2>/dev/null); and exit 0; or exit 1; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = config; and test "$argv[2]" = show' >>$fake_lxc
printf '%s\n' '  if contains -- --expanded $argv; set -l root "{\"type\":\"disk\",\"path\":\"/\",\"size\":\"20GiB\"}"; set -l eth0 "{\"type\":\"nic\",\"network\":\"lxdbr1\",\"ipv4.address\":\"10.114.28.186\"}"; if set -q READARR_BOOKS_TEST_BAD_ROOT; set root "{\"type\":\"disk\",\"path\":\"/wrong\",\"size\":\"20GiB\"}"; end; if set -q READARR_BOOKS_TEST_BAD_BRIDGE; set eth0 "{\"type\":\"nic\",\"network\":\"wrongbr0\",\"ipv4.address\":\"10.114.28.186\"}"; end; if set -q READARR_BOOKS_TEST_BAD_IP; set eth0 "{\"type\":\"nic\",\"network\":\"lxdbr1\",\"ipv4.address\":\"10.114.28.187\"}"; end; set -l extra ""; if set -q READARR_BOOKS_TEST_BAD_AUDIO; set extra ",\"audio\":{\"type\":\"disk\",\"source\":\"/plex/Audiobooks\",\"path\":\"/plex/Audiobooks\"}"; end; if set -q READARR_BOOKS_TEST_EXTRA_DISK; set extra ",\"other\":{\"type\":\"disk\",\"source\":\"/host/private\",\"path\":\"/private\"}"; end; if set -q READARR_BOOKS_TEST_PROXY; set extra "$extra,\"public\":{\"type\":\"proxy\"}"; end; printf "{\"config\":{\"security.privileged\":\"false\",\"limits.cpu\":\"2\",\"limits.memory\":\"2GiB\",\"boot.autostart\":\"true\"},\"devices\":{\"root\":%s,\"eth0\":%s,\"books\":{\"type\":\"disk\",\"source\":\"/plex/Books\",\"path\":\"/plex/Books\",\"shift\":\"true\"}$extra}}\n" $root $eth0; else; set -l entries; for device in (cat $READARR_BOOKS_TEST_DEVICES 2>/dev/null); set -a entries "\"$device\":{}"; end; printf "{\"devices\":{%s}}\n" (string join , -- $entries); end; exit 0' >>$fake_lxc
printf '%s\n' 'end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = exec; and test "$argv[4]" = ss; printf "%s\\n" "LISTEN 0 4096 10.114.28.186:8787 0.0.0.0:*"; exit 0; end' >>$fake_lxc
printf '%s\n' 'if test "$argv[1]" = exec; and test "$argv[4]" = sqlite3; if string match -rq RootFolders -- "$argv[7]"; printf "%s\\n" /plex/Books; else; printf "%s\\n" 0; end; exit 0; end' >>$fake_lxc
printf '%s\n' 'exit 0' >>$fake_lxc
chmod +x $fake_lxc

env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_TEST_DEVICES=$devices READARR_BOOKS_BUNDLE=$bundle fish --no-config "$script_dir/provision-readarr-books.fish"
or exit 1

string match -rq 'launch images:debian/12 readarr-books' < $log
or begin; printf '%s\n' 'missing launch command' >&2; exit 1; end
string match -rq 'device add readarr-books books disk source=/plex/Books path=/plex/Books shift=true' < $log
or begin; printf '%s\n' 'missing idmapped Books mount command' >&2; exit 1; end
if string match -rq '/plex/Audiobooks|proxy' < $log
    exit 1
end

env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_TEST_DEVICES=$devices READARR_BOOKS_BUNDLE=$bundle fish --no-config "$script_dir/provision-readarr-books.fish"
or exit 1
test (count (string match -r '^launch images:debian/12 readarr-books$' < $log)) -eq 1
or begin; printf '%s\n' 'second provision relaunched the container' >&2; exit 1; end
test (count (string match -r '^config device add readarr-books books ' < $log)) -eq 1
or begin; printf '%s\n' 'second provision re-added the Books mount' >&2; exit 1; end
string match -rq '^config device override readarr-books eth0$' < $log
or begin; printf '%s\n' 'provisioning did not override inherited eth0' >&2; exit 1; end
string match -rq '^config device set readarr-books eth0 network lxdbr1$' < $log
or begin; printf '%s\n' 'provisioning did not select the managed LXD network' >&2; exit 1; end

env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_TEST_DEVICES=$devices fish --no-config "$script_dir/verify-readarr-books.fish"
or begin; printf '%s\n' 'approved fake configuration did not verify' >&2; exit 1; end

if env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_TEST_DEVICES=$devices READARR_BOOKS_TEST_BAD_AUDIO=1 fish --no-config "$script_dir/verify-readarr-books.fish" >/dev/null 2>&1
    printf '%s\n' 'verifier accepted an Audio mount' >&2
    exit 1
end

if env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_TEST_DEVICES=$devices READARR_BOOKS_TEST_EXTRA_DISK=1 fish --no-config "$script_dir/verify-readarr-books.fish" >/dev/null 2>&1
    printf '%s\n' 'verifier accepted an extra host disk bind' >&2
    exit 1
end

for unsafe_state in READARR_BOOKS_TEST_BAD_ROOT READARR_BOOKS_TEST_BAD_BRIDGE READARR_BOOKS_TEST_BAD_IP READARR_BOOKS_TEST_PROXY
    if env READARR_BOOKS_LXC=$fake_lxc READARR_BOOKS_TEST_LOG=$log READARR_BOOKS_TEST_STATE=$state READARR_BOOKS_TEST_DEVICES=$devices $unsafe_state=1 fish --no-config "$script_dir/verify-readarr-books.fish" >/dev/null 2>&1
        printf 'verifier accepted unsafe state: %s\n' $unsafe_state >&2
        exit 1
    end
end

printf '%s\n' 'readarr-books script contracts pass'
