"""Unpublish older duplicate public apps and collapse repeat ratings.

Safe to run while the service is up (SQLite WAL). From the repo root:

    python -m server.scripts.dedupe_market
"""

from pathlib import Path

from server.community_store import CommunityStore
from server.history_store import HistoryStore
from server.market_dedupe import dedupe_public_market

ROOT = Path(__file__).resolve().parents[2]
APPS = ROOT / "generated"


def main() -> None:
    history = HistoryStore(APPS / "_history.json")
    community = CommunityStore(APPS / "_community.sqlite3")
    summary = dedupe_public_market(history, community, APPS)
    retired = summary["retired_apps"]
    print(f"unpublished {len(retired)} older public app(s)")
    for app_id in retired:
        print(f"  {app_id}")
    print(f"removed {summary['removed_ratings']} stacked rating(s)")


if __name__ == "__main__":
    main()
