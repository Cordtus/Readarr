import json
import sys
import unittest
from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
import readarr


PROBE_SPEC = spec_from_file_location(
    "probe_mam_release_metadata",
    Path(__file__).parent / "scripts" / "probe-mam-release-metadata.py",
)
probe_mam_release_metadata = module_from_spec(PROBE_SPEC)
PROBE_SPEC.loader.exec_module(probe_mam_release_metadata)


class FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return self._body


class CandidateStoreTest(unittest.TestCase):
    def test_token_is_single_use_and_expires(self):
        now = [100]
        store = readarr.CandidateStore(ttl_seconds=60, clock=lambda: now[0])
        token = store.put({"kind": "book", "foreignId": "book-1"})

        self.assertEqual(store.take(token), {"kind": "book", "foreignId": "book-1"})
        self.assertIsNone(store.take(token))

        expired_token = store.put({"kind": "book", "foreignId": "book-2"})
        now[0] = 160
        self.assertIsNone(store.take(expired_token))

    def test_discard_removes_a_candidate_without_returning_it(self):
        store = readarr.CandidateStore()
        token = store.put({"kind": "book", "foreignId": "book-1"})

        self.assertIsNone(store.discard(token))
        self.assertIsNone(store.take(token))


class ReadarrClientTest(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.responses = []
        self.configuration = readarr.ReadarrConfiguration(
            root_folder_path="/configured/library",
            quality_profile_id=4,
            metadata_profile_id=7,
            monitor="all",
            monitor_new_items="all",
        )
        self.client = readarr.ReadarrClient(
            "http://readarr:8787",
            "not-a-real-key",
            configurations={"audiobooks": self.configuration, "books": self.configuration},
            opener=self.opener,
        )
        self.book_candidate = readarr.Candidate(
            kind="book",
            foreign_id="book-1",
            title="A title",
            author_name="An author",
            is_existing=False,
            lookup={
                "book": {
                    "foreignBookId": "book-1",
                    "title": "A title",
                    "author": {"id": 42, "authorName": "An author"},
                }
            },
        )

    def opener(self, request, timeout):
        headers = {"X-Api-Key": request.get_header("X-api-key")}
        self.requests.append({
            "path": request.full_url.removeprefix("http://readarr:8787"),
            "method": request.get_method(),
            "headers": headers,
            "timeout": timeout,
            "json": json.loads(request.data.decode("utf-8")) if request.data else None,
        })
        return self.responses.pop(0)

    def test_search_sends_api_key_and_returns_safe_candidates(self):
        self.responses.append(FakeResponse(200, [{
            "foreignId": "book-1",
            "book": {
                "foreignBookId": "book-1",
                "title": "A title",
                "releaseDate": "1813-01-28T00:00:00Z",
                "author": {"authorName": "An author"},
                "links": [{"url": "https://untrusted.example/private"}],
            },
        }]))

        candidates = self.client.search("A title", "audiobooks")

        self.assertEqual(self.requests[0]["path"], "/api/v1/search?term=A+title")
        self.assertEqual(self.requests[0]["headers"]["X-Api-Key"], "not-a-real-key")
        self.assertEqual(self.requests[0]["timeout"], 60)
        self.assertEqual(candidates[0].title, "A title")
        self.assertEqual(candidates[0].author_name, "An author")
        self.assertEqual(candidates[0].foreign_id, "book-1")
        self.assertEqual(candidates[0].year, 1813)
        self.assertFalse(candidates[0].is_existing)
        self.assertEqual(candidates[0].target, "audiobooks")

    def test_search_keeps_book_and_author_results_distinct(self):
        self.responses.append(FakeResponse(200, [
            {
                "foreignId": "author-1",
                "author": {
                    "foreignAuthorId": "author-1",
                    "authorName": "Jane Austen",
                },
            },
            {
                "foreignId": "book-1",
                "book": {
                    "foreignBookId": "book-1",
                    "title": "Pride and Prejudice",
                    "releaseDate": "1813",
                    "author": {"authorName": "Jane Austen"},
                },
            },
        ]))

        candidates = self.client.search("Pride and Prejudice", "books")

        self.assertEqual(
            [(candidate.kind, candidate.title, candidate.year) for candidate in candidates],
            [
                ("author", "Jane Austen", None),
                ("book", "Pride and Prejudice", 1813),
            ],
        )

    def test_add_book_does_not_start_automatic_search(self):
        self.responses.append(FakeResponse(201, {"id": 99, "title": "A title"}))

        outcome = self.client.add(self.book_candidate)

        self.assertEqual(self.requests[-1]["path"], "/api/v1/book")
        self.assertFalse(self.requests[-1]["json"]["addOptions"].get("searchForNewBook", False))
        self.assertTrue(self.requests[-1]["json"]["monitored"])
        self.assertNotIn("rootFolderPath", self.requests[-1]["json"])
        self.assertEqual(outcome, {"id": 99, "title": "A title"})

    def test_release_search_normalizes_choices_without_exposing_raw_payload(self):
        self.responses.append(FakeResponse(200, [{
            "guid": "mam-guid",
            "indexerId": 7,
            "title": "A title - Unabridged",
            "size": 123456789,
            "downloadAllowed": True,
            "downloadUrl": "https://private.example/download",
        }]))

        releases = self.client.search_releases(99)

        self.assertEqual(self.requests[0]["path"], "/api/v1/release?bookId=99")
        self.assertEqual(releases[0].guid, "mam-guid")
        self.assertEqual(releases[0].indexer_id, 7)
        self.assertEqual(releases[0].title, "A title - Unabridged")
        self.assertEqual(releases[0].size, 123456789)
        self.assertTrue(releases[0].download_allowed)
        self.assertNotIn("downloadUrl", vars(releases[0]))

    def test_release_keeps_explicit_upstream_freeleech_metadata_only(self):
        self.responses.append(FakeResponse(200, [{
            "guid": "mam-guid",
            "indexerId": 7,
            "title": "A title - Unabridged",
            "size": 123456789,
            "downloadAllowed": True,
            "freeleech": True,
        }]))

        release = self.client.search_releases(99)[0]

        self.assertTrue(release.freeleech)

    def test_release_defaults_missing_upstream_freeleech_metadata_to_false(self):
        self.responses.append(FakeResponse(200, [{
            "guid": "mam-guid",
            "indexerId": 7,
            "title": "VIP freeleech edition",
            "size": 123456789,
            "downloadAllowed": True,
        }]))

        release = self.client.search_releases(99)[0]

        self.assertFalse(release.freeleech)

    def test_release_rejects_non_boolean_upstream_freeleech_metadata(self):
        self.responses.append(FakeResponse(200, [{
            "guid": "mam-guid",
            "indexerId": 7,
            "title": "A title - Unabridged",
            "size": 123456789,
            "downloadAllowed": True,
            "freeleech": "true",
        }]))

        with self.assertRaisesRegex(readarr.ReadarrError, "invalid release"):
            self.client.search_releases(99)

    def test_grab_release_posts_only_the_selected_release_identity(self):
        self.responses.append(FakeResponse(200, {"guid": "mam-guid", "indexerId": 7}))

        outcome = self.client.grab_release(readarr.Release(
            guid="mam-guid",
            indexer_id=7,
            title="A title - Unabridged",
            size=123456789,
            download_allowed=True,
        ), book_id=99)

        self.assertEqual(self.requests[0]["path"], "/api/v1/release")
        self.assertEqual(
            self.requests[0]["json"],
            {"guid": "mam-guid", "indexerId": 7, "bookId": 99},
        )
        self.assertEqual(outcome, {"guid": "mam-guid", "indexerId": 7})

    def test_book_add_adds_configuration_to_an_unstored_author_without_search(self):
        candidate = readarr.Candidate(
            kind="book",
            foreign_id="book-1",
            title="A title",
            author_name="An author",
            is_existing=False,
            lookup={
                "book": {
                    "foreignBookId": "book-1",
                    "title": "A title",
                    "author": {"foreignAuthorId": "author-1", "authorName": "An author"},
                }
            },
        )
        self.responses.append(FakeResponse(201, {}))

        self.client.request(candidate)

        author = self.requests[-1]["json"]["author"]
        self.assertEqual(author["rootFolderPath"], "/configured/library")
        self.assertEqual(author["qualityProfileId"], 4)
        self.assertEqual(author["metadataProfileId"], 7)
        self.assertEqual(author["monitorNewItems"], "all")
        self.assertEqual(author["addOptions"], {"monitor": "all"})

    def test_specific_book_request_limits_new_author_to_the_requested_book(self):
        client = readarr.ReadarrClient(
            "http://readarr:8787",
            "not-a-real-key",
            configurations={"audiobooks": readarr.ReadarrConfiguration(
                root_folder_path="/configured/library",
                quality_profile_id=4,
                metadata_profile_id=7,
                monitor="specificBook",
                monitor_new_items="all",
            )},
            opener=self.opener,
        )
        candidate = readarr.Candidate(
            kind="book",
            foreign_id="book-1",
            title="A title",
            author_name="An author",
            is_existing=False,
            lookup={
                "book": {
                    "foreignBookId": "book-1",
                    "title": "A title",
                    "author": {"foreignAuthorId": "author-1", "authorName": "An author"},
                }
            },
        )
        self.responses.append(FakeResponse(201, {}))

        client.request(candidate)

        self.assertEqual(
            self.requests[-1]["json"]["author"]["addOptions"],
            {"booksToMonitor": ["book-1"]},
        )

    def test_author_add_applies_configuration_without_search(self):
        candidate = readarr.Candidate(
            kind="author",
            foreign_id="author-1",
            title="An author",
            author_name="An author",
            is_existing=False,
            lookup={"author": {"foreignAuthorId": "author-1", "authorName": "An author"}},
        )
        self.responses.append(FakeResponse(201, {}))

        self.client.request(candidate)

        payload = self.requests[-1]["json"]
        self.assertEqual(self.requests[-1]["path"], "/api/v1/author")
        self.assertTrue(payload["monitored"])
        self.assertEqual(payload["rootFolderPath"], "/configured/library")
        self.assertEqual(payload["addOptions"], {"monitor": "all"})

    def test_existing_author_request_is_rejected_without_posting(self):
        candidate = readarr.Candidate(
            kind="author",
            foreign_id="author-1",
            title="An author",
            author_name="An author",
            is_existing=True,
            lookup={"author": {"id": 42, "authorName": "An author"}},
        )

        with self.assertRaisesRegex(readarr.ReadarrError, "already exists"):
            self.client.request(candidate)

        self.assertEqual(self.requests, [])

    def test_existing_book_request_is_rejected_without_posting(self):
        candidate = readarr.Candidate(
            kind="book",
            foreign_id="book-1",
            title="A title",
            author_name="An author",
            is_existing=True,
            lookup={
                "book": {
                    "id": 99,
                    "foreignBookId": "book-1",
                    "title": "A title",
                    "author": {"id": 42, "authorName": "An author"},
                }
            },
        )

        with self.assertRaisesRegex(readarr.ReadarrError, "already exists"):
            self.client.request(candidate)

        self.assertEqual(self.requests, [])

    def test_invalid_configuration_and_http_errors_do_not_expose_api_key(self):
        with self.assertRaisesRegex(readarr.ReadarrError, "root_folder_path"):
            readarr.ReadarrConfiguration("", 4, 7, "all", "all")

        self.responses.append(FakeResponse(500, {"message": "backend failed"}))
        with self.assertRaises(readarr.ReadarrError) as raised:
            self.client.search("A title", "audiobooks")

        self.assertNotIn("not-a-real-key", str(raised.exception))

    def test_client_rejects_non_string_empty_or_decorated_base_urls(self):
        for base_url in (None, 1, "", "http://readarr:8787?setting=value", "http://readarr:8787#fragment"):
            with self.subTest(base_url=base_url):
                with self.assertRaisesRegex(readarr.ReadarrError, "base URL"):
                    readarr.ReadarrClient(base_url, "not-a-real-key", {"audiobooks": self.configuration})


class MamReleaseMetadataProbeTest(unittest.TestCase):
    def test_probe_accepts_one_positive_stdin_book_id_without_arguments(self):
        output = StringIO()
        config = {"url": "https://readarr.example.test", "apiKey": "not-a-real-key"}
        with (
            mock.patch.object(probe_mam_release_metadata.sys, "argv", ["probe"]),
            mock.patch.object(probe_mam_release_metadata.sys, "stdin", StringIO("99\n")),
            mock.patch.object(probe_mam_release_metadata, "load_protected_config", return_value=config),
            mock.patch.object(probe_mam_release_metadata, "fetch_releases", return_value=[{"freeleech": True}]) as fetch,
            redirect_stdout(output),
        ):
            result = probe_mam_release_metadata.main()

        self.assertEqual(result, 0)
        fetch.assert_called_once_with(config, 99)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "freeleechFieldTypes": {"freeleech": ["boolean"]},
                "hasExplicitFreeleechBoolean": True,
            },
        )

    def test_probe_does_not_treat_vip_metadata_as_current_vip_entitlement(self):
        output = StringIO()
        config = {"url": "https://readarr.example.test", "apiKey": "not-a-real-key"}
        with (
            mock.patch.object(probe_mam_release_metadata.sys, "argv", ["probe"]),
            mock.patch.object(probe_mam_release_metadata.sys, "stdin", StringIO("99\n")),
            mock.patch.object(probe_mam_release_metadata, "load_protected_config", return_value=config),
            mock.patch.object(
                probe_mam_release_metadata,
                "fetch_releases",
                return_value=[{"vip": True, "vipFreeleech": True}],
            ),
            redirect_stdout(output),
        ):
            result = probe_mam_release_metadata.main()

        self.assertEqual(result, 3)
        self.assertEqual(
            json.loads(output.getvalue()),
            {
                "freeleechFieldTypes": {},
                "hasExplicitFreeleechBoolean": False,
            },
        )

    def test_probe_rejects_command_line_arguments(self):
        config = {"url": "https://readarr.example.test", "apiKey": "not-a-real-key"}
        with (
            mock.patch.object(probe_mam_release_metadata.sys, "argv", ["probe", "99"]),
            mock.patch.object(probe_mam_release_metadata.sys, "stdin", StringIO("99\n")),
            mock.patch.object(probe_mam_release_metadata, "load_protected_config", return_value=config),
            mock.patch.object(probe_mam_release_metadata, "fetch_releases", return_value=[{"freeleech": True}]),
        ):
            with self.assertRaisesRegex(ValueError, "arguments"):
                probe_mam_release_metadata.main()

    def test_probe_rejects_multiple_book_ids_from_standard_input(self):
        config = {"url": "https://readarr.example.test", "apiKey": "not-a-real-key"}
        with (
            mock.patch.object(probe_mam_release_metadata.sys, "argv", ["probe"]),
            mock.patch.object(probe_mam_release_metadata.sys, "stdin", StringIO("99\n100\n")),
            mock.patch.object(probe_mam_release_metadata, "load_protected_config", return_value=config),
            mock.patch.object(probe_mam_release_metadata, "fetch_releases", return_value=[{"freeleech": True}]),
        ):
            with self.assertRaisesRegex(ValueError, "one positive"):
                probe_mam_release_metadata.main()

    def test_probe_redacts_sensitive_and_composite_release_field_names(self):
        field_types = probe_mam_release_metadata.release_field_types([{
            "freeleech": True,
            "size": 123,
            "title": "Private title",
            "releaseTitle": "Private release title",
            "guid": "private-guid",
            "releaseGuid": "private-release-guid",
            "downloadUrl": "https://private.example/download",
            "infoUrl": "https://private.example/info",
            "magnetUri": "magnet:?xt=urn:btih:private",
            "trackerPasskey": "private-passkey",
            "apiKey": "private-api-key",
            "sessionToken": "private-token",
        }])

        self.assertEqual(field_types, {"freeleech": ["boolean"], "size": ["number"]})


if __name__ == "__main__":
    unittest.main()
