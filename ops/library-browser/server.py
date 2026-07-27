#!/usr/bin/env python3
import argparse
import json
import mimetypes
import posixpath
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from readarr import CandidateStore, ReadarrClient, ReadarrConfiguration, ReadarrError
from templates import (
    catalog,
    landing,
    request_confirmation,
    request_desk,
    request_error,
    request_results,
    request_success,
)


ROUTES = {"/Books/": "Books", "/Audiobooks/": "Audiobooks"}
MAX_FORM_BYTES = 8 * 1024


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        self.exit(2, "error: invalid command-line arguments; use --help\n")


class CandidatePreviewStore:
    def __init__(self, candidate_store, ttl_seconds=300, clock=time.time):
        self._candidate_store = candidate_store
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._previews = {}
        self._lock = threading.Lock()
        self._closed = False

    def put(self, candidate):
        with self._lock:
            if self._closed:
                raise RuntimeError("candidate preview store is closed")
            self._purge_expired()
            expires_at = self._clock() + self._ttl_seconds
            token = self._candidate_store.put(candidate)
            marker = object()
            self._schedule_expiry(token, expires_at, candidate, marker)
            return token

    def peek(self, token):
        with self._lock:
            self._purge_expired()
            preview = self._previews.get(token)
            return preview[1] if preview is not None else None

    def take(self, token):
        with self._lock:
            preview = self._previews.pop(token, None)
            if preview is not None:
                preview[2].cancel()
            return self._candidate_store.take(token)

    def close(self):
        with self._lock:
            self._closed = True
            for token, (_, _, timer, _) in self._previews.items():
                timer.cancel()
                self._candidate_store.discard(token)
            self._previews.clear()

    def _schedule_expiry(self, token, expires_at, candidate, marker):
        delay = max(0, expires_at - self._clock())
        timer = threading.Timer(delay, self._expire, args=(token, marker))
        timer.daemon = True
        self._previews[token] = (expires_at, candidate, timer, marker)
        timer.start()

    def _expire(self, token, marker):
        with self._lock:
            preview = self._previews.get(token)
            if self._closed or preview is None or preview[3] is not marker:
                return
            expires_at, candidate, _, _ = preview
            if self._clock() < expires_at:
                self._schedule_expiry(token, expires_at, candidate, marker)
                return
            self._previews.pop(token, None)
            self._candidate_store.discard(token)

    def _purge_expired(self):
        now = self._clock()
        expired_tokens = [
            token for token, (expires_at, _, _, _) in self._previews.items()
            if now >= expires_at
        ]
        for token in expired_tokens:
            _, _, timer, _ = self._previews.pop(token)
            timer.cancel()
            self._candidate_store.discard(token)


def request_candidate_store(candidate_store=None):
    candidate_store = candidate_store or CandidateStore()
    if hasattr(candidate_store, "peek"):
        return candidate_store
    return CandidatePreviewStore(candidate_store)


class LibraryServer(ThreadingHTTPServer):
    def __init__(self, server_address, request_handler_class, candidate_store):
        super().__init__(server_address, request_handler_class)
        self._candidate_store = candidate_store

    def server_close(self):
        super().server_close()
        close = getattr(self._candidate_store, "close", None)
        if close is not None:
            close()


def format_size(size):
    if size < 1024:
        return "{} B".format(size)
    units = ("KiB", "MiB", "GiB", "TiB")
    value = float(size)
    for unit in units:
        value /= 1024
        if value < 1024 or unit == units[-1]:
            return "{:.1f} {}".format(value, unit)


def url_path(path):
    return "/" + "/".join(urllib.parse.quote(part) for part in path.parts)


