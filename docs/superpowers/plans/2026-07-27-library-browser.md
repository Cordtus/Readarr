# Library Browser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the stock directory server with a safe themed library browser that renders immersive landing and catalog pages while preserving file downloads.

**Architecture:** Keep source in the repository under `ops/library-browser/`, with a Python `http.server` subclass that renders `/`, `/Books/`, and `/Audiobooks/` and serves files only from the two configured media roots. Deploy the script, templates/assets, and a service definition to the homeserver, replacing the current port-8090 process without modifying the media directories or Caddy configuration.

**Tech Stack:** Python 3 standard library, HTML/CSS, vanilla JavaScript, systemd, locally generated image asset.

---

### Task 1: Build the library browser source and tests

**Files:**
- Create: `ops/library-browser/server.py`
- Create: `ops/library-browser/templates.py`
- Create: `ops/library-browser/assets/reading-room.webp`
- Create: `ops/library-browser/test_server.py`

- [ ] **Step 1: Define the safe route and media-root model**

  Configure `/Books/` and `/Audiobooks/` as the only media roots. Normalize URL paths, resolve candidate filesystem paths, reject any path escaping its configured root with HTTP 403, and preserve ordinary URL-encoded filenames for downloads.

- [ ] **Step 2: Add deterministic server tests first**

  Use temporary directories containing one known book and one known audiobook fixture. Test `GET /` for the Library of Bex title, `GET /Books/` and `GET /Audiobooks/` for catalog headings and “Awaiting new stock” when empty, successful file responses, and traversal attempts such as `/Books/../Audiobooks/` returning 403 or 404 without leaking content.

- [ ] **Step 3: Implement catalog rendering**

  Render sorted non-hidden files and directories with escaped names, byte sizes, UTC modification dates, ordinary download links, breadcrumb links to `/library/`, and the exact empty state “Awaiting new stock”. Keep all HTML usable without JavaScript.

- [ ] **Step 4: Implement the landing scene**

  Render a compact plaque heading, a local reading-room background asset, and literal CSS shelf structures as the dominant visual. Use the existing absolute shelf URLs `/library/Books/` and `/library/Audiobooks/`, responsive layout, focus styles, and reduced-motion rules.

- [ ] **Step 5: Run the source tests and static checks**

  Run `python3 -m unittest discover -s ops/library-browser -p 'test_*.py' -v` and `python3 -m py_compile ops/library-browser/server.py ops/library-browser/templates.py`. Expected result: all tests pass and compilation exits successfully.

### Task 2: Deploy the browser as the port-8090 service

**Files:**
- Deploy: `/home/sv/library-browser/server.py`
- Deploy: `/home/sv/library-browser/templates.py`
- Deploy: `/home/sv/library-browser/assets/reading-room.webp`
- Deploy: `/etc/systemd/system/readarr-library.service`

- [ ] **Step 1: Capture current service state**

  Record the current port-8090 PID, command line, ownership, Caddy route, and symlink targets. Do not modify `/plex/Books`, `/plex/Audiobooks`, or `/home/sv/readarr-library/Books` and `Audiobooks`.

- [ ] **Step 2: Install the new files safely**

  Create `/home/sv/library-browser` owned by `sv:sv` mode `0755`; install source/assets mode `0644`. Install a systemd unit running as `sv` with `WorkingDirectory=/home/sv/library-browser`, binding `0.0.0.0:8090`, and invoking the server with explicit media-root arguments.

- [ ] **Step 3: Replace the old process with rollback available**

  Save the old command and PID in the deployment record, stop only the existing port-8090 process, enable/start the new unit, and keep the old document-root files and symlinks untouched so rollback can restore the original `python3 -m http.server` command.

- [ ] **Step 4: Verify service ownership and boundaries**

  Confirm the new listener is owned by `sv`, Readarr still owns `8787`, the unit is active, and the media directories have no changed files or timestamps caused by deployment.

### Task 3: Verify the live experience and security boundary

**Files:**
- No additional source files.

- [ ] **Step 1: Verify direct upstream pages**

  Request `/`, `/Books/`, and `/Audiobooks/` on `127.0.0.1:8090`; confirm the landing scene, catalog headings, metadata, and empty-state copy.

- [ ] **Step 2: Verify Caddy routes and no regressions**

  Request `https://readarr.basementnodes.ca/library`, `/library/`, `/library/Books/`, and `/library/Audiobooks/`; confirm `200` responses, correct content types, absolute shelf links, and no authentication challenge for LAN access. Confirm the Readarr root remains separate at `/`.

- [ ] **Step 3: Verify downloads and traversal protection**

  Create no permanent media fixtures. If a real file exists, issue a `HEAD` request through its `/library/Books/...` or `/library/Audiobooks/...` URL and confirm a successful file response. Request encoded traversal paths and confirm they cannot access the other root or arbitrary files.

- [ ] **Step 4: Verify responsive and accessible presentation**

  Inspect the live HTML for semantic headings, visible focus styles, reduced-motion handling, no external asset requests, and the exact “Awaiting new stock” text. Check desktop and narrow viewport rendering with JavaScript disabled as well as enabled.

- [ ] **Step 5: Record rollback and final state**

  Record the service unit, deployed paths, route statuses, unchanged media-root evidence, and the exact rollback command without changing Caddy, UFW, Fail2ban, or Readarr configuration.
