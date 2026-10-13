"""Rules for one public listing per creator, and one rating per person.

A creator may not keep two public apps that share a normalized name, a
target address, an uploaded icon, or an HTML content hash. The newest
listing wins. Generated placeholder icons are not compared: many unrelated
apps share that solid-color file because the site had no favicon.
"""

import re
from typing import Iterable
from urllib.parse import urlparse

_NAME_GAPS = re.compile(r"[\s_\-–—]+")
_INDEX_HTML = re.compile(r"/index\.html$", re.I)


def normalize_app_name(name: str) -> str:
    """Case-fold and drop spacing so '핑크 어드벤처' and '핑크-어드벤처' match."""
    return _NAME_GAPS.sub("", str(name or "").strip().casefold())


def normalize_target_url(url: str) -> str:
    """Host + path, ignoring scheme, www, default ports, and a trailing index.html."""
    raw = str(url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return ""
    try:
        port = parsed.port
    except ValueError:
        port = None
    scheme = (parsed.scheme or "https").lower()
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = re.sub(r"/+$", "", parsed.path or "")
    if path.lower() == "index.html":
        path = ""
    else:
        path = _INDEX_HTML.sub("", path)
        path = re.sub(r"/+$", "", path)
    return host + path


def _rank(record: dict) -> tuple:
    return (
        str(record.get("created_at") or ""),
        str(record.get("updated_at") or ""),
        str(record.get("app_id") or ""),
    )


def retirement_ids(records: Iterable[dict]) -> list:
    """App ids that lose to a newer public sibling on any duplicate key.

    Keys are ``name_key``, ``url_key``, ``icon_key``, and ``content_key``.
    Empty keys never group. An app retired by one key is not allowed to
    remain the winner of another, so the pass repeats until it settles.
    """
    by_id = {}
    for record in records:
        app_id = str((record or {}).get("app_id") or "")
        if app_id:
            by_id[app_id] = record
    retired = set()
    changed = True
    while changed:
        changed = False
        alive = [record for app_id, record in by_id.items() if app_id not in retired]
        for field in ("name_key", "url_key", "icon_key", "content_key"):
            buckets = {}
            for record in alive:
                if record["app_id"] in retired:
                    continue
                key = str(record.get(field) or "")
                if not key:
                    continue
                buckets.setdefault(key, []).append(record)
            for group in buckets.values():
                if len(group) < 2:
                    continue
                winner = max(group, key=_rank)
                for record in group:
                    if record["app_id"] != winner["app_id"]:
                        retired.add(record["app_id"])
                        changed = True
    return sorted(retired)
