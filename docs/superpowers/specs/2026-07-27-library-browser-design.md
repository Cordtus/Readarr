# Library browser redesign

## Purpose

Make `/library/` feel like an immersive personal library rather than a large
hero heading followed by generic directory links. Improve `/library/Books/` and
`/library/Audiobooks/` with matching but simpler catalog pages.

## Architecture and safety

Replace the stock `python -m http.server` process on port `8090` with a small,
dedicated Python library browser running as the existing `sv` user. It will
render custom HTML for `/`, `/Books/`, and `/Audiobooks/`, and serve files from
the existing `/plex/Books` and `/plex/Audiobooks` roots without writing into
those directories. URL normalization and resolved-path checks must prevent
directory traversal. Existing Caddy routes, LAN-only library access, and
download URLs remain unchanged.

## Visual design

- Main page: locally served illustrated reading-room background with a compact
  plaque-sized “The Library of Bex” heading, so the shelves—not the title—own
  the page.
- Books page: parchment catalog surface, ink typography, walnut/brass details,
  breadcrumb back to the library, item count, and readable file rows showing
  name, size, modified date, and a clear download link.
- Audiobooks page: the same catalog structure with a subtly warmer copper
  accent and audio/bookmark detail.
- Empty shelves use the exact message **“Awaiting new stock”**.

## Behavior and accessibility

All navigation and downloads work as ordinary links without JavaScript. Use
semantic headings, visible keyboard focus, adequate contrast, responsive layout,
and reduced-motion support. Optional enhancement may add gentle shelf hover or
focus polish, but no continuous parallax or distracting loops. The generated
background is stored locally; no external assets or runtime network calls are
required.

## Verification

Verify direct upstream and Caddy responses for `/library/`, `/library/Books/`,
and `/library/Audiobooks/`; confirm empty-state text, known-file downloads,
path traversal rejection, preserved Caddy/auth behavior, unchanged media
directories, and healthy Readarr plus library listeners.
