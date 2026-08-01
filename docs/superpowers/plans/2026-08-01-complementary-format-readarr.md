# Complementary Format Readarr Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track Audio and Written editions in independent Readarr catalogues and let the library request desk fetch the missing format without weakening MAM sharing rules.

**Architecture:** The current host Readarr continues to own Audio and `/plex/Audiobooks`. A new unprivileged `readarr-books` LXD container owns Written books and an idmapped `/plex/Books` mount. The library-browser changes from one multi-root Readarr client to two independently authenticated target clients, merges their search results by foreign book ID, and routes every add/release/grab token back to its origin target.

**Tech Stack:** Python 3 standard library HTTP server and `unittest`; Readarr .NET 6 runtime/API; LXD on the homeserver; Deluge download client; MAM through the existing interactive indexer route.

---

## File map

- Modify: `ops/library-browser/readarr.py` — target-local Readarr client state and release metadata normalization.
- Modify: `ops/library-browser/server.py` — protected two-target configuration loading, merged search handling, target-aware tokens.
- Modify: `ops/library-browser/templates.py` — Audio/Written presence and complementary-fetch actions; current VIP-freeleech label only when supplied by upstream metadata.
- Modify: `ops/library-browser/test_readarr.py` — client request and release-metadata behaviour.
- Modify: `ops/library-browser/test_server.py` — cross-catalogue result, action, failure, and token-flow behaviour.
- Modify: `ops/library-browser/README.md` — two-instance protected-config schema, safe deployment/rollback, and MAM retention rules.
- Create: `ops/library-browser/scripts/probe-mam-release-metadata.py` — sanitized, read-only runtime probe that reports only the non-secret release fields required to determine whether VIP/freeleech status is available through Readarr.
- Create: `ops/library-browser/scripts/provision-readarr-books.fish` — idempotent homeserver LXD and service provisioning commands, with no credentials embedded.
- Create: `ops/library-browser/scripts/verify-readarr-books.fish` — read-only live checks for instance boundaries, service state, root access, API reachability, and Deluge retention.

### Task 1: Preserve MAM retention and establish the release-metadata boundary

**Files:**
- Create: `ops/library-browser/scripts/probe-mam-release-metadata.py`
- Modify: `ops/library-browser/test_readarr.py`
- Modify: `ops/library-browser/README.md`

- [ ] **Step 1: Write the failing contract test for optional tracker metadata**

```python
def test_release_keeps_explicit_upstream_freeleech_metadata_only():
    self.responses.append(FakeResponse(200, [{
        "guid": "mam-guid", "indexerId": 7, "title": "A title",
        "size": 1, "downloadAllowed": True, "freeleech": True,
    }]))

    release = self.client.search_releases(99)[0]

    self.assertTrue(release.freeleech)
```

Behavior: a release explicitly marked freeleech by the upstream response retains that fact for display. Oracle: current tracker entitlement must never be guessed from a title. Plausible wrong implementation: infer freeleech from an arbitrary MAM title. Observable assertion: `release.freeleech` is true only for the explicit field. Layer: client unit test because it observes the HTTP normalization boundary.

- [ ] **Step 2: Run the test and confirm it fails because `Release` has no `freeleech` field**

Run: `python3 -m unittest ops.library-browser.test_readarr.ReadarrClientTest.test_release_keeps_explicit_upstream_freeleech_metadata_only`

Expected: FAIL with the missing field assertion.

- [ ] **Step 3: Implement minimal optional metadata normalization**

```python
@dataclass(frozen=True)
class Release:
    guid: str
    indexer_id: int
    title: str
    size: int
    download_allowed: bool
    freeleech: bool = False

# in _normalize_release
freeleech = item.get("freeleech", False)
if not isinstance(freeleech, bool):
    raise ReadarrError("Readarr returned an invalid release")
return Release(guid, indexer_id, title, size, download_allowed, freeleech)
```

- [ ] **Step 4: Run focused client tests**

Run: `python3 -m unittest ops.library-browser.test_readarr`

Expected: PASS. The existing release identity and no-download-URL assertions remain intact.

- [ ] **Step 5: Add and run the sanitized live capability probe**

The probe must load the protected browser configuration only on the homeserver, use one existing Readarr book ID supplied on stdin, and print only JSON keys/types from the release payload—never URL, API key, cookie, GUID, download URL, title, or tracker passkey. It exits nonzero if no explicit boolean freeleech/VIP field is present.

Run: `python3 ops/library-browser/scripts/probe-mam-release-metadata.py`

Expected: either an explicit supported metadata key or a clean unsupported result. Do not add a VIP/freeleech UI label if the result is unsupported.

- [ ] **Step 6: Document the proven retention setting**

State that the MAM Deluge client uses `RemoveCompletedDownloads: false`; retain that setting in the new catalogue. State that the unrelated SABnzbd removal setting is not evidence about MAM torrents.

- [ ] **Step 7: Commit**

