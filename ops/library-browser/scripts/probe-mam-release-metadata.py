#!/usr/bin/env python3
"""Report whether Readarr exposes explicit generic freeleech release metadata.

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
FREELEECH_FIELD = "freeleech"
SENSITIVE_FIELD_FRAGMENTS = (
    "api",
    "auth",
    "cookie",
    "credential",
    "download",
    "guid",
    "hash",
    "key",
    "magnet",
    "passkey",
    "password",
    "secret",
    "title",
    "token",
    "uri",
    "url",
    "user",
)


def main():
    if len(sys.argv) != 1:
        raise ValueError("the probe accepts no command-line arguments")
    book_id = read_book_id()
    config = load_protected_config()
    releases = fetch_releases(config, book_id)
    field_types = release_field_types(releases)
    freeleech_field_types = {
        FREELEECH_FIELD: field_types[FREELEECH_FIELD],
    } if FREELEECH_FIELD in field_types else {}
    has_explicit_metadata = "boolean" in freeleech_field_types.get(FREELEECH_FIELD, [])
    print(json.dumps({
        "freeleechFieldTypes": freeleech_field_types,
        "hasExplicitFreeleechBoolean": has_explicit_metadata,
    }, sort_keys=True))
    return 0 if has_explicit_metadata else 3


def read_book_id():
    values = sys.stdin.read().split()
    if len(values) != 1 or not values[0].isdecimal() or int(values[0]) <= 0:
        raise ValueError("supply exactly one positive Readarr book ID on standard input")
    return int(values[0])


def load_protected_config():
    metadata = CONFIG_PATH.stat()
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise PermissionError("protected request-desk configuration permissions are unsafe")
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    if not isinstance(config, dict):
        raise ValueError("protected request-desk configuration is invalid")
    targets = config.get("targets")
    audio_target = targets.get("audiobooks") if isinstance(targets, dict) else None
    url = audio_target.get("url") if isinstance(audio_target, dict) else None
    api_key = audio_target.get("apiKey") if isinstance(audio_target, dict) else None
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
    return any(fragment in field for fragment in SENSITIVE_FIELD_FRAGMENTS)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        print("MAM release metadata probe could not complete safely", file=sys.stderr)
        raise SystemExit(2)
