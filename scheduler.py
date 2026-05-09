"""APScheduler wrapper for delayed posts."""
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone="UTC")


def schedule_post(post_id: int, run_at: datetime) -> None:
    from posting import execute_post  # lazy import avoids circular dependency

    scheduler.add_job(
        execute_post,
        trigger="date",
        run_date=run_at,
        args=[post_id],
        id=f"post_{post_id}",
        replace_existing=True,
    )