Run: `git add ops/library-browser/readarr.py ops/library-browser/test_readarr.py ops/library-browser/scripts/probe-mam-release-metadata.py ops/library-browser/README.md && git commit -m "New: preserve MAM release metadata"`

### Task 2: Provision the isolated Written Readarr catalogue

**Files:**
- Create: `ops/library-browser/scripts/provision-readarr-books.fish`
- Create: `ops/library-browser/scripts/verify-readarr-books.fish`
- Modify: `ops/library-browser/README.md`

- [ ] **Step 1: Create the dry-run assertions before provisioning**

`verify-readarr-books.fish` must fail unless all of these are true: `readarr-books` is an unprivileged container on `lxdbr1`; it has a fixed unused address; its root disk is limited to 20GiB; its CPU/memory limits are 2/2GiB; it has an idmapped `/plex/Books` disk only; it does not have `/plex/Audiobooks`; Readarr listens only on the private LXD address; its Deluge client has `RemoveCompletedDownloads: false`; its configured root folder is `/plex/Books`.

```fish
set -l instance readarr-books
set -l lxc /snap/bin/lxc
$lxc info $instance >/dev/null; or exit 1
$lxc config show $instance --expanded | string match -rq 'source: /plex/Books'; or exit 1
not $lxc config show $instance --expanded | string match -rq '/plex/Audiobooks'; or exit 1
```

Behavior: the Written catalogue cannot see or import into the Audio tree. Oracle: approved container boundary. Plausible wrong implementation: mount both roots or omit idmapping. Observable assertion: expanded LXD config has exactly the intended media mount. Layer: live configuration check because the risk is an LXD mount boundary.

- [ ] **Step 2: Run the verification script before provisioning**

Run: `fish ops/library-browser/scripts/verify-readarr-books.fish`

Expected: FAIL because `readarr-books` does not exist.

- [ ] **Step 3: Implement idempotent Fish provisioning**

The script must launch `images:debian/12` only if the instance does not exist, then apply:

```fish
set -l lxc /snap/bin/lxc
$lxc config set readarr-books limits.cpu 2
$lxc config set readarr-books limits.memory 2GiB
$lxc config set readarr-books boot.autostart true
$lxc config device override readarr-books root size=20GiB
$lxc config device set readarr-books eth0 ipv4.address 10.114.28.186
$lxc config device add readarr-books books disk source=/plex/Books path=/plex/Books shift=true
```

Inside the container, install only the shared-library runtime dependencies needed by the existing Readarr publish, create the `readarr` service account, copy the already-proven host Readarr application bundle without copying host data/configuration, create a new `/var/lib/readarr` data directory, and install a `readarr-books.service` that binds `10.114.28.186:8787`.

Do not copy host `readarr.db`, download-client passwords, indexer credentials, API keys, Caddy configuration, or either media root. Configure the instance interactively through its local API only after the operator supplies credentials into the container; set only `/plex/Books` as its root folder, its Written quality profile, the existing Deluge client, and `RemoveCompletedDownloads: false`.

- [ ] **Step 4: Run provisioning and wait for readiness**

Run: `fish ops/library-browser/scripts/provision-readarr-books.fish`

Expected: one running container, a health response from `http://10.114.28.186:8787`, and no public LXD proxy device.

- [ ] **Step 5: Run live boundary verification**

Run: `fish ops/library-browser/scripts/verify-readarr-books.fish`

Expected: PASS for every boundary and retention assertion.

- [ ] **Step 6: Record rollback**

Document that rollback stops and deletes only `readarr-books`; it never removes `/plex/Books`, the host Audio Readarr data, host Deluge data, or the existing library-browser release. Take an LXD snapshot immediately after healthy service configuration.

- [ ] **Step 7: Commit**

Run: `git add ops/library-browser/scripts/provision-readarr-books.fish ops/library-browser/scripts/verify-readarr-books.fish ops/library-browser/README.md && git commit -m "New: provision written Readarr catalogue"`

### Task 3: Make browser targets independent and merge complementary-format state

**Files:**
- Modify: `ops/library-browser/readarr.py`
- Modify: `ops/library-browser/server.py`
- Modify: `ops/library-browser/templates.py`
- Modify: `ops/library-browser/test_readarr.py`
- Modify: `ops/library-browser/test_server.py`

- [ ] **Step 1: Write server regression tests for the four visible title states**

```python
def test_audio_only_book_offers_fetch_written(self):
    self.audio_client.candidates = [existing_book("book-1")]
    self.books_client.candidates = [new_book("book-1")]

    response, body = self.request("GET", "/request/search/?term=Example")

    self.assertEqual(response.status, 200)
    self.assertIn("In Readarr: Audio", body.decode())
    self.assertIn("Fetch Written", body.decode())
```

