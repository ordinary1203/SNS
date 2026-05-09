import os
import requests
from dotenv import load_dotenv

load_dotenv()

_GRAPH_URL = "https://graph.facebook.com/v18.0"


def _get_credentials() -> tuple[str, str]:
    user_id = os.getenv("INSTAGRAM_USER_ID", "")
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if not user_id or not token:
        raise ValueError("Instagram credentials are not fully configured in .env")
    return user_id, token


def post_instagram(content: str, image_url: str = None) -> str:
    """Post to Instagram Business account via Meta Graph API.

    Instagram requires a publicly accessible image URL.
    Text-only posts are not supported by this API.
    """
    if not image_url:
        raise ValueError(
            "Instagram requires an image. Text-only posts are not supported via the Graph API."
        )

    user_id, token = _get_credentials()

    container_resp = requests.post(
        f"{_GRAPH_URL}/{user_id}/media",
        data={"image_url": image_url, "caption": content, "access_token": token},
        timeout=30,
    )
    container_resp.raise_for_status()
    container_id = container_resp.json()["id"]

    publish_resp = requests.post(
        f"{_GRAPH_URL}/{user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=30,
    )
    publish_resp.raise_for_status()
    return publish_resp.json()["id"]
