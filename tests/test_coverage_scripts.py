import json
import os
import runpy
import sys
from pathlib import Path

import pytest

from server import config
from server.engine import apk_builder as apk_builder_module
from server.engine import distiller as distiller_module
from server.scripts import backfill_r2, rebuild_android_apks, refresh_download_pages


def _recipe(app_dir: Path, data: dict) -> Path:
    app_dir.mkdir(parents=True, exist_ok=True)
    path = app_dir / "recipe.json"
    path.write_text(json.dumps(data))
    return path


def _download(app_dir: Path, name: str = "android.apk", data: bytes = b"apk") -> Path:
    downloads = app_dir / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    path = downloads / name
    path.write_bytes(data)
    return path


def test_script_backfill_iter_app_dirs_handles_missing_and_sorted_roots(tmp_path, monkeypatch):
    missing = tmp_path / "missing"
    monkeypatch.setattr(backfill_r2, "APPS_DIR", missing)
    assert list(backfill_r2.iter_app_dirs()) == []

    apps = tmp_path / "apps"
    second = _recipe(apps / "b-app", {"id": "b-app"})
    first = _recipe(apps / "a-app", {"id": "a-app"})
    monkeypatch.setattr(backfill_r2, "APPS_DIR", apps)
    assert list(backfill_r2.iter_app_dirs()) == [
        (first.parent, first),
        (second.parent, second),
    ]


def test_script_backfill_main_rejects_missing_r2(monkeypatch, capsys):
    monkeypatch.setattr(backfill_r2.config, "r2_configured", lambda: False)
    monkeypatch.setattr(sys, "argv", ["backfill_r2"])

    assert backfill_r2.main() == 1
    captured = capsys.readouterr()
    assert "R2 is not configured" in captured.err
    assert "set -a" in captured.err


