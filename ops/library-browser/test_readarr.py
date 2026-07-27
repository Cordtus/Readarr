import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import readarr


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
            configuration=self.configuration,
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
                "author": {"authorName": "An author"},
                "links": [{"url": "https://untrusted.example/private"}],
            },
        }]))

        candidates = self.client.search("A title")

        self.assertEqual(self.requests[0]["path"], "/api/v1/search?term=A+title")
        self.assertEqual(self.requests[0]["headers"]["X-Api-Key"], "not-a-real-key")
        self.assertEqual(self.requests[0]["timeout"], 10)
        self.assertEqual(candidates[0].title, "A title")
        self.assertEqual(candidates[0].author_name, "An author")
        self.assertEqual(candidates[0].foreign_id, "book-1")
        self.assertFalse(candidates[0].is_existing)

    def test_add_request_preserves_readarr_add_options(self):
        self.responses.append(FakeResponse(201, {"id": 99, "title": "A title"}))

        outcome = self.client.request(self.book_candidate)

        self.assertEqual(self.requests[-1]["path"], "/api/v1/book")
        self.assertTrue(self.requests[-1]["json"]["addOptions"]["searchForNewBook"])
        self.assertTrue(self.requests[-1]["json"]["monitored"])
        self.assertNotIn("rootFolderPath", self.requests[-1]["json"])
        self.assertEqual(outcome, {"id": 99, "title": "A title"})

    def test_book_request_adds_configuration_to_an_unstored_author(self):
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
        self.assertEqual(author["addOptions"], {"monitor": "all", "searchForMissingBooks": True})

    def test_author_request_applies_configuration_and_missing_search(self):
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
        self.assertEqual(payload["addOptions"], {"monitor": "all", "searchForMissingBooks": True})

    def test_invalid_configuration_and_http_errors_do_not_expose_api_key(self):
        with self.assertRaisesRegex(readarr.ReadarrError, "root_folder_path"):
            readarr.ReadarrConfiguration("", 4, 7, "all", "all")

        self.responses.append(FakeResponse(500, {"message": "backend failed"}))
        with self.assertRaises(readarr.ReadarrError) as raised:
            self.client.search("A title")

        self.assertNotIn("not-a-real-key", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
