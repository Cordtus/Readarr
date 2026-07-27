# Library of Bex Readarr Request Desk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an in-theme, confirmation-based Library of Bex request desk that uses the configured Readarr instance for metadata lookup, library additions, and automatic searches.

**Architecture:** Keep the public library browser as the only web application. Add a focused standard-library Readarr client and an in-memory, expiring candidate store; the Python handler renders all pages and makes authenticated Readarr requests server-side. The existing media catalog paths and their traversal controls are unchanged.

**Tech Stack:** Python 3 standard library (`urllib.request`, `json`, `html`, `http.server`), `unittest`, existing Caddy/library-browser deployment.

---

## File structure

- Create `ops/library-browser/readarr.py`: configuration validation, HTTP client, response normalization, and short-lived candidate tokens.
- Modify `ops/library-browser/server.py`: add Readarr-aware construction, request routes, form parsing, and error-to-page handling.
- Modify `ops/library-browser/templates.py`: retain the reading-room visual system while rendering landing actions, request form/results/confirmation/success/error pages.
- Modify `ops/library-browser/test_server.py`: use a deterministic fake Readarr client and exercise HTTP routes plus media-path regression cases.
- Modify `ops/library-browser/run-library-browser.sh` and `ops/library-browser/README.md`: load a root-owned local configuration file without putting API credentials in Git or command lines, and document installation/rollback checks.

### Task 1: Add isolated Readarr client and candidate-token tests

**Files:**
- Create: `ops/library-browser/readarr.py`
- Create: `ops/library-browser/test_readarr.py`

- [ ] **Step 1: Write failing client/token tests**

```python
class CandidateStoreTest(unittest.TestCase):
    def test_token_is_single_use_and_expires(self):
        store = readarr.CandidateStore(ttl_seconds=60, clock=lambda: 100)
        token = store.put({"kind": "book", "foreignId": "book-1"})
        self.assertEqual(store.take(token), {"kind": "book", "foreignId": "book-1"})
        self.assertIsNone(store.take(token))

class ReadarrClientTest(unittest.TestCase):
    def test_search_sends_api_key_and_returns_safe_candidates(self):
        client = readarr.ReadarrClient("http://readarr:8787", "secret", opener=self.opener)
        candidates = client.search("A title")
        self.assertEqual(self.requests[0]["path"], "/api/v1/search?term=A+title")
        self.assertEqual(self.requests[0]["headers"]["X-Api-Key"], "secret")
        self.assertEqual(candidates[0].title, "A title")

    def test_add_request_preserves_readarr_add_options(self):
        outcome = self.client.request(self.book_candidate)
        self.assertEqual(self.requests[-1]["path"], "/api/v1/book")
        self.assertTrue(self.requests[-1]["json"]["addOptions"]["searchForNewBook"])
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python3 -m unittest ops/library-browser/test_readarr.py -v`

Expected: FAIL because module `readarr` and its client/token classes do not exist.

- [ ] **Step 3: Implement the minimal client contract**

```python
class ReadarrClient:
    def search(self, term):
        return self._request_json("GET", "/api/v1/search", {"term": term})

    def request(self, candidate):
        if candidate["kind"] == "author":
            payload = build_author_payload(candidate["resource"], self.settings)
            return self._request_json("POST", "/api/v1/author", payload)
        payload = build_book_payload(candidate["resource"], self.settings)
        return self._request_json("POST", "/api/v1/book", payload)
```

Implement `CandidateStore.put()` with `secrets.token_urlsafe(24)` and `take()` that removes the token before returning it. `ReadarrClient` must use `X-Api-Key`, a ten-second timeout, UTF-8 JSON, and a domain-specific `ReadarrError` that never includes the key. Copy Readarr’s established frontend payload rules: author adds set `addOptions.searchForMissingBooks = True`; book adds set `addOptions.searchForNewBook = True`, and add an author only when the lookup result has no stored author id. Read the configured root/profile/monitor values; do not invent IDs or paths.

- [ ] **Step 4: Run client tests to verify they pass**

Run: `python3 -m unittest ops/library-browser/test_readarr.py -v`

Expected: all client and token tests PASS.

- [ ] **Step 5: Commit the client slice**

```bash
git add ops/library-browser/readarr.py ops/library-browser/test_readarr.py
git commit -m "New: add Readarr request client"
```

