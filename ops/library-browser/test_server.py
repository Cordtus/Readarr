import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

import server
import templates


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
        self.httpd = server.create_server(
            "127.0.0.1", 0, self.books, self.audiobooks
        )
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.connection = HTTPConnection("127.0.0.1", self.httpd.server_port)

    def tearDown(self):
        self.connection.close()
        self.httpd.shutdown()
        self.httpd.server_close()
        self.temp_dir.cleanup()

    def request(self, method, path):
        self.connection.request(method, path)
        response = self.connection.getresponse()
        body = response.read()
        return response, body

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

    def test_request_desk_uses_the_reading_room_system_and_a_labeled_post_form(self):
        html = templates.request_desk("A & <B>")

        self.assertIn("Request a book", html)
        self.assertIn("request-page", html)
        self.assertIn('action="/library/request/" method="post"', html)
        self.assertIn('<label for="request-query">', html)
        self.assertIn('id="request-query" name="query"', html)
        self.assertIn("A &amp; &lt;B&gt;", html)
        self.assertNotIn("A & <B>", html)

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
