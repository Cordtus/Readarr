import os
import tempfile
import threading
import urllib.parse
import unittest
from http.client import HTTPConnection
from pathlib import Path

import readarr
import server
import templates


class FakeReadarrClient:
    def __init__(self):
        self.candidates = [
            readarr.Candidate(
                kind="book",
                foreign_id="book-1",
                title="A <dangerous> title",
                author_name="Author & Co.",
                is_existing=False,
                lookup={"book": {"foreignBookId": "book-1"}},
            )
        ]
        self.searches = []
        self.requests = []

    def search(self, term):
        self.searches.append(term)
        return self.candidates

    def request(self, candidate):
        self.requests.append(candidate)
        return {"id": 1}


class FakeExpiringCandidateStore:
    def __init__(self):
        self.now = 0
        self.candidates = {}

    def put(self, candidate):
        self.candidates["candidate-token"] = (self.now + 60, candidate)
        return "candidate-token"

    def peek(self, token):
        entry = self.candidates.get(token)
        if entry is None or self.now >= entry[0]:
            self.candidates.pop(token, None)
            return None
        return entry[1]

    def take(self, token):
        candidate = self.peek(token)
        self.candidates.pop(token, None)
        return candidate


class LibraryBrowserTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.books = root / "Books"
        self.audiobooks = root / "Audiobooks"
        self.books.mkdir()
        self.audiobooks.mkdir()
        (self.books / "The <Book>.epub").write_bytes(b"book content")
        series = self.books / "Series <A>"
        series.mkdir()
        (series / "Nested Book.epub").write_bytes(b"nested book")
        self.readarr_client = FakeReadarrClient()
        self.start_server(self.readarr_client)

    def start_server(self, readarr_client, candidate_store=None):
        self.httpd = server.create_server(
            "127.0.0.1",
            0,
            self.books,
            self.audiobooks,
            readarr_client=readarr_client,
            candidate_store=candidate_store,
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.connection = HTTPConnection("127.0.0.1", self.httpd.server_port)

    def tearDown(self):
        self.connection.close()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.temp_dir.cleanup()

    def restart_server(self, readarr_client, candidate_store=None):
        self.connection.close()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.start_server(readarr_client, candidate_store)

    def request(self, method, path, body=None, headers=None):
        self.connection.request(method, path, body=body, headers=headers or {})
        response = self.connection.getresponse()
        body = response.read()
        return response, body

    def search_for_candidate(self):
        response, body = self.request(
            "GET", "/library/request/search/?term=" + urllib.parse.quote("Dangerous title")
        )
        self.assertEqual(response.status, 200)
        token = body.decode().split('name="token" value="', 1)[1].split('"', 1)[0]
        return token, body.decode()

    def test_landing_page_has_local_scene_shelves_and_request_desk_link(self):
        response, body = self.request("GET", "/")
        html = body.decode()

        self.assertEqual(response.status, 200)
        self.assertIn("The Library of Bex", html)
        self.assertIn("/library/Books/", html)
        self.assertIn("/library/Audiobooks/", html)
        self.assertIn('href="/library/request/"', html)
        self.assertIn("The archives are not yet open to the public", html)
        self.assertIn("reading-room.webp", html)

    def test_request_desk_uses_the_reading_room_system_and_a_labeled_search_form(self):
        html = templates.request_desk("A & <B>")

        self.assertIn("Request a book", html)
        self.assertIn("request-page", html)
        self.assertIn('action="/library/request/search/" method="get"', html)
        self.assertIn('<label for="request-query">', html)
        self.assertIn('id="request-query" name="term"', html)
        self.assertIn('type="submit">Search the catalogue</button>', html)
        self.assertIn("A &amp; &lt;B&gt;", html)
        self.assertNotIn("A & <B>", html)

        confirmation_html = templates.request_confirmation(
            FakeReadarrClient().candidates[0], "opaque-token"
        )

        self.assertIn('action="/library/request/confirm/" method="post"', confirmation_html)
        self.assertIn('name="token" value="opaque-token"', confirmation_html)
        self.assertIn('type="submit">Confirm request</button>', confirmation_html)

    def test_search_renders_escaped_candidate_without_mutating_readarr(self):
        token, html = self.search_for_candidate()

        self.assertTrue(token)
        self.assertEqual(self.readarr_client.searches, ["Dangerous title"])
        self.assertEqual(self.readarr_client.requests, [])
        self.assertIn("A &lt;dangerous&gt; title", html)
        self.assertIn("Author &amp; Co.", html)
        self.assertNotIn("A <dangerous> title", html)

    def test_confirmation_get_does_not_mutate_readarr(self):
        token, _ = self.search_for_candidate()

        response, body = self.request("GET", "/request/confirm/?token=" + urllib.parse.quote(token))

        self.assertEqual(response.status, 200)
        self.assertIn("Confirm request", body.decode())
        self.assertIn("A &lt;dangerous&gt; title", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_expired_confirmation_preview_is_rejected_without_mutating_readarr(self):
        candidate_store = FakeExpiringCandidateStore()
        self.restart_server(self.readarr_client, candidate_store)
        token, _ = self.search_for_candidate()
        candidate_store.now = 60

        response, body = self.request("GET", "/request/confirm/?token=" + token)

        self.assertEqual(response.status, 400)
        self.assertIn("no longer available", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_confirmation_post_requests_candidate_once(self):
        token, _ = self.search_for_candidate()
        body = urllib.parse.urlencode({"token": token}).encode()

        response, response_body = self.request(
            "POST",
            "/library/request/confirm/",
            body,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(response.status, 200)
        self.assertIn("Readarr accepted your request.", response_body.decode())
        self.assertEqual(self.readarr_client.requests, self.readarr_client.candidates)

    def test_reused_confirmation_token_cannot_request_again(self):
        token, _ = self.search_for_candidate()
        body = urllib.parse.urlencode({"token": token}).encode()

        self.request(
            "POST",
            "/request/confirm/",
            body,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )
        response, response_body = self.request(
            "POST",
            "/request/confirm/",
            body,
            {"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(response.status, 400)
        self.assertIn("no longer available", response_body.decode())
        self.assertEqual(self.readarr_client.requests, self.readarr_client.candidates)

    def test_request_routes_reject_bad_term_missing_configuration_and_non_form_post(self):
        response, body = self.request("GET", "/request/search/?term=x")

        self.assertEqual(response.status, 400)
        self.assertIn("between 2 and 200 characters", body.decode())
        self.assertEqual(self.readarr_client.searches, [])

        self.restart_server(None)
        response, body = self.request("GET", "/library/request/")

        self.assertEqual(response.status, 503)
        self.assertIn("unavailable", body.decode())

        self.restart_server(self.readarr_client)
        response, body = self.request(
            "POST", "/request/confirm/", b'{"token":"not-a-form"}', {"Content-Type": "application/json"}
        )

        self.assertEqual(response.status, 415)
        self.assertIn("form", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_malformed_urlencoded_confirmation_is_rejected(self):
        response, body = self.request(
            "POST",
            "/request/confirm/",
            b"token",
            {"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(response.status, 400)
        self.assertIn("Invalid request form", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_oversized_confirmation_form_is_rejected(self):
        response, body = self.request(
            "POST",
            "/request/confirm/",
            b"token=" + (b"a" * (8 * 1024)),
            {"Content-Type": "application/x-www-form-urlencoded"},
        )

        self.assertEqual(response.status, 413)
        self.assertIn("Request form too large", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_books_catalog_escapes_names_and_exposes_metadata(self):
        response, body = self.request("GET", "/Books/")
        html = body.decode()

        self.assertEqual(response.status, 200)
        self.assertIn("Books", html)
        self.assertIn("2 items", html)
        self.assertIn("The &lt;Book&gt;.epub", html)
        self.assertNotIn("The <Book>.epub", html)
        self.assertIn("/library/Books/The%20%3CBook%3E.epub", html)
        self.assertIn("/library/Books/Series%20%3CA%3E/", html)
        self.assertIn("UTC", html)

    def test_empty_audiobooks_catalog_uses_exact_empty_state(self):
        response, body = self.request("GET", "/Audiobooks/")

        self.assertEqual(response.status, 200)
        self.assertIn("Awaiting new stock", body.decode())

    def test_audiobooks_catalog_uses_warm_audio_theme(self):
        (self.audiobooks / "A listening tale.m4b").write_bytes(b"audio")

        response, body = self.request("GET", "/Audiobooks/")
        html = body.decode()

        self.assertEqual(response.status, 200)
        self.assertIn("audio-catalog", html)
        self.assertIn("--catalog-accent: var(--copper)", html)
        self.assertIn("audio-detail", html)
        self.assertIn("A listening tale.m4b", html)

    def test_catalog_excludes_escaping_symlinks_but_keeps_in_root_symlinks(self):
        outside = Path(self.temp_dir.name) / "outside"
        outside.mkdir()
        in_root_link = self.books / "In-root alias.epub"
        escaping_link = self.books / "Escaping shelf"
        try:
            in_root_link.symlink_to(self.books / "The <Book>.epub")
            escaping_link.symlink_to(outside, target_is_directory=True)
        except (NotImplementedError, OSError):
            self.skipTest("symlinks are not supported")

        response, body = self.request("GET", "/Books/")
        html = body.decode()

        self.assertEqual(response.status, 200)
        self.assertIn("In-root alias.epub", html)
        self.assertNotIn("Escaping shelf", html)

    def test_open_directory_link_renders_nested_catalog_with_shelf_breadcrumb(self):
        response, body = self.request("GET", "/Books/Series%20%3CA%3E/")
        html = body.decode()

        self.assertEqual(response.status, 200)
        self.assertIn("Series &lt;A&gt;", html)
        self.assertIn("Nested Book.epub", html)
        self.assertIn('href="/library/Books/"', html)
        self.assertIn("/library/Books/Series%20%3CA%3E/Nested%20Book.epub", html)

    def test_nested_directory_traversal_is_rejected(self):
        response, body = self.request(
            "GET", "/Books/Series%20%3CA%3E/%2e%2e/%2e%2e/etc/passwd"
        )

        self.assertIn(response.status, (403, 404))
        self.assertNotIn(b"book content", body)

    def test_library_prefix_is_accepted_for_transparent_reverse_proxy(self):
        response, body = self.request("GET", "/library/Books/")

        self.assertEqual(response.status, 200)
        self.assertIn("Books", body.decode())

    def test_known_file_is_downloadable(self):
        response, body = self.request("GET", "/Books/The%20%3CBook%3E.epub")

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "application/epub+zip")
        self.assertEqual(body, b"book content")

    def test_head_returns_file_metadata_without_body(self):
        response, body = self.request("HEAD", "/Books/The%20%3CBook%3E.epub")

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"")
        self.assertEqual(int(response.getheader("Content-Length")), 12)

    def test_traversal_cannot_cross_media_root_or_escape_it(self):
        for path in ("/Books/../Audiobooks/", "/Books/%2e%2e/%2e%2e/etc/passwd"):
            response, body = self.request("GET", path)

            self.assertIn(response.status, (403, 404))
            self.assertNotIn(b"book content", body)


if __name__ == "__main__":
    unittest.main()
