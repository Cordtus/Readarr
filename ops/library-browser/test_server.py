import os
import json
import io
import dataclasses
import socket
import tempfile
import threading
import urllib.parse
import unittest
from contextlib import redirect_stderr
from html.parser import HTMLParser
from unittest import mock
from http.client import HTTPConnection
from pathlib import Path

import readarr
import server


READARR_REQUEST_CONFIG = {
    "url": "https://readarr.example.test",
    "apiKey": "test-readarr-api-key",
    "targets": {
        "audiobooks": {
            "rootFolderPath": "/plex/Audiobooks",
            "qualityProfileId": 2,
            "metadataProfileId": 1,
            "monitor": "all",
            "monitorNewItems": "all",
        },
        "books": {
            "rootFolderPath": "/plex/Books",
            "qualityProfileId": 1,
            "metadataProfileId": 1,
            "monitor": "all",
            "monitorNewItems": "all",
        },
    },
}


class HtmlElement:
    def __init__(self, tag, attributes=None, parent=None):
        self.tag = tag
        self.attributes = dict(attributes or ())
        self.parent = parent
        self.children = []
        self.text = []

    def descendants(self, tag=None, **attributes):
        matches = []
        for child in self.children:
            if (
                (tag is None or child.tag == tag)
                and all(child.attributes.get(name) == value for name, value in attributes.items())
            ):
                matches.append(child)
            matches.extend(child.descendants(tag, **attributes))
        return matches

    def text_content(self):
        parts = list(self.text)
        for child in self.children:
            parts.append(child.text_content())
        return " ".join(" ".join(parts).split())