### Task 2: Render themed request and unavailable-archives pages

**Files:**
- Modify: `ops/library-browser/templates.py`
- Modify: `ops/library-browser/test_server.py`

- [ ] **Step 1: Write failing template/route tests**

```python
def test_landing_has_request_link_and_honest_archives_state(self):
    response, body = self.request("GET", "/")
    self.assertEqual(response.status, 200)
    self.assertIn('/library/request/', body.decode())
    self.assertIn("The archives are not yet open to the public", body.decode())

def test_request_page_uses_existing_library_visual_language(self):
    response, body = self.request("GET", "/request/")
    self.assertEqual(response.status, 200)
    self.assertIn("Request a book", body.decode())
    self.assertIn("reading-room.webp", body.decode())
```

- [ ] **Step 2: Run the focused browser tests to verify they fail**

Run: `python3 -m unittest ops/library-browser/test_server.py -v`

Expected: FAIL because `/request/` is not routed and the landing page lacks the new copy/link.

- [ ] **Step 3: Add presentation helpers without a second visual system**

```python
def request_desk(message=None):
    return page("Request a book · The Library of Bex", REQUEST_FORM.format(message=escape(message or "")), body_class="request-page")

def archives_notice():
    return '<aside class="archives-notice"><strong>The archives</strong><p>The archives are not yet open to the public.</p></aside>'
```

Update `landing()` to include `/library/request/` and the unavailable archive notice. Reuse the existing walnut/copper/paper variables, serif heading treatment, focus selectors, mobile breakpoint, and reduced-motion rule. Keep copy semantic: one `<h1>`, labelled form controls, visibly styled submit button, and no fake archive link.

- [ ] **Step 4: Run focused browser tests to verify they pass**

Run: `python3 -m unittest ops/library-browser/test_server.py -v`

Expected: the landing, existing catalog, and request-page tests PASS.

- [ ] **Step 5: Commit the visual/request-shell slice**

```bash
git add ops/library-browser/templates.py ops/library-browser/test_server.py
git commit -m "New: add themed library request desk"
```

### Task 3: Add confirmation-gated request routes

**Files:**
- Modify: `ops/library-browser/server.py`
- Modify: `ops/library-browser/templates.py`
- Modify: `ops/library-browser/test_server.py`

- [ ] **Step 1: Write failing HTTP-flow tests with a fake client**

```python
def test_search_renders_escaped_readarr_results_without_mutating(self):
    response, body = self.request("GET", "/request/search/?term=A%20%3Ctitle%3E")
    self.assertEqual(response.status, 200)
    self.assertIn("A &lt;title&gt;", body.decode())
    self.assertEqual(self.fake_readarr.requests, [])

def test_confirmation_is_required_before_readarr_add(self):
    token = self.fake_readarr.store.put(self.fake_readarr.book_candidate)
    response, _ = self.request("GET", "/request/confirm/?token=" + quote(token))
    self.assertEqual(response.status, 200)
    self.assertEqual(self.fake_readarr.added, [])
    response, body = self.request("POST", "/request/confirm/", "token=" + quote(token))
    self.assertEqual(response.status, 200)
    self.assertEqual(self.fake_readarr.added, [self.fake_readarr.book_candidate])
    self.assertIn("Readarr accepted your request", body.decode())
```

- [ ] **Step 2: Run these tests to verify they fail**

Run: `python3 -m unittest ops/library-browser/test_server.py -v`

Expected: FAIL because request search/confirmation routes and POST parsing do not exist.

- [ ] **Step 3: Implement bounded GET and POST handlers**

```python
if request_path == "/request/":
    self.send_html(request_desk(), send_body)
elif request_path == "/request/search/":
    self.handle_request_search(query.get("term", [""])[0], send_body)
elif request_path == "/request/confirm/" and self.command == "POST":
    self.handle_request_confirmation(send_body)
```

Add `do_POST`, parse only `application/x-www-form-urlencoded` bodies capped at 8 KiB, and reject any route other than `/request/confirm/` with 404. Require a trimmed 2–200 character search term. Store full normalized Readarr candidates under short-lived opaque tokens; render tokens only in form actions. The GET confirmation consumes no token; POST atomically takes it, calls `ReadarrClient.request`, and renders success. A repeated/expired token renders a recovery page, never repeats a mutation. Map unreachable/invalid Readarr responses to a themed service-unavailable page and log only status/category, not request payloads or credentials.

