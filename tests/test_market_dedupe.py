"""Public-market duplicate rules: keep the newest listing, one rating each."""

import json
import tempfile
import unittest
from pathlib import Path

from server.community_store import CommunityStore
from server.history_store import HistoryStore
from server.market_dedupe import dedupe_public_market
from server.market_rules import normalize_app_name, normalize_target_url, retirement_ids


class NormalizeTests(unittest.TestCase):
    def test_names_ignore_case_and_spacing(self):
        self.assertEqual(normalize_app_name("핑크 어드벤처"), normalize_app_name("핑크-어드벤처"))
        self.assertEqual(normalize_app_name("핑크어드벤처"), normalize_app_name("핑크 어드벤처"))
        self.assertEqual(normalize_app_name("GitHub"), normalize_app_name("github"))
        self.assertNotEqual(normalize_app_name("쇼기 한판"), normalize_app_name("쇼기 한판!!"))

    def test_urls_ignore_scheme_www_and_index(self):
        self.assertEqual(
            normalize_target_url("https://www.rich.0g1s.com/index.html"),
            normalize_target_url("http://rich.0g1s.com/"),
        )
        self.assertEqual(
            normalize_target_url("https://github.com/"),
            normalize_target_url("https://github.com"),
        )
        self.assertNotEqual(
            normalize_target_url("http://127.0.0.1:3000/"),
            normalize_target_url("http://127.0.0.1/"),
        )


class RetirementTests(unittest.TestCase):
    def test_each_key_keeps_the_newest(self):
        records = [
            {"app_id": "old", "created_at": "2026-01-01T00:00:00Z", "updated_at": "",
             "name_key": "woofy", "url_key": "", "icon_key": "", "content_key": ""},
            {"app_id": "new", "created_at": "2026-02-01T00:00:00Z", "updated_at": "",
             "name_key": "woofy", "url_key": "", "icon_key": "", "content_key": ""},
        ]
        self.assertEqual(retirement_ids(records), ["old"])

    def test_empty_keys_do_not_group(self):
        records = [
            {"app_id": "a", "created_at": "2026-01-01", "name_key": "", "url_key": "",
             "icon_key": "", "content_key": ""},
            {"app_id": "b", "created_at": "2026-02-01", "name_key": "", "url_key": "",
             "icon_key": "", "content_key": ""},
        ]
        self.assertEqual(retirement_ids(records), [])


class DedupeStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.apps = Path(self._tmp.name)
        self.history = HistoryStore(self.apps / "_history.json")
        self.community = CommunityStore(self.apps / "_community.sqlite3")

    def tearDown(self):
        self._tmp.cleanup()

    def _app(self, app_id, fp, name, url, created_at, visibility="public",
             custom_icon=False, icon_bytes=None, content_hash=""):
        app_dir = self.apps / app_id
        app_dir.mkdir(parents=True, exist_ok=True)
        recipe = {
            "id": app_id,
            "name": name,
            "url": url,
            "visibility": visibility,
            "tags": ["tools"],
            "edit_token": f"tok-{app_id}",
            "custom_icon_uploaded": custom_icon,
        }
        if content_hash:
            recipe["content_hash"] = content_hash
        (app_dir / "recipe.json").write_text(json.dumps(recipe), encoding="utf-8")
        if icon_bytes is not None:
            (app_dir / "icon.png").write_bytes(icon_bytes)
        self.history.record_build(fp, recipe, f"/a/{app_id}", None)
        self.community.ensure_user(fp)
        self.community.set_creator(app_id, fp)
        with self.history._lock:
            self.history._conn.execute(
                "UPDATE apps SET created_at = ? WHERE app_id = ?",
                (created_at, app_id),
            )

    def _public_ids(self):
        rows = self.history.fetch_app_rows([
            app_id for fp in self.community.creator_fingerprints()
            for app_id in self.community.apps_by_creator(fp)
        ])
        return sorted(row["app_id"] for row in rows if row["visibility"] == "public")

    def test_same_creator_same_name_keeps_newest_and_preserves_token(self):
        self._app("oldpink1", "fp-a", "핑크 어드벤처", "https://s.example/a/oldpink1/site/index.html",
                  "2026-10-03T00:00:00Z")
        self._app("newpink1", "fp-a", "핑크-어드벤처", "https://s.example/a/newpink1/site/index.html",
                  "2026-10-09T00:00:00Z")
        summary = dedupe_public_market(self.history, self.community, self.apps)
        self.assertEqual(summary["retired_apps"], ["oldpink1"])
        self.assertEqual(self._public_ids(), ["newpink1"])
        stored = json.loads((self.apps / "oldpink1" / "recipe.json").read_text())
        self.assertEqual(stored["visibility"], "private")
        self.assertEqual(stored["edit_token"], "tok-oldpink1")
        # A second pass is a no-op.
        again = dedupe_public_market(self.history, self.community, self.apps)
        self.assertEqual(again["retired_apps"], [])

    def test_same_uploaded_icon_keeps_newest_placeholder_does_not(self):
        png = b"\x89PNG\r\n\x1a\ncustom-icon"
        self._app("iconold1", "fp-a", "Solar Optimize", "https://a.example/one",
                  "2026-10-02T00:00:00Z", custom_icon=True, icon_bytes=png)
        self._app("iconnew1", "fp-a", "Solar Tweaks Premium", "https://a.example/two",
                  "2026-10-02T01:00:00Z", custom_icon=True, icon_bytes=png)
        self._app("plain001", "fp-a", "First game", "https://a.example/g1",
                  "2026-10-01T00:00:00Z", custom_icon=False, icon_bytes=b"\x89PNG-placeholder")
        self._app("plain002", "fp-a", "Second game", "https://a.example/g2",
                  "2026-10-04T00:00:00Z", custom_icon=False, icon_bytes=b"\x89PNG-placeholder")
        dedupe_public_market(self.history, self.community, self.apps)
        self.assertEqual(self._public_ids(), ["iconnew1", "plain001", "plain002"])

    def test_same_url_and_content_hash_keep_newest(self):
        self._app("urlold01", "fp-a", "Local Pro", "https://plist.ca",
                  "2026-10-13T02:04:34Z")
        self._app("urlnew01", "fp-a", "Locl Pro", "https://www.plist.ca/",
                  "2026-10-13T02:05:03Z")
        self._app("hashold1", "fp-a", "커비 어드벤처", "https://s.example/a/hashold1/site/index.html",
                  "2026-10-08T00:00:00Z", content_hash="abc123")
        self._app("hashnew1", "fp-a", "핑크 어드벤처", "https://s.example/a/hashnew1/site/index.html",
                  "2026-10-09T00:00:00Z", content_hash="abc123")
        dedupe_public_market(self.history, self.community, self.apps)
        self.assertEqual(self._public_ids(), ["hashnew1", "urlnew01"])

    def test_another_creator_keeps_their_own_copy(self):
        self._app("gh-aaaa1", "fp-a", "GitHub", "https://github.com", "2026-09-29T00:00:00Z")
        self._app("gh-bbbb2", "fp-b", "Github", "https://github.com/", "2026-10-13T00:00:00Z")
        summary = dedupe_public_market(self.history, self.community, self.apps)
        self.assertEqual(summary["retired_apps"], [])
        self.assertEqual(self._public_ids(), ["gh-aaaa1", "gh-bbbb2"])

    def test_stacked_ratings_collapse_with_the_apps(self):
        self._app("rated001", "fp-a", "Neon Runner", "https://neon.example", "2026-09-27T00:00:00Z")
        self.community._conn.executemany(
            "INSERT INTO comments(app_id, fp, body, rating, created_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("rated001", "fp-a", "c moi wsh", 5, "2026-09-27T01:23:47Z"),
                ("rated001", "fp-a", "s", 5, "2026-09-27T01:23:55Z"),
                ("rated001", "fp-a", "s", 5, "2026-09-27T01:23:58Z"),
            ],
        )
        summary = dedupe_public_market(self.history, self.community, self.apps)
        self.assertEqual(summary["removed_ratings"], 2)
        self.assertEqual(self.community.rating_stats("rated001"), {"avg": 5.0, "count": 1})
        self.assertEqual(self.community.list_comments("rated001")[0]["body"], "s")