def create_handler(roots, readarr_client=None, candidate_store=None):
    resolved_roots = {name: Path(root).resolve() for name, root in roots.items()}
    candidate_store = request_candidate_store(candidate_store)
    candidate_lock = threading.Lock()

    class LibraryHandler(BaseHTTPRequestHandler):
        server_version = "ReadarrLibrary/1.0"

        def do_GET(self):
            self.handle_request(send_body=True)

        def do_HEAD(self):
            self.handle_request(send_body=False)

        def do_POST(self):
            request_path = self.application_path()
            if request_path != "/request/confirm/":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            if readarr_client is None:
                self.send_request_error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "Request desk unavailable",
                    "The request desk is unavailable right now. Please try again later.",
                )
                return
            if not self.has_same_origin():
                self.send_request_error(
                    HTTPStatus.FORBIDDEN,
                    "Request origin not accepted",
                    "Please submit the request from the request desk.",
                )
                return
            token = self.read_confirmation_token()
            if token is None:
                return
            with candidate_lock:
                candidate = candidate_store.take(token)
            if candidate is None:
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Request no longer available",
                    "This request is no longer available. Search the catalogue again to make a new request.",
                )
                return
            try:
                readarr_client.request(candidate)
            except (ReadarrError, OSError):
                self.send_request_error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "Request could not be sent",
                    "The catalogue cannot be reached right now. Please try again later.",
                )
                return
            self.send_html(request_success(candidate), send_body=True)

        def handle_request(self, send_body):
            request_path = self.application_path()
            if request_path == "/" or request_path == "":
                self.send_html(landing(), send_body)
                return
            if request_path == "/request/":
                if readarr_client is None:
                    self.send_request_error(
                        HTTPStatus.SERVICE_UNAVAILABLE,
                        "Request desk unavailable",
                        "The request desk is unavailable right now. Please try again later.",
                        send_body,
                    )
                else:
                    self.send_html(request_desk(), send_body)
                return
            if request_path == "/request/search/":
                self.send_request_search(send_body)
                return
            if request_path == "/request/confirm/":
                self.send_request_confirmation(send_body)
                return
            if request_path in ROUTES:
                self.send_catalog(ROUTES[request_path], send_body)
                return
            if request_path == "/assets/reading-room.webp":
                self.send_asset(send_body)
                return
            if request_path.startswith("/Books/") or request_path.startswith("/Audiobooks/"):
                self.send_media(request_path, send_body)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def application_path(self):
            request_path = urllib.parse.urlsplit(self.path).path
            # Support both a stripped reverse-proxy prefix and a transparent
            # /library prefix without widening the set of application routes.
            if request_path.startswith("/library/"):
                return request_path[len("/library"):]
            return request_path

        def send_request_search(self, send_body):
            if readarr_client is None:
                self.send_request_error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "Request desk unavailable",
                    "The request desk is unavailable right now. Please try again later.",
                    send_body,
                )
                return
            terms = urllib.parse.parse_qs(
                urllib.parse.urlsplit(self.path).query, keep_blank_values=True
            ).get("term", [])
            if len(terms) != 1:
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Search needs a title",
                    "Enter a search term between 2 and 200 characters.",
                    send_body,
                )
                return
            term = terms[0].strip()
            if not 2 <= len(term) <= 200:
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Search needs a title",
                    "Enter a search term between 2 and 200 characters.",
                    send_body,
                )
                return
            try:
                candidates = readarr_client.search(term)
            except (ReadarrError, OSError):
                self.send_request_error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "Catalogue unavailable",
                    "The catalogue cannot be reached right now. Please try again later.",
                    send_body,
                )
                return
            results = []
            try:
                with candidate_lock:
                    for candidate in candidates:
                        token = None
                        if not candidate.is_existing:
                            token = candidate_store.put(candidate)
                        results.append((token, candidate))
            except RuntimeError:
                self.send_request_error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "Request desk unavailable",
                    "The request desk is unavailable right now. Please try again later.",
                    send_body,
                )
                return
            self.send_html(request_results(results), send_body)

        def has_same_origin(self):
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if not origin or not host:
                return False
            try:
                parsed_origin = urllib.parse.urlsplit(origin)
            except ValueError:
                return False
            return (
                parsed_origin.scheme in ("http", "https")
                and parsed_origin.netloc == host
                and not parsed_origin.path
                and not parsed_origin.query
                and not parsed_origin.fragment
            )

        def send_request_confirmation(self, send_body):
            if readarr_client is None:
                self.send_request_error(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "Request desk unavailable",
                    "The request desk is unavailable right now. Please try again later.",
                    send_body,
                )
                return
            tokens = urllib.parse.parse_qs(
                urllib.parse.urlsplit(self.path).query, keep_blank_values=True
            ).get("token", [])
            if len(tokens) != 1 or not tokens[0]:
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Request no longer available",
                    "This request is no longer available. Search the catalogue again to make a new request.",
                    send_body,
                )
                return
            with candidate_lock:
                candidate = candidate_store.peek(tokens[0])
            if candidate is None:
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Request no longer available",
                    "This request is no longer available. Search the catalogue again to make a new request.",
                    send_body,
                )
                return
            self.send_html(request_confirmation(candidate, tokens[0]), send_body)

        def read_confirmation_token(self):
            if self.headers.get_content_type() != "application/x-www-form-urlencoded":
                self.send_request_error(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    "Request form required",
                    "Please submit the request form from the confirmation page.",
                )
                return None
            content_length = self.headers.get("Content-Length")
            try:
                content_length = int(content_length)
            except (TypeError, ValueError):
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Invalid request form",
                    "The request form could not be read. Please try again.",
                )
                return None
            if content_length < 0:
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Invalid request form",
                    "The request form could not be read. Please try again.",
                )
                return None
            if content_length > MAX_FORM_BYTES:
                self.send_request_error(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "Request form too large",
                    "The request form is too large. Please try again.",
                )
                return None
            try:
                fields = urllib.parse.parse_qs(
                    self.rfile.read(content_length).decode("utf-8"),
                    keep_blank_values=True,
                    strict_parsing=True,
                    max_num_fields=2,
                )
            except (UnicodeDecodeError, ValueError):
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Invalid request form",
                    "The request form could not be read. Please try again.",
                )
                return None
            tokens = fields.get("token", [])
            if set(fields) != {"token"} or len(tokens) != 1 or not tokens[0]:
                self.send_request_error(
                    HTTPStatus.BAD_REQUEST,
                    "Invalid request form",
                    "The request form could not be read. Please try again.",
                )
                return None
            return tokens[0]

        def send_request_error(self, status, title, message, send_body=True):
            self.send_html(request_error(title, message), send_body, status=status)

        def send_html(self, content, send_body, status=HTTPStatus.OK):
            body = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if send_body:
                self.wfile.write(body)

        def send_catalog(self, name, send_body, directory=None):
            media_root = resolved_roots[name]
            root = directory or media_root
            entries = []
            try:
                children = []
                for entry in root.iterdir():
                    if entry.name.startswith("."):
                        continue
                    try:
                        resolved = entry.resolve()
                        resolved.relative_to(root)
                        if not resolved.exists():
                            continue
                    except (OSError, ValueError):
                        continue
                    children.append((entry, resolved))
                children.sort(key=lambda pair: (not pair[1].is_dir(), pair[0].name.casefold()))
                for entry, resolved in children:
                    stat = resolved.stat()
                    relative = entry.relative_to(media_root)
                    href = "/library/{}{}".format(name, url_path(relative))
                    is_dir = resolved.is_dir()
                    if is_dir:
                        href += "/"
                    entries.append({
                        "name": entry.name,
                        "href": href,
                        "is_dir": is_dir,
                        "size": "Folder" if is_dir else format_size(stat.st_size),
                        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                    })
            except OSError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            theme = "audio" if name == "Audiobooks" else "books"
            if directory is None:
                title = name
                breadcrumbs = [("The Library of Bex", "/library/"), (name, None)]
            else:
                title = directory.name
                relative_directory = directory.relative_to(media_root)
                breadcrumbs = [
                    ("The Library of Bex", "/library/"),
                    (name, "/library/{}/".format(name)),
                ]
                current = Path()
                for part in relative_directory.parts:
                    current /= part
                    breadcrumbs.append(
                        (part, "/library/{}{}".format(name, url_path(current)) + "/")
                    )
                breadcrumbs[-1] = (breadcrumbs[-1][0], None)
            self.send_html(
                catalog(
                    title,
                    "/{}".format(name),
                    entries,
                    theme=theme,
                    breadcrumbs=breadcrumbs,
                ),
                send_body,
            )

        def safe_media_path(self, request_path):
            name, encoded_relative = request_path[1:].split("/", 1)
            if name not in resolved_roots:
                raise PermissionError
            relative = urllib.parse.unquote(encoded_relative)
            if "\\" in relative or "\x00" in relative:
                raise PermissionError
            candidate = (resolved_roots[name] / posixpath.normpath(relative)).resolve()
            candidate.relative_to(resolved_roots[name])
            return candidate

        def send_media(self, request_path, send_body):
            try:
                candidate = self.safe_media_path(request_path)
                if candidate.is_dir():
                    if not request_path.endswith("/"):
                        self.send_error(HTTPStatus.NOT_FOUND)
                        return
                    name = request_path[1:].split("/", 1)[0]
                    self.send_catalog(name, send_body, candidate)
                    return
                if not candidate.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                stat = candidate.stat()
            except (OSError, PermissionError, ValueError):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(stat.st_size))
            self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''{}".format(urllib.parse.quote(candidate.name)))
            self.end_headers()
            if send_body:
                with candidate.open("rb") as media_file:
                    while chunk := media_file.read(1024 * 1024):
                        self.wfile.write(chunk)

        def send_asset(self, send_body):
            asset = Path(__file__).with_name("assets") / "reading-room.webp"
            try:
                stat = asset.stat()
            except OSError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "image/webp")
            self.send_header("Content-Length", str(stat.st_size))
            self.end_headers()
            if send_body:
                with asset.open("rb") as image:
                    while chunk := image.read(1024 * 1024):
                        self.wfile.write(chunk)

        def log_message(self, fmt, *args):
            pass

    return LibraryHandler


