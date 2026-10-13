"""Apply the public-market duplicate rules to apps already on disk.

Older conflicting public apps are set back to private. Their download
pages stay up, so an already-shared link keeps working; they just leave
the market. Repeat ratings from the same person collapse to the newest one.
"""

import hashlib
import json
from pathlib import Path
from typing import Optional

from server.market_rules import normalize_app_name, normalize_target_url, retirement_ids


def record_from_row(row: dict, apps_dir: Path) -> dict:
    recipe = row.get("recipe") or {}
    icon_key = ""
    if recipe.get("custom_icon_uploaded"):
        icon_path = Path(apps_dir) / str(row.get("app_id") or "") / "icon.png"
        try:
            if icon_path.is_file():
                icon_key = hashlib.sha256(icon_path.read_bytes()).hexdigest()
        except OSError:
            icon_key = ""
    return {
        "app_id": row.get("app_id") or "",
        "created_at": row.get("created_at") or "",
        "updated_at": row.get("updated_at") or "",
        "name_key": normalize_app_name(row.get("name") or recipe.get("name") or ""),
        "url_key": normalize_target_url(row.get("target_url") or recipe.get("url") or ""),
        "content_key": str(recipe.get("content_hash") or "").strip().lower(),
        "icon_key": icon_key,
    }


def _candidate_records(history_store, community_store, apps_dir: Path, fp: str,
                       force_app_id: Optional[str] = None) -> list:
    ids = list(community_store.apps_by_creator(fp))
    if force_app_id and force_app_id not in ids:
        ids.append(force_app_id)
    records = []
    for row in history_store.fetch_app_rows(ids):
        if row.get("visibility") != "public" and row.get("app_id") != force_app_id:
            continue
        records.append(record_from_row(row, apps_dir))
    return records


def conflicts_with_newer(history_store, community_store, apps_dir: Path, fp: str, app_id: str) -> bool:
    """True when publishing ``app_id`` would lose to a newer public duplicate."""
    if not fp or str(fp).startswith("ip:") or not app_id:
        return False
    doomed = set(retirement_ids(_candidate_records(
        history_store, community_store, apps_dir, fp, force_app_id=app_id,
    )))
    return app_id in doomed


def _unpublish(history_store, apps_dir: Path, app_ids) -> list:
    done = []
    for app_id in app_ids:
        app_id = str(app_id or "")
        if not app_id:
            continue
        recipe_path = Path(apps_dir) / app_id / "recipe.json"
        if recipe_path.is_file():
            try:
                stored = json.loads(recipe_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                stored = None
            if isinstance(stored, dict):
                stored["visibility"] = "private"
                recipe_path.write_text(
                    json.dumps(stored, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        if history_store.set_app_visibility(app_id, "private"):
            done.append(app_id)
    return done


def unpublish_apps(history_store, apps_dir: Path, app_ids) -> list:
    """Take apps off the market without deleting their download pages."""
    return _unpublish(history_store, apps_dir, app_ids)


def dedupe_creator(history_store, community_store, apps_dir: Path, fp: str) -> list:
    """Unpublish this creator's older public duplicates. Returns those app ids."""
    if not fp or str(fp).startswith("ip:"):
        return []
    doomed = retirement_ids(_candidate_records(history_store, community_store, apps_dir, fp))
    return _unpublish(history_store, apps_dir, doomed)


def dedupe_public_market(history_store, community_store, apps_dir: Path) -> dict:
    """One pass over every creator, plus a collapse of stacked ratings."""
    retired = []
    for fp in community_store.creator_fingerprints():
        retired.extend(dedupe_creator(history_store, community_store, apps_dir, fp))
    removed_ratings = community_store.collapse_duplicate_ratings()
    return {"retired_apps": retired, "removed_ratings": removed_ratings}
