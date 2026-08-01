import copy
import dataclasses
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional


class ReadarrError(Exception):
    """A safe error raised when Readarr cannot complete a request."""


@dataclass(frozen=True)
class ReadarrConfiguration:
    root_folder_path: str
    quality_profile_id: int
    metadata_profile_id: int
    monitor: str
    monitor_new_items: str

    def __post_init__(self):
        if not isinstance(self.root_folder_path, str) or not self.root_folder_path.strip():
            raise ReadarrError("root_folder_path must be configured")
        if not isinstance(self.quality_profile_id, int) or isinstance(self.quality_profile_id, bool):
            raise ReadarrError("quality_profile_id must be an integer")
        if not isinstance(self.metadata_profile_id, int) or isinstance(self.metadata_profile_id, bool):
            raise ReadarrError("metadata_profile_id must be an integer")
        if not isinstance(self.monitor, str) or not self.monitor.strip():
            raise ReadarrError("monitor must be configured")
        if not isinstance(self.monitor_new_items, str) or not self.monitor_new_items.strip():
            raise ReadarrError("monitor_new_items must be configured")


@dataclass(frozen=True)
class Candidate:
    kind: str
    foreign_id: str
    title: str
    author_name: str
    is_existing: bool
    lookup: Mapping[str, Any]
    year: Optional[int] = None
    target: str = "audiobooks"


@dataclass(frozen=True)
class Release:
    guid: str
    indexer_id: int
    title: str
    size: int
    download_allowed: bool
    freeleech: bool = False


@dataclass(frozen=True)
class ReleaseSelection:
    release: Release
    book_id: int
    book_title: str
    scope: str


class CandidateStore:
    def __init__(self, ttl_seconds=300, clock: Callable[[], float] = time.time):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._candidates = {}
        self._lock = threading.Lock()

    def put(self, candidate):
        with self._lock:
            token = secrets.token_urlsafe(24)
            self._candidates[token] = (self._clock() + self._ttl_seconds, candidate)
            return token

    def take(self, token):
        with self._lock:
            entry = self._candidates.pop(token, None)
            if entry is None:
                return None
            expires_at, candidate = entry
            if self._clock() >= expires_at:
                return None
            return candidate

    def discard(self, token):
        with self._lock:
            self._candidates.pop(token, None)


