#!/usr/bin/env python3
import argparse
import mimetypes
import posixpath
import urllib.parse
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from templates import catalog, landing


ROUTES = {"/Books/": "Books", "/Audiobooks/": "Audiobooks"}


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


def create_handler(roots):
    resolved_roots = {name: Path(root).resolve() for name, root in roots.items()}

    class LibraryHandler(BaseHTTPRequestHandler):
        server_version = "ReadarrLibrary/1.0"

        def do_GET(self):
            self.handle_request(send_body=True)

        def do_HEAD(self):
            self.handle_request(send_body=False)

        def handle_request(self, send_body):
            request_path = urllib.parse.urlsplit(self.path).path
            # Support both a stripped reverse-proxy prefix and a transparent
            # /library prefix without widening the set of application routes.
            if request_path.startswith("/library/"):
                request_path = request_path[len("/library"):]
            if request_path == "/" or request_path == "":
                self.send_html(landing(), send_body)
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

        def send_html(self, content, send_body):
            body = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
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
            print("{} - - [{}] {}".format(self.client_address[0], self.log_date_time_string(), fmt % args), flush=True)

    return LibraryHandler


def create_server(host, port, books_root, audiobooks_root):
    roots = {"Books": Path(books_root), "Audiobooks": Path(audiobooks_root)}
    return ThreadingHTTPServer((host, port), create_handler(roots))


def main():
    parser = argparse.ArgumentParser(description="Readarr Library Browser")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--books-root", required=True)
    parser.add_argument("--audiobooks-root", required=True)
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.books_root, args.audiobooks_root)
    print("Readarr Library Browser listening on {}:{}".format(args.host, args.port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
