# Library Bookcase Navigation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the landing navigation cards with an iPhone-first built-in bookcase that previews both media shelves and contains every request state.

**Architecture:** Keep the Python standard-library server and existing request URLs. Add a small preview model derived from the same safe catalog listing, then make every landing and request renderer use one shared reading-room/bookcase shell. Use semantic server-rendered controls for baseline behavior and a small inline progressive-enhancement script for pinned accordion state.

**Tech Stack:** Python 3 standard library, semantic HTML, native CSS and JavaScript, `unittest`, WebKit/Playwright for browser checks.

---

## File structure

- Modify `ops/library-browser/server.py`: derive safe shelf previews and pass them to every shell-rendering route.
- Modify `ops/library-browser/templates.py`: render the bookcase shell, request states, iOS-safe CSS, and progressive accordion behavior.
- Modify `ops/library-browser/test_server.py`: protect preview safety, shared-shell request states, semantics, no-JavaScript behavior, and iPhone requirements.
- Modify `ops/library-browser/README.md`: document the shared-shell deployment and mobile verification.

Testing in this plan must assert observable server, DOM, interaction, and
computed-browser behavior. Do not grep source files or assert CSS class names,
literal CSS declarations, script fragments, or arbitrary markup strings.
Remove nearby tests that do so instead of carrying those implementation locks
forward.

### Task 1: Safe dynamic shelf previews

**Files:**
- Modify: `ops/library-browser/server.py`
- Modify: `ops/library-browser/templates.py`
- Test: `ops/library-browser/test_server.py`

- [ ] **Step 1: Write failing preview behavior tests**

Add tests which create several catalog entries with deterministic timestamps,
request `/library/`, parse the response with `html.parser`, and assert the
observable preview model:

```python
self.assertEqual(books_preview.count, 3)
self.assertEqual(books_preview.entries, ["Newest.epub", "Nested Book.epub", "Oldest.epub"])
self.assertEqual(books_preview.destination, "/library/Books/")
self.assertNotIn("escape-target", books_preview.entries)
```

Also assert an empty Audiobooks root exposes an empty preview with no entries
and a usable `/library/Audiobooks/` destination. Use existing
symlink/traversal fixtures. Do not assert implementation-specific classes or
raw source text.

- [ ] **Step 2: Run the focused tests and verify the expected failures**

Run:

```sh
python3 -m unittest \
  test_server.LibraryBrowserTest.test_landing_previews_safe_recent_entries \
  test_server.LibraryBrowserTest.test_landing_preview_has_honest_empty_state -v
```

Expected: failures because `landing()` has no preview input and renders no
entry metadata.

- [ ] **Step 3: Implement one preview model from the safe catalog listing**

Have `server.py` reuse the existing root-bound entry listing to create:

```python
{
    "label": "Books",
    "href": "/library/Books/",
    "count": len(entries),
    "entries": entries[:3],
    "empty": "No volumes catalogued yet.",
}
```

Sort preview entries by modified time descending with deterministic name
tie-breaking. Never list a path that the catalog route would reject. Pass both
preview models into `templates.landing(...)`.

- [ ] **Step 4: Render semantic previews and rerun the focused tests**

Each shelf uses a real button for preview state and an `Open shelf` anchor for
navigation. Render count, up to three entry names, and the media-specific empty
copy. Run the focused tests and expect both to pass.

- [ ] **Step 5: Run the browser unit suite and commit**

Run:

```sh
python3 -m unittest discover -s ops/library-browser -p 'test_*.py' -v
```

Commit only the Task 1 files:

```sh
git add ops/library-browser/server.py ops/library-browser/templates.py ops/library-browser/test_server.py
git commit -m "New: add safe library shelf previews"
```

### Task 2: Shared bookcase shell and embedded request flow

**Files:**
- Modify: `ops/library-browser/server.py`
- Modify: `ops/library-browser/templates.py`
- Test: `ops/library-browser/test_server.py`

- [ ] **Step 1: Write failing shared-shell request tests**

