"""Core posting logic — called both immediately and by the scheduler."""
import json
import os

from database import SessionLocal
from models import Post
from services.instagram import post_instagram
from services.twitter import post_tweet


def execute_post(post_id: int) -> None:
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return

        post.status = "processing"
        db.commit()

        platforms = json.loads(post.platforms)
        errors: list[str] = []

        if "twitter" in platforms:
            try:
                tweet_id = post_tweet(post.content, post.image_path)
                post.twitter_post_id = tweet_id
            except Exception as exc:
                errors.append(f"Twitter: {exc}")

        if "instagram" in platforms:
            try:
                image_url = None
                if post.image_path:
                    base_url = os.getenv("SERVER_BASE_URL", "http://localhost:8000")
                    image_url = f"{base_url}/{post.image_path}"
                ig_id = post_instagram(post.content, image_url)
                post.instagram_post_id = ig_id
            except Exception as exc:
                errors.append(f"Instagram: {exc}")

        if errors:
            post.error_message = "\n".join(errors)
            succeeded = post.twitter_post_id or post.instagram_post_id
            post.status = "partial" if succeeded else "failed"
        else:
            post.status = "posted"

        db.commit()
    finally:
        db.close()
