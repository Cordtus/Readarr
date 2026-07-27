# Library of Bex Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Python directory index at `/library/` with an accessible, themed “The Library of Bex” landing page while preserving download behavior.

**Architecture:** Add one self-contained static `index.html` to the existing `/home/sv/readarr-library` document root. The page will contain semantic HTML, inline CSS, and a small progressive-enhancement script that counts entries from the existing `Books/` and `Audiobooks/` directory indexes. Caddy routing and the two symlinks remain unchanged.

**Tech Stack:** Python `http.server`, semantic HTML, inline CSS, vanilla JavaScript.

---

### Task 1: Create the static Library of Bex page

**Files:**
- Create on homeserver: `/home/sv/readarr-library/index.html`

- [ ] **Step 1: Build the document shell**

  Add a valid HTML5 document with `lang="en"`, a descriptive title, viewport metadata, a deep-ink masthead, and the heading `The Library of Bex`.

- [ ] **Step 2: Add the shelf links**

  Add two semantic `<a>` cards with exact relative targets `Books/` and `Audiobooks/`. Give each a heading, short description, accessible decorative icon label, and an initially hidden count element. Keep the links ordinary anchors so they work without JavaScript.

- [ ] **Step 3: Add the visual system**

  Use inline CSS variables for parchment, ink, walnut, brass, and muted text; a serif display stack with a system sans-serif body stack; a CSS book/crest detail; responsive two-column-to-one-column layout at 700px; visible `:focus-visible` rings; and `@media (prefers-reduced-motion: reduce)` to remove transitions.

- [ ] **Step 4: Add progressive enhancement**

  Fetch `Books/` and `Audiobooks/` relative to the page, parse same-origin directory anchors, count visible non-parent entries, and reveal the count only after a successful response. Leave the cards fully usable when fetch or JavaScript fails.

### Task 2: Deploy without disturbing the library data

**Files:**
- Remote `/home/sv/readarr-library/index.html`
- Preserve remote `/home/sv/readarr-library/Books`
- Preserve remote `/home/sv/readarr-library/Audiobooks`

- [ ] **Step 1: Back up any pre-existing landing file**

  Check whether `/home/sv/readarr-library/index.html` exists. If it does, copy it to a timestamped sibling backup before installing the new file.

- [ ] **Step 2: Install with safe ownership and mode**

  Install the page as user `sv`, group `sv`, mode `0644`, without changing either shelf symlink or any files below `/plex/Books` and `/plex/Audiobooks`.

- [ ] **Step 3: Confirm the service remains unchanged**

  Confirm the Python server still listens on `0.0.0.0:8090` and Readarr still listens on `*:8787`; no service restart is needed because `http.server` reads the landing file per request.

### Task 3: Verify routing, links, and presentation

**Files:**
- No source changes.

- [ ] **Step 1: Verify direct upstream responses**

  From the homeserver, request `/`, `/Books/`, and `/Audiobooks/` on `127.0.0.1:8090`; expect the branded page for `/` and directory listings for both shelf paths.

- [ ] **Step 2: Verify Caddy routing**

  Request `https://readarr.basementnodes.ca/library/`, `/library/Books/`, and `/library/Audiobooks/` through Caddy with the correct hostname; expect the branded page, directory listings, and no authentication challenge for the LAN source.

- [ ] **Step 3: Verify download behavior**

  Issue `HEAD` requests against one known file in each available shelf and confirm a successful file response with the expected content type or length.

- [ ] **Step 4: Verify fallback and responsive behavior**

  Inspect the HTML for semantic headings, exact shelf targets, the title text, reduced-motion rules, and focus styles. Use a browser or headless browser at desktop and narrow viewport widths, and verify the page remains usable with JavaScript disabled.

- [ ] **Step 5: Record the deployment result**

  Report the remote file path, backup path if created, HTTP status results, and any unrelated pre-existing warnings without changing the Caddy or Fail2ban configuration.
