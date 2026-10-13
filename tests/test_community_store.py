"""Unit tests for server.community_store — sequential user numbers, profile
validation, creator attribution, comments + ratings (issue #81)."""

import tempfile
import unittest
from pathlib import Path

from server.community_store import CommunityStore, MAX_BIO_LEN, MAX_COMMENT_LEN


class CommunityStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = CommunityStore(Path(self._tmp.name) / "_community.sqlite3")

    def tearDown(self):
        self._tmp.cleanup()

    # ---------- user numbers ----------

    def test_user_nums_are_sequential_in_first_seen_order(self):
        a = self.store.ensure_user("fp-a")
        b = self.store.ensure_user("fp-b")
        c = self.store.ensure_user("fp-c")
        self.assertEqual((a["user_num"], b["user_num"], c["user_num"]), (1, 2, 3))
        # Idempotent: re-seeing a fingerprint returns the same number.
        self.assertEqual(self.store.ensure_user("fp-a")["user_num"], 1)

    def test_empty_fingerprint_gets_no_profile(self):
        self.assertEqual(self.store.ensure_user(""), {})
        self.assertEqual(self.store.ensure_user(None), {})

    # ---------- profile validation ----------

    def test_name_must_match_pattern(self):
        for bad in ("a", "x" * 21, "bad name!", "<script>", "name?"):
            with self.assertRaises(ValueError):
                self.store.update_profile("fp-a", name=bad, bio_md="")
        for good in ("ab", "x" * 20, "中文名", "user_1-2"):
            profile = self.store.update_profile("fp-a", name=good, bio_md="")
            self.assertEqual(profile["name"], good)

    def test_names_are_unique_case_insensitive(self):
        self.store.update_profile("fp-a", name="Alice", bio_md="")
        with self.assertRaises(ValueError) as ctx:
            self.store.update_profile("fp-b", name="alice", bio_md="")
        self.assertEqual(str(ctx.exception), "name_taken")
        # Same user keeping their own name with different case is fine.
        profile = self.store.update_profile("fp-a", name="ALICE", bio_md="")
        self.assertEqual(profile["name"], "ALICE")

    def test_bio_is_truncated_at_limit(self):
        profile = self.store.update_profile("fp-a", name="aa", bio_md="x" * (MAX_BIO_LEN + 50))
        self.assertEqual(len(profile["bio_md"]), MAX_BIO_LEN)

    def test_profile_lookup_by_num(self):
        self.store.update_profile("fp-a", name="Alice", bio_md="hi")
        profile = self.store.profile_by_num(1)
        self.assertEqual(profile["name"], "Alice")
        self.assertEqual(profile["bio_md"], "hi")
        self.assertIsNone(self.store.profile_by_num(999))

    # ---------- creators ----------

    def test_first_creator_wins(self):
        self.store.set_creator("app1", "fp-a")
        self.store.set_creator("app1", "fp-b")  # attach must not reattribute
        self.assertEqual(self.store.creator_of("app1"), "fp-a")
        self.assertEqual(self.store.apps_by_creator("fp-a"), ["app1"])
        self.assertEqual(self.store.apps_by_creator("fp-b"), [])

    def test_creator_nums_map_decorates_profiles(self):
        self.store.ensure_user("fp-a")
        self.store.update_profile("fp-a", name="Maker", bio_md="")
        self.store.set_creator("app1", "fp-a")
        m = self.store.creator_nums_map(["app1", "app2"])
        self.assertEqual(m["app1"]["user_num"], 1)
        self.assertEqual(m["app1"]["name"], "Maker")
        self.assertNotIn("app2", m)

    # ---------- comments & ratings ----------

    def test_comment_lifecycle(self):
        c = self.store.add_comment("app1", "fp-a", "nice", 5)
        self.assertEqual(c["rating"], 5)
        self.assertEqual(c["user_num"], 1)
        self.assertTrue(c["mine"])  # viewer was the author
        listed = self.store.list_comments("app1", viewer_fp="fp-b")
        self.assertEqual(len(listed), 1)
        self.assertFalse(listed[0]["mine"])
        self.assertEqual(self.store.delete_comment(c["id"], fp="fp-b"), "forbidden")
        self.assertEqual(self.store.delete_comment(c["id"], fp="fp-a"), "deleted")
        self.assertEqual(self.store.delete_comment(c["id"], fp="fp-a"), "not_found")

    def test_admin_can_delete_any_comment(self):
        c = self.store.add_comment("app1", "fp-a", "spam", None)
        self.assertEqual(self.store.delete_comment(c["id"], fp="fp-b"), "forbidden")
        self.assertEqual(self.store.delete_comment(c["id"], fp="fp-b", admin=True), "deleted")

    def test_comment_validation(self):
        with self.assertRaises(ValueError):
            self.store.add_comment("app1", "fp-a", "   ", None)
        with self.assertRaises(ValueError):
            self.store.add_comment("app1", "fp-a", "ok", 6)
        long_body = self.store.add_comment("app1", "fp-a", "y" * (MAX_COMMENT_LEN + 10), None)
        self.assertEqual(len(long_body["body"]), MAX_COMMENT_LEN)

    def test_repeat_rating_replaces_the_previous_one(self):
        first = self.store.add_comment("app1", "fp-a", "one", 5)
        second = self.store.add_comment("app1", "fp-a", "two", 3)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["body"], "two")
        self.assertEqual(second["rating"], 3)
        # A note without a score does not erase the rating, and someone
        # else still counts as a second vote.
        self.store.add_comment("app1", "fp-a", "just a note", None)
        self.store.add_comment("app1", "fp-b", "other", 4)
        stats = self.store.rating_stats("app1")
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["avg"], 3.5)
        self.assertEqual(len(self.store.list_comments("app1")), 3)

    def test_collapse_duplicate_ratings_keeps_the_newest(self):
        self.store.ensure_user("fp-a")
        self.store._conn.executemany(
            "INSERT INTO comments(app_id, fp, body, rating, created_at) VALUES (?, ?, ?, ?, ?)",
            [
                ("app1", "fp-a", "old", 1, "2026-01-01T00:00:00Z"),
                ("app1", "fp-a", "mid", 2, "2026-02-01T00:00:00Z"),
                ("app1", "fp-a", "new", 5, "2026-03-01T00:00:00Z"),
                ("app1", "fp-a", "note", None, "2026-04-01T00:00:00Z"),
            ],
        )
        self.assertEqual(self.store.collapse_duplicate_ratings(), 2)
        self.assertEqual(self.store.collapse_duplicate_ratings(), 0)
        stats = self.store.rating_stats("app1")
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["avg"], 5.0)
        bodies = sorted(item["body"] for item in self.store.list_comments("app1"))
        self.assertEqual(bodies, ["new", "note"])

    # ---------- backfill ----------

    def test_backfill_assigns_oldest_users_lowest_nums_and_is_once(self):
        rows = [
            ("fp-old", "2020-01-01", ["appA"]),
            ("fp-new", "2024-01-01", ["appB"]),
        ]
        self.assertEqual(self.store.backfill_devices(rows), 2)
        self.assertEqual(self.store.profile_by_fp("fp-old")["user_num"], 1)
        self.assertEqual(self.store.profile_by_fp("fp-new")["user_num"], 2)
        self.assertEqual(self.store.creator_of("appA"), "fp-old")
        # Second run is a no-op even with different data.
        self.assertEqual(self.store.backfill_devices([("fp-x", "2021-01-01", [])]), 0)
        self.assertIsNone(self.store.profile_by_fp("fp-x"))


if __name__ == "__main__":
    unittest.main()
