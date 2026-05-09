import json
import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv, set_key
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

load_dotenv()

from database import engine, get_db
from models import Base, Post
from posting import execute_post
from scheduler import schedule_post, scheduler

UPLOAD_DIR = Path("static/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="SNS Auto Poster", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------------------------------------------------------------------------
# Posts API
# ---------------------------------------------------------------------------

@app.get("/api/posts")
async def list_posts(db: Session = Depends(get_db)):
    posts = db.query(Post).order_by(Post.created_at.desc()).all()
    return [_serialize_post(p) for p in posts]


@app.post("/api/posts", status_code=201)
async def create_post(
    background_tasks: BackgroundTasks,
    content: str = Form(...),
    platforms: str = Form(...),       # JSON array string e.g. '["twitter","instagram"]'
    scheduled_at: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    platforms_list: list[str] = json.loads(platforms)
    if not platforms_list:
        raise HTTPException(status_code=400, detail="プラットフォームを1つ以上選択してください")

    # Save uploaded image
    image_path: Optional[str] = None
    if image and image.filename:
        ext = image.filename.rsplit(".", 1)[-1].lower()
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"非対応の画像形式: {ext}")
        filename = f"{int(datetime.utcnow().timestamp() * 1000)}.{ext}"
        image_path = str(UPLOAD_DIR / filename)
        with open(image_path, "wb") as fh:
            shutil.copyfileobj(image.file, fh)

    # Parse optional schedule time (ISO 8601)
    scheduled_datetime: Optional[datetime] = None
    if scheduled_at and scheduled_at.strip():
        try:
            scheduled_datetime = datetime.fromisoformat(
                scheduled_at.replace("Z", "+00:00")
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="日時のフォーマットが正しくありません")

    post = Post(
        content=content,
        image_path=image_path,
        platforms=json.dumps(platforms_list),
        scheduled_at=scheduled_datetime,
        status="scheduled" if scheduled_datetime else "pending",
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    if scheduled_datetime:
        schedule_post(post.id, scheduled_datetime)
    else:
        background_tasks.add_task(execute_post, post.id)

    return _serialize_post(post)


@app.delete("/api/posts/{post_id}")
async def delete_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")
    if post.image_path and os.path.exists(post.image_path):
        os.remove(post.image_path)
    db.delete(post)
    db.commit()
    return {"message": "deleted"}


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

@app.get("/api/settings")
async def get_settings():
    def masked(key: str) -> str:
        val = os.getenv(key, "")
        return "***" if val else ""

    return {
        "twitter_api_key": os.getenv("TWITTER_API_KEY", ""),
        "twitter_api_secret": masked("TWITTER_API_SECRET"),
        "twitter_access_token": masked("TWITTER_ACCESS_TOKEN"),
        "twitter_access_token_secret": masked("TWITTER_ACCESS_TOKEN_SECRET"),
        "twitter_bearer_token": masked("TWITTER_BEARER_TOKEN"),
        "instagram_user_id": os.getenv("INSTAGRAM_USER_ID", ""),
        "instagram_access_token": masked("INSTAGRAM_ACCESS_TOKEN"),
        "server_base_url": os.getenv("SERVER_BASE_URL", "http://localhost:8000"),
        "twitter_configured": bool(
            os.getenv("TWITTER_API_KEY")
            and os.getenv("TWITTER_API_SECRET")
            and os.getenv("TWITTER_ACCESS_TOKEN")
            and os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
        ),
        "instagram_configured": bool(
            os.getenv("INSTAGRAM_USER_ID") and os.getenv("INSTAGRAM_ACCESS_TOKEN")
        ),
    }


@app.post("/api/settings")
async def save_settings(body: dict):
    env_file = ".env"
    if not os.path.exists(env_file):
        Path(env_file).touch()

    key_map = {
        "twitter_api_key": "TWITTER_API_KEY",
        "twitter_api_secret": "TWITTER_API_SECRET",
        "twitter_access_token": "TWITTER_ACCESS_TOKEN",
        "twitter_access_token_secret": "TWITTER_ACCESS_TOKEN_SECRET",
        "twitter_bearer_token": "TWITTER_BEARER_TOKEN",
        "instagram_user_id": "INSTAGRAM_USER_ID",
        "instagram_access_token": "INSTAGRAM_ACCESS_TOKEN",
        "server_base_url": "SERVER_BASE_URL",
    }

    for field, env_key in key_map.items():
        value = body.get(field, "")
        if value and value != "***":
            set_key(env_file, env_key, value)
            os.environ[env_key] = value

    return {"message": "設定を保存しました"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_post(post: Post) -> dict:
    return {
        "id": post.id,
        "content": post.content,
        "image_path": post.image_path,
        "platforms": json.loads(post.platforms),
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "status": post.status,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "twitter_post_id": post.twitter_post_id,
        "instagram_post_id": post.instagram_post_id,
        "error_message": post.error_message,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