Create matching cases for Written-only (`Fetch Audio`), both formats (no fetch action), and an unavailable target (the other target's result remains visible with a safe format-check warning).

Behavior: the user can request only the format absent from that catalogue. Oracle: approved complementary-format workflow. Plausible wrong implementation: block every existing title or offer a duplicate for an already-present format. Observable assertion: labelled action and its target-local token. Layer: HTTP server test because it observes the browser contract.

- [ ] **Step 2: Run the focused server tests and confirm failures**

Run: `python3 -m unittest ops.library-browser.test_server.LibraryServerTest.test_audio_only_book_offers_fetch_written`

Expected: FAIL because the current request client has one shared endpoint and existing books receive no token.

- [ ] **Step 3: Replace shared configuration with target-local clients**

Parse protected configuration as:

```json
{
  "targets": {
    "audiobooks": {"url": "...", "apiKey": "...", "rootFolderPath": "..."},
    "books": {"url": "...", "apiKey": "...", "rootFolderPath": "..."}
  }
}
```

Construct one `ReadarrClient` per target. Keep the existing strict target-name set, URL validation, API-key validation, and single-use token store. Merge book candidates by `foreign_id`; retain separate target-local candidate copies so confirmation, release lookup, and grab can never cross catalogue boundaries.

- [ ] **Step 4: Render format state and actions without adding a duplicate request path**

For an Audio-only match render `In Readarr: Audio` with a `Fetch Written` POST form containing the Books candidate token. For Written-only render the inverse. For both render `In Readarr: Audio and Written` and no book action. Preserve author handling, current default scope picker, escape rules, close control, and the existing explicit confirmation/release steps.

If Task 1 proved explicit upstream freeleech metadata, render `VIP freeleech while VIP is active` only for that boolean; otherwise do not add a VIP label.

- [ ] **Step 5: Run focused suites**

Run: `python3 -m unittest ops.library-browser.test_readarr ops.library-browser.test_server`

Expected: PASS, including token expiry, same-origin enforcement, no automatic release grab, and all four format states.

- [ ] **Step 6: Commit**

Run: `git add ops/library-browser/readarr.py ops/library-browser/server.py ops/library-browser/templates.py ops/library-browser/test_readarr.py ops/library-browser/test_server.py && git commit -m "New: request complementary book formats"`

### Task 4: Deploy and verify the assembled system

**Files:**
- Modify: `ops/library-browser/README.md`
- Test: `ops/library-browser/test_server.py`

- [ ] **Step 1: Update protected runtime configuration manually on the homeserver**

Keep `/home/sv/library-browser/readarr-request.json` mode `0600` and owned by `sv`. Add the Books instance URL/API key only there. Do not print it, commit it, or place it in a process argument.

- [ ] **Step 2: Create an immutable browser release and preserve rollback**

Copy only `server.py`, `readarr.py`, `templates.py`, assets, and the watchdog script into a new `/home/sv/library-browser/releases/<commit>-complementary-formats` directory; atomically repoint `current`; preserve the old target path in the deployment rollback record; restart exactly one watchdog.

- [ ] **Step 3: Run code and live verification**

Run: `python3 -m unittest ops.library-browser.test_readarr ops.library-browser.test_server`

Run: `fish ops/library-browser/scripts/verify-readarr-books.fish`

Run read-only browser checks for an Audio-only title, Written-only title, and a title absent from both. Confirm the release-selection screen states the correct target and does not grab a release before the explicit POST.

- [ ] **Step 4: Verify import and sharing boundaries**

For one manually selected Written release, prove its resulting file is under `/plex/Books`, its audio counterpart is not changed, the Books shelf lists the imported author folder, and the Deluge torrent remains present after Readarr imports the file. For an Audio release, prove Plex’s Music library records the imported path. Do not claim Plex handles Written books unless a Plex library is explicitly configured for them.

- [ ] **Step 5: Commit deployment documentation**

Run: `git add ops/library-browser/README.md && git commit -m "Docs: deploy complementary format requests"`

### Task 5: Explicit MAM wedge capability follow-up

**Files:**
- Modify: `docs/superpowers/specs/2026-08-01-complementary-format-readarr-design.md`
- Create only after an authenticated, documented tracker operation exists: `ops/library-browser/mam.py`
- Test only after that module exists: `ops/library-browser/test_mam.py`

- [ ] **Step 1: Require an exact documented MAM operation before code**

Capture the tracker endpoint, authentication mechanism, CSRF requirement, selected torrent identifier, current wedge balance, cost, and response semantics without copying session cookies or passkeys into the repository. If any item is unavailable, record "unsupported" in the spec and stop this task.

- [ ] **Step 2: Define the test intent before implementation**

Behavior: after the reader chooses one release and explicitly confirms the shown MAM torrent ID and wedge cost, the system sends exactly the documented wedge operation once. Oracle: documented MAM transaction contract. Plausible wrong implementation: spend a wedge on a similarly titled torrent, a VIP-freeleech release, or a double-click. Observable assertion: the fake tracker receives only the selected ID after confirmation. Layer: adapter integration test because it is an authenticated HTTP boundary.

- [ ] **Step 3: Do not deploy a transaction feature without live preview acceptance**

The live page must show the exact torrent ID and cost before a final confirmation; the no-confirmation path must make no tracker call. A successful test with a fake tracker is necessary but not sufficient for authorizing a real point spend.