def create_server(host, port, books_root, audiobooks_root, readarr_client=None, candidate_store=None):
    roots = {"Books": Path(books_root), "Audiobooks": Path(audiobooks_root)}
    candidate_store = request_candidate_store(candidate_store)
    return LibraryServer(
        (host, port), create_handler(roots, readarr_client, candidate_store), candidate_store
    )


def parse_args(arguments=None):
    parser = SafeArgumentParser(description="Readarr Library Browser")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--books-root", required=True)
    parser.add_argument("--audiobooks-root", required=True)
    parser.add_argument("--readarr-config", type=Path)
    return parser.parse_args(arguments)


def load_readarr_client(config_path, log=print):
    if config_path is None:
        return None
    try:
        with Path(config_path).open(encoding="utf-8") as config_file:
            values = json.load(config_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        log("Readarr request desk unavailable: configuration could not be read")
        return None
    try:
        if not isinstance(values, dict):
            raise ReadarrError("Readarr configuration must be a JSON object")
        configuration = ReadarrConfiguration(
            root_folder_path=values["rootFolderPath"],
            quality_profile_id=values["qualityProfileId"],
            metadata_profile_id=values["metadataProfileId"],
            monitor=values["monitor"],
            monitor_new_items=values["monitorNewItems"],
        )
        return ReadarrClient(values["url"], values["apiKey"], configuration)
    except (KeyError, TypeError, ValueError, ReadarrError):
        log("Readarr request desk unavailable: configuration is invalid")
        return None


def main():
    args = parse_args()
    readarr_client = load_readarr_client(args.readarr_config)
    server = create_server(
        args.host,
        args.port,
        args.books_root,
        args.audiobooks_root,
        readarr_client=readarr_client,
    )
    print("Readarr Library Browser listening on {}:{}".format(args.host, args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