def test_script_backfill_main_dry_run_covers_skips_and_bad_recipe(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    _recipe(apps / "no-downloads", {"id": "no-downloads"})

    empty = apps / "empty"
    _recipe(empty, {"id": "empty"})
    (empty / "downloads" / "nested").mkdir(parents=True)

    bad = apps / "bad-recipe"
    bad.mkdir(parents=True)
    (bad / "recipe.json").write_text("not-json")
    _download(bad)

    planned = apps / "planned"
    _recipe(planned, {"id": "planned"})
    _download(planned, "android.apk")
    _download(planned, "ios.mobileconfig")

    monkeypatch.setattr(backfill_r2, "APPS_DIR", apps)
    monkeypatch.setattr(backfill_r2.config, "r2_configured", lambda: True)
    monkeypatch.setattr(backfill_r2.config, "r2_bucket", lambda: "bucket")
    monkeypatch.setattr(backfill_r2.config, "r2_public_base_url", lambda: "https://cdn.test")
    monkeypatch.setattr(
        backfill_r2.r2_storage,
        "upload_app_downloads",
        lambda *_args: pytest.fail("dry run must not upload"),
    )
    monkeypatch.setattr(sys, "argv", ["backfill_r2", "--dry-run"])

    assert backfill_r2.main() == 2
    output = capsys.readouterr().out
    assert "Mode        : DRY RUN" in output
    assert "[skip] empty: no download files" in output
    assert "[skip] no-downloads: no download files" in output
    assert "[ERR ] bad-recipe: cannot read recipe.json" in output
    assert "[plan] planned: would upload 2 file(s)" in output
    assert "Apps scanned : 4" in output
    assert "Files done   : 2" in output
    assert "Errors       : 1" in output


def test_script_backfill_main_live_covers_upload_outcomes_and_merge(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    failing = apps / "upload-error"
    _recipe(failing, {"id": "upload-error"})
    _download(failing)

    empty_result = apps / "nothing-uploaded"
    _recipe(empty_result, {"id": "nothing-uploaded"})
    _download(empty_result)

    successful = apps / "success"
    successful_recipe = _recipe(
        successful,
        {"id": "success", "downloads_cdn": {"ios.mobileconfig": "https://old/ios"}},
    )
    _download(successful)

    def upload(app_id, _downloads_dir):
        if app_id == "upload-error":
            raise RuntimeError("offline")
        if app_id == "nothing-uploaded":
            return {}
        return {"android.apk": "https://cdn.test/success/android.apk"}

    monkeypatch.setattr(backfill_r2, "APPS_DIR", apps)
    monkeypatch.setattr(backfill_r2.config, "r2_configured", lambda: True)
    monkeypatch.setattr(backfill_r2.config, "r2_bucket", lambda: "bucket")
    monkeypatch.setattr(backfill_r2.config, "r2_public_base_url", lambda: "https://cdn.test")
    monkeypatch.setattr(backfill_r2.r2_storage, "upload_app_downloads", upload)
    monkeypatch.setattr(sys, "argv", ["backfill_r2"])

    assert backfill_r2.main() == 2
    saved = json.loads(successful_recipe.read_text())
    assert saved["downloads_cdn"] == {
        "ios.mobileconfig": "https://old/ios",
        "android.apk": "https://cdn.test/success/android.apk",
    }
    output = capsys.readouterr().out
    assert "Mode        : LIVE" in output
    assert "upload failed (offline)" in output
    assert "nothing uploaded" in output
    assert "[ok  ] success: 1 file(s)" in output


def test_script_backfill_main_empty_scan_succeeds(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill_r2, "APPS_DIR", tmp_path / "absent")
    monkeypatch.setattr(backfill_r2.config, "r2_configured", lambda: True)
    monkeypatch.setattr(backfill_r2.config, "r2_bucket", lambda: "bucket")
    monkeypatch.setattr(backfill_r2.config, "r2_public_base_url", lambda: "https://cdn.test")
    monkeypatch.setattr(sys, "argv", ["backfill_r2"])
    assert backfill_r2.main() == 0


def test_script_backfill_module_entrypoint(monkeypatch):
    monkeypatch.setattr(backfill_r2.config, "r2_configured", lambda: False)
    monkeypatch.setattr(sys, "argv", [backfill_r2.__file__])
    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(backfill_r2.__file__, run_name="__main__")
    assert exc_info.value.code == 1


def test_rebuild_needs_rebuild_all_file_states(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    assert rebuild_android_apks._needs_rebuild(app, force=True) is False
    _recipe(app, {"url": "https://example.test"})
    assert rebuild_android_apks._needs_rebuild(app, force=True) is True
    assert rebuild_android_apks._needs_rebuild(app, force=False) is True

    apk = _download(app, data=b"x" * 1025)
    assert rebuild_android_apks._needs_rebuild(app, force=False) is False
    apk.write_bytes(b"small")
    assert rebuild_android_apks._needs_rebuild(app, force=False) is False
    (app / "downloads" / "android.zip").write_bytes(b"legacy")
    assert rebuild_android_apks._needs_rebuild(app, force=False) is True


class _BuildingDistiller:
    def __init__(self):
        self.placeholder_colors = []

    def _make_placeholder_png(self, color):
        self.placeholder_colors.append(color)
        return b"placeholder-png"

    def _build_android(self, downloads, _recipe_data, _icon_png, _shell_url):
        (downloads / "android.apk").write_bytes(b"a" * 2048)
        return {"apk": "android.apk", "package": "test.package"}


def test_rebuild_one_builds_placeholder_uploads_and_preserves_other_errors(tmp_path, monkeypatch):
    app = tmp_path / "fallback-id"
    recipe_path = _recipe(
        app,
        {
            "url": "https://example.test",
            "color": "#123456",
            "downloads_cdn": {"ios.mobileconfig": "https://old/ios"},
            "platform_errors": {"android": "old error", "ios": "keep me"},
        },
    )
    _download(app, "android.zip", b"legacy")
    distiller = _BuildingDistiller()
    monkeypatch.setattr(config, "r2_configured", lambda: True)
    monkeypatch.setattr(
        rebuild_android_apks.r2_storage,
        "upload_app_downloads",
        lambda app_id, _downloads: {"android.apk": f"https://cdn.test/{app_id}/android.apk"},
    )

    result = rebuild_android_apks.rebuild_one(distiller, app, upload=True)

    assert result == {"app_id": "fallback-id", "apk": True, "size": 2048, "cdn": True}
    assert distiller.placeholder_colors == ["#123456"]
    assert not (app / "icon.png").exists()
    assert not (app / "downloads" / "android.zip").exists()
    saved = json.loads(recipe_path.read_text())
    assert saved["id"] == "fallback-id"
    assert saved["downloads_cdn"]["ios.mobileconfig"] == "https://old/ios"
    assert saved["downloads_cdn"]["android.apk"].endswith("/fallback-id/android.apk")
    assert saved["platform_errors"] == {"ios": "keep me"}
    assert saved["android"]["apk"] == "android.apk"


def test_rebuild_one_uses_existing_icon_and_removes_empty_platform_errors(tmp_path, monkeypatch):
    app = tmp_path / "directory-name"
    recipe_path = _recipe(
        app,
        {
            "id": "recipe-id",
            "url": "https://example.test",
            "platform_errors": {"android": "old error"},
        },
    )
    (app / "icon.png").write_bytes(b"real-icon")
    distiller = _BuildingDistiller()
    monkeypatch.setattr(
        rebuild_android_apks.r2_storage,
        "upload_app_downloads",
        lambda *_args: pytest.fail("upload=False must not upload"),
    )

    result = rebuild_android_apks.rebuild_one(distiller, app, upload=False)

    assert result["app_id"] == "recipe-id"
    assert result["cdn"] is False
    assert distiller.placeholder_colors == []
    assert "platform_errors" not in json.loads(recipe_path.read_text())


def test_rebuild_one_handles_empty_upload_and_no_platform_errors(tmp_path, monkeypatch):
    app = tmp_path / "app"
    recipe_path = _recipe(app, {"url": "https://example.test"})
    (app / "icon.png").write_bytes(b"real-icon")
    monkeypatch.setattr(config, "r2_configured", lambda: True)
    monkeypatch.setattr(rebuild_android_apks.r2_storage, "upload_app_downloads", lambda *_args: {})

    result = rebuild_android_apks.rebuild_one(_BuildingDistiller(), app, upload=True)

    assert result["cdn"] is False
    assert "downloads_cdn" not in json.loads(recipe_path.read_text())


def test_rebuild_one_rejects_missing_url_and_failed_build(tmp_path):
    missing_url = tmp_path / "missing-url"
    _recipe(missing_url, {})
    with pytest.raises(RuntimeError, match="recipe missing url"):
        rebuild_android_apks.rebuild_one(_BuildingDistiller(), missing_url, upload=False)

    failed_build = tmp_path / "failed-build"
    _recipe(failed_build, {"url": "https://example.test"})

    class FailedDistiller(_BuildingDistiller):
        def _build_android(self, *_args):
            return None

    with pytest.raises(RuntimeError, match="android rebuild failed"):
        rebuild_android_apks.rebuild_one(FailedDistiller(), failed_build, upload=False)


def _set_ready_builder(monkeypatch, ready=True):
    class Builder:
        can_build_apk = ready

    monkeypatch.setattr(apk_builder_module, "ApkBuilder", Builder)
    monkeypatch.setattr(rebuild_android_apks, "Distiller", lambda: object())


def test_rebuild_main_reports_builder_exception(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    apps.mkdir()

    def broken_builder():
        raise RuntimeError("sdk missing")

    monkeypatch.setattr(rebuild_android_apks, "Distiller", lambda: object())
    monkeypatch.setattr(apk_builder_module, "ApkBuilder", broken_builder)
    monkeypatch.setattr(sys, "argv", ["rebuild", "--apps-dir", str(apps)])

    assert rebuild_android_apks.main() == 2
    assert "apk builder unavailable: sdk missing" in capsys.readouterr().err


def test_rebuild_main_reports_unready_builder(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    apps.mkdir()
    _set_ready_builder(monkeypatch, ready=False)
    monkeypatch.setattr(sys, "argv", ["rebuild", "--apps-dir", str(apps)])

    assert rebuild_android_apks.main() == 2
    assert "can_build_apk=false" in capsys.readouterr().err


def test_rebuild_main_explicit_ids_limit_and_no_upload(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    selected = apps / "selected"
    _recipe(selected, {"url": "https://example.test"})
    calls = []

    def fake_rebuild(_distiller, app_dir, upload):
        calls.append((app_dir.name, upload))
        return {"app_id": app_dir.name, "size": 321, "cdn": False}

    _set_ready_builder(monkeypatch)
    monkeypatch.setattr(rebuild_android_apks, "rebuild_one", fake_rebuild)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "rebuild",
            "--apps-dir",
            str(apps),
            "--app-id",
            "missing",
            "--app-id",
            "selected",
            "--limit",
            "1",
            "--no-upload",
        ],
    )

    assert rebuild_android_apks.main() == 0
    assert calls == [("selected", False)]
    output = capsys.readouterr().out
    assert "candidates=1 upload=False" in output
    assert "ok selected size=321 cdn=False" in output
    assert "done ok=1 failed=0" in output


def test_rebuild_main_discovers_candidates_and_reports_failure(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    candidate_recipe = _recipe(apps / "candidate", {"url": "https://example.test"})
    ignored_recipe = _recipe(apps / "ignored", {"url": "https://example.test"})
    os.utime(candidate_recipe, (1, 1))
    os.utime(ignored_recipe, (2, 2))
    checked = []

    def needs_rebuild(app_dir, force):
        checked.append((app_dir.name, force))
        return app_dir.name == "candidate"

    def fail_rebuild(_distiller, _app_dir, upload):
        assert upload is True
        raise RuntimeError("build failed")

    _set_ready_builder(monkeypatch)
    monkeypatch.setattr(rebuild_android_apks, "_needs_rebuild", needs_rebuild)
    monkeypatch.setattr(rebuild_android_apks, "rebuild_one", fail_rebuild)
    monkeypatch.setattr(sys, "argv", ["rebuild", "--apps-dir", str(apps), "--force"])

    assert rebuild_android_apks.main() == 3
    assert checked == [("candidate", True), ("ignored", True)]
    captured = capsys.readouterr()
    assert "fail candidate: build failed" in captured.err
    assert "done ok=0 failed=1" in captured.out


def test_rebuild_module_entrypoint_covers_path_bootstrap_and_missing_apps(tmp_path, monkeypatch):
    root = str(rebuild_android_apks.ROOT)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != root])
    monkeypatch.setattr(
        sys,
        "argv",
        [rebuild_android_apks.__file__, "--apps-dir", str(tmp_path / "missing")],
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(rebuild_android_apks.__file__, run_name="__main__")
    assert exc_info.value.code == 1


class _PageDistiller:
    def __init__(self):
        self.written = []

    def _write_download_page(self, app_dir, recipe):
        self.written.append((app_dir.name, recipe))


def test_refresh_main_explicit_paths_limit_missing_error_and_success(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    good = _recipe(apps / "good", {"id": "good"})
    bad = _recipe(apps / "bad", {"id": "bad"})
    bad.write_text("not-json")
    fake = _PageDistiller()
    monkeypatch.setattr(refresh_download_pages, "Distiller", lambda: fake)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh",
            "--apps-dir",
            str(apps),
            "--app-id",
            "missing",
            "--app-id",
            "bad",
            "--app-id",
            "good",
            "--limit",
            "3",
        ],
    )

    assert refresh_download_pages.main() == 1
    assert fake.written == [("good", {"id": "good"})]
    captured = capsys.readouterr()
    assert "fail bad:" in captured.err
    assert "ok good" in captured.out
    assert "done ok=1 failed=2" in captured.out


def test_refresh_main_discovers_newest_first_and_succeeds(tmp_path, monkeypatch, capsys):
    apps = tmp_path / "apps"
    older = _recipe(apps / "older", {"id": "older"})
    newer = _recipe(apps / "newer", {"id": "newer"})
    os.utime(older, (1, 1))
    os.utime(newer, (2, 2))
    fake = _PageDistiller()
    monkeypatch.setattr(refresh_download_pages, "Distiller", lambda: fake)
    monkeypatch.setattr(sys, "argv", ["refresh", "--apps-dir", str(apps)])

    assert refresh_download_pages.main() == 0
    assert [name for name, _recipe_data in fake.written] == ["newer", "older"]
    assert "done ok=2 failed=0" in capsys.readouterr().out


def test_refresh_module_entrypoint_covers_path_bootstrap(tmp_path, monkeypatch):
    apps = tmp_path / "apps"
    apps.mkdir()
    fake = _PageDistiller()
    monkeypatch.setattr(distiller_module, "Distiller", lambda: fake)
    root = str(refresh_download_pages.ROOT)
    monkeypatch.setattr(sys, "path", [entry for entry in sys.path if entry != root])
    monkeypatch.setattr(
        sys,
        "argv",
        [refresh_download_pages.__file__, "--apps-dir", str(apps)],
    )

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(refresh_download_pages.__file__, run_name="__main__")
    assert exc_info.value.code == 0
    assert fake.written == []
