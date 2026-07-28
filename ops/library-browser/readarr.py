import copy
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
        configuration: Optional[ReadarrConfiguration] = None,
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
        self._configuration = configuration
        self._opener = opener

    def search(self, term):
        if not isinstance(term, str) or not term.strip():
            raise ReadarrError("search term must not be empty")
        response = self._send("GET", "/api/v1/search?{}".format(
            urllib.parse.urlencode({"term": term})
        ))
        if not isinstance(response, list):
            raise ReadarrError("Readarr returned an invalid search response")
        return [self._normalize_candidate(item) for item in response]

    def request(self, candidate):
        if not isinstance(candidate, Candidate):
            raise ReadarrError("invalid request candidate")
        if candidate.is_existing:
            raise ReadarrError("request candidate already exists")
        configuration = self._require_configuration()
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
            payload["addOptions"] = {"searchForNewBook": True}
            payload["monitored"] = True
            return self._send("POST", "/api/v1/book", payload)
        raise ReadarrError("invalid request candidate")

    def _require_configuration(self):
        if self._configuration is None:
            raise ReadarrError("Readarr request configuration must be configured")
        return self._configuration

    @staticmethod
    def _new_author(author, configuration):
        payload = copy.deepcopy(dict(author))
        payload["addOptions"] = {
            "monitor": configuration.monitor,
            "searchForMissingBooks": True,
        }
        payload["monitored"] = True
        payload["monitorNewItems"] = configuration.monitor_new_items
        payload["qualityProfileId"] = configuration.quality_profile_id
        payload["metadataProfileId"] = configuration.metadata_profile_id
        payload["rootFolderPath"] = configuration.root_folder_path
        return payload

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
            with self._opener(request, timeout=10) as response:
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