Exercise request form, search results, confirmation, expired-token error, and
success through the HTTP server. Parse each response into shelf controls,
panels, forms, links, headings, and live regions. Assert that exactly one shelf
is expanded, every control references its panel, the request state is inside
the expanded request panel, and the expected form remains executable without
JavaScript:

```python
self.assertEqual(document.main_heading, "The Library of Bex")
self.assertEqual(document.expanded_shelves, ["request"])
self.assertEqual(document.forms[0].action, "/library/request/search/")
self.assertEqual(document.forms[0].method, "get")
self.assertEqual(document.live_region.role, "alert")
```

Preserve the existing mutation assertions: GET confirmation never adds, POST
adds exactly once, and a reused token cannot add again. Visible error and
success copy may be asserted where it is the user-facing outcome, but selectors,
class names, style rules, and source fragments are not test contracts.

- [ ] **Step 2: Run the request-flow tests and verify they fail**

Run:

```sh
python3 -m unittest \
  test_server.LibraryBrowserTest.test_request_desk_uses_shared_bookcase_shell \
  test_server.LibraryBrowserTest.test_search_results_remain_in_bookcase \
  test_server.LibraryBrowserTest.test_confirmation_post_requests_candidate_once -v
```

Expected: the request routes still render the separate `request-desk` page.

- [ ] **Step 3: Introduce a single shared shell renderer**

Create a private template helper with this stable contract:

```python
def library_shell(previews, *, active_shelf=None, request_content="", title="The Library of Bex"):
    ...
```

Use it for landing, request form, results, confirmation, success, and errors.
Keep all current request routes, form methods, origin checks, token handling,
and catalog URLs unchanged. The request form and all subsequent states live in
the request shelf panel. Put the archives status in a quiet bookcase footer,
not a separate card.

- [ ] **Step 4: Make preview data available to every request state**

Bind the safe preview provider into the handler and supply it to all request
renderers. Request failures must not stop Books or Audiobooks previews from
rendering. Keep direct request URLs and browser Back behavior valid without
JavaScript.

- [ ] **Step 5: Rerun focused and full tests, then commit**

Run the focused tests, then:

```sh
python3 -m unittest discover -s ops/library-browser -p 'test_*.py' -v
```

Commit:

```sh
git add ops/library-browser/server.py ops/library-browser/templates.py ops/library-browser/test_server.py
git commit -m "New: embed requests in library bookcase"
```

### Task 3: iPhone-first presentation and accessible motion

**Files:**
- Modify: `ops/library-browser/templates.py`
- Modify: `ops/library-browser/test_server.py`
- Modify: `ops/library-browser/README.md`

- [ ] **Step 1: Write failing semantic accordion tests**

Render the landing and request states, parse them with `html.parser`, and
verify shelf trigger IDs are unique and match panel `aria-labelledby` /
`aria-controls` relationships. Verify the request form exposes a visible label,
search input semantics, and submit control through parsed attributes:

```python
self.assertEqual(document.viewport["viewport-fit"], "cover")
self.assertEqual(document.control("books").controls, document.panel("books").id)
self.assertEqual(document.panel("books").labelledby, document.control("books").id)
self.assertEqual(document.search_input.type, "search")
self.assertEqual(document.search_input.enterkeyhint, "search")
```

Do not unit-test CSS by searching `PAGE_STYLE` or response text for property
names. Minimum font size, target size, overflow, safe-area padding, and media
query behavior belong to the WebKit verification in Task 4.

- [ ] **Step 2: Run the mobile contract tests and verify they fail**

Run the newly added test methods directly. Expected: failure because the old
viewport metadata and shelf semantics do not expose the accordion contract.

- [ ] **Step 3: Implement the built-in bookcase visual system**

Replace square card styling with a dark-wood cabinet integrated into the left
side of the reading-room scene. Integrate `A private collection` and `The
Library of Bex` into the cabinet plaque. Use horizontal shelf fronts and the
approved distinct copy. Do not include the rejected floating tagline.

On screens below 760px, keep a shallow room scene above a full-width,
normal-flow cabinet. Add:

```html
<meta name="viewport"
      content="width=device-width, initial-scale=1, viewport-fit=cover">
```

Use `max()` with `env(safe-area-inset-*)`, `100svh`/`100dvh` as progressive
enhancements, 16px form controls, 44px targets, no fixed background, and no
root overflow lock.

- [ ] **Step 4: Add restrained progressive accordion behavior**

Use a small inline script that toggles only classes, `aria-expanded`, and the
`hidden` state. One touch/click-pinned shelf is open at a time. Restrict
temporary hover previews to fine pointers in CSS. Animate only inner opacity
and translate over 220-320ms with a custom decelerating curve; exits are
quieter. Reduced motion and reduced transparency produce immediate, solid
states. The page remains fully navigable and request forms remain functional
when the script does not execute.

- [ ] **Step 5: Document and verify**

Update `README.md` with WebKit viewport checks, real-iPhone acceptance, and
rollback notes. Run:

```sh
python3 -m py_compile ops/library-browser/server.py ops/library-browser/readarr.py ops/library-browser/templates.py
python3 -m unittest discover -s ops/library-browser -p 'test_*.py' -v
sh -n ops/library-browser/run-library-browser.sh
git diff --check
```

Commit:

```sh
git add ops/library-browser/templates.py ops/library-browser/test_server.py ops/library-browser/README.md
git commit -m "New: add responsive library bookcase"
```

### Task 4: Review, deploy, and verify live behavior

**Files:**
- Deploy: `/home/sv/library-browser/server.py`
- Deploy: `/home/sv/library-browser/readarr.py`
- Deploy: `/home/sv/library-browser/templates.py`
- Deploy: `/home/sv/library-browser/assets/reading-room.webp`
- Deploy: `/home/sv/library-browser/run-library-browser.sh`
- Preserve: `/home/sv/library-browser/readarr-request.json`

- [ ] **Step 1: Run spec and code-quality review**

Review the complete diff against
`docs/superpowers/specs/2026-07-28-library-bookcase-navigation-design.md`.
Resolve all findings, rerun the full verification command, and record the final
commit SHA.

- [ ] **Step 2: Capture the live pre-deploy state**

Record the current watchdog and child PIDs, listener, checksums, media-root
stats, Caddy route status, and protected config mode. Create a timestamped
runtime backup under `/home/sv/library-browser/backups/` without touching
either media root.

- [ ] **Step 3: Deploy the complete runtime bundle**

Stage all runtime files in a private temporary directory, atomically replace
the bundle, preserve `readarr-request.json`, terminate exactly the verified
watchdog PID, and let the existing cron supervisor start one replacement.

- [ ] **Step 4: Verify live desktop, mobile, and request behavior**

Verify:

```sh
curl -fsS https://readarr.basementnodes.ca/library/
curl -fsS https://readarr.basementnodes.ca/library/request/
curl -fsS 'https://readarr.basementnodes.ca/library/request/search/?term=Pride%20and%20Prejudice'
```

Confirm 200 responses, the bookcase shell, non-empty request candidates, no
rejected tagline, no credential in HTML/process/logs, one listener, unchanged
media roots, and passing Caddy upstream checks. Use Playwright WebKit at 393 by
852 and 430 by 932, portrait and landscape, to check no overflow, visible form
focus, accordion interaction, 44px computed targets, 16px computed form text,
safe-area padding, and reduced-motion operation. These are browser assertions,
not source-text checks.

- [ ] **Step 5: Push the verified branch**

Push `codex/library-readarr-request` to `cordtus` and report the live URL,
backup path, verification counts, commit SHA, and any check that still requires
a physical iPhone.

## Plan self-review

- Spec coverage: Tasks 1-3 cover previews, the shared request shell, visual
  composition, motion, accessibility, and all iPhone requirements. Task 4
  covers controlled deployment, rollback, and live verification.
- Placeholder scan: all steps name exact files, behavior, commands, expected
  outcomes, and rollback boundaries.
- Type consistency: `library_shell`, preview dictionaries, shelf identifiers,
  and request-state inputs are introduced before all consumers.