class HtmlDocumentParser(HTMLParser):
    VOID_ELEMENTS = {"meta", "link", "input", "img", "br", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = HtmlElement("document")
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        element = HtmlElement(tag, attrs, self.current)
        self.current.children.append(element)
        if tag not in self.VOID_ELEMENTS:
            self.current = element

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(HtmlElement(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent

    def handle_data(self, data):
        if data.strip():
            self.current.text.append(data)


def parse_html(document):
    parser = HtmlDocumentParser()
    parser.feed(document)
    parser.close()
    return parser.root


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
        self.adds = []
        self.release_searches = []
        self.grabs = []
        self.releases = [
            readarr.Release(
                guid="release-1",
                indexer_id=7,
                title="A dangerous title - Unabridged",
                size=123456789,
                download_allowed=True,
            ),
            readarr.Release(
                guid="release-2",
                indexer_id=8,
                title="A dangerous title - MP3",
                size=234567890,
                download_allowed=True,
            ),
        ]

    def search(self, term, target):
        self.searches.append((term, target))
        return [
            dataclasses.replace(candidate, target=target)
            for candidate in self.candidates
        ]

    def add(self, candidate):
        self.adds.append(candidate)
        self.requests.append(candidate)
        return {"id": 1}

    def request(self, candidate):
        return self.add(candidate)

    def search_releases(self, book_id):
        self.release_searches.append(book_id)
        return self.releases

    def grab_release(self, release, book_id):
        self.grabs.append((release, book_id))
        return {"guid": release.guid, "indexerId": release.indexer_id}


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


class FakeCandidateStore:
    def __init__(self):
        self.candidates = {}
        self.next_token = 0

    def put(self, candidate):
        self.next_token += 1
        token = "candidate-{}".format(self.next_token)
        self.candidates[token] = candidate
        return token

    def take(self, token):
        return self.candidates.pop(token, None)

    def discard(self, token):
        self.candidates.pop(token, None)


class RecordingCandidateStore:
    def __init__(self, clock):
        self._store = readarr.CandidateStore(ttl_seconds=120, clock=clock)
        self.last_token = None

    def put(self, candidate):
        self.last_token = self._store.put(candidate)
        return self.last_token

    def take(self, token):
        return self._store.take(token)

    def discard(self, token):
        self._store.discard(token)


class FakeTimer:
    timers = []

    def __init__(self, delay, callback, args=None, kwargs=None):
        self.delay = delay
        self.callback = lambda: callback(*(args or ()), **(kwargs or {}))
        self.cancelled = False
        self.started = False

    def start(self):
        self.started = True
        self.timers.append(self)

    def cancel(self):
        self.cancelled = True

    @classmethod
    def run_due(cls, now):
        for timer in list(cls.timers):
            if timer.started and not timer.cancelled and timer.delay <= now:
                timer.cancelled = True
                timer.callback()


class CandidatePreviewStoreTest(unittest.TestCase):
    def test_expired_preview_is_removed_by_timer_without_a_later_handler_request(self):
        clock = [0]
        FakeTimer.timers = []
        backing_store = FakeCandidateStore()
        with mock.patch.object(server.threading, "Timer", FakeTimer):
            previews = server.CandidatePreviewStore(
                backing_store, ttl_seconds=60, clock=lambda: clock[0]
            )
            previews.put({"title": "A candidate"})
            clock[0] = 60
            FakeTimer.run_due(clock[0])

            self.assertEqual(backing_store.candidates, {})

    def test_put_after_close_rejects_without_retaining_a_backing_candidate(self):
        backing_store = FakeCandidateStore()
        previews = server.CandidatePreviewStore(backing_store)
        previews.close()

        with self.assertRaisesRegex(RuntimeError, "closed"):
            previews.put({"title": "A candidate"})

        self.assertEqual(backing_store.candidates, {})


class LibraryServerTest(unittest.TestCase):
    def test_bind_failure_preserves_the_socket_error_and_closes_the_candidate_store(self):
        candidate_store = mock.Mock()
        candidate_store.peek.return_value = None

        with tempfile.TemporaryDirectory() as media_root:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen()

                try:
                    server.create_server(
                        "127.0.0.1",
                        listener.getsockname()[1],
                        Path(media_root) / "Books",
                        Path(media_root) / "Audiobooks",
                        candidate_store=candidate_store,
                    )
                except Exception as error:
                    bind_error = error
                else:
                    self.fail("occupied port unexpectedly accepted a second listener")

        self.assertIsInstance(bind_error, OSError)
        candidate_store.close.assert_called_once_with()


class ReadarrStartupConfigurationTest(unittest.TestCase):
    def test_parse_args_accepts_config_path_without_an_api_key_option(self):
        args = server.parse_args([
            "--books-root", "/plex/Books",
            "--audiobooks-root", "/plex/Audiobooks",
            "--assets-root", "/srv/library/assets",
            "--readarr-config", "/home/sv/library-browser/readarr-request.json",
        ])

        self.assertEqual(
            args.readarr_config,
            Path("/home/sv/library-browser/readarr-request.json"),
        )
        self.assertEqual(args.assets_root, Path("/srv/library/assets"))
        self.assertNotIn("api_key", vars(args))

    def test_parse_args_redacts_invalid_argument_values(self):
        secret = "SENTINEL_SECRET"
        stderr = io.StringIO()

        with redirect_stderr(stderr), self.assertRaises(SystemExit) as error:
            server.parse_args(["--api-key", secret])

        self.assertEqual(error.exception.code, 2)
        self.assertEqual(
            stderr.getvalue(),
            "error: invalid command-line arguments; use --help\n",
        )
        self.assertNotIn(secret, stderr.getvalue())
        self.assertNotIn("--api-key", stderr.getvalue())

    def test_valid_json_configuration_constructs_a_readarr_client(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "readarr-request.json"
            config_path.write_text(json.dumps(READARR_REQUEST_CONFIG), encoding="utf-8")

            client = server.load_readarr_client(config_path)

        self.assertIsInstance(client, readarr.ReadarrClient)
        self.assertEqual(client._base_url, READARR_REQUEST_CONFIG["url"])
        self.assertEqual(client._api_key, READARR_REQUEST_CONFIG["apiKey"])
        self.assertEqual(
            {
                name: (configuration.root_folder_path, configuration.quality_profile_id)
                for name, configuration in client._configurations.items()
            },
            {"audiobooks": ("/plex/Audiobooks", 2), "books": ("/plex/Books", 1)},
        )

    def test_missing_configuration_leaves_the_request_desk_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "readarr-request.json"
            messages = []

            self.assertIsNone(server.load_readarr_client(config_path, messages.append))

        self.assertEqual(len(messages), 1)

    def test_invalid_configuration_values_are_not_reported(self):
        secret = "DO_NOT_LOG_THIS_SECRET"
        values = dict(READARR_REQUEST_CONFIG, url="http://[", apiKey=secret)
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "readarr-request.json"
            config_path.write_text(json.dumps(values), encoding="utf-8")
            messages = []

            self.assertIsNone(server.load_readarr_client(config_path, messages.append))

        self.assertEqual(len(messages), 1)
        self.assertNotIn(secret, messages[0])


class BlockingReadarrClient(FakeReadarrClient):
    def __init__(self):
        super().__init__()
        self.search_started = threading.Event()
        self.release_search = threading.Event()

    def search(self, term, target):
        self.search_started.set()
        self.release_search.wait(5)
        return super().search(term, target)


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
        document = parse_html(body.decode())
        token_inputs = document.descendants("input", name="token")
        self.assertEqual(len(token_inputs), 1)
        token = token_inputs[0].attributes["value"]
        return token, body.decode()

    def confirmation_headers(self, origin=None):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if origin is not None:
            headers["Origin"] = origin
        return headers

    def same_origin_headers(self):
        return self.confirmation_headers(
            "http://127.0.0.1:{}".format(self.httpd.server_port)
        )

    def test_landing_page_exposes_catalog_destinations_and_inline_request_form(self):
        response, body = self.request("GET", "/")
        document = parse_html(body.decode())
        landing = [
            main
            for main in document.descendants("main")
            if "landing" in main.attributes.get("class", "").split()
        ][0]
        destinations = {
            link.attributes.get("href")
            for link in document.descendants("a")
        }
        request_panel = document.descendants(id="shelf-request-panel")
        shelf_buttons = [
            button
            for button in landing.descendants("button")
            if "aria-controls" in button.attributes
        ]

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [child.tag for child in landing.children],
            ["header", "nav", "aside"],
        )
        self.assertEqual(
            [heading.text_content() for heading in document.descendants("h1")],
            ["The Library of Bex"],
        )
        self.assertEqual(
            [button.attributes["aria-expanded"] for button in shelf_buttons],
            ["false", "false", "false"],
        )
        control_groups = landing.descendants(
            "div", role="group", **{"aria-label": "Choose a shelf"}
        )
        self.assertEqual(len(control_groups), 1)
        self.assertEqual(control_groups[0].descendants("button"), shelf_buttons)
        self.assertEqual(
            {"/library/Books/", "/library/Audiobooks/"} - destinations,
            set(),
        )
        self.assertEqual(len(request_panel), 1)
        self.assertEqual(
            [
                (form.attributes["action"], form.attributes["method"])
                for form in request_panel[0].descendants("form")
            ],
            [("/library/request/search/", "get")],
        )

    def test_request_desk_defaults_searches_to_audiobooks_but_offers_written_books(self):
        response, body = self.request("GET", "/request/")
        request_panel = parse_html(body.decode()).descendants(
            id="shelf-request-panel"
        )[0]
        scopes = request_panel.descendants("input", name="scope")

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [(scope.attributes.get("value"), "checked" in scope.attributes) for scope in scopes],
            [("audiobooks", True), ("books", False)],
        )
        self.assertIn("Audiobooks", request_panel.text_content())
        self.assertIn("Written books", request_panel.text_content())

    def test_landing_previews_recent_safe_entries_and_an_empty_shelf(self):
        older = self.books / "Older.epub"
        newest = self.books / "Newest.epub"
        older.write_bytes(b"older")
        newest.write_bytes(b"newest")
        os.utime(older, (100, 100))
        os.utime(self.books / "The <Book>.epub", (200, 200))
        os.utime(self.books / "Series <A>", (300, 300))
        os.utime(newest, (400, 400))

        outside = Path(self.temp_dir.name) / "outside-preview.epub"
        outside.write_bytes(b"outside")
        escaping_link = self.books / "escape-target"
        try:
            escaping_link.symlink_to(outside)
        except (NotImplementedError, OSError):
            pass

        response, body = self.request("GET", "/library/")
        document = parse_html(body.decode())
        books_panel = document.descendants(id="shelf-books-panel")
        audio_panel = document.descendants(id="shelf-audiobooks-panel")

        self.assertEqual(response.status, 200)
        self.assertEqual(len(books_panel), 1)
        self.assertEqual(
            [item.text_content() for item in books_panel[0].descendants("li")],
            ["Newest.epub", "Series <A>", "The <Book>.epub"],
        )
        self.assertEqual(
            [link.attributes["href"] for link in books_panel[0].descendants("a")],
            ["/library/Books/"],
        )
        self.assertEqual(len(audio_panel), 1)
        self.assertEqual(audio_panel[0].descendants("li"), [])
        self.assertEqual(
            [link.attributes["href"] for link in audio_panel[0].descendants("a")],
            ["/library/Audiobooks/"],
        )

    def test_landing_distinguishes_an_unavailable_media_root_from_an_empty_shelf(self):
        self.books.rename(self.books.with_name("Books unavailable"))

        response, body = self.request("GET", "/library/")
        books_panel = parse_html(body.decode()).descendants(id="shelf-books-panel")[0]

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [alert.text_content() for alert in books_panel.descendants(role="alert")],
            ["The Books shelf cannot be read right now."],
        )
        self.assertNotIn("No volumes catalogued yet.", books_panel.text_content())

    def test_request_desk_is_the_expanded_shelf_and_works_without_javascript(self):
        response, body = self.request("GET", "/library/request/")
        document = parse_html(body.decode())
        shelf_buttons = [
            button
            for button in document.descendants("button")
            if "aria-controls" in button.attributes
        ]

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [button.attributes["aria-label"] for button in shelf_buttons],
            ["Books", "Audiobooks", "Request a book"],
        )
        self.assertEqual(
            [
                button.attributes["aria-label"]
                for button in shelf_buttons
                if button.attributes.get("aria-expanded") == "true"
            ],
            ["Request a book"],
        )
        for button in shelf_buttons:
            panels = document.descendants(id=button.attributes["aria-controls"])
            self.assertEqual(len(panels), 1)
            self.assertEqual(panels[0].attributes["aria-labelledby"], button.attributes["id"])

        request_panel = document.descendants(id="shelf-request-panel")[0]
        forms = request_panel.descendants("form")
        search_inputs = request_panel.descendants("input", name="term")
        labels = request_panel.descendants("label", **{"for": "request-query"})

        self.assertEqual(
            [(form.attributes["action"], form.attributes["method"]) for form in forms],
            [("/library/request/search/", "get")],
        )
        self.assertEqual(len(search_inputs), 1)
        self.assertEqual(search_inputs[0].attributes["type"], "search")
        self.assertEqual(len(labels), 1)

    def test_mobile_document_and_search_input_expose_ios_safe_semantics(self):
        response, body = self.request("GET", "/library/request/")
        document = parse_html(body.decode())
        viewport = document.descendants("meta", name="viewport")
        search_inputs = document.descendants("input", name="term")

        self.assertEqual(response.status, 200)
        self.assertEqual(len(viewport), 1)
        viewport_values = {
            value.strip()
            for value in viewport[0].attributes["content"].split(",")
        }
        self.assertEqual(
            viewport_values,
            {"width=device-width", "initial-scale=1", "viewport-fit=cover"},
        )
        self.assertEqual(len(search_inputs), 1)
        self.assertEqual(search_inputs[0].attributes["type"], "search")
        self.assertEqual(search_inputs[0].attributes["enterkeyhint"], "search")

    def test_search_renders_escaped_candidate_without_mutating_readarr(self):
        token, html = self.search_for_candidate()
        document = parse_html(html)
        request_panel = document.descendants(id="shelf-request-panel")[0]

        self.assertTrue(token)
        self.assertEqual(self.readarr_client.searches, [("Dangerous title", "audiobooks")])
        self.assertEqual(self.readarr_client.requests, [])
        self.assertEqual(
            [
                heading.text_content()
                for heading in request_panel.descendants("h4", **{"class": "result-title"})
            ],
            ["A <dangerous> title"],
        )
        self.assertEqual(
            request_panel.descendants("dangerous"),
            [],
        )
        self.assertIn("Author & Co.", request_panel.text_content())

    def test_search_results_identify_books_and_authors_and_allow_refining_query(self):
        self.readarr_client.candidates = [
            readarr.Candidate(
                kind="author",
                foreign_id="author-1",
                title="Jane Austen",
                author_name="Jane Austen",
                is_existing=False,
                lookup={"author": {"foreignAuthorId": "author-1"}},
            ),
            readarr.Candidate(
                kind="book",
                foreign_id="book-1",
                title="Pride and Prejudice",
                author_name="Jane Austen",
                is_existing=False,
                lookup={"book": {"foreignBookId": "book-1"}},
                year=1813,
            ),
        ]

        response, body = self.request(
            "GET", "/request/search/?term=Pride%20and%20Prejudice"
        )
        request_panel = parse_html(body.decode()).descendants(
            id="shelf-request-panel"
        )[0]
        result_groups = request_panel.descendants("section", **{"data-result-kind": "book"})
        author_groups = request_panel.descendants(
            "section", **{"data-result-kind": "author"}
        )
        refine_inputs = request_panel.descendants("input", name="term")
        scope_inputs = request_panel.descendants("input", name="scope")
        buttons = [
            button.text_content()
            for button in request_panel.descendants("button")
        ]

        self.assertEqual(response.status, 200)
        self.assertEqual(len(result_groups), 1)
        self.assertEqual(len(author_groups), 1)
        self.assertIn("Pride and Prejudice", result_groups[0].text_content())
        self.assertIn("1813", result_groups[0].text_content())
        self.assertIn("Jane Austen", author_groups[0].text_content())
        self.assertIn("adds the author and searches monitored books", author_groups[0].text_content())
        self.assertEqual(
            [input_.attributes.get("value") for input_ in refine_inputs],
            ["Pride and Prejudice"],
        )
        self.assertEqual(
            [input_.attributes.get("value") for input_ in scope_inputs],
            ["audiobooks"],
        )
        self.assertIn("Review book", buttons)
        self.assertIn("Review author", buttons)
        self.assertEqual(self.readarr_client.requests, [])

    def test_confirmation_adds_book_without_search_and_shows_release_choices(self):
        token, _ = self.search_for_candidate()

        response, body = self.request(
            "GET", "/request/confirm/?token=" + urllib.parse.quote(token)
        )
        confirmation_panel = parse_html(body.decode()).descendants(
            id="shelf-request-panel"
        )[0]

        self.assertEqual(response.status, 200)
        self.assertIn(
            "add this book to Readarr without downloading it",
            confirmation_panel.text_content(),
        )

        response, body = self.request(
            "POST",
            "/request/confirm/",
            urllib.parse.urlencode({"token": token}),
            self.same_origin_headers(),
        )
        release_panel = parse_html(body.decode()).descendants(
            id="shelf-request-panel"
        )[0]

        self.assertEqual(response.status, 200)
        self.assertIn("Select exactly one release", release_panel.text_content())
        self.assertIn("Nothing is downloaded until you choose", release_panel.text_content())
        self.assertEqual(self.readarr_client.adds, self.readarr_client.candidates)
        self.assertEqual(self.readarr_client.release_searches, [1])
        self.assertEqual(self.readarr_client.grabs, [])

    def test_written_book_scope_is_preserved_through_confirmation(self):
        response, body = self.request(
            "GET", "/request/search/?term=Dangerous%20title&scope=books"
        )
        token = parse_html(body.decode()).descendants("input", name="token")[0].attributes["value"]

        response, _ = self.request(
            "POST",
            "/request/confirm/",
            urllib.parse.urlencode({"token": token}),
            self.same_origin_headers(),
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(self.readarr_client.searches, [("Dangerous title", "books")])
        self.assertEqual([candidate.target for candidate in self.readarr_client.adds], ["books"])

    def test_author_confirmation_explains_the_broader_monitoring_action(self):
        self.readarr_client.candidates = [
            readarr.Candidate(
                kind="author",
                foreign_id="author-1",
                title="Jane Austen",
                author_name="Jane Austen",
                is_existing=False,
                lookup={"author": {"foreignAuthorId": "author-1"}},
            )
        ]
        token, _ = self.search_for_candidate()

        response, body = self.request(
            "GET", "/request/confirm/?token=" + urllib.parse.quote(token)
        )
        request_panel = parse_html(body.decode()).descendants(
            id="shelf-request-panel"
        )[0]

        self.assertEqual(response.status, 200)
        self.assertIn(
            "add this author to Readarr without starting an automatic search",
            request_panel.text_content(),
        )
        self.assertEqual(self.readarr_client.requests, [])

    def test_request_workflow_states_remain_inside_the_request_shelf(self):
        token, search_html = self.search_for_candidate()
        search_document = parse_html(search_html)
        search_panel = search_document.descendants(id="shelf-request-panel")

        self.assertEqual(len(search_panel), 1)
        self.assertEqual(
            [heading.text_content() for heading in search_panel[0].descendants("h2")],
            ["Search results"],
        )
        self.assertEqual(
            [
                (form.attributes["action"], form.attributes["method"])
                for form in search_panel[0].descendants("form")
            ],
            [
                ("/library/request/search/", "get"),
                ("/library/request/confirm/", "get"),
            ],
        )

        response, body = self.request(
            "GET",
            "/library/request/confirm/?token=" + urllib.parse.quote(token),
        )
        confirmation_panel = parse_html(body.decode()).descendants(id="shelf-request-panel")

        self.assertEqual(response.status, 200)
        self.assertEqual(len(confirmation_panel), 1)
        self.assertEqual(
            [heading.text_content() for heading in confirmation_panel[0].descendants("h2")],
            ["Confirm request"],
        )
        self.assertEqual(
            [
                (form.attributes["action"], form.attributes["method"])
                for form in confirmation_panel[0].descendants("form")
            ],
            [("/library/request/confirm/", "post")],
        )

        response, body = self.request(
            "POST",
            "/library/request/confirm/",
            urllib.parse.urlencode({"token": token}),
            self.same_origin_headers(),
        )
        success_panel = parse_html(body.decode()).descendants(id="shelf-request-panel")

        self.assertEqual(response.status, 200)
        self.assertEqual(len(success_panel), 1)
        self.assertIn("Nothing is downloaded until you choose", success_panel[0].text_content())
        self.assertEqual(
            [form.attributes["method"] for form in success_panel[0].descendants("form")],
            ["post", "post"],
        )

        response, body = self.request(
            "GET",
            "/library/request/confirm/?token=" + urllib.parse.quote(token),
        )
        error_panel = parse_html(body.decode()).descendants(id="shelf-request-panel")

        self.assertEqual(response.status, 400)
        self.assertEqual(len(error_panel), 1)
        self.assertEqual(
            [alert.text_content() for alert in error_panel[0].descendants(role="alert")],
            [
                "This request is no longer available. Search the catalogue again to make a new request."
            ],
        )

    def test_existing_search_results_are_marked_without_request_tokens(self):
        candidate_store = FakeCandidateStore()
        self.restart_server(self.readarr_client, candidate_store)
        self.readarr_client.candidates = [
            readarr.Candidate(
                kind="author",
                foreign_id="author-1",
                title="Existing author",
                author_name="Existing author",
                is_existing=True,
                lookup={"author": {"id": 10, "authorName": "Existing author"}},
            ),
            readarr.Candidate(
                kind="book",
                foreign_id="book-2",
                title="Existing book",
                author_name="Existing author",
                is_existing=True,
                lookup={"book": {"id": 11, "foreignBookId": "book-2"}},
            ),
        ]

        response, body = self.request("GET", "/request/search/?term=Existing")
        request_panel = parse_html(body.decode()).descendants(id="shelf-request-panel")[0]

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [status.text_content() for status in request_panel.descendants(role="status")],
            ["Already in Readarr", "Already in Readarr"],
        )
        self.assertIn("This author is already monitored by Readarr.", request_panel.text_content())
        self.assertIn("This book is already in Readarr.", request_panel.text_content())
        self.assertNotIn("This adds the author", request_panel.text_content())
        self.assertEqual(
            [
                (form.attributes["action"], form.attributes["method"])
                for form in request_panel.descendants("form")
            ],
            [("/library/request/search/", "get")],
        )
        self.assertEqual(request_panel.descendants("input", name="token"), [])
        self.assertEqual(candidate_store.candidates, {})
        self.assertEqual(self.readarr_client.requests, [])

    def test_confirmation_get_does_not_mutate_readarr(self):
        token, _ = self.search_for_candidate()

        response, body = self.request("GET", "/request/confirm/?token=" + urllib.parse.quote(token))
        request_panel = parse_html(body.decode()).descendants(id="shelf-request-panel")[0]

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [heading.text_content() for heading in request_panel.descendants("h2")],
            ["Confirm request"],
        )
        self.assertEqual(
            [strong.text_content() for strong in request_panel.descendants("strong")],
            ["A <dangerous> title"],
        )
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

    def test_expired_preview_timer_discards_backing_candidate_before_confirmation(self):
        clock = [0]
        backing_store = readarr.CandidateStore(
            ttl_seconds=120, clock=lambda: clock[0]
        )
        FakeTimer.timers = []
        with mock.patch.object(server.threading, "Timer", FakeTimer):
            previews = server.CandidatePreviewStore(
                backing_store, ttl_seconds=60, clock=lambda: clock[0]
            )
            self.restart_server(self.readarr_client, previews)
            token, _ = self.search_for_candidate()
            clock[0] = 60
            FakeTimer.run_due(clock[0])

            response, body = self.request(
                "POST",
                "/request/confirm/",
                urllib.parse.urlencode({"token": token}).encode(),
                self.same_origin_headers(),
            )

        self.assertEqual(response.status, 400)
        self.assertIn("no longer available", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_eager_preview_purge_discards_backing_candidate_before_confirmation(self):
        clock = [0]
        backing_store = readarr.CandidateStore(
            ttl_seconds=120, clock=lambda: clock[0]
        )
        FakeTimer.timers = []
        with mock.patch.object(server.threading, "Timer", FakeTimer):
            previews = server.CandidatePreviewStore(
                backing_store, ttl_seconds=60, clock=lambda: clock[0]
            )
            self.restart_server(self.readarr_client, previews)
            token, _ = self.search_for_candidate()
            clock[0] = 60
            previews.peek("another-token")

            response, body = self.request(
                "POST",
                "/request/confirm/",
                urllib.parse.urlencode({"token": token}).encode(),
                self.same_origin_headers(),
            )

        self.assertEqual(response.status, 400)
        self.assertIn("no longer available", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_closing_preview_store_discards_backing_candidates_before_confirmation(self):
        clock = [0]
        backing_store = readarr.CandidateStore(
            ttl_seconds=120, clock=lambda: clock[0]
        )
        FakeTimer.timers = []
        with mock.patch.object(server.threading, "Timer", FakeTimer):
            previews = server.CandidatePreviewStore(
                backing_store, ttl_seconds=60, clock=lambda: clock[0]
            )
            self.restart_server(self.readarr_client, previews)
            direct_token = previews.put({"title": "A direct candidate"})
            request_token, _ = self.search_for_candidate()
            self.connection.close()
            self.httpd.shutdown()
            self.httpd.server_close()
            direct_candidate = backing_store.take(direct_token)
            self.start_server(self.readarr_client, previews)

            response, body = self.request(
                "POST",
                "/request/confirm/",
                urllib.parse.urlencode({"token": request_token}).encode(),
                self.same_origin_headers(),
            )

        self.assertIsNone(direct_candidate)
        self.assertEqual(response.status, 400)
        self.assertIn("no longer available", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_server_close_cleans_up_candidates_added_by_an_inflight_search(self):
        clock = [0]
        readarr_client = BlockingReadarrClient()
        backing_store = RecordingCandidateStore(lambda: clock[0])
        FakeTimer.timers = []
        with mock.patch.object(server.threading, "Timer", FakeTimer):
            previews = server.CandidatePreviewStore(
                backing_store, ttl_seconds=60, clock=lambda: clock[0]
            )
            self.restart_server(readarr_client, previews)
            result = {}

            def search():
                connection = HTTPConnection("127.0.0.1", self.httpd.server_port)
                try:
                    connection.request("GET", "/request/search/?term=Concurrent")
                    response = connection.getresponse()
                    result["status"] = response.status
                    response.read()
                except OSError:
                    result["closed"] = True
                finally:
                    connection.close()

            request_thread = threading.Thread(target=search)
            request_thread.start()
            self.assertTrue(readarr_client.search_started.wait(2))
            close_thread = threading.Thread(target=self.httpd.server_close)
            close_thread.start()
            readarr_client.release_search.set()
            request_thread.join(5)
            close_thread.join(5)

        self.assertFalse(request_thread.is_alive())
        self.assertFalse(close_thread.is_alive())
        self.assertIn("status", result)
        self.assertIsNone(backing_store.take(backing_store.last_token))
        self.assertFalse(
            any(timer.started and not timer.cancelled for timer in FakeTimer.timers)
        )

    def test_release_selection_grabs_only_the_selected_release(self):
        token, _ = self.search_for_candidate()
        body = urllib.parse.urlencode({"token": token}).encode()

        response, response_body = self.request(
            "POST",
            "/library/request/confirm/",
            body,
            self.same_origin_headers(),
        )

        self.assertEqual(response.status, 200)
        release_document = parse_html(response_body.decode())
        release_tokens = release_document.descendants("input", name="token")
        self.assertEqual(len(release_tokens), 2)
        selected_token = release_tokens[1].attributes["value"]
        self.assertEqual(self.readarr_client.grabs, [])

        response, response_body = self.request(
            "POST",
            "/library/request/release/",
            urllib.parse.urlencode({"token": selected_token}),
            self.same_origin_headers(),
        )

        self.assertEqual(response.status, 200)
        self.assertIn("Readarr accepted the selected release.", response_body.decode())
        self.assertEqual(self.readarr_client.grabs[0][0].guid, "release-2")
        self.assertEqual(self.readarr_client.grabs[0][1], 1)

        response, response_body = self.request(
            "POST",
            "/library/request/release/",
            urllib.parse.urlencode({"token": selected_token}),
            self.same_origin_headers(),
        )

        self.assertEqual(response.status, 400)
        self.assertIn("no longer available", response_body.decode())
        self.assertEqual(len(self.readarr_client.grabs), 1)

    def test_reused_confirmation_token_cannot_request_again(self):
        token, _ = self.search_for_candidate()
        body = urllib.parse.urlencode({"token": token}).encode()

        self.request(
            "POST",
            "/request/confirm/",
            body,
            self.same_origin_headers(),
        )
        response, response_body = self.request(
            "POST",
            "/request/confirm/",
            body,
            self.same_origin_headers(),
        )

        self.assertEqual(response.status, 400)
        self.assertIn("no longer available", response_body.decode())
        self.assertEqual(self.readarr_client.requests, self.readarr_client.candidates)

    def test_confirmation_post_rejects_non_matching_origins_without_consuming_tokens(self):
        for origin in (None, "not-an-origin", "https://other.example"):
            token, _ = self.search_for_candidate()
            body = urllib.parse.urlencode({"token": token}).encode()
            initial_request_count = len(self.readarr_client.requests)

            response, response_body = self.request(
                "POST",
                "/request/confirm/",
                body,
                self.confirmation_headers(origin),
            )

            self.assertEqual(response.status, 403)
            self.assertNotIn(origin or "missing", response_body.decode())
            self.assertEqual(len(self.readarr_client.requests), initial_request_count)

            response, _ = self.request(
                "POST",
                "/request/confirm/",
                body,
                self.same_origin_headers(),
            )

            self.assertEqual(response.status, 200)
            self.assertEqual(len(self.readarr_client.requests), initial_request_count + 1)

    def test_request_routes_reject_bad_term_missing_configuration_and_non_form_post(self):
        response, body = self.request("GET", "/request/search/?term=x")

        self.assertEqual(response.status, 400)
        self.assertIn("between 2 and 200 characters", body.decode())
        self.assertEqual(self.readarr_client.searches, [])

        self.restart_server(None)
        response, body = self.request("GET", "/library/request/")

        self.assertEqual(response.status, 503)
        self.assertIn("unavailable", body.decode())

        secret = "DO_NOT_LOG_THIS_SECRET"
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "readarr-request.json"
            config_path.write_text('{"apiKey": "' + secret + '",', encoding="utf-8")
            messages = []
            self.restart_server(server.load_readarr_client(config_path, messages.append))
        response, body = self.request("GET", "/library/request/")

        self.assertEqual(response.status, 503)
        self.assertIn("unavailable", body.decode())
        self.assertNotIn(secret, body.decode())
        self.assertTrue(all(secret not in message for message in messages))

        self.restart_server(self.readarr_client)
        response, body = self.request(
            "POST",
            "/request/confirm/",
            b'{"token":"not-a-form"}',
            dict(self.same_origin_headers(), **{"Content-Type": "application/json"}),
        )

        self.assertEqual(response.status, 415)
        self.assertIn("form", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_malformed_urlencoded_confirmation_is_rejected(self):
        response, body = self.request(
            "POST",
            "/request/confirm/",
            b"token",
            self.same_origin_headers(),
        )

        self.assertEqual(response.status, 400)
        self.assertIn("Invalid request form", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_oversized_confirmation_form_is_rejected(self):
        response, body = self.request(
            "POST",
            "/request/confirm/",
            b"token=" + (b"a" * (8 * 1024)),
            self.same_origin_headers(),
        )

        self.assertEqual(response.status, 413)
        self.assertIn("Request form too large", body.decode())
        self.assertEqual(self.readarr_client.requests, [])

    def test_books_catalog_escapes_names_and_exposes_metadata(self):
        response, body = self.request("GET", "/Books/")
        document = parse_html(body.decode())
        catalog = document.descendants("section", **{"aria-label": "Books catalog"})[0]
        links = [
            (link.text_content(), link.attributes["href"])
            for link in catalog.descendants("a")
        ]

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [heading.text_content() for heading in document.descendants("h1")],
            ["Books"],
        )
        self.assertIn(
            ("The <Book>.epub", "/library/Books/The%20%3CBook%3E.epub"),
            links,
        )
        self.assertIn(
            ("Series <A>", "/library/Books/Series%20%3CA%3E/"),
            links,
        )
        self.assertEqual(document.descendants("book"), [])

    def test_empty_audiobooks_catalog_uses_exact_empty_state(self):
        response, body = self.request("GET", "/Audiobooks/")
        document = parse_html(body.decode())

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [
                paragraph.text_content()
                for paragraph in document.descendants("p")
                if paragraph.text_content() == "Awaiting new stock"
            ],
            ["Awaiting new stock"],
        )

    def test_audiobooks_catalog_exposes_the_available_recording(self):
        (self.audiobooks / "A listening tale.m4b").write_bytes(b"audio")

        response, body = self.request("GET", "/Audiobooks/")
        document = parse_html(body.decode())
        catalog = document.descendants(
            "section", **{"aria-label": "Audiobooks catalog"}
        )[0]
        recording_links = [
            link
            for link in catalog.descendants("a")
            if link.text_content() == "A listening tale.m4b"
        ]

        self.assertEqual(response.status, 200)
        self.assertEqual(len(recording_links), 1)
        response, recording = self.request(
            "GET", recording_links[0].attributes["href"]
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(recording, b"audio")

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
        document = parse_html(body.decode())
        catalog = document.descendants("section", **{"aria-label": "Books catalog"})[0]
        names = [link.text_content() for link in catalog.descendants("a")]

        self.assertEqual(response.status, 200)
        self.assertIn("In-root alias.epub", names)
        self.assertNotIn("Escaping shelf", names)

    def test_open_directory_link_renders_nested_catalog_with_shelf_breadcrumb(self):
        response, body = self.request("GET", "/Books/Series%20%3CA%3E/")
        document = parse_html(body.decode())
        breadcrumbs = document.descendants("nav", **{"aria-label": "Breadcrumb"})[0]
        catalog = document.descendants(
            "section", **{"aria-label": "Series <A> catalog"}
        )[0]
        nested_links = [
            link
            for link in catalog.descendants("a")
            if link.text_content() == "Nested Book.epub"
        ]

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [
                (link.text_content(), link.attributes["href"])
                for link in breadcrumbs.descendants("a")
            ],
            [
                ("The Library of Bex", "/library/"),
                ("Books", "/library/Books/"),
            ],
        )
        self.assertEqual(len(nested_links), 1)
        response, nested_book = self.request(
            "GET", nested_links[0].attributes["href"]
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(nested_book, b"nested book")

    def test_nested_directory_traversal_is_rejected(self):
        response, body = self.request(
            "GET", "/Books/Series%20%3CA%3E/%2e%2e/%2e%2e/etc/passwd"
        )

        self.assertIn(response.status, (403, 404))
        self.assertNotIn(b"book content", body)

    def test_library_prefix_is_accepted_for_transparent_reverse_proxy(self):
        response, body = self.request("GET", "/library/Books/")
        document = parse_html(body.decode())

        self.assertEqual(response.status, 200)
        self.assertEqual(
            [heading.text_content() for heading in document.descendants("h1")],
            ["Books"],
        )

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

    def test_symlink_resolution_loops_do_not_terminate_requests(self):
        for path, expected_status in (
            ("/library/", 200),
            ("/library/Books/The%20%3CBook%3E.epub", 403),
        ):
            with self.subTest(path=path):
                with mock.patch.object(
                    Path, "resolve", side_effect=RuntimeError("Symlink loop")
                ):
                    try:
                        response, _ = self.request("GET", path)
                    except Exception as error:
                        result = error
                    else:
                        result = response.status

                self.assertEqual(result, expected_status)


if __name__ == "__main__":
    unittest.main()