- [ ] **Step 4: Run the flow tests and media-security regressions**

Run: `python3 -m unittest discover -s ops/library-browser -p 'test_*.py' -v`

Expected: all tests PASS, including symlink and traversal rejection tests.

- [ ] **Step 5: Commit the request-flow slice**

```bash
git add ops/library-browser/server.py ops/library-browser/templates.py ops/library-browser/test_server.py
git commit -m "New: route library requests through Readarr"
```

### Task 4: Configure and deploy without exposing credentials

**Files:**
- Modify: `ops/library-browser/server.py`
- Modify: `ops/library-browser/run-library-browser.sh`
- Modify: `ops/library-browser/README.md`

- [ ] **Step 1: Write the failing configuration tests**

```python
def test_missing_readarr_configuration_keeps_request_desk_read_only(self):
    response, body = self.request("GET", "/request/")
    self.assertEqual(response.status, 503)
    self.assertIn("request desk is being prepared", body.decode())

def test_api_key_file_is_not_exposed_by_argument_parser(self):
    args = server.parse_args(["--readarr-config", "/run/readarr-library/config.json"])
    self.assertEqual(args.readarr_config, "/run/readarr-library/config.json")
```

- [ ] **Step 2: Run configuration tests to verify they fail**

Run: `python3 -m unittest ops/library-browser/test_server.py -v`

Expected: FAIL because server configuration parsing/read-only mode is absent.

- [ ] **Step 3: Add file-based configuration and operational instructions**

```python
parser.add_argument("--readarr-config")
readarr_client = load_readarr_client(args.readarr_config) if args.readarr_config else None
server = create_server(args.host, args.port, books_root, audiobooks_root, readarr_client)
```

Use a `0600`, `sv`-readable JSON file outside the repository at `/home/sv/library-browser/readarr-request.json` with `url`, `apiKey`, `rootFolderPath`, `qualityProfileId`, `metadataProfileId`, `monitor`, and `monitorNewItems`. Update the watchdog to pass only `--readarr-config /home/sv/library-browser/readarr-request.json`; never put the secret in crontab, process arguments, output, or Git. Document exact safe deployment: preserve the old script, install the config through a protected channel, restart only the watchdog child, confirm `ps` has no key, and roll back by restoring the preceding server/script version while preserving media roots.

- [ ] **Step 4: Run all local checks**

Run: `python3 -m py_compile ops/library-browser/server.py ops/library-browser/readarr.py ops/library-browser/templates.py && python3 -m unittest discover -s ops/library-browser -p 'test_*.py' -v && git diff --check`

Expected: compilation succeeds, every test PASSes, and `git diff --check` is silent.

- [ ] **Step 5: Perform controlled live verification**

Run from the homeserver after configuration: `curl -fsS http://127.0.0.1:8090/request/ -o /dev/null && curl -fsS 'http://127.0.0.1:8090/request/search/?term=Agatha%20Christie' -o /tmp/readarr-library-request.html && grep -F 'Request a book' /tmp/readarr-library-request.html`

Expected: both requests return successfully and the search response is themed; inspect the response before using one explicit confirmation request. Confirm the Readarr command/add result in Readarr, then check Caddy `/library/` and `/library/request/`, ensuring no secret is in HTML, watchdog log, process list, or repository.

- [ ] **Step 6: Commit deployment guidance**

```bash
git add ops/library-browser/server.py ops/library-browser/run-library-browser.sh ops/library-browser/README.md ops/library-browser/test_server.py
git commit -m "Docs: configure Readarr request desk deployment"
```

## Plan self-review

- Spec coverage: Task 2 preserves the theme and unavailable archives state; Tasks 1 and 3 implement server-side Readarr lookup/add with confirmation and recoverable failures; Task 4 keeps credentials/configuration outside Git and requires local/live verification. Existing catalog and path safety are regression-tested in Task 3.
- Placeholder scan: no deferred implementation markers or unspecified error-handling steps remain.
- Type consistency: `ReadarrClient`, `CandidateStore`, candidate tokens, and request routes are defined before the handler and deployment tasks that consume them.
