"""Seven-day grace for apps whose icon was a flat color.

The public notice dated 2026-10-13 is the start of the clock for icons
already removed. A flat icon found later gets seven days from the moment
we notice it. When the deadline passes and there is still no usable icon,
the app leaves the market. The download page stays up.
"""

import tarfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.engine.icon_quality import is_unusable_icon, strip_solid_icons
from server.market_dedupe import unpublish_apps

# Matches the announcement timeline. Apps that already lost a flat icon
# share this start, so the date in the notice and the deadline agree.
NOTICE_AT = "2026-10-13T16:00:00Z"
REVIEW_DAYS = 7


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))


def review_deadline_passed(deadline_at: str, now: datetime = None) -> bool:
    moment = now or datetime.now(timezone.utc)
    return moment >= _parse(deadline_at)


def deadline_for(flagged_at: str, days: int = REVIEW_DAYS) -> str:
    moment = _parse(flagged_at) + timedelta(days=days)
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _created_at(history_store, app_id: str) -> str:
    rows = history_store.fetch_app_rows([app_id])
    if not rows:
        return ""
    return str(rows[0].get("created_at") or "")


def _flag(history_store, app_id: str) -> bool:
    created = _created_at(history_store, app_id)
    if created and created <= NOTICE_AT:
        return history_store.flag_icon_review(app_id, flagged_at=NOTICE_AT)
    return history_store.flag_icon_review(app_id)


def _read_zip_icon(path: Path, suffix: str) -> bytes:
    if not path.is_file():
        return b""
    try:
        with zipfile.ZipFile(path) as bundle:
            names = [name for name in bundle.namelist() if name.lower().endswith(suffix)]
            if not names:
                return b""
            names.sort(key=len)
            return bundle.read(names[0])
    except (OSError, zipfile.BadZipFile, KeyError):
        return b""


def _read_tar_icon(path: Path) -> bytes:
    if not path.is_file():
        return b""
    try:
        with tarfile.open(path, "r:gz") as bundle:
            members = [member for member in bundle.getmembers() if member.isfile() and member.name.lower().endswith("icon.png")]
            if not members:
                return b""
            extracted = bundle.extractfile(members[0])
            return extracted.read() if extracted else b""
    except (OSError, tarfile.TarError):
        return b""


def embedded_icon_bytes(app_dir: Path) -> bytes:
    """Icon bytes saved inside a desktop package.

    The Android package also carries a flat purple filler when a build has
    no icon. That filler is not evidence the app used a flat icon, so the
    APK is not read here.
    """
    downloads = Path(app_dir) / "downloads"
    for reader in (
        lambda: _read_zip_icon(downloads / "windows.zip", "icon.png"),
        lambda: _read_tar_icon(downloads / "linux.tar.gz"),
    ):
        data = reader()
        if data:
            return data
    return b""


def find_packaged_solid_apps(apps_dir: Path) -> list:
    """Apps with no current icon whose old package still holds a flat one."""
    root = Path(apps_dir)
    if not root.is_dir():
        return []
    found = []
    for app_dir in root.iterdir():
        if not app_dir.is_dir() or app_dir.name.startswith("_"):
            continue
        if not (app_dir / "recipe.json").is_file():
            continue
        icon_path = app_dir / "icon.png"
        if icon_path.is_file():
            try:
                if not is_unusable_icon(icon_path.read_bytes()):
                    continue
            except OSError:
                continue
        blob = embedded_icon_bytes(app_dir)
        if blob and is_unusable_icon(blob):
            found.append(app_dir.name)
    return found


def _icon_is_good(apps_dir: Path, app_id: str) -> bool:
    icon_path = Path(apps_dir) / app_id / "icon.png"
    if not icon_path.is_file():
        return False
    try:
        return not is_unusable_icon(icon_path.read_bytes())
    except OSError:
        return False


def enforce_icon_review_deadlines(history_store, apps_dir: Path, now: str = "") -> list:
    """Unpublish public apps that missed the icon deadline. Returns those ids."""
    moment = _parse(now) if now else datetime.now(timezone.utc)
    pending = history_store.open_icon_reviews()
    late = []
    for app_id, review in pending.items():
        if _icon_is_good(apps_dir, app_id):
            history_store.resolve_icon_review(app_id)
            continue
        deadline = _parse(review["deadline_at"])
        if moment < deadline:
            continue
        visibility = history_store.get_app_visibility(app_id) or {}
        if visibility.get("visibility") == "public":
            late.append(app_id)
    return unpublish_apps(history_store, apps_dir, late)


def run_icon_review_pass(history_store, apps_dir: Path) -> dict:
    stripped = strip_solid_icons(apps_dir)
    flagged = []
    for app_id in list(stripped) + find_packaged_solid_apps(apps_dir):
        if _flag(history_store, app_id):
            flagged.append(app_id)
    unpublished = enforce_icon_review_deadlines(history_store, apps_dir)
    return {
        "stripped": stripped,
        "flagged": flagged,
        "unpublished": unpublished,
    }
