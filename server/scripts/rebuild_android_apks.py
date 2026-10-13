#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.engine.distiller import Distiller
from server.engine.icon_quality import is_unusable_icon
from server.engine.storage import r2_storage


def _load_recipe(app_dir: Path) -> dict:
    recipe_path = app_dir / "recipe.json"
    return json.loads(recipe_path.read_text())


def _needs_rebuild(app_dir: Path, force: bool) -> bool:
    dl = app_dir / "downloads"
    apk = dl / "android.apk"
    zip_path = dl / "android.zip"
    if force:
        return (app_dir / "recipe.json").exists()
    if apk.exists() and apk.stat().st_size > 1024:
        return False
    return zip_path.exists() or not apk.exists()


def rebuild_one(distiller: Distiller, app_dir: Path, upload: bool) -> dict:
    recipe = _load_recipe(app_dir)
    app_id = recipe.get("id") or app_dir.name
    recipe["id"] = app_id
    dl = app_dir / "downloads"
    dl.mkdir(parents=True, exist_ok=True)

    icon_path = app_dir / "icon.png"
    icon_png = icon_path.read_bytes() if icon_path.exists() else None
    if icon_png and is_unusable_icon(icon_png):
        try:
            icon_path.unlink()
        except OSError:
            pass
        icon_png = None
    if not icon_png:
        # The APK toolchain wants a real PNG, but a flat color is not an
        # icon the market should keep. Pass it to the builder only.
        icon_png = distiller._make_placeholder_png(recipe.get("color") or "#7c3aed")

    shell_url = recipe.get("url") or ""
    if not shell_url:
        raise RuntimeError("recipe missing url")

    meta = distiller._build_android(dl, recipe, icon_png, shell_url)
    if not meta or not meta.get("apk"):
        raise RuntimeError(f"android rebuild failed for {app_id}: {meta}")

    zip_path = dl / "android.zip"
    if zip_path.exists():
        zip_path.unlink()

    cdn = dict(recipe.get("downloads_cdn") or {})
    if upload and r2_storage.configured:
        uploaded = r2_storage.upload_app_downloads(app_id, dl)
        if uploaded:
            cdn.update(uploaded)
            recipe["downloads_cdn"] = cdn

    recipe["android"] = meta
    if "platform_errors" in recipe:
        pe = dict(recipe.get("platform_errors") or {})
        pe.pop("android", None)
        if pe:
            recipe["platform_errors"] = pe
        else:
            recipe.pop("platform_errors", None)

    (app_dir / "recipe.json").write_text(json.dumps(recipe, ensure_ascii=False, indent=2))
    return {"app_id": app_id, "apk": True, "size": (dl / "android.apk").stat().st_size, "cdn": bool(cdn.get("android.apk"))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild missing Android APKs from existing recipes")
    parser.add_argument("--apps-dir", default=str(ROOT / "generated"))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-upload", action="store_true")
    parser.add_argument("--app-id", action="append", default=[])
    args = parser.parse_args()

    apps_dir = Path(args.apps_dir)
    if not apps_dir.exists():
        print(f"apps dir not found: {apps_dir}", file=sys.stderr)
        return 1

    distiller = Distiller()
    builder_ok = False
    try:
        from server.engine.apk_builder import ApkBuilder
        builder_ok = bool(ApkBuilder().can_build_apk)
    except Exception as exc:
        print(f"apk builder unavailable: {exc}", file=sys.stderr)
        return 2
    if not builder_ok:
        print("android toolchain not ready (can_build_apk=false)", file=sys.stderr)
        return 2

    candidates = []
    if args.app_id:
        for app_id in args.app_id:
            app_dir = apps_dir / app_id
            if (app_dir / "recipe.json").exists():
                candidates.append(app_dir)
    else:
        for recipe_path in sorted(apps_dir.glob("*/recipe.json"), key=lambda p: p.stat().st_mtime):
            app_dir = recipe_path.parent
            if _needs_rebuild(app_dir, args.force):
                candidates.append(app_dir)

    if args.limit and args.limit > 0:
        candidates = candidates[: args.limit]

    print(f"candidates={len(candidates)} upload={not args.no_upload}")
    ok = 0
    failed = 0
    for app_dir in candidates:
        app_id = app_dir.name
        try:
            result = rebuild_one(distiller, app_dir, upload=not args.no_upload)
            ok += 1
            print(f"ok {result['app_id']} size={result['size']} cdn={result['cdn']}")
        except Exception as exc:
            failed += 1
            print(f"fail {app_id}: {exc}", file=sys.stderr)
    print(f"done ok={ok} failed={failed}")
    return 0 if failed == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
