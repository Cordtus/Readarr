# Complementary Format Readarr Design

## Goal

Allow a reader to request the other format of a title already tracked in
Readarr, without mixing written books and audiobooks in the same Readarr
catalogue or media root.

## Decision

Run a second, lightweight unprivileged Readarr instance in a new LXD
container on the homeserver. The existing host Readarr remains the Audio
catalogue and owns `/plex/Audiobooks`; the new `readarr-books` container owns
the Written catalogue and receives `/plex/Books` as its only read/write media
mount.

The library-browser request desk will query both catalogues for each search.
It will merge book results by foreign book ID and show each present format.
For a title tracked only in Audio it will show `In Readarr: Audio` and a
`Fetch Written` action; the inverse action is shown for Written-only titles.
The action enters the existing confirmation and explicit-release-selection
flow against the catalogue for the requested format. A title in both shows
both statuses without a duplicate-fetch action.

## Alternatives considered

1. Reuse the existing Readarr record and switch its root/profile temporarily.
   This risks importing the complementary file to the wrong library and
   changes the existing catalogue's configuration.
2. Download the other format outside Readarr. This would make it untracked,
   bypass the existing release-selection/import workflow, and make shelf
   behaviour inconsistent.
3. Separate catalogues (selected). Each format has an independent database,
   root, profile, release filtering, and import history.

## Container boundaries

`readarr-books` will use the existing homeserver LXD `lxdbr1` bridge and
`pool0` storage, with a fixed private address, a small root disk, bounded
memory/CPU, no public proxy device, and automatic start. It needs network
access only to its configured metadata/indexer/download services and a
read/write disk device for `/plex/Books`. It must not mount
`/plex/Audiobooks`, the host Readarr data directory, or the library-browser
credentials file.

The new service configuration and API key remain inside the container. The
host library-browser configuration will reference each target's local URL and
API key from its protected, mode-0600 runtime configuration; no credentials
will be committed.

## Data flow and errors

The browser searches both targets independently. If one target is
temporarily unavailable, the page must retain safe results from the other and
say that the unavailable format cannot be checked. A request token names the
target that created it and remains single-use. Release listings and grabs are
made only through that target. No release is grabbed merely because it is
displayed.

## Verification

Regression tests will cover Audio-only, Written-only, both-format, and
one-target-unavailable search results; selecting the complementary action
must use the intended target and leave the existing target untouched. Live
acceptance will verify the container's mount/network/service state, both
catalogue roots, Readarr's imported file, the shelf entry, and Plex's Music
library visibility for Audio imports.
