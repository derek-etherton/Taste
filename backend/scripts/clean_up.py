"""Delete guests unseen for 180 days and sessions idle for 90 (SqlProfileStore.clean_up).
Run daily, e.g. a scheduled task or cron:

    python scripts/clean_up.py
"""

from taste.settings import get_settings
from taste.storage import SqlProfileStore


def main() -> None:
    url = get_settings().database_url
    if not url:
        raise SystemExit("Set TASTE_DATABASE_URL.")
    print(f"Deleted {SqlProfileStore(url).clean_up()} idle guests.")


if __name__ == "__main__":
    main()
