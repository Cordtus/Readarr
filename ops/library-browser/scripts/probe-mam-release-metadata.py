#!/usr/bin/env python3
"""Report whether Readarr exposes explicit freeleech/VIP release metadata.

This probe is read-only. It loads the protected local request-desk
configuration, accepts one existing Readarr book ID on standard input, and
prints field names and JSON value types only. It never prints release values
or protected configuration values.
"""

import json
import os
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


CONFIG_PATH = Path("/home/sv/library-browser/readarr-request.json")
FREELEECH_FIELDS = {"freeleech", "vip", "vipfreeleech"}


def main():
    book_id = read_book_id()
    config = load_protected_config()
    releases = fetch_releases(config, book_id)
    field_types = release_field_types(releases)
    has_explicit_metadata = any(
        field.lower() in FREELEECH_FIELDS and "boolean" in types
        for field, types in field_types.items()
    )
    print(json.dumps({
        "releaseFieldTypes": field_types,
        "hasExplicitFreeleechOrVipBoolean": has_explicit_metadata,
    }, sort_keys=True))
    return 0 if has_explicit_metadata else 3


def read_book_id():
    value = sys.stdin.readline().strip()
    if not value.isdecimal() or int(value) <= 0:
        raise ValueError("supply one positive Readarr book ID on standard input")
    return int(value)


def load_protected_config():
    metadata = CONFIG_PATH.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("protected request-desk configuration permissions are unsafe")
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict):
        raise ValueError("protected request-desk configuration is invalid")
    url = config.get("url")
    api_key = config.get("apiKey")
    if not isinstance(url, str) or not url or not isinstance(api_key, str) or not api_key:
        raise ValueError("protected request-desk configuration is invalid")
    return {"url": url.rstrip("/"), "apiKey": api_key}


def fetch_releases(config, book_id):
    endpoint = "{}/api/v1/release?{}".format(
        config["url"], urllib.parse.urlencode({"bookId": book_id})
    )
    request = urllib.request.Request(endpoint, headers={"X-Api-Key": config["apiKey"]})
    with urllib.request.urlopen(request, timeout=60) as response:
        releases = json.loads(response.read().decode("utf-8"))
    if not isinstance(releases, list):
        raise ValueError("Readarr returned an invalid release response")
    return releases


def release_field_types(releases):
    fields = {}
    for release in releases:
        if not isinstance(release, dict):
            continue
        for field, value in release.items():
            if is_sensitive_field(field):
                continue
            fields.setdefault(field, set()).add(json_type(value))
    return {field: sorted(types) for field, types in sorted(fields.items())}


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def is_sensitive_field(field):
    field = field.lower()
    return (
        field == "title"
        or field.endswith("url")
        or any(fragment in field for fragment in ("apikey", "cookie", "guid", "passkey", "token"))
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        print("MAM release metadata probe could not complete safely", file=sys.stderr)
        raise SystemExit(2)