class ReadarrClient:
    def __init__(
        self,
        base_url,
        api_key,
        configurations: Optional[Mapping[str, ReadarrConfiguration]] = None,
        opener=urllib.request.urlopen,
    ):
        if not isinstance(base_url, str) or not base_url:
            raise ReadarrError("Readarr base URL must be an absolute HTTP URL")
        parsed_url = urllib.parse.urlsplit(base_url)
        if (
            parsed_url.scheme not in ("http", "https")
            or not parsed_url.netloc
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ReadarrError("Readarr base URL must be an absolute HTTP URL")
        if not isinstance(api_key, str) or not api_key:
            raise ReadarrError("Readarr API key must be configured")
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        if not isinstance(configurations, Mapping) or not configurations:
            raise ReadarrError("Readarr request targets must be configured")
        if any(
            not isinstance(name, str) or not name
            or not isinstance(configuration, ReadarrConfiguration)
            for name, configuration in configurations.items()
        ):
            raise ReadarrError("Readarr request targets are invalid")
        self._configurations = dict(configurations)
        self._opener = opener

    def search(self, term, target):
        if not isinstance(term, str) or not term.strip():
            raise ReadarrError("search term must not be empty")
        self._require_configuration(target)
        response = self._send("GET", "/api/v1/search?{}".format(
            urllib.parse.urlencode({"term": term})
        ))
        if not isinstance(response, list):
            raise ReadarrError("Readarr returned an invalid search response")
        return [
            dataclasses.replace(self._normalize_candidate(item), target=target)
            for item in response
        ]

    def add(self, candidate):
        if not isinstance(candidate, Candidate):
            raise ReadarrError("invalid request candidate")
        if candidate.is_existing:
            raise ReadarrError("request candidate already exists")
        configuration = self._require_configuration(candidate.target)
        if candidate.kind == "author":
            author = candidate.lookup.get("author")
            if not isinstance(author, Mapping):
                raise ReadarrError("invalid author candidate")
            if author.get("id"):
                raise ReadarrError("author candidate already exists")
            return self._send("POST", "/api/v1/author", self._new_author(author, configuration))
        if candidate.kind == "book":
            book = candidate.lookup.get("book")
            if not isinstance(book, Mapping):
                raise ReadarrError("invalid book candidate")
            payload = copy.deepcopy(dict(book))
            author = payload.get("author")
            if not isinstance(author, Mapping):
                raise ReadarrError("invalid book author")
            if not author.get("id"):
                payload["author"] = self._new_author(author, configuration)
                if configuration.monitor == "specificBook":
                    payload["author"]["addOptions"].pop("monitor")
                    payload["author"]["addOptions"]["booksToMonitor"] = [payload["foreignBookId"]]
            payload["addOptions"] = {}
            payload["monitored"] = True
            return self._send("POST", "/api/v1/book", payload)
        raise ReadarrError("invalid request candidate")

    def request(self, candidate):
        """Add a candidate without searching; releases are selected separately."""
        return self.add(candidate)

    def search_releases(self, book_id):
        if not isinstance(book_id, int) or isinstance(book_id, bool) or book_id <= 0:
            raise ReadarrError("invalid Readarr book id")
        response = self._send("GET", "/api/v1/release?{}".format(
            urllib.parse.urlencode({"bookId": book_id})
        ))
        if not isinstance(response, list):
            raise ReadarrError("Readarr returned an invalid release response")
        return [self._normalize_release(item) for item in response]

    def grab_release(self, release, book_id):
        if not isinstance(release, Release):
            raise ReadarrError("invalid release selection")
        if not release.download_allowed:
            raise ReadarrError("release is not available for download")
        if not isinstance(book_id, int) or isinstance(book_id, bool) or book_id <= 0:
            raise ReadarrError("invalid Readarr book id")
        return self._send("POST", "/api/v1/release", {
            "guid": release.guid,
            "indexerId": release.indexer_id,
            "bookId": book_id,
        })

    def _require_configuration(self, target):
        if not isinstance(target, str) or target not in self._configurations:
            raise ReadarrError("Readarr request target must be configured")
        return self._configurations[target]

    @staticmethod
    def _new_author(author, configuration):
        payload = copy.deepcopy(dict(author))
        payload["addOptions"] = {
            "monitor": configuration.monitor,
        }
        payload["monitored"] = True
        payload["monitorNewItems"] = configuration.monitor_new_items
        payload["qualityProfileId"] = configuration.quality_profile_id
        payload["metadataProfileId"] = configuration.metadata_profile_id
        payload["rootFolderPath"] = configuration.root_folder_path
        return payload

    @staticmethod
    def _normalize_release(item):
        if not isinstance(item, Mapping):
            raise ReadarrError("Readarr returned an invalid release")
        guid = item.get("guid")
        indexer_id = item.get("indexerId")
        title = item.get("title")
        size = item.get("size", 0)
        download_allowed = item.get("downloadAllowed")
        freeleech = item.get("freeleech", False)
        if (
            not isinstance(guid, str) or not guid
            or not isinstance(indexer_id, int) or isinstance(indexer_id, bool)
            or not isinstance(title, str) or not title
            or not isinstance(size, int) or isinstance(size, bool) or size < 0
            or not isinstance(download_allowed, bool)
            or not isinstance(freeleech, bool)
        ):
            raise ReadarrError("Readarr returned an invalid release")
        return Release(guid, indexer_id, title, size, download_allowed, freeleech)

    def _normalize_candidate(self, item):
        if not isinstance(item, Mapping):
            raise ReadarrError("Readarr returned an invalid search result")
        book = item.get("book")
        if isinstance(book, Mapping):
            author = book.get("author")
            if not isinstance(author, Mapping):
                raise ReadarrError("Readarr returned an invalid book result")
            foreign_id = book.get("foreignBookId") or item.get("foreignId")
            title = book.get("title")
            author_name = author.get("authorName", "")
            year = self._release_year(book.get("releaseDate"))
            if not isinstance(foreign_id, str) or not isinstance(title, str):
                raise ReadarrError("Readarr returned an invalid book result")
            return Candidate(
                kind="book",
                foreign_id=foreign_id,
                title=title,
                author_name=author_name if isinstance(author_name, str) else "",
                is_existing=bool(book.get("id")),
                lookup=copy.deepcopy(dict(item)),
                year=year,
            )
        author = item.get("author")
        if isinstance(author, Mapping):
            foreign_id = author.get("foreignAuthorId") or item.get("foreignId")
            title = author.get("authorName")
            if not isinstance(foreign_id, str) or not isinstance(title, str):
                raise ReadarrError("Readarr returned an invalid author result")
            return Candidate(
                kind="author",
                foreign_id=foreign_id,
                title=title,
                author_name=title,
                is_existing=bool(author.get("id")),
                lookup=copy.deepcopy(dict(item)),
            )
        raise ReadarrError("Readarr returned an invalid search result")

    @staticmethod
    def _release_year(value):
        if not isinstance(value, str) or len(value) < 4:
            return None
        try:
            year = int(value[:4])
        except ValueError:
            return None
        return year if 1 <= year <= 9999 else None

    def _send(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"X-Api-Key": self._api_key, "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            "{}{}".format(self._base_url, path),
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with self._opener(request, timeout=60) as response:
                status = getattr(response, "status", response.getcode())
                response_body = response.read()
        except urllib.error.HTTPError as error:
            raise ReadarrError("Readarr returned HTTP {}".format(error.code)) from error
        except (urllib.error.URLError, OSError) as error:
            raise ReadarrError("Readarr is unavailable") from error
        if status < 200 or status >= 300:
            raise ReadarrError("Readarr returned HTTP {}".format(status))
        try:
            return json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReadarrError("Readarr returned invalid JSON") from error
