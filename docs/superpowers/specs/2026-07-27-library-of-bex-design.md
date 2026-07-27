# The Library of Bex landing page

## Purpose

Replace the default Python directory index at `/library/` with a welcoming,
private household library landing page titled **The Library of Bex**. The page
must keep the existing download directories and links unchanged.

## Visual direction

Use a mixed reading-room and gothic-archive mood: parchment and warm ivory for
the primary surface, deep ink/navy for the header, and restrained brass/copper
accents. Use a classic serif display face with a readable system fallback;
avoid external font or image dependencies so the page works offline and loads
quickly through the existing Python server.

## Layout and content

- Header: small “Private collection” label, “The Library of Bex” title,
  literary subtitle, and a simple CSS open-book/crest detail.
- Main content: two prominent shelf cards linking to `Books/` and
  `Audiobooks/`, with distinct book and headphone/bookmark motifs.
- Each shelf card progressively enhances itself by fetching its directory index
  and displaying the current number of visible entries when available. A plain
  link remains usable if JavaScript is unavailable.
- Footer: a short archival note and a clear indication that the collection is
  served locally.

## Behavior and accessibility

Use semantic headings, links, visible focus styles, sufficient color contrast,
and responsive single-column layout below 700px. Hover/focus transitions are
subtle and disabled under `prefers-reduced-motion: reduce`. No authentication,
routing, or filesystem behavior changes are part of this redesign.

## Delivery and verification

Add `/home/sv/readarr-library/index.html` on the homeserver, preserving the
existing `Books` and `Audiobooks` symlinks. Verify Caddy's `/library/` route,
both shelf links, directory download behavior, JavaScript-disabled fallback,
and desktop/mobile rendering through the public hostname.
