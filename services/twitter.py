import os
import tweepy
from dotenv import load_dotenv

load_dotenv()


def _get_credentials() -> dict:
    creds = {
        "api_key": os.getenv("TWITTER_API_KEY", ""),
        "api_secret": os.getenv("TWITTER_API_SECRET", ""),
        "access_token": os.getenv("TWITTER_ACCESS_TOKEN", ""),
        "access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET", ""),
    }
    if not all(creds.values()):
        raise ValueError("Twitter credentials are not fully configured in .env")
    return creds


def post_tweet(content: str, image_path: str = None) -> str:
    creds = _get_credentials()

    media_ids = None
    if image_path and os.path.exists(image_path):
        auth = tweepy.OAuth1UserHandler(
            creds["api_key"],
            creds["api_secret"],
            creds["access_token"],
            creds["access_token_secret"],
        )
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(filename=image_path)
        media_ids = [media.media_id]

    client = tweepy.Client(
        consumer_key=creds["api_key"],
        consumer_secret=creds["api_secret"],
        access_token=creds["access_token"],
        access_token_secret=creds["access_token_secret"],
    )
    response = client.create_tweet(text=content, media_ids=media_ids)
    return str(response.data["id"])
