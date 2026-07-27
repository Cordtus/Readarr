import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

import server


class LibraryBrowserTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.books = root / "Books"
        self.audiobooks = root / "Audiobooks"
        self.books.mkdir()
        self.audiobooks.mkdir()
        (self.books / "The <Book>.epub").write_bytes(b"book content")
        (self.books / "Series <A>").mkdir()
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

    def test_landing_page_has_local_scene_and_absolute_shelf_links(self):
        response, body = self.request("GET", "/")
        html = body.decode()

        self.assertEqual(response.status, 200)
        self.assertIn("The Library of Bex", html)
        self.assertIn("/library/Books/", html)
        self.assertIn("/library/Audiobooks/", html)
        self.assertIn("reading-room.webp", html)

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
