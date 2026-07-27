# Library of Bex Readarr request desk

## Purpose

Extend the existing themed library browser with a simple, private request flow
that uses Readarr as the only metadata and download backend. The collection
pages remain file browsers. No external catalogs, source adapters, or archive
aggregation are included in this slice.

## Routes and presentation

`/library/` will retain its reading-room landing scene and add two in-theme
actions beneath the Books and Audiobooks shelves:

- **Request a book** links to `/library/request/`.
- **The archives** is visually subdued and says, “The archives are not yet
  open to the public.” It has no search or download action until new sources
  are deliberately integrated outside Readarr.

The request page follows the established paper, walnut, copper, serif, and
small-label vocabulary. It works without JavaScript for a basic submit and
confirmation flow; JavaScript may improve result selection and pending-state
feedback. It must keep the existing mobile layout, keyboard focus treatment,
and reduced-motion behavior.

## Request flow

1. A visitor enters a title, author, ISBN, or similar Readarr-supported term.
2. The library server asks Readarr for matching metadata and renders concise
   author/book cards. Results identify an already-added item instead of
   duplicating it.
3. The visitor chooses one result and is shown the exact action: add to the
   configured Readarr root/profile and begin an automatic search for the
   requested book or monitored author.
4. Only an explicit confirmation performs the mutation. The success page shows
   the Readarr item and command outcome in plain language, with links back to
   the request desk and library.

Readarr owns metadata discovery, duplicate handling, monitoring, automatic
search, queueing, download-client handoff, import, and library organization.
The library browser neither queries indexers directly nor makes source or
format promises.

## Backend boundary and safety

Extend `ops/library-browser/server.py` with a small Readarr client and
request-specific handlers. Configuration supplies the internal Readarr base
URL and API key only on the homeserver; neither appears in HTML, JavaScript,
logs, error pages, or repository files. The client uses Readarr's existing
search/lookup and add endpoints, then its native automatic-search command.

Keep all existing path validation and media-root isolation unchanged. Apply a
short request timeout, size bounds for query input, escaped output, and
same-origin POST/confirmation handling. Treat Readarr unreachability, missing
configuration, invalid results, duplicate requests, and rejected commands as
clear recoverable page states. Do not weaken Caddy authentication, LAN
exceptions, UFW, or Fail2ban rules.

## Verification

Focused unit tests will cover themed landing/request rendering, validation,
escaped metadata, existing-item behavior, confirmation-before-mutation,
Readarr request construction, and API failure handling with a fake client.
Deployment verification will use a non-mutating metadata lookup first, then a
single controlled request against the live Readarr configuration, confirming
the native command is accepted and no API credential appears in output. The
existing library tests, Python compilation, direct upstream routes, Caddy
routes, and traversal protections must remain green.
